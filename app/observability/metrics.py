"""Prometheus metrics. Label values come only from our own code (route classes, step names, warning codes).

With several gunicorn workers, PROMETHEUS_MULTIPROC_DIR must be set before this module is imported.
"""

import os
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

_LONG_BUCKETS = (0.5, 1, 2, 5, 10, 20, 30, 60, 90, 120, 180, 240, 300, 400)

REQUESTS = Counter("topic_tree_requests_total", "HTTP requests by route class and status", ["route", "status"])
REQUEST_SECONDS = Histogram(
    "topic_tree_request_seconds", "Request duration by route class", ["route"], buckets=_LONG_BUCKETS
)
LLM_CALLS = Counter("topic_tree_llm_calls_total", "LLM calls by pipeline step and outcome", ["step", "outcome"])
LLM_SECONDS = Histogram("topic_tree_llm_seconds", "LLM call duration by step", ["step"], buckets=_LONG_BUCKETS)
LLM_TOKENS = Counter("topic_tree_llm_tokens_total", "LLM tokens by kind (prompt, cached, completion)", ["kind"])
WARNINGS = Counter("topic_tree_warnings_total", "Warnings returned to callers by code", ["code"])


def observe_request(route: str, status: int, seconds: float) -> None:
    REQUESTS.labels(route=route, status=str(status)).inc()
    REQUEST_SECONDS.labels(route=route).observe(seconds)


def observe_llm(step: str, outcome: str, seconds: float, usage: Any) -> None:
    LLM_CALLS.labels(step=step, outcome=outcome).inc()
    LLM_SECONDS.labels(step=step).observe(seconds)
    if usage is None:
        return
    LLM_TOKENS.labels(kind="prompt").inc(getattr(usage, "prompt_tokens", 0) or 0)
    LLM_TOKENS.labels(kind="completion").inc(getattr(usage, "completion_tokens", 0) or 0)
    details = getattr(usage, "prompt_tokens_details", None)
    LLM_TOKENS.labels(kind="cached").inc((getattr(details, "cached_tokens", 0) or 0) if details else 0)


def count_warning(code: str) -> None:
    WARNINGS.labels(code=code).inc()


def render() -> tuple[bytes, str]:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
