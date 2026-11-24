"""Test isolation: clear service environment variables so host shells never leak into tests."""

import pytest

_PREFIXES = ("SERVICE_", "B_API_", "OPENAI_", "LLM_", "REF_", "LOG_", "UI_")
_EXACT = {
    "PUBLIC_PORT",
    "INTERNAL_PORT",
    "WEB_CONCURRENCY",
    "REQUEST_TIMEOUT_SECONDS",
    "ITEMS_INLINE_MAX",
    "LEGACY_MAX_RETRIES",
    "MAX_RETRIES",
}


@pytest.fixture(autouse=True)
def _clean_service_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from app.settings import get_settings

    for key in list(os.environ):
        if key in _EXACT or key.startswith(_PREFIXES):
            monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
