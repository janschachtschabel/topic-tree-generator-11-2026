"""Reject request bodies above MAX_REQUEST_BYTES before anything parses them (413).

Checks `Content-Length` up front and counts streamed chunks for requests without it. v2 routes answer in the v2
error format; every other route keeps FastAPI's `{"detail": ...}` format.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import V2_PREFIX, error_response

_MESSAGE = "Die Anfrage ist zu groß; große Dokumente oder Itemlisten bitte über fulltext.ref bzw. items_ref übergeben."


class _TooLarge(Exception):
    pass


def _response(path: str) -> JSONResponse:
    if path.startswith(V2_PREFIX):
        return error_response(413, "REQUEST_TOO_LARGE", _MESSAGE)
    return JSONResponse(status_code=413, content={"detail": _MESSAGE})


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > self.max_bytes:
            await _response(scope["path"])(scope, receive, send)
            return

        received = 0
        too_large = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    raise _TooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if too_large and not started:
                return  # the app's own error for the aborted body is replaced by the 413 below
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _TooLarge:
            if started:
                raise  # the app already answered; a second response is impossible
        if too_large and not started:
            await _response(scope["path"])(scope, receive, send)
