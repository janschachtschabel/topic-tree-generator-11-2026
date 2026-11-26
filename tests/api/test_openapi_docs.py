"""The Swagger page (/docs) explains the v2 endpoint and offers an example for every kind of call."""

import re

from fastapi.testclient import TestClient

from app.api.examples import REQUEST_EXAMPLES
from app.main import create_app
from app.schemas.request_v2 import TopicTreeRequestV2

client = TestClient(create_app())


def _requests() -> dict[str, TopicTreeRequestV2]:
    return {name: TopicTreeRequestV2.model_validate(ex["value"]) for name, ex in REQUEST_EXAMPLES.items()}


def test_endpoint_description_covers_use_cases_modes_roles_options_and_answer() -> None:
    op = client.get("/openapi.json").json()["paths"]["/v2/topic-tree"]["post"]
    text = op["description"]
    for term in (
        "use_case",
        "topic",
        "document",
        "folders",
        "contents",
        "mode",
        "refine",
        "assign_only",
        "describe",
        "use",
        "folders_use",
        "structure",
        "content",
        "frame",
        "shape",
        "hints",
        "min_confidence",
        "multi_assign",
        "improve",
        "auto_metadata",
        "unassigned",
        "warnings",
        "questions",
        "nodeId",
    ):
        assert re.search(rf"`[^`]*\b{term}\b[^`]*`", text), term
    for name in REQUEST_EXAMPLES:
        if name.startswith("combo_"):
            assert name in text, f"combination example {name} is not named in the description"


def test_every_example_has_a_summary_and_a_description() -> None:
    for name, example in REQUEST_EXAMPLES.items():
        assert example.get("summary") and len(example.get("description", "")) > 40, name


def test_examples_cover_every_use_case_role_and_folder_role() -> None:
    reqs = _requests().values()
    assert {r.use_case for r in reqs if r.mode == "create"} == {"topic", "document", "folders", "contents"}
    roles = {tuple(sorted(r.effective_use(i))) for r in reqs for i in r.items or []}
    assert {("structure",), ("content",), ("content", "structure")} <= roles
    assert {tuple(sorted(r.folders_use)) for r in reqs if r.folders_use is not None} >= {("structure",), ("content",)}
    assert any(r.folders and r.folders_use is None and r.use_case != "folders" for r in reqs)
    assert any(r.options.assign_only for r in reqs)
    assert any(c.op == "describe" for r in reqs if r.feedback for c in r.feedback.changes)
    assert any(r.mode == "refine" and r.items and r.feedback and r.feedback.changes for r in reqs)


def test_examples_combine_topic_with_contents_both_ways() -> None:
    topic_items = [r for r in _requests().values() if r.use_case == "topic" and r.mode == "create" and r.items]
    only_content = [r for r in topic_items if all(r.effective_use(i) == {"content"} for i in r.items)]
    inspiring = [r for r in topic_items if any("structure" in r.effective_use(i) for i in r.items)]
    assert only_content and inspiring


def test_tags_point_from_the_legacy_endpoints_to_v2() -> None:
    tags = {t["name"]: t["description"] for t in client.get("/openapi.json").json()["tags"]}
    assert "Examples" in tags["Themenbaum v2"]
    assert "/v2/topic-tree" in tags["Themenbaum-Generator"]
    assert "describe" in tags["Sammlungsbeschreibungen generieren"]
