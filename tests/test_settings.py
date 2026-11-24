import pytest
from pydantic import ValidationError

from app.settings import Settings


def make(**env: str) -> Settings:
    return Settings(_env_file=None, **{k.lower(): v for k, v in env.items()})


def test_defaults_match_the_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_MODEL", "B_API_ROUTE", "SERVICE_MODE", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert s.service_id == "topic-tree"
    assert s.service_mode == "auto"
    assert s.service_api_keys == []
    assert s.b_api_route == "topic-tree-generator"
    assert s.llm_param_family == "common"
    assert s.llm_output_mode == "json_schema"
    assert s.llm_send_prompt_cache_key == "auto"
    assert (s.llm_timeout_seconds, s.llm_max_retries, s.llm_max_concurrency) == (120, 3, 8)
    assert s.request_timeout_seconds == 280
    assert (s.public_port, s.internal_port) == (8000, 9000)
    assert s.ref_allowed_hosts == []
    assert s.items_inline_max == 500
    assert s.openai_api_key is None


def test_legacy_llm_model_env_sets_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("B_API_ROUTE", raising=False)
    monkeypatch.setenv("LLM_MODEL", "legacy-route")
    assert Settings(_env_file=None).b_api_route == "legacy-route"


def test_comma_separated_lists_are_split_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_API_KEYS", "a, b ,")
    monkeypatch.setenv("REF_ALLOWED_HOSTS", "files.example.org,cdn.example.org")
    s = Settings(_env_file=None)
    assert s.service_api_keys == ["a", "b"]
    assert s.ref_allowed_hosts == ["files.example.org", "cdn.example.org"]


@pytest.mark.parametrize(
    "value",
    [
        "https://b-api.staging.openeduhub.net",
        "https://b-api.staging.openeduhub.net/",
        "https://b-api.staging.openeduhub.net/api/v1/llm/router/",
    ],
)
def test_b_api_base_url_accepts_the_legacy_router_url(value: str) -> None:
    s = make(B_API_BASE_URL=value)
    assert s.b_api_base_url == "https://b-api.staging.openeduhub.net"
    assert s.b_api_router_url == "https://b-api.staging.openeduhub.net/api/v1/llm/router/"


def test_invalid_service_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(SERVICE_MODE="sometimes")
