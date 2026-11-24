"""Health on the public port (readiness probe target) and the legacy `/_ping`. Hidden from OpenAPI."""

from fastapi import APIRouter

from app.internal_server import health_payload
from app.settings import get_settings

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return health_payload(get_settings())


@router.get("/_ping", include_in_schema=False)
async def ping() -> dict[str, str]:
    return {"status": "ok"}
