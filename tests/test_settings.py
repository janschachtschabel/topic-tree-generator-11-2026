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
    assert (s.llm_timeout_seconds, s.llm_max_retries, s.llm_max_concurrency) == (120, 3, 20)
    assert (s.max_tree_depth, s.max_nodes_per_level) == (3, 20)
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


def test_blank_optional_env_values_normalize_to_none() -> None:
    s = make(
        OPENAI_API_KEY="",
        OPENAI_BASE_URL="   ",
        B_API_DEV_KEY="",
        B_API_DELEGATION_HEADER="",
        DOMAIN="",
    )
    assert s.openai_api_key is None
    assert s.openai_base_url is None
    assert s.b_api_dev_key is None
    assert s.b_api_delegation_header is None
    assert s.domain is None


@pytest.mark.parametrize("host", ["trees.example.de", "srv123456.example.cloud", "localhost"])
def test_domain_accepts_bare_hostnames(host: str) -> None:
    assert make(DOMAIN=host).domain == host


@pytest.mark.parametrize(
    "bad",
    [
        "https://trees.example.de",
        "http://trees.example.de",
        "trees.example.de/api",
        "trees.example.de:8000",
        "bad host.example.de",
        "-bad.example.de",
    ],
)
def test_domain_rejects_schemes_paths_ports_and_invalid_hostnames(bad: str) -> None:
    with pytest.raises(ValidationError, match="DOMAIN"):
        make(DOMAIN=bad)


@pytest.mark.parametrize("effort", ["none", "minimal", "low"])
def test_reasoning_effort_accepts_up_to_low(effort: str) -> None:
    assert make(LLM_REASONING_EFFORT=effort).llm_reasoning_effort == effort


@pytest.mark.parametrize("effort", ["medium", "high", "xhigh"])
def test_reasoning_effort_rejects_anything_above_low(effort: str) -> None:
    with pytest.raises(ValidationError):
        make(LLM_REASONING_EFFORT=effort)


def test_shape_cost_limits_validate_bounds() -> None:
    assert make(MAX_TREE_DEPTH="2", MAX_NODES_PER_LEVEL="12").max_tree_depth == 2
    with pytest.raises(ValidationError):
        make(MAX_TREE_DEPTH="0")
    with pytest.raises(ValidationError):
        make(MAX_TREE_DEPTH="5")
    with pytest.raises(ValidationError):
        make(MAX_NODES_PER_LEVEL="1")
    with pytest.raises(ValidationError):
        make(MAX_NODES_PER_LEVEL="21")


def test_ports_are_configurable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_PORT", "8010")
    monkeypatch.setenv("INTERNAL_PORT", "9010")
    s = Settings(_env_file=None)
    assert (s.public_port, s.internal_port) == (8010, 9010)


@pytest.mark.parametrize("ports", [(0, 9000), (70000, 9000), (8000, 0), (8000, 65536)])
def test_ports_outside_the_tcp_range_are_rejected(ports: tuple[int, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, public_port=ports[0], internal_port=ports[1])


def test_public_and_internal_port_must_differ() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        Settings(_env_file=None, public_port=8010, internal_port=8010)


def test_b_api_model_option_needs_its_path_which_is_normalized() -> None:
    s = make(B_API_MODEL="gpt-6-luna", B_API_MODEL_PATH="api/v1/llm/openai")
    assert s.b_api_model_url == "https://b-api.staging.openeduhub.net/api/v1/llm/openai/"
    assert s.b_api_router_url.endswith("/api/v1/llm/router/")
    with pytest.raises(ValidationError, match="B_API_MODEL_PATH"):
        make(B_API_MODEL="gpt-6-luna")
    assert make(B_API_MODEL="", B_API_MODEL_PATH="").b_api_model is None


@pytest.mark.parametrize("bad", ["https://evil.example/x", "/a/../b", "/a b"])
def test_b_api_model_path_rejects_urls_and_odd_paths(bad: str) -> None:
    with pytest.raises(ValidationError):
        make(B_API_MODEL="gpt-6-luna", B_API_MODEL_PATH=bad)
