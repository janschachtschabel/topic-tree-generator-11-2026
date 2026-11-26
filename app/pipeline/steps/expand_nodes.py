"""New nodes from text feedback get subtopics down to the depth of their neighbouring branches. One LLM call."""

from pydantic import BaseModel, Field

from app.domain.tree import Node, path
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


def missing_levels(node: Node, siblings: list[Node]) -> int:
    """Levels a new leaf lacks compared with its deepest sibling branch (0 when nothing is missing)."""
    if node.children:
        return 0
    return max((_height(s) for s in siblings if s is not node), default=1) - 1


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
    added: list[Node] = []
    for item in result.nodes:
        if item.key.strip() not in by_key or by_key[item.key.strip()][0].children:
            continue
        node, levels = by_key[item.key.strip()]
        node.children = convert_children(item.children, levels, width[1], Cut())
        _mark(node.children)
        added.extend(node.children)
    return added
