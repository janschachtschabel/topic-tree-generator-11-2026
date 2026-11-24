import copy

from app.pipeline.run_context import RunContext
from app.pipeline.steps.plan_structure import _max_tokens, plan_structure
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


def req(data: dict) -> TopicTreeRequestV2:
    return TopicTreeRequestV2.model_validate(copy.deepcopy(data))


def answer(n_main: int, n_children: int, order: str = "Themen", n_grand: int = 0) -> dict:
    return {
        "order": order,
        "levels": ["Thema", "Teilthema", "Aspekt"],
        "rationale": "Schule, Sekundarstufe I",
        "description": "Optik im Alltag",
        "main_topics": [
            {
                "title": f"Haupt {i}",
                "shorttitle": f"H{i}",
                "from_inputs": False,
                "children": [
                    {
                        "title": f"Kind {i}.{j}",
                        "shorttitle": f"K{i}{j}",
                        "children": [
                            {"title": f"Enkel {i}.{j}.{g}", "shorttitle": f"E{i}{j}{g}", "children": []}
                            for g in range(n_grand)
                        ],
                    }
                    for j in range(n_children)
                ],
            }
            for i in range(n_main)
        ],
    }


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=10**12)


async def test_prompt_contains_context_block_then_shape_instruction() -> None:
    llm = FakeLLM({"plan_structure": answer(6, 3, n_grand=3)})
    await plan_structure(req(ex.TOPIC), rc(llm), context="## Anfragekontext\nThema: Optik")
    (prompt,) = llm.prompts("plan_structure")
    assert prompt.startswith("## Anfragekontext\nThema: Optik")
    assert "6 bis 12 reguläre Hauptthemen" in prompt
    assert "3 bis 8" in prompt
    assert "3 Ebenen" in prompt
    assert "duplikate" in prompt.lower()


async def test_order_hint_is_used_and_marked_as_hint() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["hints"]["order"] = "Themenfelder"
    llm = FakeLLM({"plan_structure": answer(6, 3, order="Themenfelder")})
    result = await plan_structure(req(data), rc(llm), context="CTX")
    assert result.structure.source == "hint"
    assert result.structure.order == "Themenfelder"
    assert "vorgegebene Ordnungsprinzip" in llm.prompts("plan_structure")[0]


async def test_detected_order_is_recorded() -> None:
    llm = FakeLLM({"plan_structure": answer(6, 3)})
    result = await plan_structure(req(ex.TOPIC), rc(llm), context="CTX")
    assert result.structure.source == "detected"
    assert result.structure.levels == ["Thema", "Teilthema", "Aspekt"]


async def test_too_many_topics_are_cut_with_a_warning() -> None:
    llm = FakeLLM({"plan_structure": answer(15, 10)})
    context = rc(llm)
    result = await plan_structure(req(ex.TOPIC), context, context="CTX")
    assert len(result.roots) == 12
    assert all(len(r.children) == 8 for r in result.roots)
    assert [w.code for w in context.warnings] == ["SHAPE_WIDTH", "SHAPE_WIDTH"]


async def test_depth_one_has_no_children_in_skeleton() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["shape"]["depth"] = 1
    llm = FakeLLM({"plan_structure": answer(6, 3)})
    result = await plan_structure(req(data), rc(llm), context="CTX")
    assert all(r.children == [] for r in result.roots)
    assert "keine Unterthemen" in llm.prompts("plan_structure")[0]


async def test_nodes_from_inputs_are_suggested_and_origin_is_topic() -> None:
    data = answer(6, 3)
    data["main_topics"][0]["from_inputs"] = True
    llm = FakeLLM({"plan_structure": data})
    result = await plan_structure(req(ex.TOPIC), rc(llm), context="CTX", inputs_block="## Ergänzende Eingaben\n- X")
    assert result.roots[0].status == "suggested"
    assert result.roots[1].status is None
    assert result.roots[0].origin.type == "topic"
    assert "## Ergänzende Eingaben" in llm.prompts("plan_structure")[0]


async def test_three_level_skeleton_keeps_grandchildren_and_cuts_excess_depth() -> None:
    llm = FakeLLM({"plan_structure": answer(6, 3, n_grand=3)})
    result = await plan_structure(req(ex.TOPIC), rc(llm), context="CTX")
    assert len(result.roots) == 6
    assert len(result.roots[0].children) == 3
    assert len(result.roots[0].children[0].children) == 3

    data = copy.deepcopy(ex.TOPIC)
    data["shape"]["depth"] = 2
    context = rc(FakeLLM({"plan_structure": answer(6, 3, n_grand=3)}))
    shallow = await plan_structure(req(data), context, context="CTX")
    assert all(c.children == [] for r in shallow.roots for c in r.children)
    assert "SHAPE_DEPTH" in [w.code for w in context.warnings]


async def test_extra_topics_do_not_count_against_main_max() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["shape"]["main_topics"] = {"min": 6, "max": 6}
    data["shape"]["extra_topics"] = ["general"]
    payload = answer(6, 3, n_grand=2)
    payload["main_topics"].insert(
        0,
        {
            "title": "Allgemeines",
            "shorttitle": "Allgemeines",
            "from_inputs": False,
            "children": [{"title": "Grundlagen", "shorttitle": "Grundlagen", "children": []}],
        },
    )
    context = rc(FakeLLM({"plan_structure": payload}))
    result = await plan_structure(req(data), context, context="CTX")
    assert len(result.roots) == 7
    assert context.warnings == []


def test_token_budget_scales_with_shape_and_respects_bounds() -> None:
    def budget(shape: dict) -> int:
        return _max_tokens(TopicTreeRequestV2.model_validate({**ex.TOPIC, "shape": shape}))

    small = budget({"depth": 1, "main_topics": {"min": 3, "max": 5}})
    medium = budget({"depth": 3, "main_topics": {"min": 6, "max": 12}, "children": {"min": 3, "max": 8}})
    huge = budget({"depth": 3, "main_topics": {"min": 6, "max": 20}, "children": {"min": 3, "max": 20}})
    assert small == 4000
    # 12 + 96 + 768 = 876 skeleton nodes must fit without truncating the JSON answer.
    assert medium >= 876 * 30
    assert huge == 32000


async def test_from_inputs_is_ignored_without_supplementary_inputs() -> None:
    data = answer(6, 3)
    data["main_topics"][0]["from_inputs"] = True
    llm = FakeLLM({"plan_structure": data})
    result = await plan_structure(req(ex.TOPIC), rc(llm), context="CTX")
    assert result.roots[0].status is None
