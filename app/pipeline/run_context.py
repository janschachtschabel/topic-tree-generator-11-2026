"""Everything a pipeline step needs for one request: LLM, settings, deadline and the warning list."""

import time
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from app.llm.usage import UsageTracker
from app.observability import metrics
from app.schemas.response_v2 import ServiceWarning
from app.settings import Settings


class LLM(Protocol):
    model_name: str
    usage: UsageTracker

    async def complete_json[M: BaseModel](
        self, step: str, user: str, model: type[M], *, max_tokens: int = 4000
    ) -> M: ...


@dataclass
class RunContext:
    llm: LLM
    settings: Settings
    deadline: float
    warnings: list[ServiceWarning] = field(default_factory=list)

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def expired(self) -> bool:
        return self.remaining() <= 0

    def warn(self, code: str, message: str, key: str | None = None, step: str | None = None) -> None:
        self.warnings.append(ServiceWarning(code=code, message=message, key=key, step=step))
        metrics.count_warning(code)
