import copy
import time

from app.domain.tree import walk
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.pipeline.strategies.topic import build
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


def req(**changes) -> TopicTreeRequestV2:
    data = copy.deepcopy(ex.TOPIC)
    for key, value in changes.items():
        data[key] = value
    return TopicTreeRequestV2.model_validate(data)


def plan_answer(n_main: int, n_children: int) -> dict:
    return {
        "order": "Themen",
        "levels": ["Thema", "Teilthema", "Aspekt"],
        "rationale": "r",
        "description": "Baum",
        "main_topics": [
            {
                "title": f"Haupt {i}",
                "shorttitle": f"H{i}",
                "from_inputs": False,
                "children": [{"title": f"Kind {i}.{j}", "shorttitle": f"K{j}"} for j in range(n_children)],
            }
            for i in range(n_main)
        ],
    }


def branch(prompt: str, grand: int = 3) -> dict:
    main = prompt.split("Hauptthema: ")[-1].splitlines()[0]
    given = [line[2:] for line in prompt.split("Vorgegebene Unterthemen:\n")[-1].splitlines() if line.startswith("- ")]
    given = given or [f"{main} neu {j}" for j in range(3)]
    return {
        "description": "wort " * 60,
        "keywords": ["a"],
        "children": [
            {
                "title": t,
                "shorttitle": t[:10],
                "description": "wort " * 60,
                "keywords": ["b"],
                "children": [
                    {
                        "title": f"{t} E{e}",
                        "shorttitle": f"E{e}",
                        "description": "wort " * 60,
                        "keywords": [],
                        "children": [],
                    }
                    for e in range(grand)
                ],
            }
            for t in given
        ],
    }


def rc(llm: FakeLLM, context: str = "CTX") -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context=context)


async def test_eight_by_five_by_three_needs_at_most_ten_llm_calls() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(8, 5), "expand_branch": branch})
    request = req(shape={"depth": 3, "main_topics": {"min": 8, "max": 8}, "children": {"min": 3, "max": 5}})
    result = await build(request, rc(llm))
    assert len(llm.calls) <= 10
    assert len(result.roots) == 8
    assert sum(1 for _ in walk(result.roots)) == 8 + 8 * 5 + 8 * 5 * 3
    assert result.structure.source == "detected"
    assert result.title == ex.TOPIC["topic"]


async def test_extra_topics_are_inserted_first_and_last() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch})
    shape = {"depth": 2, "extra_topics": ["general", "methodology"]}
    result = await build(req(shape=shape), rc(llm))
    titles = [r.title for r in result.roots]
    assert titles[0] == "Allgemeines" and titles[-1] == "Methodik und Didaktik"
    assert len(result.roots) == 8
    assert result.roots[0].children


async def test_depth_one_uses_describe_instead_of_branches() -> None:
    def describe(prompt: str) -> dict:
        keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
        return {"nodes": [{"key": k, "description": "wort " * 60, "keywords": []} for k in keys]}

    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
    result = await build(req(shape={"depth": 1}), rc(llm))
    assert llm.prompts("expand_branch") == []
    assert len(llm.prompts("describe_nodes")) == 1
    assert all(r.description and r.children == [] for r in result.roots)


async def test_structure_items_feed_the_plan_prompt() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch})
    items = [
        {
            "id": "s1",
            "use": ["structure", "content"],
            "properties": {"cm:title": ["Unterrichtsreihe Farben"]},
            "fulltext": {"format": "markdown", "text": "# Farben\nSpektrum und Prisma"},
        }
    ]
    await build(req(items=items), rc(llm))
    prompt = llm.prompts("plan_structure")[0]
    assert "## Ergänzende Eingaben" in prompt
    assert "Unterrichtsreihe Farben" in prompt and "Spektrum und Prisma" in prompt


async def test_context_block_comes_from_the_run_context() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch})
    await build(req(), rc(llm, context="## Anfragekontext\nThema: X"))
    assert all(user.startswith("## Anfragekontext\nThema: X") for _, user in llm.calls)


async def test_orchestrator_end_to_end_without_warnings() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req(), context)
    assert resp.warnings == []
    assert len(resp.collection) == 6
    assert resp.metadata.generation.usage.llm_calls == 7
    assert llm.calls[0][1].startswith("## Anfragekontext")


async def test_orchestrator_assigns_content_items_after_building() -> None:
    def assign(prompt: str) -> dict:
        return {
            "items": [
                {"id": "c1", "nodes": [{"key": "k-haupt-0", "confidence": 0.9}]},
                {"id": "c2", "nodes": [], "off_topic": True},
            ]
        }

    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch, "assign_contents": assign})
    items = [
        ex.content_item("c1", "Linse"),
        ex.content_item("c2", "Kochrezept"),
        {"id": "s1", "use": ["structure"], "properties": {"cm:title": ["Reihe"]}},
    ]
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req(items=items), context)
    assert [c.id for c in resp.collection[0].contents] == ["c1"]
    assert [(u.id, u.reason) for u in resp.unassigned] == [("c2", "off_topic")]
    assert "s1" not in llm.prompts("assign_contents")[0]


async def test_assignment_can_be_switched_off() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "expand_branch": branch})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    await orchestrator.run(req(items=[ex.content_item("c1", "Linse")], options={"assign_contents": False}), context)
    assert llm.prompts("assign_contents") == []
