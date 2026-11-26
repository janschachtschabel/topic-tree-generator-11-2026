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

    for name, mime in (
        ("styles.css", "text/css"),
        ("i18n.js", "javascript"),
        ("parsers.js", "javascript"),
        ("payload.js", "javascript"),
        ("tree.js", "javascript"),
        ("changes.js", "javascript"),
        ("result.js", "javascript"),
        ("form.js", "javascript"),
        ("app.js", "javascript"),
        ("base.js", "javascript"),
        ("boot.js", "javascript"),
    ):
        asset = client.get(f"/ui/assets/{name}")
        assert asset.status_code == 200, name
        assert mime in asset.headers["content-type"]

    # Zero external font URLs or CSS @import/@font-face rules in stylesheet.
    css = client.get("/ui/assets/styles.css").text
    assert "@import" not in css
    assert "@font-face" not in css
    assert "http://" not in css and "https://" not in css

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
    from app.vocab.labels import is_known

    for preset in presets:
        req = TopicTreeRequestV2.model_validate(preset["payload"])
        check_request(req, settings)
        for uri in (
            *req.frame.discipline_uri,
            *req.frame.educational_context_uri,
            *req.frame.intended_end_user_role_uri,
        ):
            assert is_known(uri), f"preset {preset['id']!r} uses unknown vocab URI: {uri}"

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
    assert "<summary><span" in html
    assert html.count("<summary>") == html.count("<summary><span")


def test_ui_navigates_by_task_and_exposes_every_request_input() -> None:
    client = _client(ui_enabled=True)
    html = client.get("/ui/").text
    for task in ("topic", "document", "folders", "contents", "assign", "refine"):
        assert f'data-task="{task}"' in html, task
    # Example picker in the sidebar, filtered by task in the browser.
    assert 'id="f-preset"' in html and 'id="btn-reset"' in html
    for field_id in (
        "f-topic",
        "discipline-chips",
        "f-context",
        "f-role",
        "f-materials-a",
        "f-materials-b",
        "f-folder-outline",
        "f-opt-improve",
        "f-doc-markdown",
        "f-doc-ref",
        "f-items-ref",
        "f-current-tree",
        "changes-editor",
        "btn-add-change",
        "f-fb-text",
        "f-fb-locked",
        "f-opt-assign-only",
        "f-opt-auto-meta",
        "f-extra-general",
        "f-extra-methodology",
        "f-hint-lang",
        "f-desc-len",
        "f-json",
        "btn-json-edit",
        "x-structure-materials",
        "x-content-materials",
        "x-document",
        "x-doc-content",
    ):
        assert f'id="{field_id}"' in html, f"missing UI control #{field_id}"
    # Result view: metrics card, adopt-as-base action and the base tree for targeted changes.
    for field_id in ("metrics", "btn-use-refine", "base-tree", "btn-copy-json", "btn-download-json"):
        assert f'id="{field_id}"' in html, field_id
    assert "onEditNode" in client.get("/ui/assets/tree.js").text


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


def test_ui_provides_de_en_toggle_and_duplicate_node_highlighting() -> None:
    client = _client(ui_enabled=True)
    html = client.get("/ui/").text
    css = client.get("/ui/assets/styles.css").text
    tree_js = client.get("/ui/assets/tree.js").text
    i18n_js = client.get("/ui/assets/i18n.js").text

    assert 'id="lang-de"' in html and 'id="lang-en"' in html
    order = [
        "i18n.js",
        "parsers.js",
        "payload.js",
        "tree.js",
        "changes.js",
        "result.js",
        "form.js",
        "app.js",
        "base.js",
        "boot.js",
    ]
    positions = [html.index(f"/ui/assets/{name}") for name in order]
    assert positions == sorted(positions)
    assert ".tree-node.is-duplicate" in css
    assert ".status-badge.duplicate" in css
    assert "is-duplicate" in tree_js
    assert "tree.badge.duplicate" in tree_js
    assert '"Duplikat"' in i18n_js and '"Duplicate"' in i18n_js


def test_refine_presets_start_from_a_fully_described_tree() -> None:
    from app.ui.presets import PRESETS

    def nodes(items: list[dict]):
        for item in items:
            yield item
            yield from nodes(item.get("subcollections", []))

    for preset in PRESETS:
        current = preset["payload"].get("current_tree")
        if not current or preset["task"] == "assign":  # sorting in never describes, foreign trees may lack texts
            continue
        undescribed = [
            n["key"] for n in nodes(current["collection"]) if not n.get("properties", {}).get("cm:description")
        ]
        assert undescribed == [], f"{preset['id']}: {undescribed}"


