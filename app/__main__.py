"""Local development: public API and internal port in one process. Production uses gunicorn (gunicorn.conf.py)."""

import os

import uvicorn

if prom_dir := os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
    os.makedirs(prom_dir, exist_ok=True)

from app.internal_server import start_internal_server
from app.settings import get_settings


def main() -> None:
    settings = get_settings()
    start_internal_server(settings)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.public_port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
