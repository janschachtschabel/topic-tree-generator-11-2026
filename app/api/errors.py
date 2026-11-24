"""Error responses: `{"error": {"code", "message", "trace_id", "details"?}}` for v2 routes.

Legacy routes keep FastAPI's `{"detail": ...}` format so existing callers see no change.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from app.context.tracing import get_trace
from app.errors import ApiError

__all__ = ["ApiError", "error_response", "install_error_handlers"]

V2_PREFIX = "/v2/"


def error_response(status: int, code: str, message: str, details: Any = None, headers=None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "trace_id": get_trace().trace_id}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body}, headers=headers)


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message, exc.details, exc.headers)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not request.url.path.startswith(V2_PREFIX):
        return await request_validation_exception_handler(request, exc)
    # Input values are deliberately left out: they may be large or contain personal data.
    details = [
        {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()
    ]
    return error_response(422, "INVALID_INPUT", "Die Anfrage ist ungültig.", details)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=exc).error("unhandled error")
    return error_response(500, "INTERNAL", "Interner Fehler. Bitte mit der trace_id melden.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
