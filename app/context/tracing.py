"""B3 trace propagation and the operator's `x-client-trace-id`.

Incoming values are only adopted when well-formed, otherwise any caller could write arbitrary text into every
log line. The service never invents an `x-client-trace-id`; it only forwards one it received.
"""

import re
import secrets
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass

_TRACE_ID = re.compile(r"^(?:[0-9a-f]{16}|[0-9a-f]{32})$")
_SPAN_ID = re.compile(r"^[0-9a-f]{16}$")
_SAMPLED = {"0", "1", "d"}
_CLIENT_TRACE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: str | None = None
    client_trace_id: str | None = None


current_trace: ContextVar[TraceContext | None] = ContextVar("current_trace", default=None)


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def _valid_trace_id(value: str | None) -> str | None:
    if value and _TRACE_ID.match(value) and value.strip("0"):
        return value
    return None


def _valid_span_id(value: str | None) -> str | None:
    if value and _SPAN_ID.match(value) and value.strip("0"):
        return value
    return None


def _parse_single_header(value: str | None) -> tuple[str | None, str | None, str | None]:
    """Parse `b3: {TraceId}-{SpanId}-{Sampled}-{ParentSpanId}` into (trace, span, sampled)."""
    if not value or len(value) > 200:
        return None, None, None
    parts = value.split("-")
    if len(parts) < 2:
        return None, None, parts[0] if parts and parts[0] in _SAMPLED else None
    sampled = parts[2] if len(parts) > 2 and parts[2] in _SAMPLED else None
    return parts[0], parts[1], sampled


def from_headers(headers: Mapping[str, str]) -> TraceContext:
    """Build the trace context for an incoming request. The caller's span becomes our parent."""
    h = {k.lower(): v for k, v in headers.items()}
    single_trace, single_span, single_sampled = _parse_single_header(h.get("b3"))

    trace_id = _valid_trace_id(h.get("x-b3-traceid") or single_trace)
    parent = _valid_span_id(h.get("x-b3-spanid") or single_span) if trace_id else None
    sampled = h.get("x-b3-sampled") or single_sampled
    client = h.get("x-client-trace-id")

    return TraceContext(
        trace_id=trace_id or new_trace_id(),
        span_id=new_span_id(),
        parent_span_id=parent,
        sampled=sampled if sampled in _SAMPLED else None,
        client_trace_id=client if client and _CLIENT_TRACE_ID.match(client) else None,
    )


def outgoing_headers(tc: TraceContext) -> dict[str, str]:
    """Headers for a call to one of our own dependencies (b-api, LLM endpoint). Never send these to third parties."""
    headers = {"X-B3-TraceId": tc.trace_id, "X-B3-SpanId": new_span_id(), "X-B3-ParentSpanId": tc.span_id}
    if tc.sampled:
        headers["X-B3-Sampled"] = tc.sampled
    if tc.client_trace_id:
        headers["x-client-trace-id"] = tc.client_trace_id
    return headers


def get_trace() -> TraceContext:
    """The current request's trace, or a fresh one outside a request (e.g. startup code)."""
    return current_trace.get() or TraceContext(trace_id=new_trace_id(), span_id=new_span_id())
