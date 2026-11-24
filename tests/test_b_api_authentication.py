from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.legacy import router as legacy
from app.main import app
from app.settings import Settings


class FakeAsyncOpenAI:
    api_keys: list[str] = []
    base_urls: list[str | None] = []
    models: list[str] = []
    max_retries: list[int] = []

    def __init__(self, *, api_key: str, base_url: str | None, max_retries: int):
        self.api_keys.append(api_key)
        self.base_urls.append(base_url)
        self.max_retries.append(max_retries)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=self.create_completion,
            )
        )

    async def create_completion(self, *, model: str = "", **_: object) -> SimpleNamespace:
        self.models.append(model)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Generated description"))])


def _reset_fake() -> None:
    FakeAsyncOpenAI.api_keys = []
    FakeAsyncOpenAI.base_urls = []
    FakeAsyncOpenAI.models = []
    FakeAsyncOpenAI.max_retries = []


client = TestClient(app)


def test_non_b_api_routes_are_public() -> None:
    for path in ("/_ping", "/docs", "/redoc", "/openapi.json"):
        response = client.get(path)

        assert response.status_code == 200


def test_b_api_endpoints_require_bearer_tokens(monkeypatch) -> None:
    monkeypatch.setattr(legacy, "settings", Settings(_env_file=None))

    description_response = client.post(
        "/generate-collection-description",
        json={"text_context": "Mathematik"},
    )
    topic_tree_response = client.post(
        "/generate-topic-tree",
        json={"theme": "Mathematik"},
        headers={"Authorization": "Basic not-a-bearer-token"},
    )

    assert description_response.status_code == 401
    assert description_response.headers["www-authenticate"] == "Bearer"
    assert topic_tree_response.status_code == 401
    assert topic_tree_response.headers["www-authenticate"] == "Bearer"


def test_description_forwards_the_callers_bearer_token_to_b_api(monkeypatch) -> None:
    monkeypatch.setattr(legacy, "settings", Settings(_env_file=None))
    _reset_fake()

    with patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI):
        response = client.post(
            "/generate-collection-description",
            json={"text_context": "Mathematik"},
            headers={"Authorization": "Bearer caller-b-api-key"},
        )

    assert response.status_code == 200
    assert response.json() == "Generated description"
    assert FakeAsyncOpenAI.api_keys == ["caller-b-api-key"]
    assert FakeAsyncOpenAI.max_retries == [legacy.settings.legacy_max_retries]


def test_topic_tree_forwards_the_callers_bearer_token_to_b_api(monkeypatch) -> None:
    monkeypatch.setattr(legacy, "settings", Settings(_env_file=None))
    _reset_fake()

    async def generate_empty_topic_tree(**_: object) -> dict[str, object]:
        return {"collections": [], "description": "Generated topic tree"}

    with (
        patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI),
        patch.object(legacy, "generate_structured_text", generate_empty_topic_tree),
    ):
        response = client.post(
            "/generate-topic-tree",
            json={"theme": "Mathematik", "num_main_topics": 1},
            headers={"Authorization": "Bearer another-caller-b-api-key"},
        )

    assert response.status_code == 200
    assert FakeAsyncOpenAI.api_keys == ["another-caller-b-api-key"]
    assert FakeAsyncOpenAI.max_retries == [legacy.settings.legacy_max_retries]


def test_legacy_endpoints_work_without_bearer_in_standalone_openai_mode(monkeypatch) -> None:
    cfg = Settings(
        _env_file=None,
        openai_api_key="test-openai-key",
        openai_base_url="https://llm.example/v1",
        openai_model="gpt-6-luna",
    )
    monkeypatch.setattr(legacy, "settings", cfg)
    _reset_fake()
    seen_models: list[str] = []

    async def generate_empty_topic_tree(*, model: str, **_: object) -> dict[str, object]:
        seen_models.append(model)
        return {"collections": [], "description": "Generated topic tree"}

    with (
        patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI),
        patch.object(legacy, "generate_structured_text", generate_empty_topic_tree),
    ):
        desc = client.post("/generate-collection-description", json={"text_context": "Physik"})
        tree = client.post("/generate-topic-tree", json={"theme": "Physik", "num_main_topics": 1})

    assert desc.status_code == 200
    assert tree.status_code == 200
    assert FakeAsyncOpenAI.api_keys == ["test-openai-key", "test-openai-key"]
    assert FakeAsyncOpenAI.base_urls == ["https://llm.example/v1", "https://llm.example/v1"]
    assert FakeAsyncOpenAI.models == ["gpt-6-luna"]
    assert seen_models == ["gpt-6-luna"]


