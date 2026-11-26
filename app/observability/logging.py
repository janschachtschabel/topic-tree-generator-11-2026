"""Logging to stdout: JSON lines for operations, plain text for local development.

Every line carries `service`, `trace_id` and `span_id` so the operations team can follow one request across
services; lines of a request that came with the operator's `x-client-trace-id` also carry it as
`client_trace_id`. `diagnose` is disabled so loguru never renders local variable values (which may hold tokens).
"""

import json
import logging
import sys
import traceback
from typing import Any, TextIO

from loguru import logger

from app.context.tracing import current_trace

_RESERVED = {"service", "trace_id", "span_id"}


def _json_sink(stream: TextIO):
    def write(message: Any) -> None:
        record = message.record
        extra = record["extra"]
        payload: dict[str, Any] = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "service": extra.get("service"),
            "trace_id": extra.get("trace_id"),
            "span_id": extra.get("span_id"),
            "message": record["message"],
        }
        payload.update({k: v for k, v in extra.items() if k not in _RESERVED})
        if record["exception"] is not None:
            exc = record["exception"]
            payload["exception"] = "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))
        stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        stream.flush()

    return write


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (gunicorn, uvicorn, httpx) into loguru so everything shares one format."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(service: str, level: str = "INFO", fmt: str = "json", stream: TextIO | None = None) -> None:
    """(Re)configure the global logger. Safe to call more than once."""
    stream = stream or sys.stdout

    def patch(record: dict) -> None:
        tc = current_trace.get()
        record["extra"].setdefault("service", service)
        record["extra"]["trace_id"] = tc.trace_id if tc else None
        record["extra"]["span_id"] = tc.span_id if tc else None
        if tc and tc.client_trace_id:
            record["extra"]["client_trace_id"] = tc.client_trace_id

    logger.remove()
    logger.configure(patcher=patch)
    if fmt == "json":
        logger.add(_json_sink(stream), level=level.upper(), backtrace=False, diagnose=False)
    else:
        logger.add(
            stream,
            level=level.upper(),
            backtrace=False,
            diagnose=False,
            colorize=False,
            format="{time:HH:mm:ss.SSS} | {level: <7} | {extra[trace_id]} | {message}",
        )
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "gunicorn.error"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
    # httpx/httpcore (and their httpx2 fork, used by Starlette 1.x and the openai SDK) log every URL at INFO;
    # URLs may carry caller-controlled or secret query values.
    for name in ("httpx", "httpcore", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # The access log of the server is replaced by our own line per request (no header values, no raw paths).
    for name in ("uvicorn.access", "gunicorn.access"):
        logging.getLogger(name).disabled = True
