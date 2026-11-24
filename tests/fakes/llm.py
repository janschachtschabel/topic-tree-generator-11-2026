"""A scripted stand-in for LLMClient at pipeline level: answers per step name, records every prompt."""

import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.llm.client import LLMStepError
from app.llm.usage import UsageTracker

Answer = dict | BaseModel | Exception | Callable[[str], Any]


class FakeLLM:
    def __init__(self, answers: dict[str, Answer | list[Answer]] | None = None, delay: float = 0.0) -> None:
        self.answers = {k: (v if isinstance(v, list) else [v]) for k, v in (answers or {}).items()}
        self.calls: list[tuple[str, str]] = []
        self.usage = UsageTracker()
        self.model_name = "fake-route"
        self.system_prompt = "SYSTEM"
        self.delay = delay

    def prompts(self, step: str) -> list[str]:
        return [user for s, user in self.calls if s == step]

    async def complete_json[M: BaseModel](self, step: str, user: str, model: type[M], *, max_tokens: int = 4000) -> M:
        self.calls.append((step, user))
        if self.delay:
            await asyncio.sleep(self.delay)
        queue = self.answers.get(step)
        if not queue:
            raise LLMStepError(step, "no_scripted_answer")
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(answer) and not isinstance(answer, type):
            answer = answer(user)
        if isinstance(answer, Exception):
            self.usage.record_failure(step)
            raise answer
        self.usage.record(step, None)
        return answer if isinstance(answer, BaseModel) else model.model_validate(answer)