def test_legacy_endpoints_work_without_bearer_with_b_api_dev_key(monkeypatch) -> None:
    cfg = Settings(_env_file=None, b_api_dev_key="dev-b-api-key")
    monkeypatch.setattr(legacy, "settings", cfg)
    _reset_fake()

    with patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI):
        desc = client.post("/generate-collection-description", json={"text_context": "Biologie"})

    assert desc.status_code == 200
    assert FakeAsyncOpenAI.api_keys == ["dev-b-api-key"]
    assert FakeAsyncOpenAI.base_urls == [cfg.b_api_router_url]
    assert FakeAsyncOpenAI.models == [cfg.legacy_route]


def test_legacy_endpoints_enforce_service_api_keys(monkeypatch) -> None:
    cfg = Settings(
        _env_file=None,
        service_api_keys=["svc-secret"],
        openai_api_key="test-openai-key",
        openai_model="gpt-6-luna",
    )
    monkeypatch.setattr(legacy, "settings", cfg)
    _reset_fake()

    with patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI):
        missing = client.post("/generate-collection-description", json={"text_context": "Chemie"})
        wrong = client.post(
            "/generate-collection-description",
            json={"text_context": "Chemie"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        ok = client.post(
            "/generate-collection-description",
            json={"text_context": "Chemie"},
            headers={"Authorization": "Bearer svc-secret"},
        )
        delegated = client.post(
            "/generate-collection-description",
            json={"text_context": "Chemie"},
            headers={"Authorization": "Bearer bdt_delegation_tok"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert ok.status_code == 200
    assert delegated.status_code == 200
    assert FakeAsyncOpenAI.api_keys == ["test-openai-key", "bdt_delegation_tok"]
    assert FakeAsyncOpenAI.models == ["gpt-6-luna", cfg.legacy_route]


def test_legacy_endpoints_require_bearer_in_bapi_mode_even_with_openai_key(monkeypatch) -> None:
    cfg = Settings(
        _env_file=None,
        service_mode="bapi",
        openai_api_key="test-openai-key",
    )
    monkeypatch.setattr(legacy, "settings", cfg)
    _reset_fake()

    with patch.object(legacy, "AsyncOpenAI", FakeAsyncOpenAI):
        missing = client.post("/generate-collection-description", json={"text_context": "Geschichte"})
        ok = client.post(
            "/generate-collection-description",
            json={"text_context": "Geschichte"},
            headers={"Authorization": "Bearer bdt_live_tok"},
        )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert ok.status_code == 200
    assert FakeAsyncOpenAI.api_keys == ["bdt_live_tok"]
    assert FakeAsyncOpenAI.base_urls == [cfg.b_api_router_url]
    assert FakeAsyncOpenAI.models == [cfg.legacy_route]


def test_max_retries_uses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("MAX_RETRIES", "7")

    assert Settings(_env_file=None).legacy_max_retries == 7


def test_openapi_marks_only_b_api_endpoints_as_protected() -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/generate-topic-tree"]["post"]["security"] == [{"HTTPBearer": []}]
    assert schema["paths"]["/generate-collection-description"]["post"]["security"] == [{"HTTPBearer": []}]
    # Leitfaden: infrastructure paths are reachable but not part of the public spec.
    assert "/_ping" not in schema["paths"]
    assert "/health" not in schema["paths"]
