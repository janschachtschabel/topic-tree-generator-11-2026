import copy
import time

from app.domain.keys import assign_missing_keys
from app.domain.tree import Node
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.pipeline.steps.expand_branch import BRANCH_MARKER, expand_branches
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


def req(depth: int = 3) -> TopicTreeRequestV2:
    data = copy.deepcopy(ex.TOPIC)
    data["shape"]["depth"] = depth
    return TopicTreeRequestV2.model_validate(data)


def skeleton(n: int = 4) -> list[Node]:
    roots = [
        Node(key=None, title=f"Haupt {i}", children=[Node(key=None, title=f"Kind {i}.{j}") for j in range(3)])
        for i in range(n)
    ]
    assign_missing_keys(roots)
    return roots


def branch_answer(prompt: str, grand: int = 3, too_deep: bool = False) -> dict:
    main = prompt.split("Hauptthema: ")[-1].splitlines()[0]
    return {
        "description": f"Beschreibung {main}",
        "keywords": ["a", "b", "c"],
        "children": [
            {
                "title": f"{main} K{j}",
                "shorttitle": f"K{j}",
                "description": "d",
                "keywords": ["x"],
                "children": [
                    {
                        "title": f"{main} K{j} E{e}",
                        "shorttitle": f"E{e}",
                        "description": "e",
                        "keywords": [],
                        "children": [
                            {"title": "zu tief", "shorttitle": "t", "description": "", "keywords": [], "children": []}
                        ]
                        if too_deep
                        else [],
                    }
                    for e in range(grand)
                ],
            }
            for j in range(3)
        ],
    }


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)


async def test_one_parallel_call_per_main_topic() -> None:
    llm = FakeLLM({"expand_branch": branch_answer}, delay=0.05)
    roots = skeleton(6)
    start = time.perf_counter()
    await expand_branches(roots, req(), rc(llm), context="CTX", levels=["Thema", "Teilthema", "Aspekt"])
    assert len(llm.prompts("expand_branch")) == 6
    assert time.perf_counter() - start < 0.2
    assert roots[0].description == "Beschreibung Haupt 0"
    assert [c.title for c in roots[0].children] == ["Haupt 0 K0", "Haupt 0 K1", "Haupt 0 K2"]
    assert roots[0].children[0].children[0].title == "Haupt 0 K0 E0"
    assert roots[0].children[0].origin.type == "topic"


async def test_branch_prompts_share_everything_before_the_branch_block() -> None:
    llm = FakeLLM({"expand_branch": branch_answer})
    await expand_branches(skeleton(4), req(), rc(llm), context="CTX", levels=["Thema"])
    prompts = llm.prompts("expand_branch")
    prefixes = {p.split(BRANCH_MARKER)[0] for p in prompts}
    assert len(prefixes) == 1
    assert prompts[0].startswith("CTX")
    assert "Haupt 3" in next(iter(prefixes))


async def test_levels_below_depth_are_cut_and_reported() -> None:
    llm = FakeLLM({"expand_branch": lambda p: branch_answer(p, too_deep=True)})
    roots = skeleton(1)
    context = rc(llm)
    await expand_branches(roots, req(depth=3), context, context="CTX", levels=[])
    assert roots[0].children[0].children[0].children == []
    assert [w.code for w in context.warnings] == ["SHAPE_DEPTH"]


async def test_too_many_children_are_cut_and_reported() -> None:
    llm = FakeLLM({"expand_branch": lambda p: branch_answer(p, grand=12)})
    roots = skeleton(1)
    context = rc(llm)
    await expand_branches(roots, req(depth=3), context, context="CTX", levels=[])
    assert len(roots[0].children[0].children) == 8
    assert [w.code for w in context.warnings] == ["SHAPE_WIDTH"]


async def test_depth_two_requests_no_deeper_levels() -> None:
    llm = FakeLLM({"expand_branch": branch_answer})
    roots = skeleton(1)
    await expand_branches(roots, req(depth=2), rc(llm), context="CTX", levels=[])
    assert "keine weiteren Ebenen" in llm.prompts("expand_branch")[0]
    assert roots[0].children[0].children == []


async def test_failed_branch_keeps_skeleton_and_warns() -> None:
    def flaky(prompt: str) -> dict:
        if "Hauptthema: Haupt 1" in prompt:
            raise LLMStepError("expand_branch", "invalid_output")
        return branch_answer(prompt)

    llm = FakeLLM({"expand_branch": flaky})
    context = rc(llm)
    roots = skeleton(3)
    await expand_branches(roots, req(), context, context="CTX", levels=[])
    assert [c.title for c in roots[1].children] == ["Kind 1.0", "Kind 1.1", "Kind 1.2"]
    assert roots[0].description and roots[2].description
    assert [(w.code, w.key) for w in context.warnings] == [("BRANCH_FAILED", "k-haupt-1")]


async def test_deadline_failure_is_reported_as_deadline() -> None:
    llm = FakeLLM({"expand_branch": LLMStepError("expand_branch", "deadline")})
    context = rc(llm)
    await expand_branches(skeleton(2), req(), context, context="CTX", levels=[])
    assert [w.code for w in context.warnings] == ["DEADLINE_EXCEEDED"]


async def test_empty_answer_keeps_skeleton_children() -> None:
    llm = FakeLLM({"expand_branch": {"description": "D", "keywords": [], "children": []}})
    roots = skeleton(1)
    await expand_branches(roots, req(), rc(llm), context="CTX", levels=[])
    assert roots[0].description == "D"
    assert len(roots[0].children) == 3


async def test_branch_prompt_instructs_against_cross_branch_duplicates() -> None:
    llm = FakeLLM({"expand_branch": branch_answer})
    await expand_branches(skeleton(2), req(), rc(llm), context="CTX", levels=["Thema"])
    prompt = llm.prompts("expand_branch")[0]
    assert "keinen gleichnamigen Knoten" in prompt
