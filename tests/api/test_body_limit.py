"""Audit 2026-11-25 #7: request bodies are bounded before they are parsed."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def _client(limit: int = 1024) -> TestClient:
    settings = Settings(_env_file=None, max_request_bytes=limit, ui_enabled=False)
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_oversized_v2_body_is_rejected_with_413_in_v2_error_format() -> None:
    r = _client().post(
        "/v2/topic-tree", content=b"{" + b" " * 2000 + b"}", headers={"content-type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_oversized_chunked_body_without_content_length_is_rejected() -> None:
    def chunks():
        for _ in range(10):
            yield b" " * 500

    r = _client().post("/v2/topic-tree", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_oversized_legacy_body_keeps_the_detail_format() -> None:
    r = _client().post("/generate-topic-tree", content=b" " * 2000, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert "detail" in r.json()


def test_small_bodies_pass_through() -> None:
    r = _client().post("/v2/topic-tree", json={"mode": "create"})
    assert r.status_code != 413
