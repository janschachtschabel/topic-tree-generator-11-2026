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


def plan_answer(n_main: int, n_children: int, n_grand: int = 0) -> dict:
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
                "children": [
                    {
                        "title": f"Kind {i}.{j}",
                        "shorttitle": f"K{j}",
                        "children": [
                            {"title": f"Enkel {i}.{j}.{g}", "shorttitle": f"E{g}", "children": []}
                            for g in range(n_grand)
                        ],
                    }
                    for j in range(n_children)
                ],
            }
            for i in range(n_main)
        ],
    }


def describe(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {"nodes": [{"key": k, "description": "wort " * 60, "keywords": ["Licht", "Optik"]} for k in keys]}


def rc(llm: FakeLLM, context: str = "CTX") -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context=context)


async def test_eight_by_five_by_three_fits_in_one_parallel_worker_wave() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(8, 5, n_grand=3), "describe_nodes": describe})
    request = req(shape={"depth": 3, "main_topics": {"min": 8, "max": 8}, "children": {"min": 3, "max": 5}})
    result = await build(request, rc(llm))
    # 1 skeleton + ceil(168 / 10) = 18 calls (all 17 describe batches run in 1 parallel wave under 20 workers).
    assert len(llm.calls) <= 20
    assert len(result.roots) == 8
    assert sum(1 for _ in walk(result.roots)) == 8 + 8 * 5 + 8 * 5 * 3
    assert all(node.description for node, _, _ in walk(result.roots))
    assert result.structure.source == "detected"
    assert result.title == ex.TOPIC["topic"]


async def test_extra_topics_are_inserted_first_and_last() -> None:
    payload = plan_answer(6, 3)
    payload["main_topics"].append(
        {
            "title": "Allgemeines",
            "shorttitle": "Allgemeines",
            "from_inputs": False,
            "children": [
                {"title": "Einstieg", "shorttitle": "Einstieg", "children": []},
                {"title": "Grundbegriffe", "shorttitle": "Grundbegriffe", "children": []},
            ],
        }
    )
    llm = FakeLLM({"plan_structure": payload, "describe_nodes": describe})
    shape = {"depth": 2, "extra_topics": ["general", "methodology"]}
    result = await build(req(shape=shape), rc(llm))
    titles = [r.title for r in result.roots]
    assert titles[0] == "Allgemeines" and titles[-1] == "Methodik und Didaktik"
    assert len(result.roots) == 8
    assert [c.title for c in result.roots[0].children] == ["Einstieg", "Grundbegriffe"]


async def test_cross_branch_duplicates_in_skeleton_are_eliminated_before_describing() -> None:
    payload = plan_answer(6, 3, n_grand=3)
    # Inject a duplicate leaf across two branches.
    payload["main_topics"][1]["children"][0]["children"][0]["title"] = "Enkel 0.0.0"
    llm = FakeLLM({"plan_structure": payload, "describe_nodes": describe})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req(), context)
    assert not [w for w in resp.warnings if w.code == "DUPLICATE_TITLE"]


async def test_depth_one_uses_describe_instead_of_branches() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
    result = await build(req(shape={"depth": 1}), rc(llm))
    assert len(llm.prompts("describe_nodes")) == 1
    assert all(r.description and r.children == [] for r in result.roots)


async def test_structure_items_feed_the_plan_prompt() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
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


async def test_many_structure_items_keep_titles_and_keywords_and_warn_above_limit() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
    twelve = [
        {
            "id": f"m{i}",
            "use": ["structure", "content"],
            "properties": {"cm:title": [f"Material Baustein {i}"], "cclom:general_keyword": [f"Begriff{i}"]},
        }
        for i in range(12)
    ]
    await build(req(items=twelve), rc(llm))
    prompt = llm.prompts("plan_structure")[0]
    assert "Material Baustein 11" in prompt
    assert "Begriff11" in prompt

    many = [{"id": f"x{i}", "use": ["structure"], "properties": {"cm:title": [f"Eintrag {i}"]}} for i in range(55)]
    context = rc(FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe}))
    await build(req(items=many), context)
    assert "INPUTS_TRUNCATED" in [w.code for w in context.warnings]


async def test_context_block_comes_from_the_run_context() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
    await build(req(), rc(llm, context="## Anfragekontext\nThema: X"))
    assert all(user.startswith("## Anfragekontext\nThema: X") for _, user in llm.calls)


async def test_orchestrator_end_to_end_without_warnings() -> None:
    llm = FakeLLM({"plan_structure": plan_answer(6, 3, n_grand=3), "describe_nodes": describe})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req(), context)
    assert resp.warnings == []
    assert len(resp.collection) == 6
    # 1 skeleton + ceil((6 + 18 + 54) / 10) = 1 + 8 = 9 LLM calls
    assert resp.metadata.generation.usage.llm_calls == 9
    assert llm.calls[0][1].startswith("## Anfragekontext")


