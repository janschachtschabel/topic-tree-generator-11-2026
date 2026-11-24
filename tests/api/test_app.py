from fastapi.testclient import TestClient

from app.main import app, create_app
from app.pipeline import orchestrator
from app.pipeline.result import StrategyResult
from app.schemas.common import UseCase
from app.settings import Settings

client = TestClient(app)


def test_openapi_lists_only_public_api_paths() -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {"/generate-topic-tree", "/generate-collection-description", "/v2/topic-tree"}


def test_openapi_info_describes_the_service_for_end_users() -> None:
    info = client.get("/openapi.json").json()["info"]
    assert info["title"] == "Themenbaum-Generator"
    assert "Themenbäume" in info["description"]


def test_public_health_and_legacy_ping() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert client.get("/_ping").json() == {"status": "ok"}


def test_create_app_propagates_custom_settings_to_health_and_v2_deps(monkeypatch) -> None:
    custom = Settings(
        _env_file=None,
        service_id="custom-tree-svc",
        service_mode="standalone",
        service_api_keys=["svc-secret-1"],
        openai_api_key="sk-dummy-key",
    )
    custom_client = TestClient(create_app(custom))
    assert custom_client.get("/health").json()["service"] == "custom-tree-svc"

    payload = {"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {}}
    assert custom_client.post("/v2/topic-tree", json=payload).status_code == 401

    async def fast_strategy(req, rc):
        assert rc.settings.service_id == "custom-tree-svc"
        assert rc.mode == "standalone"
        return StrategyResult(roots=[], title="Optik", shape_checked=False)

    monkeypatch.setitem(orchestrator.STRATEGIES, UseCase.topic, fast_strategy)
    ok = custom_client.post("/v2/topic-tree", json=payload, headers={"Authorization": "Bearer svc-secret-1"})
    assert ok.status_code == 200
    assert ok.json()["metadata"]["title"] == "Optik"
