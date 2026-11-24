from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.errors import ApiError, install_error_handlers


class Body(BaseModel):
    count: int


def _client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/v2/thing")
    async def v2(body: Body) -> dict:
        if body.count == 1:
            raise ApiError(422, "MISSING_INPUT", "topic is required", details={"field": "topic"})
        if body.count == 2:
            raise RuntimeError("database password=hunter2 leaked in message")
        return {"ok": True}

    @app.post("/generate-topic-tree")
    async def legacy(body: Body) -> dict:
        raise HTTPException(status_code=500, detail="Fehler bei der Generierung: x")

    return TestClient(app, raise_server_exceptions=False)


def test_api_error_is_rendered_with_code_message_and_trace_id() -> None:
    r = _client().post("/v2/thing", json={"count": 1})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "MISSING_INPUT"
    assert err["message"] == "topic is required"
    assert err["details"] == {"field": "topic"}
    assert len(err["trace_id"]) == 32


def test_v2_validation_errors_list_field_paths_without_input_values() -> None:
    r = _client().post("/v2/thing", json={"count": "secret-value"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_INPUT"
    assert err["details"][0]["loc"] == ["body", "count"]
    assert "secret-value" not in r.text


def test_unhandled_errors_never_echo_exception_text() -> None:
    r = _client().post("/v2/thing", json={"count": 2})
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL"
    assert "hunter2" not in r.text


def test_legacy_routes_keep_the_fastapi_detail_format() -> None:
    client = _client()
    assert client.post("/generate-topic-tree", json={"count": 0}).json() == {"detail": "Fehler bei der Generierung: x"}
    invalid = client.post("/generate-topic-tree", json={"count": "x"})
    assert invalid.status_code == 422
    assert "detail" in invalid.json()


def test_api_error_headers_are_sent() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/v2/auth")
    async def auth() -> None:
        raise ApiError(401, "UNAUTHORIZED", "Bearer token required", headers={"WWW-Authenticate": "Bearer"})

    r = TestClient(app).get("/v2/auth")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
