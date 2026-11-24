import copy

from app.domain.tree import Node
from app.pipeline.finalize import FinalizeInput, finalize, next_version
from app.schemas.common import NodeStatus
from app.schemas.properties import Properties
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import StructureInfo
from app.version import service_version
from tests.fixtures import spec_examples as ex

OTHER_DISC = "http://w3id.org/openeduhub/vocabs/discipline/080"


def req(data: dict) -> TopicTreeRequestV2:
    return TopicTreeRequestV2.model_validate(copy.deepcopy(data))


def roots() -> list[Node]:
    narrow = Node(
        key="k-bio",
        title="Auge",
        status=NodeStatus.new,
        properties=Properties.model_validate({"ccm:taxonid": [OTHER_DISC], "ccm:oeh_x": ["y"]}),
    )
    return [
        Node(
            key="k-optik",
            title="Optik",
            shorttitle="Optik",
            description="Licht",
            keywords=["Licht"],
            status=NodeStatus.new,
            children=[narrow],
        )
    ]


def run(data: dict, **kw):
    payload = FinalizeInput(roots=roots(), title="Optik", description="Baum", **kw)
    return finalize(req(data), payload, model="route-x", usage={"llm_calls": 3}, duration_ms=1200).dump()


def test_frame_values_land_in_every_node_unless_narrower() -> None:
    out = run(ex.TOPIC)
    optik = out["collection"][0]
    props = optik["properties"]
    assert props["cm:title"] == ["Optik"]
    assert props["ccm:collectionshorttitle"] == ["Optik"]
    assert props["cm:description"] == ["Licht"]
    assert props["cclom:general_keyword"] == ["Licht"]
    assert props["ccm:taxonid"] == [ex.DISC]
    assert props["ccm:educationalcontext"] == [ex.SEK1]
    assert props["ccm:educationalintendedenduserrole"] == [ex.TEACHER]
    bio = optik["subcollections"][0]
    assert bio["properties"]["ccm:taxonid"] == [OTHER_DISC]
    assert bio["properties"]["ccm:oeh_x"] == ["y"]
    assert bio["subcollections"] == []


def test_create_starts_version_chain_and_records_generation() -> None:
    out = run(ex.TOPIC, structure=StructureInfo(order="Themen", levels=["Thema"], source="detected"))
    meta = out["metadata"]
    assert (meta["version"], meta.get("based_on")) == ("v1", None)
    assert meta["schema_version"] == "2.0"
    gen = meta["generation"]
    assert gen["mode"] == "create" and gen["use_case"] == "topic"
    assert gen["topic"] == ex.TOPIC["topic"]
    assert gen["generator_version"] == service_version()
    assert gen["model"] == "route-x"
    assert gen["structure"]["source"] == "detected"
    assert gen["usage"]["llm_calls"] == 3 and gen["usage"]["duration_ms"] == 1200
    assert meta["target_audience"] == "Lehrkräfte"


def test_refine_bumps_version_and_appends_feedback_history() -> None:
    data = copy.deepcopy(ex.FOLDERS_REFINE)
    data["current_tree"]["generation"]["feedback"] = [{"version": "v1", "text": "alt"}]
    out = run(data)
    meta = out["metadata"]
    assert (meta["version"], meta["based_on"]) == ("v2", "v1")
    assert [f["text"] for f in meta["generation"]["feedback"]] == ["alt", data["feedback"]["text"]]
    assert meta["generation"]["feedback"][-1]["version"] == "v2"


def test_input_counts_without_item_data() -> None:
    gen = run(ex.DOCUMENT)["metadata"]["generation"]
    assert gen["inputs"] == {"folders": 0, "items": {"structure": 1, "content": 1}}
    assert "items" not in {k for k in gen if k != "inputs"}


def test_next_version() -> None:
    assert next_version(None) == ("v1", None)
    assert next_version("v1") == ("v2", "v1")
    assert next_version("v9") == ("v10", "v9")
    assert next_version("1.2.6") == ("v2", "1.2.6")


def test_audience_resolves_other_oeh_roles_from_vocab() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["frame"]["intended_end_user_role_uri"] = [
        "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/parent",
        "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/manager",
    ]
    out = run(data)
    assert out["metadata"]["target_audience"] == "Eltern, Verwaltung"
