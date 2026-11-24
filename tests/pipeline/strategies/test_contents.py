import copy
import time

from app.domain.tree import walk
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.pipeline.strategies.contents import SAMPLE_SIZE, build
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex

D60 = "wort " * 60


def grouping(n: int = 5) -> dict:
    return {
        "order": "Themen",
        "levels": ["Thema", "Teilthema"],
        "description": "Optik-Bestand",
        "groups": [
            {
                "title": f"Gruppe {i}",
                "shorttitle": f"G{i}",
                "description": D60,
                "keywords": ["k"],
                "children": [
                    {
                        "title": f"Teil {i}.{j}",
                        "shorttitle": f"T{j}",
                        "description": D60,
                        "keywords": [],
                        "children": [],
                    }
                    for j in range(3)
                ],
            }
            for i in range(n)
        ],
    }


def items(n: int) -> list[dict]:
    return [
        {"id": f"c{i}", "properties": {"cm:title": [f"Material {i}"], "cclom:general_keyword": ["Licht"]}}
        for i in range(n)
    ]


def req(item_list: list[dict], **extra) -> TopicTreeRequestV2:
    data = {
        "mode": "create",
        "use_case": "contents",
        "topic": "Optik",
        "items": item_list,
        "frame": ex.FRAME,
        "shape": {"depth": 2, "main_topics": {"min": 3, "max": 8}, "children": {"min": 2, "max": 6}},
    }
    return TopicTreeRequestV2.model_validate(copy.deepcopy({**data, **extra}))


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context="CTX")


async def test_groups_become_cluster_nodes_with_descriptions() -> None:
    llm = FakeLLM({"group_contents": grouping()})
    result = await build(req(items(10)), rc(llm))
    assert len(result.roots) == 5
    assert all(n.origin.type == "cluster" and n.description for n, _, _ in walk(result.roots))
    assert llm.prompts("describe_nodes") == []
    assert result.structure.source == "detected"


async def test_only_structure_items_shape_the_groups() -> None:
    llm = FakeLLM({"group_contents": grouping()})
    data = [*items(3), {"id": "c77", "use": ["content"], "properties": {"cm:title": ["Sammelmappe Optik"]}}]
    await build(req(data), rc(llm))
    prompt = llm.prompts("group_contents")[0]
    assert "Material 1" in prompt
    assert "Sammelmappe" not in prompt


async def test_large_sets_use_a_sample_plus_title_list() -> None:
    llm = FakeLLM({"group_contents": grouping()})
    await build(
        req(items(450)),
        RunContext(
            llm=llm,
            settings=Settings(_env_file=None, items_inline_max=1000),
            deadline=time.monotonic() + 60,
            context="CTX",
        ),
    )
    prompt = llm.prompts("group_contents")[0]
    detailed = [line for line in prompt.splitlines() if line.startswith("- id: ")]
    assert len(detailed) == SAMPLE_SIZE
    assert "Weitere Titel" in prompt and "Material 449" in prompt


async def test_end_to_end_assigns_with_confidence_and_reports_off_topic() -> None:
    def assign(prompt: str) -> dict:
        return {
            "items": [
                {"id": "c0", "nodes": [{"key": "k-gruppe-0", "confidence": 0.9}]},
                {"id": "c1", "nodes": [], "off_topic": True},
                {"id": "c77", "nodes": [{"key": "k-teil-1-1", "confidence": 0.7}]},
            ]
        }

    llm = FakeLLM({"group_contents": grouping(), "assign_contents": assign})
    data = [*items(2), {"id": "c77", "use": ["content"], "properties": {"cm:title": ["Sammelmappe Optik"]}}]
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req(data), context)
    assert [c.id for c in resp.collection[0].contents] == ["c0"]
    assert [(u.id, u.reason) for u in resp.unassigned] == [("c1", "off_topic")]
    assert resp.collection[1].subcollections[1].contents[0].confidence == 0.7
    assert "Thema: Optik" in llm.prompts("group_contents")[0]


