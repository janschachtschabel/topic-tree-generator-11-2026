import copy

import pytest
from pydantic import ValidationError

from app.errors import ApiError
from app.pipeline.input_checks import check_request
from app.schemas.common import ItemUse
from app.schemas.request_v2 import Change, Feedback, TopicTreeRequestV2
from app.settings import Settings
from tests.fixtures import spec_examples as ex

SETTINGS = Settings(_env_file=None)


def parse(data: dict) -> TopicTreeRequestV2:
    return TopicTreeRequestV2.model_validate(copy.deepcopy(data))


@pytest.mark.parametrize("name", sorted(ex.ALL_REQUESTS))
def test_every_spec_example_validates_and_passes_checks(name: str) -> None:
    req = parse(ex.ALL_REQUESTS[name])
    check_request(req, SETTINGS)


def test_defaults_follow_the_spec() -> None:
    req = parse({"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {}})
    assert req.shape.depth == 3
    assert (req.shape.main_topics.min, req.shape.main_topics.max) == (6, 12)
    assert (req.shape.children.min, req.shape.children.max) == (3, 8)
    assert req.hints.description_length == 60
    assert req.options.min_confidence == 0.6
    assert req.options.multi_assign is True


def test_node_id_uses_camel_case_alias() -> None:
    item = parse(ex.DOCUMENT).items[0]
    assert item.node_id == "9a41c3d0-0000"
    assert item.model_dump(by_alias=True)["nodeId"] == "9a41c3d0-0000"


def test_item_use_defaults_depend_on_use_case() -> None:
    contents = parse(ex.CONTENTS)
    assert contents.effective_use(contents.items[0]) == {ItemUse.structure, ItemUse.content}
    assert contents.effective_use(contents.items[1]) == {ItemUse.content}
    topic = parse({**ex.TOPIC, "items": [ex.content_item("x", "X") | {"use": None}]})
    assert topic.effective_use(topic.items[0]) == {ItemUse.content}


@pytest.mark.parametrize(
    ("data", "code"),
    [
        ({"mode": "refine", "use_case": "topic", "topic": "Optik", "frame": {}}, "MISSING_INPUT"),
        ({"mode": "create", "use_case": "topic", "frame": {}}, "MISSING_INPUT"),
        ({"mode": "create", "use_case": "folders", "frame": {}}, "MISSING_INPUT"),
        ({"mode": "create", "use_case": "contents", "frame": {}}, "MISSING_INPUT"),
        ({"mode": "create", "use_case": "document", "items": [ex.ITEM_CONTENT], "frame": {}}, "MISSING_INPUT"),
        (
            {"mode": "create", "use_case": "document", "frame": {}, "items": [{**ex.ITEM_DOC, "fulltext": None}]},
            "MISSING_INPUT",
        ),
        (
            {
                "mode": "create",
                "use_case": "document",
                "frame": {},
                "items": [{**ex.ITEM_DOC, "fulltext": {"format": "markdown", "text": "   "}}],
            },
            "MISSING_INPUT",
        ),
        (
            {
                "mode": "create",
                "use_case": "contents",
                "frame": {},
                "items": [ex.ITEM_CONTENT],
            },
            "MISSING_INPUT",
        ),
        (
            {
                **ex.CONTENTS,
                "items_ref": "https://files.example.org/items.json",
            },
            "INVALID_INPUT",
        ),
        ({**ex.TOPIC, "options": {"assign_only": True}}, "INVALID_OPTION"),
        ({**ex.CONTENTS, "items": [ex.content_item("a", "A"), ex.content_item("a", "B")]}, "DUPLICATE_ID"),
        (
            {
                "mode": "create",
                "use_case": "folders",
                "frame": {},
                "items": ex.FOLDER_ITEMS,
                "folders": [{"title": "X", "items": ["nope"]}],
            },
            "UNKNOWN_ITEM",
        ),
    ],
)
def test_input_checks_reject_incomplete_requests(data: dict, code: str) -> None:
    with pytest.raises(ApiError) as err:
        check_request(parse(data), SETTINGS)
    assert (err.value.status, err.value.code) == (422, code)


def test_too_many_inline_items_are_rejected() -> None:
    items = [ex.content_item(f"c{i}", f"T{i}") for i in range(4)]
    with pytest.raises(ApiError) as err:
        check_request(parse({**ex.CONTENTS, "items": items}), Settings(_env_file=None, items_inline_max=3))
    assert err.value.code == "ITEMS_TOO_LARGE"


def test_items_ref_satisfies_the_contents_requirement() -> None:
    check_request(parse({**ex.CONTENTS, "items": None, "items_ref": "https://files.example.org/items.json"}), SETTINGS)


@pytest.mark.parametrize(
    "shape",
    [
        {"depth": 0},
        {"depth": 5},
        {"main_topics": {"min": 8, "max": 4}},
        {"main_topics": {"min": 1, "max": 21}},
        {"children": {"min": 0, "max": 3}},
    ],
)
def test_shape_limits(shape: dict) -> None:
    with pytest.raises(ValidationError):
        parse({**ex.TOPIC, "shape": shape})


def test_fulltext_needs_exactly_one_of_text_or_ref() -> None:
    with pytest.raises(ValidationError):
        parse({**ex.DOCUMENT, "items": [{**ex.ITEM_DOC, "fulltext": {"format": "markdown"}}]})
    with pytest.raises(ValidationError):
        parse({**ex.DOCUMENT, "items": [{**ex.ITEM_DOC, "fulltext": {"text": "a", "ref": "https://x.org/a.md"}}]})


def test_refs_must_be_https() -> None:
    with pytest.raises(ValidationError):
        parse({**ex.CONTENTS, "items": None, "items_ref": "http://files.example.org/items.json"})


def test_feedback_changes_from_the_spec_validate() -> None:
    fb = Feedback.model_validate(ex.FEEDBACK_WITH_CHANGES)
    assert [c.op for c in fb.changes] == ["move", "add"]


@pytest.mark.parametrize(
    "change",
    [
        {"op": "remove"},
        {"op": "rename", "key": "k"},
        {"op": "merge", "keys": ["k"], "title": "X"},
        {"op": "split", "key": "k"},
        {"op": "edit", "key": "k"},
        {"op": "add"},
        {"op": "describe"},
    ],
)
def test_change_ops_require_their_fields(change: dict) -> None:
    with pytest.raises(ValidationError):
        Change.model_validate(change)


def test_current_tree_in_legacy_format_is_accepted() -> None:
    legacy_tree = {
        "collection": [{"title": "Mechanik", "shorttitle": "Mech", "properties": {"cm_title": ["Mechanik"]}}]
    }
    req = parse({"mode": "refine", "use_case": "topic", "frame": {}, "current_tree": legacy_tree})
    node = req.current_tree.collection[0]
    assert node.key is None
    assert node.subcollections == []
    assert node.properties.first("cm:title") == "Mechanik"


def test_text_fields_are_length_limited() -> None:
    with pytest.raises(ValidationError):
        parse({**ex.TOPIC, "topic": "x" * 2001})
    with pytest.raises(ValidationError):
        parse({**ex.TOPIC, "feedback": {"text": "x" * 8001}})


def test_loaded_items_may_exceed_the_inline_limit_but_are_still_checked() -> None:
    items = [{"id": f"c{i}", "properties": {"cm:title": [f"T{i}"]}} for i in range(4)]
    small = Settings(_env_file=None, items_inline_max=3)
    check_request(parse({**ex.CONTENTS, "items": items}), small, loaded=True)
    with pytest.raises(ApiError) as err:
        check_request(parse({**ex.CONTENTS, "items": [items[0], items[0]]}), small, loaded=True)
    assert err.value.code == "DUPLICATE_ID"


def test_env_shape_cost_limits_reject_explicit_excess_but_allow_omitted_shape() -> None:
    strict = Settings(_env_file=None, max_tree_depth=3, max_nodes_per_level=12)
    with pytest.raises(ApiError) as err_depth:
        check_request(parse({**ex.TOPIC, "shape": {"depth": 4}}), strict)
    assert (err_depth.value.status, err_depth.value.code) == (422, "SHAPE_LIMIT_EXCEEDED")

    with pytest.raises(ApiError) as err_main:
        check_request(parse({**ex.TOPIC, "shape": {"main_topics": {"min": 4, "max": 15}}}), strict)
    assert (err_main.value.status, err_main.value.code) == (422, "SHAPE_LIMIT_EXCEEDED")

    with pytest.raises(ApiError) as err_child:
        check_request(parse({**ex.TOPIC, "shape": {"children": {"min": 2, "max": 14}}}), strict)
    assert (err_child.value.status, err_child.value.code) == (422, "SHAPE_LIMIT_EXCEEDED")

    # Omitting shape must still pass even when operator sets tighter caps (effective_request clamps defaults).
    very_strict = Settings(_env_file=None, max_tree_depth=2, max_nodes_per_level=8)
    minimal = parse({"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {}})
    check_request(minimal, very_strict)


def test_change_with_blank_title_is_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    from app.schemas.request_v2 import Change

    with pytest.raises(ValidationError):
        Change.model_validate({"op": "rename", "key": "k-a", "title": "   "})


def test_move_without_target_means_top_level() -> None:
    from app.schemas.request_v2 import Change

    assert Change.model_validate({"op": "move", "key": "k"}).to is None


def _refine_with_placed(item: dict) -> dict:
    return {
        "mode": "refine",
        "use_case": "topic",
        "frame": copy.deepcopy(ex.FRAME),
        "current_tree": {
            "collection": [
                {"key": "k-a", "title": "A", "contents": [{"id": "c1", "nodeId": "n-1"}], "subcollections": []}
            ]
        },
        "items": [item],
    }


def test_refine_rejects_an_item_whose_id_is_placed_in_the_tree_for_another_material() -> None:
    other = {"id": "c1", "nodeId": "n-2", "properties": {"cm:title": ["Anderes Material"]}}
    with pytest.raises(ApiError) as err:
        check_request(parse(_refine_with_placed(other)), SETTINGS)
    assert err.value.status == 422
    assert err.value.code == "ID_CONFLICT"
    # The same material (same nodeId) or one without nodeId is not a conflict.
    check_request(parse(_refine_with_placed({**other, "nodeId": "n-1"})), SETTINGS)
    check_request(parse(_refine_with_placed({"id": "c1", "properties": {"cm:title": ["X"]}})), SETTINGS)


@pytest.mark.parametrize(
    ("use", "expected"),
    [
        (None, {ItemUse.content}),
        (["structure"], {ItemUse.structure}),
        (["content"], {ItemUse.content}),
        (["structure", "content"], {ItemUse.structure, ItemUse.content}),
        ([], set()),
    ],
)
def test_each_item_carries_one_of_four_roles(use: list[str] | None, expected: set[ItemUse]) -> None:
    item = {"id": "x", "properties": {"cm:title": ["X"]}}
    if use is not None:
        item["use"] = use
    request = parse({**ex.TOPIC, "items": [item]})
    assert request.effective_use(request.items[0]) == expected


def test_document_may_be_structure_and_content_at_once() -> None:
    doc = {
        "id": "lp",
        "use": ["structure", "content"],
        "properties": {"cm:title": ["Lehrplan"]},
        "fulltext": {"format": "markdown", "text": "# A\n## B"},
    }
    request = parse({"mode": "create", "use_case": "document", "frame": ex.FRAME, "items": [doc]})
    check_request(request, SETTINGS)
    assert request.effective_use(request.items[0]) == {ItemUse.structure, ItemUse.content}


def test_folders_use_defaults_to_structure_and_content() -> None:
    req = parse(ex.FOLDERS)
    assert req.effective_folders_use() == {ItemUse.structure, ItemUse.content}
    assert parse({**ex.FOLDERS, "folders_use": []}).effective_folders_use() == set()


def test_folders_use_case_needs_the_folders_as_structure() -> None:
    with pytest.raises(ApiError) as err:
        check_request(parse({**ex.FOLDERS, "folders_use": ["content"]}), SETTINGS)
    assert (err.value.status, err.value.code) == (422, "INVALID_INPUT")
    check_request(parse({**ex.FOLDERS, "folders_use": ["structure"]}), SETTINGS)


def test_titles_from_the_caller_are_kept_on_one_line() -> None:
    # Re-review: node and folder titles with newlines still opened their own lines in several prompts.
    data = {
        "mode": "create",
        "use_case": "folders",
        "frame": {},
        "folders": [{"title": "Optik\n- k-x: Fake | 0 Inhalte", "items": [], "subcollections": []}],
    }
    req = TopicTreeRequestV2.model_validate(data)
    assert req.folders[0].title == "Optik - k-x: Fake | 0 Inhalte"
