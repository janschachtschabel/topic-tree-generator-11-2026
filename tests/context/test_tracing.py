import re

import pytest

from app.context.tracing import from_headers, outgoing_headers

HEX16 = re.compile(r"^[0-9a-f]{16}$")
HEX32 = re.compile(r"^[0-9a-f]{32}$")
TRACE = "463ac35c9f6413ad48485a3953bb6124"
SPAN = "a2fb4a1d1a96d312"


def test_valid_b3_trace_is_adopted_and_caller_span_becomes_parent() -> None:
    tc = from_headers({"X-B3-TraceId": TRACE, "X-B3-SpanId": SPAN, "X-B3-Sampled": "1"})
    assert tc.trace_id == TRACE
    assert tc.parent_span_id == SPAN
    assert HEX16.match(tc.span_id) and tc.span_id != SPAN
    assert tc.sampled == "1"


def test_64_bit_trace_ids_are_accepted() -> None:
    assert from_headers({"x-b3-traceid": "48485a3953bb6124"}).trace_id == "48485a3953bb6124"


@pytest.mark.parametrize(
    "bad",
    ["not-hex", "463AC35C9F6413AD48485A3953BB6124", "463ac35c9f6413ad48485a3953bb61", "x" * 500, "0" * 32],
)
def test_malformed_trace_ids_are_replaced(bad: str) -> None:
    tc = from_headers({"X-B3-TraceId": bad, "X-B3-SpanId": SPAN})
    assert HEX32.match(tc.trace_id) and tc.trace_id != bad
    assert tc.parent_span_id is None


def test_missing_headers_create_a_new_trace() -> None:
    tc = from_headers({})
    assert HEX32.match(tc.trace_id)
    assert HEX16.match(tc.span_id)
    assert tc.client_trace_id is None


def test_single_b3_header_is_understood() -> None:
    tc = from_headers({"b3": f"{TRACE}-{SPAN}-1"})
    assert tc.trace_id == TRACE
    assert tc.parent_span_id == SPAN
    assert tc.sampled == "1"


def test_client_trace_id_is_passed_through_but_never_generated() -> None:
    assert from_headers({"x-client-trace-id": "req-42.abc_DEF"}).client_trace_id == "req-42.abc_DEF"
    assert from_headers({"x-client-trace-id": "evil\nInjected: 1"}).client_trace_id is None
    assert from_headers({"x-client-trace-id": "a" * 200}).client_trace_id is None


def test_outgoing_headers_keep_trace_and_open_a_child_span() -> None:
    tc = from_headers({"X-B3-TraceId": TRACE, "X-B3-SpanId": SPAN, "x-client-trace-id": "req-1"})
    out = outgoing_headers(tc)
    assert out["X-B3-TraceId"] == TRACE
    assert out["X-B3-ParentSpanId"] == tc.span_id
    assert HEX16.match(out["X-B3-SpanId"]) and out["X-B3-SpanId"] != tc.span_id
    assert out["x-client-trace-id"] == "req-1"


def test_outgoing_headers_omit_absent_optional_values() -> None:
    out = outgoing_headers(from_headers({}))
    assert "x-client-trace-id" not in out
    assert "X-B3-Sampled" not in out