def _walk(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk(node.get("subcollections", []))


def test_presets_are_grouped_by_task_with_at_least_two_per_task() -> None:
    from app.ui.presets import PRESETS

    tasks = [p["task"] for p in PRESETS]
    for task in ("topic", "document", "folders", "contents", "assign", "refine"):
        assert tasks.count(task) >= 2, task
    for preset in PRESETS:
        payload = preset["payload"]
        assign_only = payload.get("options", {}).get("assign_only")
        expected = ("assign" if assign_only else "refine") if payload["mode"] == "refine" else payload["use_case"]
        assert preset["task"] == expected, preset["id"]
    assert len({p["id"] for p in PRESETS}) == len(PRESETS)


def test_presets_cover_every_change_op_with_existing_keys() -> None:
    from app.schemas.common import ChangeOp
    from app.ui.presets import PRESETS

    seen: set[str] = set()
    for preset in PRESETS:
        payload = preset["payload"]
        changes = (payload.get("feedback") or {}).get("changes") or []
        if not changes:
            continue
        keys = {n["key"] for n in _walk(payload["current_tree"]["collection"])}
        for change in changes:
            seen.add(change["op"])
            refs = [change.get("key"), change.get("parent"), change.get("to"), *(change.get("keys") or [])]
            assert {r for r in refs if r} <= keys, (preset["id"], change)
    assert seen == {op.value for op in ChangeOp}


def test_presets_include_elementary_and_higher_education_and_combinations() -> None:
    from app.ui.presets import PRESETS

    contexts = {uri for p in PRESETS for uri in p["payload"]["frame"]["educational_context_uri"]}
    assert any(uri.endswith("/elementarbereich") for uri in contexts)
    assert any(uri.endswith("/hochschule") for uri in contexts)

    def uses(preset: dict) -> set[tuple[str, ...]]:
        return {tuple(item.get("use") or ()) for item in preset["payload"].get("items") or []}

    by_task: dict[str, list[dict]] = {}
    for preset in PRESETS:
        by_task.setdefault(preset["task"], []).append(preset)
    assert any({("structure", "content"), ("content",)} <= uses(p) for p in by_task["topic"])
    assert any(("structure",) in uses(p) for p in by_task["topic"])
    assert any(p["payload"].get("topic") for p in by_task["document"])
    assert any(
        not p["payload"].get("options", {}).get("improve") and ("content",) in uses(p) for p in by_task["folders"]
    )
    assert any({("structure", "content"), ("content",)} <= uses(p) for p in by_task["contents"])
    assert any(p["payload"].get("items") and p["payload"]["feedback"].get("changes") for p in by_task["refine"])
    assert any(p["payload"]["frame"] != p["payload"]["current_tree"]["generation"]["frame"] for p in by_task["refine"])


def test_ui_every_field_has_an_accessible_name_and_shape_errors_name_the_field() -> None:
    # Regression: the two JSON areas had no accessible name; a bad number showed the raw id "f-depth".
    import re
    from pathlib import Path

    static = Path("app/ui/static")
    html = (static / "index.html").read_text(encoding="utf-8")
    labelled = set(re.findall(r'<label[^>]*for="([^"]+)"', html))
    for tag, ident in re.findall(r'<(input|select|textarea)\b[^>]*\bid="([^"]+)"', html):
        match = re.search(rf'<{tag}\b[^>]*\bid="{ident}"[^>]*>', html)
        element, before = match.group(0), html[: match.start()]
        wrapped = before.rfind("<label") > before.rfind("</label>")
        named = ident in labelled or wrapped or "aria-label" in element or 'type="hidden"' in element
        assert named, f"{ident} has no accessible name"
    i18n = (static / "i18n.js").read_text(encoding="utf-8")
    for field in ("f-depth", "f-main-min", "f-main-max", "f-child-min", "f-child-max"):
        assert i18n.count(f'"fieldname.{field}"') == 2


def test_assign_presets_include_a_foreign_tree_with_node_ids() -> None:
    from app.ui.presets import PRESETS

    assign = [p for p in PRESETS if p["task"] == "assign"]

    def foreign(nodes: list[dict]) -> bool:
        return all("key" not in n and n.get("nodeId") and foreign(n.get("subcollections", [])) for n in nodes)

    assert any(
        foreign(p["payload"]["current_tree"]["collection"]) and "generation" not in p["payload"]["current_tree"]
        for p in assign
    )
    assert all(not p["payload"].get("feedback") for p in assign)


def test_every_create_task_offers_combinations_marked_as_such() -> None:
    from app.ui.presets import PRESETS

    for task in ("topic", "document", "folders", "contents"):
        assert any(p.get("combo") for p in PRESETS if p["task"] == task), task
    for preset in PRESETS:
        if preset.get("combo"):
            assert preset["task"] not in ("assign", "refine"), preset["id"]


def test_topic_offers_contents_that_are_only_sorted_in() -> None:
    from app.ui.presets import PRESETS

    def only_content(p: dict) -> bool:
        items = p["payload"].get("items") or []
        return bool(items) and all(i.get("use", ["content"]) == ["content"] for i in items)

    assert any(p["task"] == "topic" and p.get("combo") and only_content(p) for p in PRESETS)


def test_preset_picker_groups_basic_examples_and_combinations() -> None:
    from pathlib import Path

    js = (Path("app/ui/static") / "app.js").read_text(encoding="utf-8")
    assert "optgroup" in js and "preset.group.combo" in js
