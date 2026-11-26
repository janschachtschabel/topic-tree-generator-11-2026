"""The single way the pipeline talks to an LLM.

Guarantees: no streaming; one parameter family per deployment; structured output validated against a Pydantic
model with exactly one repair attempt (a larger budget when the reply was cut at the token limit); per-process
concurrency cap; every call bounded by the request deadline; transport retries (with Retry-After) delegated to the
OpenAI SDK; no prompt content in logs.
"""

import asyncio
import json
import re
import time
import weakref
from collections.abc import Callable
from http.cookiejar import DefaultCookiePolicy
from typing import Any

import httpx
import openai
from loguru import logger
from pydantic import BaseModel, ValidationError

from app.context.tracing import TraceContext, get_trace, outgoing_headers
from app.llm.backend import LLMBackend
from app.llm.json_schema import strict_schema
from app.llm.usage import UsageTracker
from app.settings import Settings

OnCall = Callable[[str, str, float, Any], None]

_FENCE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)
_MIN_CALL_SECONDS = 1.0
# Ceiling for the one retry after a reply was cut at the token limit (same as the largest step budget).
_MAX_RETRY_TOKENS = 32000
_REPAIR = (
    "Deine letzte Antwort war kein gültiges JSON nach dem geforderten Schema ({error}). "
    "Antworte jetzt ausschließlich mit dem korrigierten JSON."
)

_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]]" = (
    weakref.WeakKeyDictionary()
)
_http_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = weakref.WeakKeyDictionary()


class LLMStepError(Exception):
    """A pipeline step could not get a usable answer. Carries no prompt or response content."""

    def __init__(self, step: str, reason: str, status: int | None = None, detail: str | None = None) -> None:
        super().__init__(f"LLM step '{step}' failed: {reason}" + (f" (HTTP {status})" if status else ""))
        self.step = step
        self.reason = reason
        self.status = status
        self.detail = detail


