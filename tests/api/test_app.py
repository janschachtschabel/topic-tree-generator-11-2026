from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_lists_only_public_api_paths() -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {"/generate-topic-tree", "/generate-collection-description"}


def test_openapi_info_describes_the_service_for_end_users() -> None:
    info = client.get("/openapi.json").json()["info"]
    assert info["title"] == "Themenbaum-Generator"
    assert "Themenbäume" in info["description"]


def test_public_health_and_legacy_ping() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert client.get("/_ping").json() == {"status": "ok"}
