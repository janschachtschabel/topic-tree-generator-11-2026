"""Error responses: `{"error": {"code", "message", "trace_id", "details"?}}` for v2 routes.

Legacy routes keep FastAPI's `{"detail": ...}` format so existing callers see no change.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


_HTTP_CODES = {404: ("NOT_FOUND", "Diesen Pfad gibt es nicht."), 405: ("METHOD_NOT_ALLOWED", "Methode nicht erlaubt.")}


async def _http_error(request: Request, exc: StarletteHTTPException):
    if not request.url.path.startswith(V2_PREFIX):
        return await http_exception_handler(request, exc)
    code, message = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", "Die Anfrage konnte nicht bearbeitet werden."))
    return error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


class UnhandledErrorMiddleware:
    """Turns an unexpected exception into the 500 JSON answer while the request's trace context is still set.

    Starlette's own catch-all runs outside every middleware, after the access log has reset the trace, so its
    answer and log line would carry a trace_id that matches nothing.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            logger.opt(exception=exc).error("unhandled error")
            if started:
                raise
            response = error_response(500, "INTERNAL", "Interner Fehler. Bitte mit der trace_id melden.")
            await response(scope, receive, send)


def install_error_handlers(app: FastAPI) -> None:
    """Call before adding other middleware: the catch-all must sit inside the access log."""
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_middleware(UnhandledErrorMiddleware)
