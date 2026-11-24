"""Tests for the optional built-in test UI (`/ui/`, controlled by `UI_ENABLED`)."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline.input_checks import check_request
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings


def _client(ui_enabled: bool) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, ui_enabled=ui_enabled)))


def test_ui_disabled_returns_404_on_all_ui_routes() -> None:
    client = _client(ui_enabled=False)
    for path in ("/ui", "/ui/", "/ui/presets", "/ui/assets/styles.css", "/ui/assets/app.js"):
        assert client.get(path, follow_redirects=False).status_code == 404, path


def test_ui_enabled_serves_self_hosted_html_and_assets_without_exposing_in_openapi() -> None:
    client = _client(ui_enabled=True)

    # OpenAPI must keep only the public API routes (Leitfaden Kap. 1).
    openapi_paths = set(client.get("/openapi.json").json()["paths"])
    assert not any(p.startswith("/ui") for p in openapi_paths)

    redirect = client.get("/ui", follow_redirects=False)
    assert redirect.status_code in (302, 307)
    assert redirect.headers["location"].endswith("/ui/")

    page = client.get("/ui/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    html = page.text
    assert 'lang="de"' in html
    assert "skip-link" in html
    assert 'aria-live="polite"' in html
    # GDPR/DSGVO: zero third-party CDN fonts or scripts.
    assert "fonts.googleapis.com" not in html
    assert "cdn.jsdelivr.net" not in html
    assert "unpkg.com" not in html

    for name, mime in (("styles.css", "text/css"), ("tree.js", "javascript"), ("app.js", "javascript")):
        asset = client.get(f"/ui/assets/{name}")
        assert asset.status_code == 200, name
        assert mime in asset.headers["content-type"]

    # Path traversal / unknown assets must be rejected.
    assert client.get("/ui/assets/unknown.js").status_code == 404
    assert client.get("/ui/assets/..%2Frouter.py").status_code == 404


def test_ui_presets_cover_all_use_cases_and_validate_against_v2_schema() -> None:
    client = _client(ui_enabled=True)
    resp = client.get("/ui/presets")
    assert resp.status_code == 200
    data = resp.json()

    presets = data["presets"]
    use_cases = {p["payload"]["use_case"] for p in presets}
    modes = {p["payload"]["mode"] for p in presets}
    assert {"topic", "document", "folders", "contents"} <= use_cases
    assert {"create", "refine"} <= modes
    assert any(p["payload"].get("options", {}).get("assign_only") for p in presets)

    settings = Settings(_env_file=None)
    for preset in presets:
        req = TopicTreeRequestV2.model_validate(preset["payload"])
        check_request(req, settings)

    vocabs = data["vocabs"]
    assert any(v["label"] == "Physik" for v in vocabs["discipline"])
    assert any("Physik" in v["label"] for v in vocabs["hochschulfaechersystematik"])
    assert any("Sekundarstufe I" in v["label"] for v in vocabs["educationalContext"])
    assert any(v["uri"].endswith("/teacher") for v in vocabs["intendedEndUserRole"])
