"""Per-request wiring: caller mode, LLM backend and the run context with its deadline."""

import time

from fastapi import Request

from app.context.caller import resolve_caller
from app.context.tracing import current_trace
from app.llm.backend import resolve_backend
from app.llm.client import LLMClient
from app.llm.usage import UsageTracker
from app.observability import metrics
from app.pipeline.run_context import RunContext
from app.prompts import load
from app.settings import get_settings


def run_context(request: Request) -> RunContext:
    settings = get_settings()
    caller = resolve_caller(request.headers, settings)
    backend = resolve_backend(caller, settings)
    deadline = time.monotonic() + settings.request_timeout_seconds
    llm = LLMClient(
        backend,
        settings,
        system_prompt=load("system"),
        usage=UsageTracker(),
        deadline=deadline,
        trace=current_trace.get(),
        on_call=metrics.observe_llm,
    )
    return RunContext(llm=llm, settings=settings, deadline=deadline, mode=caller.mode)
