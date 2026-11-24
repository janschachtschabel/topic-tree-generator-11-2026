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
