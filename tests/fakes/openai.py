"""A fake `AsyncOpenAI` for client-level tests: records every create() call and returns scripted replies."""

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import openai

Reply = str | Exception | Callable[[dict[str, Any]], str]


def completion(content: str, prompt: int = 100, cached: int = 0, completion_tokens: int = 50) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion_tokens,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        ),
        model="fake-model",
    )


class FakeOpenAI:
    """Replies are consumed in order; the last one repeats."""

    def __init__(self, replies: list[Reply], delay: float = 0.0, honor_timeout: bool = False) -> None:
        self.replies = list(replies)
        # Like the SDK: an attempt longer than the `timeout` argument fails with APITimeoutError.
        self.honor_timeout = honor_timeout
        self.calls: list[dict[str, Any]] = []
        self.constructed: list[dict[str, Any]] = []
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def factory(self, **kwargs: Any) -> "FakeOpenAI":
        self.constructed.append(kwargs)
        return self

    async def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            timeout = kwargs.get("timeout")
            if self.honor_timeout and timeout is not None and self.delay > timeout:
                await asyncio.sleep(timeout)
                raise openai.APITimeoutError(request=httpx.Request("POST", "https://llm.invalid/chat/completions"))
            if self.delay:
                await asyncio.sleep(self.delay)
            reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
            if isinstance(reply, Exception):
                raise reply
            if callable(reply):
                reply = reply(kwargs)
            return completion(reply)
        finally:
            self.active -= 1


def as_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
