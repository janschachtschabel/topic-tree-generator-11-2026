import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

from app.context.tracing import TraceContext, current_trace
from app.observability.access_log import AccessLogMiddleware
from app.observability.logging import configure_logging

TRACE = "463ac35c9f6413ad48485a3953bb6124"


@pytest.fixture
def stream() -> io.StringIO:
    buffer = io.StringIO()
    configure_logging(service="topic-tree", level="DEBUG", fmt="json", stream=buffer)
    yield buffer
    configure_logging(service="topic-tree", level="INFO", fmt="text")


def lines(buffer: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def test_json_lines_carry_service_and_trace_fields(stream: io.StringIO) -> None:
    token = current_trace.set(TraceContext(trace_id=TRACE, span_id="a2fb4a1d1a96d312"))
    try:
        logger.info("hello")
    finally:
        current_trace.reset(token)
    (line,) = lines(stream)
    assert line["message"] == "hello"
    assert line["level"] == "INFO"
    assert line["service"] == "topic-tree"
    assert line["trace_id"] == TRACE
    assert line["span_id"] == "a2fb4a1d1a96d312"
    assert "timestamp" in line


def test_json_lines_carry_the_operators_client_trace_id(stream: io.StringIO) -> None:
    # Leitfaden Kap. 2.3: operations filter logs across services by x-client-trace-id.
    tc = TraceContext(trace_id=TRACE, span_id="a2fb4a1d1a96d312", client_trace_id="op-4711")
    token = current_trace.set(tc)
    try:
        logger.info("with client trace")
    finally:
        current_trace.reset(token)
    logger.info("outside a request")
    inside, outside = lines(stream)
    assert inside["client_trace_id"] == "op-4711"
    assert "client_trace_id" not in outside


def test_text_format_is_plain() -> None:
    buffer = io.StringIO()
    configure_logging(service="topic-tree", level="INFO", fmt="text", stream=buffer)
    logger.info("plain")
    assert "plain" in buffer.getvalue()
    with pytest.raises(json.JSONDecodeError):
        json.loads(buffer.getvalue().splitlines()[0])


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware, route_classes={("POST", "/v2/topic-tree"): "v2.topic_tree"})

    @app.post("/v2/topic-tree")
    async def endpoint() -> dict:
        logger.info("inside")
        return {"ok": True}

    return app


def test_access_line_uses_route_class_and_never_header_values(stream: io.StringIO) -> None:
    client = TestClient(_app())
    client.post(
        "/v2/topic-tree?q=secret-query",
        headers={"Authorization": "Bearer bdt_SUPERSECRET", "X-B3-TraceId": TRACE},
    )
    out = stream.getvalue()
    assert "bdt_SUPERSECRET" not in out
    assert "secret-query" not in out
    access = [line for line in lines(stream) if line.get("event") == "request"]
    assert len(access) == 1
    assert access[0]["route"] == "v2.topic_tree"
    assert access[0]["status"] == 200
    assert access[0]["trace_id"] == TRACE
    assert isinstance(access[0]["duration_ms"], (int, float))
    inner = [line for line in lines(stream) if line["message"] == "inside"]
    assert inner[0]["trace_id"] == TRACE


def test_unknown_paths_are_logged_as_other(stream: io.StringIO) -> None:
    TestClient(_app()).get("/does/not/exist/abc")
    access = [line for line in lines(stream) if line.get("event") == "request"]
    assert access[0]["route"] == "other"
    assert "/does/not/exist" not in stream.getvalue()
