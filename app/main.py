"""Application factory for the public port."""

from fastapi import FastAPI

from app.api.body_limit import BodyLimitMiddleware
from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.v2 import router as v2_router
from app.legacy.router import router as legacy_router
from app.observability import metrics
from app.observability.access_log import AccessLogMiddleware
from app.observability.logging import configure_logging
from app.settings import Settings, get_settings
from app.ui.router import router as ui_router
from app.version import service_version

ROUTE_CLASSES = {
    ("POST", "/generate-topic-tree"): "legacy.topic_tree",
    ("POST", "/generate-collection-description"): "legacy.description",
    ("POST", "/v2/topic-tree"): "v2.topic_tree",
    ("GET", "/health"): "health",
    ("GET", "/_ping"): "health",
    ("GET", "/openapi.json"): "docs",
    ("GET", "/docs"): "docs",
    ("GET", "/redoc"): "docs",
    ("GET", "/ui"): "ui",
    ("GET", "/ui/"): "ui",
    ("GET", "/ui/presets"): "ui",
}

DESCRIPTION = (
    "Erzeugt Themenbäume (Sammlungsstrukturen) für Bildungsinhalte: aus einem Thema, einem Strukturdokument wie "
    "einem Lehrplan, aus Ordnern und Dateien oder aus unstrukturierten Inhalten. Entwürfe lassen sich mit "
    "Rückmeldungen weiterentwickeln, Inhalte werden den Knoten zugeordnet."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(service=settings.service_id, level=settings.log_level, fmt=settings.log_format)
    app = FastAPI(title="Themenbaum-Generator", description=DESCRIPTION, version=service_version())
    app.state.settings = settings
    install_error_handlers(app)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        AccessLogMiddleware,
        route_classes=ROUTE_CLASSES,
        on_finish=metrics.observe_request,
        quiet_routes={"health"},
    )
    app.include_router(health_router)
    app.include_router(v2_router)
    app.include_router(legacy_router)
    if settings.ui_enabled:
        app.include_router(ui_router)
    return app


app = create_app()
