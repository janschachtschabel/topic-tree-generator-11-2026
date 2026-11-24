from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.legacy import router as legacy
from app.main import app
from app.settings import Settings


class FakeAsyncOpenAI:
    api_keys: list[str] = []
    max_retries: list[int] = []

    def __init__(self, *, api_key: str, base_url: str, max_retries: int):
        self.api_keys.append(api_key)
        self.max_retries.append(max_retries)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=self.create_completion,
            )
        )

    async def create_completion(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Generated description"))])


client = TestClient(app)


def test_non_b_api_routes_are_public() -> None:
    for path in ("/_ping", "/docs", "/redoc", "/openapi.json"):
        response = client.get(path)

        assert response.status_code == 200


def test_b_api_endpoints_require_bearer_tokens() -> None:
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


def test_description_forwards_the_callers_bearer_token_to_b_api() -> None:
    FakeAsyncOpenAI.api_keys = []
    FakeAsyncOpenAI.max_retries = []

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


def test_topic_tree_forwards_the_callers_bearer_token_to_b_api() -> None:
    FakeAsyncOpenAI.api_keys = []
    FakeAsyncOpenAI.max_retries = []

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
