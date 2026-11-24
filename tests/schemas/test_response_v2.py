import copy

from app.schemas.response_v2 import NodeOut, TopicTreeResponseV2
from tests.fixtures import spec_examples as ex


def test_spec_response_example_round_trips() -> None:
    resp = TopicTreeResponseV2.model_validate(copy.deepcopy(ex.RESPONSE))
    out = resp.dump()
    assert out["collection"][0]["properties"]["cm:title"] == ["Optik"]
    assert out["collection"][0]["contents"][0]["nodeId"] == "5c0e1f2a-0000"
    assert out["changes"][0]["from"] == "feedback_text"
    assert out["metadata"]["schema_version"] == "2.0"
    assert out["metadata"]["generation"]["inputs"]["items"]["content"] == 82


def test_subcollections_are_always_present() -> None:
    node = NodeOut(key="k-a", title="A", shorttitle="A", status="new")
    out = node.model_dump(by_alias=True, exclude_none=True)
    assert out["subcollections"] == []
    assert out["contents"] == []
    assert "confidence" not in out


def test_dump_omits_none_but_keeps_empty_lists() -> None:
    resp = TopicTreeResponseV2.model_validate(copy.deepcopy(ex.RESPONSE))
    out = resp.dump()
    assert out["questions"] == [] and out["warnings"] == []
    assert "section" not in out["collection"][0]["origin"]


def test_generation_holds_counts_not_item_data() -> None:
    resp = TopicTreeResponseV2.model_validate(copy.deepcopy(ex.RESPONSE))
    generation = resp.dump()["metadata"]["generation"]
    assert "items" not in generation
    assert "folders" not in generation
