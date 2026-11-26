import copy
import time

from app.domain.tree import find, walk
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.pipeline.strategies.folders import build
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


def req(**changes) -> TopicTreeRequestV2:
    data = {
        "mode": "create",
        "use_case": "folders",
        "folders": ex.FOLDERS_TREE,
        "items": ex.FOLDER_ITEMS,
        "frame": ex.FRAME,
    }
    data = copy.deepcopy({**data, **changes})
    return TopicTreeRequestV2.model_validate(data)


def describe(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {"nodes": [{"key": k, "description": "wort " * 60, "keywords": ["x"]} for k in keys]}


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context="CTX")


async def test_folders_are_taken_over_with_contents_and_origin() -> None:
    llm = FakeLLM({"describe_nodes": describe})
    result = await build(req(), rc(llm))
    assert [r.title for r in result.roots] == ["Optik", "Neuer Ordner (2)"]
    optik = result.roots[0]
    assert optik.origin.path == "Optik"
    assert optik.children[0].origin.path == "Optik/Linsen"
    assert [(c.id, c.confidence) for c in optik.contents] == [("c1", 1.0), ("c2", 1.0)]
    assert llm.prompts("improve_folders") == []
    assert all(n.description for n, _, _ in walk(result.roots))
    assert "Inhalte: Licht, Schatten" in llm.prompts("describe_nodes")[0]
    assert result.shape_checked is False
    assert result.structure.source == "input"


async def test_improve_applies_service_changes() -> None:
    improve = {
        "changes": [
            {"op": "rename", "key": "k-neuer-ordner-2", "title": "Spiegel"},
            {"op": "move", "key": "k-neuer-ordner-2", "to": "k-optik"},
        ]
    }
    llm = FakeLLM({"improve_folders": improve, "describe_nodes": describe})
    result = await build(req(options={"improve": True}), rc(llm))
    spiegel = find(result.roots, "k-neuer-ordner-2")
    assert spiegel.title == "Spiegel"
    assert spiegel in result.roots[0].children
    assert [(c.op, c.source) for c in result.changes] == [("rename", "service"), ("move", "service")]
    assert result.shape_checked is True
    assert "k-neuer-ordner-2: Neuer Ordner (2) | 1 Inhalte | Spiegelbild" in llm.prompts("improve_folders")[0]


async def test_invalid_improvements_are_rejected_not_applied() -> None:
    improve = {"changes": [{"op": "move", "key": "k-optik", "to": "k-linsen"}]}
    context = rc(FakeLLM({"improve_folders": improve, "describe_nodes": describe}))
    result = await build(req(options={"improve": True}), context)
    assert [r.title for r in result.roots] == ["Optik", "Neuer Ordner (2)"]
    assert [w.code for w in context.warnings] == ["CHANGE_REJECTED"]


async def test_structure_only_items_in_folders_are_not_contents() -> None:
    items = [
        *ex.FOLDER_ITEMS[:1],
        {"id": "c2", "use": ["structure"], "properties": {"cm:title": ["Plan"]}},
        *ex.FOLDER_ITEMS[2:],
    ]
    result = await build(req(items=items), rc(FakeLLM({"describe_nodes": describe})))
    assert [c.id for c in result.roots[0].contents] == ["c1"]


async def test_end_to_end_status_against_folders_and_leftover_assignment() -> None:
    improve = {
        "changes": [
            {"op": "rename", "key": "k-neuer-ordner-2", "title": "Spiegel"},
            {"op": "move", "key": "k-neuer-ordner-2", "to": "k-optik"},
        ]
    }
    assign = {"items": [{"id": "c9", "nodes": [{"key": "k-linsen", "confidence": 0.8}]}]}
    llm = FakeLLM({"improve_folders": improve, "describe_nodes": describe, "assign_contents": assign})
    items = [*ex.FOLDER_ITEMS, ex.content_item("c9", "Brille")]
    request = req(
        items=items,
        options={"improve": True},
        shape={"main_topics": {"min": 1, "max": 5}, "children": {"min": 2, "max": 5}},
    )
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, context)
    optik = resp.collection[0]
    assert optik.status == "unchanged"
    spiegel = next(n for n in optik.subcollections if n.key == "k-neuer-ordner-2")
    assert spiegel.status == "moved"
    linsen = next(n for n in optik.subcollections if n.key == "k-linsen")
    assert [c.id for c in linsen.contents] == ["c3", "c9"]
    assert "c1" not in llm.prompts("assign_contents")[0]


async def test_improve_includes_supplementary_structure_items() -> None:
    llm = FakeLLM({"improve_folders": {"changes": []}, "describe_nodes": describe})
    items = [
        *ex.FOLDER_ITEMS,
        {
            "id": "d1",
            "use": ["structure"],
            "properties": {"cm:title": ["Stoffverteilungsplan Optik"]},
            "fulltext": {"format": "markdown", "text": "## Farben und Spektrum"},
        },
    ]
    await build(req(items=items, options={"improve": True}), rc(llm))
    assert "Stoffverteilungsplan Optik" in llm.prompts("improve_folders")[0]
    assert "Farben und Spektrum" in llm.prompts("improve_folders")[0]


async def test_folders_degrade_gracefully_when_llm_rejects_requests() -> None:
    from app.llm.client import LLMStepError

    llm = FakeLLM(
        {
            "improve_folders": LLMStepError("improve_folders", "http_error", 403),
            "describe_nodes": LLMStepError("describe_nodes", "http_error", 403),
        }
    )
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, mode="bapi")
    resp = await orchestrator.run(req(options={"improve": True}), context)
    assert [n.title for n in resp.collection] == ["Optik", "Neuer Ordner (2)"]
    assert [c.id for c in resp.collection[0].contents] == ["c1", "c2"]
    codes = [w.code for w in resp.warnings]
    assert "LLM_DEGRADED" in codes and "DESCRIBE_FAILED" in codes


async def test_items_marked_neither_structure_nor_content_stay_out_of_folders() -> None:
    items = [*ex.FOLDER_ITEMS[:1], {"id": "c2", "use": [], "properties": {"cm:title": ["Notiz"]}}, *ex.FOLDER_ITEMS[2:]]
    result = await build(req(items=items), rc(FakeLLM({"describe_nodes": describe})))
    assert [c.id for c in result.roots[0].contents] == ["c1"]


async def test_a_structure_document_without_improve_is_reported_as_ignored() -> None:
    llm = FakeLLM({"describe_nodes": describe})
    doc = {
        "id": "d1",
        "use": ["structure"],
        "properties": {"cm:title": ["Plan"]},
        "fulltext": {"format": "markdown", "text": "## Farben"},
    }
    context = rc(llm)
    await build(req(items=[*ex.FOLDER_ITEMS, doc]), context)
    assert "INPUT_IGNORED" in [w.code for w in context.warnings]


async def test_folders_without_structure_documents_give_no_input_warning() -> None:
    context = rc(FakeLLM({"describe_nodes": describe}))
    await build(req(), context)
    assert "INPUT_IGNORED" not in [w.code for w in context.warnings]
