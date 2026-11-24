"""Internal port: /health (liveness), /ready (configuration only, no dependency calls), /metrics.

Runs as a thread: once in the gunicorn master (see gunicorn.conf.py) or next to uvicorn in dev mode.
It must never be exposed outside the cluster.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.observability import metrics
from app.settings import Settings
from app.version import service_version
from app.vocab.labels import snapshot_date


def readiness(settings: Settings) -> tuple[bool, str | None]:
    """Ready unless the service can never answer: standalone mode without any LLM configured."""
    if settings.service_mode == "standalone" and not (settings.openai_api_key or settings.b_api_dev_key):
        return False, "LLM_NOT_CONFIGURED"
    return True, None


def health_payload(settings: Settings) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_id,
        "version": service_version(),
        "vocab_snapshot": snapshot_date(),
    }


def _handler(settings: Settings) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json")

        def do_GET(self) -> None:
            if self.path == "/health":
                self._json(200, health_payload(settings))
            elif self.path == "/ready":
                ok, reason = readiness(settings)
                self._json(200 if ok else 503, {"status": "ready" if ok else "not_ready", "reason": reason})
            elif self.path == "/metrics":
                body, content_type = metrics.render()
                self._send(200, body, content_type)
            else:
                self._json(404, {"status": "not_found"})

        def log_message(self, format: str, *args: object) -> None:
            return  # probes would flood the logs

    return Handler


def start_internal_server(settings: Settings, host: str = "0.0.0.0", port: int | None = None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, settings.internal_port if port is None else port), _handler(settings))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="internal-server", daemon=True).start()
    return server
