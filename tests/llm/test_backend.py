import pytest

from app.context.caller import CallerContext
from app.errors import ApiError
from app.llm.backend import resolve_backend
from app.settings import Settings

BAPI = CallerContext(mode="bapi", delegation_token="bdt_xyz")
STANDALONE = CallerContext(mode="standalone")


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_bapi_mode_uses_router_with_route_and_forwarded_token() -> None:
    b = resolve_backend(BAPI, settings(b_api_route="topic-tree-generator"))
    assert b.kind == "bapi"
    assert b.base_url == "https://b-api.staging.openeduhub.net/api/v1/llm/router/"
    assert b.api_key == "bdt_xyz"
    assert b.model == "topic-tree-generator"
    assert b.send_cache_key is False


def test_standalone_with_openai_key_uses_openai() -> None:
    b = resolve_backend(STANDALONE, settings(openai_api_key="sk-test", openai_model="gpt-6-luna"))
    assert (b.kind, b.base_url, b.api_key, b.model, b.send_cache_key) == ("openai", None, "sk-test", "gpt-6-luna", True)


def test_standalone_openai_compatible_base_url_is_used() -> None:
    b = resolve_backend(STANDALONE, settings(openai_api_key="k", openai_base_url="http://llm.local/v1"))
    assert b.base_url == "http://llm.local/v1"


def test_standalone_dev_key_uses_b_api_router() -> None:
    b = resolve_backend(STANDALONE, settings(b_api_dev_key="dev-key"))
    assert b.kind == "dev"
    assert b.base_url.endswith("/api/v1/llm/router/")
    assert b.api_key == "dev-key"


def test_standalone_without_llm_configuration_is_503() -> None:
    with pytest.raises(ApiError) as err:
        resolve_backend(STANDALONE, settings())
    assert (err.value.status, err.value.code) == (503, "LLM_NOT_CONFIGURED")


@pytest.mark.parametrize(("flag", "expected"), [("true", True), ("false", False)])
def test_prompt_cache_key_flag_overrides_auto(flag: str, expected: bool) -> None:
    assert resolve_backend(BAPI, settings(llm_send_prompt_cache_key=flag)).send_cache_key is expected


def test_api_key_is_hidden_from_repr() -> None:
    assert "bdt_xyz" not in repr(resolve_backend(BAPI, settings()))