async def test_orchestrator_assigns_content_items_after_building() -> None:
    def assign(prompt: str) -> dict:
        return {
            "items": [
                {"id": "c1", "nodes": [{"key": "k-haupt-0", "confidence": 0.9}]},
                {"id": "c2", "nodes": [], "off_topic": True},
            ]
        }

    llm = FakeLLM(
        {"plan_structure": plan_answer(6, 3, n_grand=3), "describe_nodes": describe, "assign_contents": assign}
    )
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
    llm = FakeLLM({"plan_structure": plan_answer(6, 3, n_grand=3), "describe_nodes": describe})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    await orchestrator.run(req(items=[ex.content_item("c1", "Linse")], options={"assign_contents": False}), context)
    assert llm.prompts("assign_contents") == []


async def test_extra_topic_variants_are_recognised_and_renamed() -> None:
    payload = plan_answer(5, 2)
    payload["main_topics"].append(
        {
            "title": "Methodik & Didaktik",
            "shorttitle": "Methodik",
            "from_inputs": False,
            "children": [
                {"title": "Experimente planen", "shorttitle": "Experimente", "children": []},
                {"title": "Lernstand erheben", "shorttitle": "Lernstand", "children": []},
            ],
        }
    )
    llm = FakeLLM({"plan_structure": payload, "describe_nodes": describe})
    shape = {"depth": 2, "main_topics": {"min": 3, "max": 6}, "extra_topics": ["methodology"]}
    run = rc(llm)
    result = await build(req(shape=shape), run)
    titles = [r.title for r in result.roots]
    assert titles.count("Methodik und Didaktik") == 1 and titles[-1] == "Methodik und Didaktik"
    assert "Methodik & Didaktik" not in titles
    assert len(result.roots) == 6
    assert [c.title for c in result.roots[-1].children] == ["Experimente planen", "Lernstand erheben"]
    assert not any(w.code == "SHAPE_WIDTH" for w in run.warnings)


async def test_requested_extra_topic_is_never_marked_suggested() -> None:
    payload = plan_answer(6, 2)
    payload["main_topics"].insert(
        0,
        {
            "title": "Allgemeines",
            "shorttitle": "Allgemeines",
            "from_inputs": True,
            "children": [
                {"title": "Begriffe", "shorttitle": "Begriffe", "children": []},
                {"title": "Sicherheit", "shorttitle": "Sicherheit", "children": []},
            ],
        },
    )
    llm = FakeLLM({"plan_structure": payload, "describe_nodes": describe})
    data = copy.deepcopy(ex.TOPIC)
    data["shape"] = {"depth": 2, "extra_topics": ["general"]}
    data["items"] = [{"id": "s1", "use": ["structure"], "properties": {"cm:title": ["Lehrplan Optik"]}}]
    result = await build(TopicTreeRequestV2.model_validate(data), rc(llm))
    assert result.roots[0].title == "Allgemeines"
    assert result.roots[0].status is None


async def test_untitled_llm_nodes_are_dropped_with_a_warning() -> None:
    # Audit 2026-11-25, open point 1: a collection without a name is unusable in edu-sharing.
    answer = plan_answer(3, 2)
    answer["main_topics"][1]["children"][0]["title"] = "   "
    llm = FakeLLM({"plan_structure": answer, "describe_nodes": describe})
    context = rc(llm)
    request = req(shape={"depth": 2, "main_topics": {"min": 3, "max": 3}, "children": {"min": 2, "max": 2}})
    resp = await orchestrator.run(request, context)
    titles = [n.title for n in resp.collection[1].subcollections]
    assert titles == ["Kind 1.1"]
    assert "UNTITLED_NODE" in [w.code for w in resp.warnings]


async def test_create_ignores_a_sent_current_tree_and_says_so() -> None:
    current = {
        "version": "v3",
        "collection": [{"key": "k-alt", "title": "Alt"}],
        "generation": {
            "use_case": "topic",
            "options": {"min_confidence": 0.95},
            "feedback": [{"version": "v2", "text": "x"}],
        },
    }
    llm = FakeLLM({"plan_structure": plan_answer(6, 3), "describe_nodes": describe})
    resp = await orchestrator.run(req(current_tree=current), rc(llm))
    meta = resp.metadata
    assert (meta.version, meta.based_on) == ("v1", None)
    assert meta.generation.options.min_confidence == 0.6
    assert meta.generation.feedback == []
    assert "INPUT_IGNORED" in [w.code for w in resp.warnings]
