import time

from app.domain.keys import assign_missing_keys
from app.domain.tree import Node, walk
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import NODES_MARKER, describe_nodes
from app.settings import Settings
from tests.fakes.llm import FakeLLM


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)


def tree(n: int) -> list[Node]:
    roots = [Node(key=None, title="Optik", children=[Node(key=None, title=f"Thema {i}") for i in range(n)])]
    assign_missing_keys(roots)
    return roots


def echo(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {
        "nodes": [{"key": k, "description": f"Text {k}", "keywords": ["a"]} for k in keys]
        + [{"key": "k-erfunden", "description": "x", "keywords": []}]
    }


async def test_batches_of_thirty_with_paths_and_extra_info() -> None:
    roots = tree(40)
    targets = [n for n, _, _ in walk(roots)]
    llm = FakeLLM({"describe_nodes": echo})
    await describe_nodes(targets, roots, rc(llm), context="CTX", extra={"k-thema-0": "Inhalte: Linse, Prisma"})
    prompts = llm.prompts("describe_nodes")
    assert len(prompts) == 2
    assert "Pfad: Optik > Thema 0" in prompts[0]
    assert "Inhalte: Linse, Prisma" in prompts[0]
    assert {p.split(NODES_MARKER)[0] for p in prompts} == {prompts[0].split(NODES_MARKER)[0]}
    assert all(n.description.startswith("Text k-") for n in targets)
    assert targets[1].keywords == ["a"]


async def test_extra_info_is_truncated() -> None:
    roots = tree(2)
    llm = FakeLLM({"describe_nodes": echo})
    await describe_nodes([roots[0]], roots, rc(llm), context="CTX", extra={roots[0].key: "x" * 5000})
    assert len(llm.prompts("describe_nodes")[0]) < 3000


async def test_failed_batch_warns_and_leaves_nodes_empty() -> None:
    roots = tree(3)
    llm = FakeLLM({"describe_nodes": LLMStepError("describe_nodes", "invalid_output")})
    context = rc(llm)
    await describe_nodes(roots[0].children, roots, context, context="CTX")
    assert all(n.description == "" for n in roots[0].children)
    assert [w.code for w in context.warnings] == ["DESCRIBE_FAILED"]


async def test_nothing_to_describe_makes_no_call() -> None:
    llm = FakeLLM({"describe_nodes": echo})
    await describe_nodes([], tree(1), rc(llm), context="CTX")
    assert llm.calls == []


async def test_unknown_keys_from_llm_are_ignored_and_reported() -> None:
    roots = tree(2)
    context = rc(FakeLLM({"describe_nodes": echo}))
    await describe_nodes([roots[0]], roots, context, context="CTX")
    assert "DESCRIBE_UNKNOWN_KEY" in [w.code for w in context.warnings]
