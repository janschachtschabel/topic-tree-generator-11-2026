import copy
import time

from app.pipeline.run_context import RunContext
from app.pipeline.unused_inputs import warn_unused_inputs
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


def messages(data: dict) -> list[str]:
    rc = RunContext(llm=FakeLLM(), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    warn_unused_inputs(TopicTreeRequestV2.model_validate(copy.deepcopy(data)), rc)
    return [w.message for w in rc.warnings if w.code == "INPUT_IGNORED"]


def test_no_warning_for_a_plain_combination() -> None:
    assert messages({**ex.TOPIC, "folders": ex.FOLDERS_TREE, "items": ex.FOLDER_ITEMS}) == []
    assert messages(ex.FOLDERS) == []


def test_folders_with_no_role_are_reported() -> None:
    found = messages({**ex.TOPIC, "folders": ex.FOLDERS_TREE, "items": ex.FOLDER_ITEMS, "folders_use": []})
    assert len(found) == 1 and "folders_use []" in found[0]


def test_switched_off_assignment_reports_the_contents_left_out() -> None:
    found = messages({**ex.TOPIC, "items": ex.FOLDER_ITEMS, "options": {"assign_contents": False}})
    assert len(found) == 1 and "4 Inhalte" in found[0]
    loose = [*ex.FOLDER_ITEMS, ex.content_item("b1", "Lupe")]
    found = messages({**ex.FOLDERS, "items": loose, "options": {"assign_contents": False}})
    assert len(found) == 1 and "1 Inhalte" in found[0] and "b1" in found[0]


def test_refine_reports_folders_and_explicit_structure_items() -> None:
    doc = {**ex.content_item("d1", "Neuer Lehrplan"), "use": ["structure"]}
    data = {**ex.ASSIGN_ONLY, "options": {}, "folders": ex.FOLDERS_TREE, "items": [*ex.FOLDER_ITEMS, doc]}
    found = messages(data)
    assert len(found) == 2
    assert "folders" in found[0] and "d1" in found[1]


def test_refine_does_not_report_default_roles_of_a_contents_tree() -> None:
    tree = {**ex.CURRENT_TREE, "generation": {**ex.CURRENT_TREE["generation"], "use_case": "contents"}}
    item = {"id": "n1", "properties": {"cm:title": ["Neu"]}}
    data = {"mode": "refine", "use_case": "contents", "current_tree": tree, "items": [item], "frame": ex.FRAME}
    assert messages(data) == []
