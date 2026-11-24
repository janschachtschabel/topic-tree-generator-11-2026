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


def test_ui_css_enforces_hidden_attribute_over_flex_and_grid() -> None:
    client = _client(ui_enabled=True)
    css = client.get("/ui/assets/styles.css").text
    assert "[hidden] { display: none !important; }" in css
    assert "align-items: end;" in css
    html = client.get("/ui/").text
    # Every accordion <summary> wraps its label in a single <span> so flex space-between does not split <code> nodes.
    assert "<summary><span>" in html
    assert html.count("<summary>") == html.count("<summary><span>")


def test_ui_exposes_compact_preset_selector_and_all_manual_v2_inputs() -> None:
    client = _client(ui_enabled=True)
    html = client.get("/ui/").text
    # Compact dropdown in sidebar instead of a tall preset button wall.
    assert 'id="f-preset"' in html
    assert 'id="btn-reset"' in html
    assert 'id="preset-list"' not in html
    # Full manual input coverage for v2 request fields.
    for field_id in (
        "discipline-chips",
        "f-hint-lang",
        "f-items-ref",
        "f-doc-markdown",
        "f-items",
        "f-folders",
        "f-current-tree",
        "f-fb-text",
        "f-fb-locked",
        "f-fb-changes",
    ):
        assert f'id="{field_id}"' in html, f"missing UI control #{field_id}"


def test_ui_tree_defaults_to_titles_only_with_details_toggle() -> None:
    client = _client(ui_enabled=True)
    html = client.get("/ui/").text
    css = client.get("/ui/assets/styles.css").text
    assert 'id="opt-show-details"' in html
    assert 'id="opt-show-details" type="checkbox" checked' not in html
    assert 'id="tree-container" class="tree-root compact-tree"' in html
    assert ".tree-root.compact-tree .node-body" in css


def test_ui_presets_expose_operator_shape_limits_and_keep_concurrency_env_only() -> None:
    client = TestClient(create_app(Settings(_env_file=None, ui_enabled=True, max_tree_depth=3, max_nodes_per_level=15)))
    data = client.get("/ui/presets").json()
    assert data["limits"] == {"max_tree_depth": 3, "max_nodes_per_level": 15}
    html = client.get("/ui/").text
    assert 'id="shape-limits-note"' in html
    # Worker / concurrency limits stay strictly env-controlled, never editable from the UI.
    assert "llm_max_concurrency" not in html and "web_concurrency" not in html
