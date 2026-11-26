"""New nodes from text feedback get subtopics down to the depth of their neighbouring branches. One LLM call."""

from pydantic import BaseModel, Field

from app.domain.tree import Node, path, walk
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import render_tree_outline
from app.pipeline.steps.node_conversion import Cut
from app.pipeline.steps.plan_structure import PlannedChild, convert_children
from app.prompts import render
from app.schemas.common import OriginType
from app.schemas.response_v2 import Origin

STEP = "expand_nodes"


class ExpandedNode(BaseModel):
    key: str
    children: list[PlannedChild] = Field(default_factory=list)


class ExpandResult(BaseModel):
    nodes: list[ExpandedNode]


def _height(node: Node) -> int:
    return 1 + max((_height(child) for child in node.children), default=0)


def shallow_leaves(node: Node, siblings: list[Node]) -> list[tuple[Node, int]]:
    """Leaves of a new branch with the levels each lacks against the deepest sibling branch."""
    target = max((_height(s) for s in siblings if s is not node), default=1)
    found: list[tuple[Node, int]] = []

    def visit(current: Node, depth: int) -> None:
        if not current.children:
            if target - depth > 0:
                found.append((current, target - depth))
            return
        for child in current.children:
            visit(child, depth + 1)

    visit(node, 1)
    return found


def _fold(title: str) -> str:
    return " ".join(title.casefold().split())


def _without_known(nodes: list[Node], known: set[str]) -> list[Node]:
    """Drop proposed subtopics whose title already stands in the tree (and repeats within the proposal)."""
    kept = []
    for node in nodes:
        if _fold(node.title) in known:
            continue
        known.add(_fold(node.title))
        node.children = _without_known(node.children, known)
        kept.append(node)
    return kept


def _mark(nodes: list[Node]) -> None:
    for node in nodes:
        node.origin = Origin(type=OriginType.feedback)
        _mark(node.children)


async def expand_nodes(
    targets: list[tuple[Node, int]], roots: list[Node], rc: RunContext, width: tuple[int, int]
) -> list[Node]:
    """Fill each (node, levels) target with planned subtopics; returns the new nodes."""
    lines = "\n".join(
        f"- key: {node.key} | Pfad: {' > '.join(path(roots, node.key))} | {levels} Ebene{'n' if levels > 1 else ''}"
        for node, levels in targets
    )
    prompt = render(
        STEP,
        context=rc.context,
        outline=render_tree_outline(roots),
        width=f"{width[0]} bis {width[1]}",
        nodes=lines,
    )
    result = await rc.llm.complete_json(STEP, prompt, ExpandResult, max_tokens=3000)
    by_key = {node.key: (node, levels) for node, levels in targets}
    known = {_fold(node.title) for node, _, _ in walk(roots)}
    added: list[Node] = []
    for item in result.nodes:
        if item.key.strip() not in by_key or by_key[item.key.strip()][0].children:
            continue
        node, levels = by_key[item.key.strip()]
        node.children = _without_known(convert_children(item.children, levels, width[1], Cut()), known)
        _mark(node.children)
        added.extend(node.children)
    return added
