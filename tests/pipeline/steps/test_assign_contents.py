import time

from app.domain.keys import assign_missing_keys
from app.domain.tree import Node, find
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.pipeline.steps.assign_contents import ITEMS_MARKER, assign_contents
from app.schemas.request_v2 import Item, Options
from app.settings import Settings
from tests.fakes.llm import FakeLLM


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context="CTX")


def tree() -> list[Node]:
    roots = [
        Node(key=None, title="Optik", children=[Node(key=None, title="Linsen"), Node(key=None, title="Spiegel")]),
        Node(key=None, title="Mechanik"),
    ]
    assign_missing_keys(roots)
    return roots


def item(i: int, title: str = "Material") -> Item:
    return Item.model_validate({"id": f"c{i}", "nodeId": f"n{i}", "properties": {"cm:title": [f"{title} {i}"]}})


def ids_in(prompt: str) -> list[str]:
    return [line.split("id: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- id: ")]


async def test_assignments_with_confidence_and_node_ids() -> None:
    answer = {
        "items": [
            {"id": "c1", "nodes": [{"key": "k-linsen", "confidence": 0.9}], "off_topic": False, "excluded": False},
            {
                "id": "c2",
                "nodes": [{"key": "k-linsen", "confidence": 0.8}, {"key": "k-mechanik", "confidence": 0.7}],
                "off_topic": False,
                "excluded": False,
            },
        ]
    }
    roots = tree()
    unassigned = await assign_contents(roots, [item(1), item(2)], rc(FakeLLM({"assign_contents": answer})), Options())
    linsen = find(roots, "k-linsen")
    assert [(c.id, c.node_id, c.confidence) for c in linsen.contents] == [("c1", "n1", 0.9), ("c2", "n2", 0.8)]
    assert [c.id for c in find(roots, "k-mechanik").contents] == ["c2"]
    assert unassigned == []


async def test_single_assignment_keeps_only_the_best_node() -> None:
    answer = {
        "items": [
            {"id": "c1", "nodes": [{"key": "k-mechanik", "confidence": 0.7}, {"key": "k-linsen", "confidence": 0.95}]}
        ]
    }
    roots = tree()
    await assign_contents(roots, [item(1)], rc(FakeLLM({"assign_contents": answer})), Options(multi_assign=False))
    assert find(roots, "k-mechanik").contents == []
    assert [c.id for c in find(roots, "k-linsen").contents] == ["c1"]


async def test_reasons_for_unassigned_items() -> None:
    answer = {
        "items": [
            {"id": "c1", "nodes": [{"key": "k-linsen", "confidence": 0.3}]},
            {"id": "c2", "nodes": [], "off_topic": True},
            {"id": "c3", "nodes": [], "excluded": True},
            {"id": "c4", "nodes": []},
        ]
    }
    unassigned = await assign_contents(
        tree(), [item(i) for i in range(1, 5)], rc(FakeLLM({"assign_contents": answer})), Options()
    )
    assert [(u.id, u.reason, u.node_id) for u in unassigned] == [
        ("c1", "low_confidence", "n1"),
        ("c2", "off_topic", "n2"),
        ("c3", "excluded", "n3"),
        ("c4", "no_matching_node", "n4"),
    ]


async def test_unknown_keys_and_missing_items_are_handled() -> None:
    answer = {
        "items": [
            {"id": "c1", "nodes": [{"key": "k-erfunden", "confidence": 0.9}]},
            {"id": "c-erfunden", "nodes": [{"key": "k-linsen", "confidence": 0.9}]},
        ]
    }
    context = rc(FakeLLM({"assign_contents": answer}))
    roots = tree()
    unassigned = await assign_contents(roots, [item(1), item(2)], context, Options())
    assert {u.id for u in unassigned} == {"c1", "c2"}
    assert find(roots, "k-linsen").contents == []
    assert [w.code for w in context.warnings] == ["ASSIGN_FAILED"]


async def test_batches_of_forty_share_the_tree_prefix() -> None:
    def answer(prompt: str) -> dict:
        return {"items": [{"id": i, "nodes": [{"key": "k-optik", "confidence": 0.9}]} for i in ids_in(prompt)]}

    llm = FakeLLM({"assign_contents": answer})
    roots = tree()
    await assign_contents(roots, [item(i) for i in range(90)], rc(llm), Options())
    prompts = llm.prompts("assign_contents")
    assert len(prompts) == 3
    assert len({p.split(ITEMS_MARKER)[0] for p in prompts}) == 1
    assert "k-linsen: Optik > Linsen" in prompts[0]
    assert len(find(roots, "k-optik").contents) == 90


async def test_failed_batch_leaves_items_unassigned_with_warning() -> None:
    context = rc(FakeLLM({"assign_contents": LLMStepError("assign_contents", "timeout")}))
    unassigned = await assign_contents(tree(), [item(1)], context, Options())
    assert [(u.id, u.reason) for u in unassigned] == [("c1", "no_matching_node")]
    assert [w.code for w in context.warnings] == ["ASSIGN_FAILED"]


async def test_existing_assignment_is_not_duplicated() -> None:
    answer = {"items": [{"id": "c1", "nodes": [{"key": "k-linsen", "confidence": 0.9}]}]}
    roots = tree()
    llm = FakeLLM({"assign_contents": answer})
    await assign_contents(roots, [item(1)], rc(llm), Options())
    await assign_contents(roots, [item(1)], rc(llm), Options())
    assert len(find(roots, "k-linsen").contents) == 1
