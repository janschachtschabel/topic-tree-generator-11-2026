"""Auth and LLM target resolution for the frozen v1 endpoints, aligned with v2."""

from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.context.caller import extract_bearer, resolve_caller
from app.errors import ApiError
from app.settings import Settings


@dataclass(frozen=True)
class LegacyTarget:
    api_key: str = field(repr=False)
    base_url: str | None
    model: str
    max_retries: int


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authorization Bearer token required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _standalone_target(cfg: Settings) -> LegacyTarget | None:
    if cfg.openai_api_key:
        return LegacyTarget(
            cfg.openai_api_key.get_secret_value(),
            cfg.openai_base_url,
            cfg.openai_model,
            cfg.legacy_max_retries,
        )
    if cfg.b_api_dev_key:
        return LegacyTarget(
            cfg.b_api_dev_key.get_secret_value(),
            cfg.b_api_router_url,
            cfg.legacy_route,
            cfg.legacy_max_retries,
        )
    return None


def resolve_target(request: Request, cfg: Settings) -> LegacyTarget:
    """Resolve v1 LLM target using v2 caller rules, keeping legacy bearer passthrough when unconfigured."""
    try:
        caller = resolve_caller(request.headers, cfg)
    except ApiError as exc:
        if exc.status == status.HTTP_401_UNAUTHORIZED:
            raise _unauthorized() from exc
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc

    if caller.mode == "bapi" and caller.delegation_token:
        return LegacyTarget(caller.delegation_token, cfg.b_api_router_url, cfg.legacy_route, cfg.legacy_max_retries)

    target = _standalone_target(cfg)
    if target is not None:
        return target

    if cfg.service_mode == "auto" and not cfg.service_api_keys:
        token = extract_bearer(request.headers)
        if token:
            return LegacyTarget(token, cfg.b_api_router_url, cfg.legacy_route, cfg.legacy_max_retries)
        raise _unauthorized()

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Kein LLM konfiguriert (OPENAI_API_KEY oder B_API_DEV_KEY).",
    )