async def test_stratified_sampling_preserves_minority_disciplines_and_includes_labels() -> None:
    physics_uri = "http://w3id.org/openeduhub/vocabs/discipline/460"
    biology_uri = "http://w3id.org/openeduhub/vocabs/discipline/080"
    chemistry_uri = "http://w3id.org/openeduhub/vocabs/discipline/100"
    mixed = [
        *[
            {"id": f"p{i}", "properties": {"cm:title": [f"Physik {i}"], "ccm:taxonid": [physics_uri]}}
            for i in range(420)
        ],
        *[
            {"id": f"b{i}", "properties": {"cm:title": [f"Biologie {i}"], "ccm:taxonid": [biology_uri]}}
            for i in range(15)
        ],
        *[
            {"id": f"c{i}", "properties": {"cm:title": [f"Chemie {i}"], "ccm:taxonid": [chemistry_uri]}}
            for i in range(15)
        ],
    ]
    llm = FakeLLM({"group_contents": grouping()})
    await build(
        req(mixed),
        RunContext(
            llm=llm,
            settings=Settings(_env_file=None, items_inline_max=1000),
            deadline=time.monotonic() + 60,
            context="CTX",
        ),
    )
    prompt = llm.prompts("group_contents")[0]
    detailed = [line for line in prompt.splitlines() if line.startswith("- id: ")]
    assert len(detailed) == SAMPLE_SIZE
    bio_in_sample = [line for line in detailed if line.startswith("- id: b")]
    chem_in_sample = [line for line in detailed if line.startswith("- id: c")]
    assert len(bio_in_sample) == 15
    assert len(chem_in_sample) == 15
    assert any("Fach: Biologie" in line for line in bio_in_sample)
    assert any("Fach: Physik" in line for line in detailed)


async def test_stratified_sampling_uses_keywords_when_no_discipline_is_set() -> None:
    mixed = [
        *[
            {
                "id": f"m{i}",
                "properties": {"cm:title": [f"Mechanik {i}"], "cclom:general_keyword": ["Arbeitsblatt", "Mechanik"]},
            }
            for i in range(430)
        ],
        *[
            {
                "id": f"q{i}",
                "properties": {"cm:title": [f"Quanten {i}"], "cclom:general_keyword": ["Unterricht", "Quantenphysik"]},
            }
            for i in range(20)
        ],
    ]
    llm = FakeLLM({"group_contents": grouping()})
    await build(
        req(mixed),
        RunContext(
            llm=llm,
            settings=Settings(_env_file=None, items_inline_max=1000),
            deadline=time.monotonic() + 60,
            context="CTX",
        ),
    )
    prompt = llm.prompts("group_contents")[0]
    detailed = [line for line in prompt.splitlines() if line.startswith("- id: ")]
    assert len(detailed) == SAMPLE_SIZE
    quant_in_sample = [line for line in detailed if line.startswith("- id: q")]
    assert len(quant_in_sample) == 20


async def test_stratified_sampling_handles_more_than_sample_size_strata_and_keeps_dominant() -> None:
    unique_items = [
        {"id": f"u{i}", "properties": {"cm:title": [f"Einzelthema{i} Titel"], "cclom:general_keyword": [f"kw{i}"]}}
        for i in range(320)
    ]
    dominant_items = [
        {"id": f"dom{i}", "properties": {"cm:title": [f"Wellenoptik {i}"], "cclom:general_keyword": ["Wellenoptik"]}}
        for i in range(50)
    ]
    llm = FakeLLM({"group_contents": grouping()})
    await build(
        req([*unique_items, *dominant_items]),
        RunContext(
            llm=llm,
            settings=Settings(_env_file=None, items_inline_max=1000),
            deadline=time.monotonic() + 60,
            context="CTX",
        ),
    )
    prompt = llm.prompts("group_contents")[0]
    detailed = [line for line in prompt.splitlines() if line.startswith("- id: ")]
    assert len(detailed) == SAMPLE_SIZE
    assert any(line.startswith("- id: dom") for line in detailed)


async def test_subgroups_are_cut_at_children_max_not_main_max() -> None:
    data = grouping(2)
    data["groups"][0]["children"] = [
        {"title": f"Teil 0.{j}", "shorttitle": f"T{j}", "description": D60, "keywords": [], "children": []}
        for j in range(8)
    ]
    llm = FakeLLM({"group_contents": data})
    run = rc(llm)
    result = await build(req(items(10)), run)
    assert len(result.roots[0].children) == 6
    assert any(w.code == "SHAPE_WIDTH" for w in run.warnings)
