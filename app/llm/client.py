"""The single way the pipeline talks to an LLM.

Guarantees: no streaming; one parameter family per deployment; structured output validated against a Pydantic
model with exactly one repair attempt; per-process concurrency cap; per-call timeout bounded by the request
deadline; transport retries (with Retry-After) delegated to the OpenAI SDK; no prompt content in logs.
"""

import asyncio
import json
import re
import time
import weakref
from collections.abc import Callable
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

    def __init__(self, step: str, reason: str, status: int | None = None) -> None:
        super().__init__(f"LLM step '{step}' failed: {reason}" + (f" (HTTP {status})" if status else ""))
        self.step = step
        self.reason = reason
        self.status = status


def _semaphore(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    entry = _semaphores.get(loop)
    if entry is None or entry[0] != limit:
        entry = (limit, asyncio.Semaphore(limit))
        _semaphores[loop] = entry
    return entry[1]


def _shared_http_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _http_clients.get(loop)
    if client is None:
        client = httpx.AsyncClient(limits=httpx.Limits(max_connections=50, max_keepalive_connections=20))
        _http_clients[loop] = client
    return client


def default_client_factory(**kwargs: Any) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(http_client=_shared_http_client(), **kwargs)


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
                default_headers=outgoing_headers(self.trace or get_trace()),
            )
        return self._client

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

    async def _call(self, step: str, body: dict[str, Any]) -> str | None:
        timeout = self._timeout(step)
        start = time.perf_counter()
        outcome = "ok"
        response = None
        try:
            async with _semaphore(self.settings.llm_max_concurrency):
                response = await self._openai().chat.completions.create(**body, timeout=timeout)
        except openai.APITimeoutError as exc:
            outcome = "timeout"
            raise LLMStepError(step, "timeout") from exc
        except openai.APIConnectionError as exc:
            outcome = "connection"
            raise LLMStepError(step, "connection") from exc
        except openai.APIStatusError as exc:
            outcome = f"http_{exc.status_code}"
            raise LLMStepError(step, "http_error", exc.status_code) from exc
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
        return response.choices[0].message.content if response.choices else None

    async def complete_json[M: BaseModel](self, step: str, user: str, model: type[M], *, max_tokens: int = 4000) -> M:
        """Ask for a JSON answer matching `model`. Raises LLMStepError when no valid answer is obtained."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(user, model)},
        ]
        content = await self._call(step, self._body(step, messages, model, max_tokens))
        try:
            return parse_json(content, model)
        except (ValueError, ValidationError) as first_error:
            error = type(first_error).__name__
            logger.bind(step=step).warning("invalid LLM output, attempting one repair")
        repair = [
            *messages,
            {"role": "assistant", "content": content or ""},
            {"role": "user", "content": _REPAIR.format(error=error)},
        ]
        content = await self._call(step, self._body(step, repair, model, max_tokens))
        try:
            return parse_json(content, model)
        except (ValueError, ValidationError) as exc:
            raise LLMStepError(step, "invalid_output") from exc