def acquire_llm_slot(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    entry = _semaphores.get(loop)
    if entry is None or entry[0] != limit:
        entry = (limit, asyncio.Semaphore(limit))
        _semaphores[loop] = entry
    return entry[1]


def new_http_client(**kwargs: Any) -> httpx.AsyncClient:
    """HTTP client shared by all callers of a worker: it must never keep per-caller state such as cookies."""
    client = httpx.AsyncClient(limits=httpx.Limits(max_connections=50, max_keepalive_connections=20), **kwargs)
    client.cookies.jar.set_policy(DefaultCookiePolicy(allowed_domains=[]))
    return client


def shared_http_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _http_clients.get(loop)
    if client is None:
        client = new_http_client()
        _http_clients[loop] = client
    return client


def default_client_factory(**kwargs: Any) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(http_client=shared_http_client(), **kwargs)


def parse_json[M: BaseModel](content: str | None, model: type[M]) -> M:
    if not content or not content.strip():
        raise ValueError("leere Antwort")
    match = _FENCE.match(content)
    text = match.group(1) if match else content
    return model.model_validate(json.loads(text))


class LLMClient:
    def __init__(
        self,
        backend: LLMBackend,
        settings: Settings,
        *,
        system_prompt: str,
        usage: UsageTracker,
        deadline: float | None = None,
        trace: TraceContext | None = None,
        client_factory: Callable[..., Any] = default_client_factory,
        on_call: OnCall | None = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.system_prompt = system_prompt
        self.usage = usage
        self.deadline = deadline
        self.trace = trace
        self.on_call = on_call
        self._client_factory = client_factory
        self._client: Any = None

    @property
    def model_name(self) -> str:
        return self.backend.model

    def _openai(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(
                api_key=self.backend.api_key,
                base_url=self.backend.base_url,
                max_retries=self.settings.llm_max_retries,
            )
        return self._client

    def _trace_headers(self) -> dict[str, str]:
        """Trace headers only for our own dependency (the b-api); a provider called directly is a third party.

        Built per call: each LLM call is its own span (X-B3-SpanId) under the request's span."""
        if self.backend.kind == "openai":
            return {}
        return outgoing_headers(self.trace or get_trace())

    def _timeout(self, step: str) -> float:
        if self.deadline is None:
            return self.settings.llm_timeout_seconds
        remaining = self.deadline - time.monotonic()
        if remaining < _MIN_CALL_SECONDS:
            raise LLMStepError(step, "deadline")
        return min(self.settings.llm_timeout_seconds, remaining)

    def _body(self, step: str, messages: list[dict], model: type[BaseModel], max_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.backend.model, "messages": messages}
        family = self.settings.llm_param_family
        if family == "classic":
            body["max_tokens"] = max_tokens
        else:
            body["max_completion_tokens"] = max_tokens
        if family == "common":
            body["reasoning_effort"] = self.settings.llm_reasoning_effort
        elif family == "gpt5":
            # Models in the gpt5 family reject "none" and default to "medium"; cap at "low" (or "minimal").
            effort = self.settings.llm_reasoning_effort
            body["reasoning_effort"] = "low" if effort == "none" else effort
        mode = self.settings.llm_output_mode
        if mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": step, "schema": strict_schema(model), "strict": True},
            }
        elif mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        if self.backend.send_cache_key:
            body["prompt_cache_key"] = f"{self.settings.service_id}:{step}"
        return body

    def _user_content(self, user: str, model: type[BaseModel]) -> str:
        if self.settings.llm_output_mode == "json_schema":
            return user
        # Appended last so the cacheable prefix stays identical across calls.
        schema = json.dumps(strict_schema(model), ensure_ascii=False)
        return f"{user}\n\nAntworte ausschließlich mit JSON nach diesem Schema:\n{schema}"

    def _budget(self, step: str) -> float | None:
        """Request time left for the whole call (slot wait, SDK retries included); None without a deadline.

        Deliberately not capped by LLM_TIMEOUT_SECONDS: that limit applies per attempt (SDK `timeout`), so a slow
        attempt stays a retryable "timeout" and only an exhausted request deadline is reported as "deadline".
        """
        if self.deadline is None:
            return None
        remaining = self.deadline - time.monotonic()
        if remaining < _MIN_CALL_SECONDS:
            raise LLMStepError(step, "deadline")
        return remaining

    async def _call(self, step: str, body: dict[str, Any]) -> tuple[str | None, str | None]:
        budget = self._budget(step)
        start = time.perf_counter()
        outcome = "ok"
        response = None
        try:
            # The SDK applies `timeout` per attempt; the outer bound keeps retries and slot waits within the deadline.
            async with asyncio.timeout(budget), acquire_llm_slot(self.settings.llm_max_concurrency):
                timeout = self._timeout(step)  # recomputed: waiting for the slot used up part of the budget
                headers = self._trace_headers()
                extra = {"extra_headers": headers} if headers else {}
                response = await self._openai().chat.completions.create(**body, timeout=timeout, **extra)
        except (TimeoutError, LLMStepError) as exc:
            outcome = "deadline"
            raise LLMStepError(step, "deadline") from exc
        except openai.APITimeoutError as exc:
            outcome = "timeout"
            raise LLMStepError(step, "timeout") from exc
        except openai.APIConnectionError as exc:
            outcome = "connection"
            raise LLMStepError(step, "connection") from exc
        except openai.APIStatusError as exc:
            outcome = f"http_{exc.status_code}"
            raw_detail = str(exc.body if exc.body is not None else exc.message)[:200]
            raise LLMStepError(step, "http_error", exc.status_code, detail=raw_detail) from exc
        finally:
            seconds = time.perf_counter() - start
            usage = getattr(response, "usage", None)
            if outcome == "ok":
                self.usage.record(step, usage)
            else:
                self.usage.record_failure(step)
            logger.bind(event="llm_call", step=step, outcome=outcome, seconds=round(seconds, 2)).debug(
                "llm call finished"
            )
            if self.on_call:
                self.on_call(step, outcome, seconds, usage)
        if not response.choices:
            return None, None
        choice = response.choices[0]
        return choice.message.content, getattr(choice, "finish_reason", None)

    async def complete_json[M: BaseModel](self, step: str, user: str, model: type[M], *, max_tokens: int = 4000) -> M:
        """Ask for a JSON answer matching `model`. Raises LLMStepError when no valid answer is obtained."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(user, model)},
        ]
        content, finish = await self._call(step, self._body(step, messages, model, max_tokens))
        try:
            return parse_json(content, model)
        except (ValueError, ValidationError) as first_error:
            error = type(first_error).__name__
        if finish == "length":
            # Cut off at the token limit: sending the fragment back cannot help; ask again with more room.
            budget = max(max_tokens, min(2 * max_tokens, _MAX_RETRY_TOKENS))
            logger.bind(step=step, max_tokens=budget).warning("LLM output truncated, retrying with a larger budget")
            content, _ = await self._call(step, self._body(step, messages, model, budget))
        else:
            logger.bind(step=step).warning("invalid LLM output, attempting one repair")
            repair = [
                *messages,
                {"role": "assistant", "content": content or ""},
                {"role": "user", "content": _REPAIR.format(error=error)},
            ]
            content, _ = await self._call(step, self._body(step, repair, model, max_tokens))
        try:
            return parse_json(content, model)
        except (ValueError, ValidationError) as exc:
            raise LLMStepError(step, "invalid_output") from exc
