"""gunicorn configuration: several uvicorn workers on the public port, the internal port once in the master.

Prometheus runs in multiprocess mode; PROMETHEUS_MULTIPROC_DIR must be set before prometheus_client is imported,
which is why it is defaulted at the very top of this file.
"""

import os
import shutil

os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus")

from prometheus_client import multiprocess

from app.observability.logging import configure_logging
from app.settings import get_settings

_settings = get_settings()

bind = f"0.0.0.0:{_settings.public_port}"
workers = _settings.web_concurrency
worker_class = "uvicorn_worker.UvicornWorker"
# Requests run synchronously up to REQUEST_TIMEOUT_SECONDS; the worker timeout must be longer.
timeout = int(_settings.request_timeout_seconds) + 30
graceful_timeout = max(70, int(_settings.request_timeout_seconds) + 10)
keepalive = 5
accesslog = None


def on_starting(server) -> None:
    configure_logging(service=_settings.service_id, level=_settings.log_level, fmt=_settings.log_format)
    path = os.environ["PROMETHEUS_MULTIPROC_DIR"]
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


def when_ready(server) -> None:
    from app.internal_server import start_internal_server

    start_internal_server(_settings)


def child_exit(server, worker) -> None:
    multiprocess.mark_process_dead(worker.pid)
