import copy
import time
from pathlib import Path

from app.domain.tree import walk
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.pipeline.strategies.document import build
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex

LEHRPLAN = (Path(__file__).parents[2] / "fixtures" / "lehrplan_physik_auszug.md").read_text(encoding="utf-8")
D60 = "wort " * 60


def doc(item_id: str = "d1", text: str = LEHRPLAN, use: list | None = None, fmt: str = "markdown") -> dict:
    return {
        "id": item_id,
        "nodeId": f"n-{item_id}",
        "use": use or ["structure"],
        "properties": {"cm:title": [f"Lehrplan {item_id}"]},
        "fulltext": {"format": fmt, "text": text},
    }


def req(items: list[dict], **extra) -> TopicTreeRequestV2:
    data = {
        "mode": "create",
        "use_case": "document",
        "items": items,
        "frame": ex.FRAME,
        "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
    }
    return TopicTreeRequestV2.model_validate(copy.deepcopy({**data, **extra}))


MAPPING = {
    "order": "Themenfelder",
    "levels": ["Themenfeld", "Fachbegriff"],
    "description": "Physik nach Lehrplan",
    "nodes": [
        {
            "title": "Wahrnehmung",
            "shorttitle": "Wahrnehmung",
            "section_ids": ["d1:s2"],
            "children": [
                {"title": "Licht und Sehen", "shorttitle": "Sehen", "section_ids": ["d1:s2"], "children": []},
                {"title": "Schatten", "shorttitle": "Schatten", "section_ids": ["d1:s99"], "children": []},
            ],
        },
        {
            "title": "Optische Phänomene",
            "shorttitle": "Phänomene",
            "section_ids": ["d1:s4", "d1:s5"],
            "children": [
                {"title": "Reflexion", "shorttitle": "Reflexion", "section_ids": ["d1:s5"], "children": []},
                {"title": "Brechung", "shorttitle": "Brechung", "section_ids": ["d1:s5"], "children": []},
            ],
        },
    ],
}


def describe(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {"nodes": [{"key": k, "description": D60, "keywords": ["x"]} for k in keys]}


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context="CTX")


async def test_llm_sees_the_compact_outline_not_the_full_text() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc()]), rc(llm))
    prompt = llm.prompts("map_outline")[0]
    assert "d1:s4 | Ebene 2 | Seite 14 | Themenfeld 2: Optische Phänomene an Grenzflächen" in prompt
    assert "Reflexion, Brechung, Absorption." not in prompt


async def test_nodes_carry_document_origin_with_section_and_page() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    result = await build(req([doc()]), rc(llm))
    phaen = result.roots[1]
    assert (phaen.origin.type, phaen.origin.id, phaen.origin.section, phaen.origin.page) == (
        "document",
        "d1",
        "Themenfeld 2: Optische Phänomene an Grenzflächen",
        14,
    )
    assert result.structure.order == "Themenfelder" and result.structure.source == "input"
    assert all(n.description for n, _, _ in walk(result.roots))


async def test_unknown_section_ids_are_dropped_and_reported() -> None:
    context = rc(FakeLLM({"map_outline": MAPPING, "describe_nodes": describe}))
    result = await build(req([doc()]), context)
    schatten = result.roots[0].children[1]
    assert schatten.origin.type == "document" and schatten.origin.section is None
    assert [w.code for w in context.warnings] == ["SECTION_UNKNOWN"]


async def test_descriptions_get_section_excerpts() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc()]), rc(llm))
    assert "Reflexion, Brechung, Absorption." in llm.prompts("describe_nodes")[0]


async def test_several_documents_are_merged_into_one_outline() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc("d1"), doc("d2", "# Zusatz\n## Farben\nSpektrum")]), rc(llm))
    prompt = llm.prompts("map_outline")[0]
    assert "d2:s2 | Ebene 2 | Farben" in prompt and "d1:s1" in prompt


async def test_document_without_headings_sends_an_excerpt() -> None:
    llm = FakeLLM(
        {
            "map_outline": {
                **MAPPING,
                "nodes": [
                    {"title": "Licht", "shorttitle": "Licht", "section_ids": [], "children": []},
                    {"title": "Schall", "shorttitle": "Schall", "section_ids": [], "children": []},
                ],
            },
            "describe_nodes": describe,
        }
    )
    result = await build(req([doc(text="Licht breitet sich aus. Schall braucht ein Medium.", fmt="text")]), rc(llm))
    assert "Licht breitet sich aus" in llm.prompts("map_outline")[0]
    assert result.roots[0].origin.id == "d1"


async def test_structure_only_document_is_not_assigned_but_content_document_is() -> None:
    assign = {"items": [{"id": "d1", "nodes": [{"key": "k-wahrnehmung", "confidence": 0.9}]}]}
    for use, expected in ((["structure"], False), (["structure", "content"], True)):
        llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe, "assign_contents": assign})
        context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
        await orchestrator.run(req([doc(use=use)]), context)
        assert bool(llm.prompts("assign_contents")) is expected


async def test_end_to_end_uses_hints_in_the_context() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req([doc()], hints={"exclude": ["Wahlpflicht"]}), context)
    assert "Ausschließen: Wahlpflicht" in llm.prompts("map_outline")[0]
    assert resp.collection[0].origin.type == "document"


async def test_trimming_to_the_shape_is_reported() -> None:
    deep = copy.deepcopy(MAPPING)
    deep["nodes"][0]["children"][0]["children"] = [
        {"title": "zu tief", "shorttitle": "t", "section_ids": [], "children": []}
    ]
    deep["nodes"] += [
        {"title": f"Extra {i}", "shorttitle": f"E{i}", "section_ids": [], "children": []} for i in range(6)
    ]
    context = rc(FakeLLM({"map_outline": deep, "describe_nodes": describe}))
    result = await build(req([doc()]), context)
    assert len(result.roots) == 6
    assert {"SHAPE_DEPTH", "SHAPE_WIDTH"} <= {w.code for w in context.warnings}
