"""One log line per request, plus the trace context for everything logged while the request runs.

Only a fixed route class is logged, never the raw path or query (they are caller-controlled text).
"""

import time
from collections.abc import Mapping

from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.context.tracing import current_trace, from_headers

RouteClasses = Mapping[tuple[str, str], str]


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp, route_classes: RouteClasses, on_finish=None, quiet_routes=frozenset()) -> None:
        self.app = app
        self.route_classes = route_classes
        self.on_finish = on_finish
        # Probe traffic (e.g. readiness checks every few seconds) is logged at DEBUG only.
        self.quiet_routes = quiet_routes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        token = current_trace.set(from_headers(headers))
        route = self.route_classes.get((scope["method"], scope["path"]), "other")
        status = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            level = "DEBUG" if route in self.quiet_routes and status < 400 else "INFO"
            logger.bind(event="request", route=route, status=status, duration_ms=round(duration * 1000, 1)).log(
                level, "request finished"
            )
            if self.on_finish:
                self.on_finish(route, status, duration)
            current_trace.reset(token)
