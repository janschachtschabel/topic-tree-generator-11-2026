"""Pick the LLM endpoint for one request: b-api router (with the caller's token), native OpenAI, or local dev."""

from dataclasses import dataclass, field
from typing import Literal

from app.context.caller import CallerContext
from app.errors import ApiError
from app.settings import Settings

BackendKind = Literal["bapi", "openai", "dev"]


@dataclass(frozen=True)
class LLMBackend:
    kind: BackendKind
    base_url: str | None
    model: str
    send_cache_key: bool
    api_key: str = field(repr=False)


def _cache_key_flag(kind: BackendKind, settings: Settings) -> bool:
    if settings.llm_send_prompt_cache_key == "auto":
        # Off behind the b-api until probed: GWDG models may reject unknown body fields.
        return kind == "openai"
    return settings.llm_send_prompt_cache_key == "true"


def _b_api_target(settings: Settings) -> tuple[str, str]:
    """(endpoint, model): the route at the router when set, otherwise the single model at its endpoint."""
    if settings.b_api_route:
        return settings.b_api_router_url, settings.b_api_route
    if settings.b_api_model and settings.b_api_model_url:
        return settings.b_api_model_url, settings.b_api_model
    raise ApiError(
        503,
        "LLM_NOT_CONFIGURED",
        "Für die b-api ist weder eine Route (B_API_ROUTE) noch ein Modell (B_API_MODEL mit B_API_MODEL_PATH) gesetzt.",
    )


def resolve_backend(ctx: CallerContext, settings: Settings) -> LLMBackend:
    if ctx.mode == "bapi" and ctx.delegation_token:
        kind: BackendKind = "bapi"
        return LLMBackend(kind, *_b_api_target(settings), _cache_key_flag(kind, settings), ctx.delegation_token)
    if settings.openai_api_key:
        kind = "openai"
        return LLMBackend(
            kind,
            settings.openai_base_url,
            settings.openai_model,
            _cache_key_flag(kind, settings),
            settings.openai_api_key.get_secret_value(),
        )
    if settings.b_api_dev_key:
        kind = "dev"
        return LLMBackend(
            kind,
            *_b_api_target(settings),
            _cache_key_flag(kind, settings),
            settings.b_api_dev_key.get_secret_value(),
        )
    raise ApiError(503, "LLM_NOT_CONFIGURED", "Kein LLM konfiguriert (OPENAI_API_KEY oder Aufruf über die b-api).")
