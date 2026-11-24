"""Token and call accounting for one request (reported in `metadata.generation.usage`)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageTracker:
    llm_calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    failed_calls: int = 0
    calls_by_step: dict[str, int] = field(default_factory=dict)

    def record(self, step: str, usage: Any) -> None:
        self.llm_calls += 1
        self.calls_by_step[step] = self.calls_by_step.get(step, 0) + 1
        if usage is None:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        self.cached_tokens += (getattr(details, "cached_tokens", 0) or 0) if details else 0

    def record_failure(self, step: str) -> None:
        self.failed_calls += 1
        self.calls_by_step[step] = self.calls_by_step.get(step, 0) + 1

    def snapshot(self) -> dict[str, int]:
        return {
            "llm_calls": self.llm_calls,
            "failed_calls": self.failed_calls,
            "prompt_tokens": self.prompt_tokens,
            "cached_tokens": self.cached_tokens,
            "completion_tokens": self.completion_tokens,
        }
