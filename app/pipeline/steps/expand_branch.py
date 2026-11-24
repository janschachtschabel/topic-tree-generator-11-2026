"""Step 2 of a generated tree: one call per main topic, in parallel, filling descriptions and deeper levels.

Every branch prompt is identical up to BRANCH_MARKER (context + full skeleton + instructions), so parallel calls
share the provider's prompt cache. A failed branch keeps its skeleton and is reported in `warnings`.
"""

import asyncio

from pydantic import BaseModel, Field

from app.domain.tree import Node
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.common import OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin

STEP = "expand_branch"
BRANCH_MARKER = "## Dieser Ast"


class BranchNode(BaseModel):
    title: str
    shorttitle: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    children: list["BranchNode"] = Field(default_factory=list)


class BranchResult(BaseModel):
    description: str
    keywords: list[str] = Field(default_factory=list)
    children: list[BranchNode] = Field(default_factory=list)


def render_skeleton(roots: list[Node]) -> str:
    lines = []
    for root in roots:
        lines.append(f"- {root.title}")
        lines.extend(f"  - {child.title}" for child in root.children)
    return "\n".join(lines)


def _depth_instruction(req: TopicTreeRequestV2) -> str:
    below = req.shape.depth - 2
    if below <= 0:
        return "Erzeuge unter den Unterthemen keine weiteren Ebenen."
    c = req.shape.children
    levels = "eine weitere Ebene" if below == 1 else f"{below} weitere Ebenen"
    return f"Erzeuge unter jedem Unterthema {levels} mit je {c.min} bis {c.max} Kindern, alle mit Beschreibung."


def _branch_block(main: Node) -> str:
    given = "\n".join(f"- {child.title}" for child in main.children) or "(keine)"
    return f"{BRANCH_MARKER}\nHauptthema: {main.title}\nVorgegebene Unterthemen:\n{given}"


def _max_tokens(req: TopicTreeRequestV2, main: Node) -> int:
    width = req.shape.children.max
    first = len(main.children) or width
    nodes = sum(first * width**level for level in range(max(req.shape.depth - 1, 0)))
    per_node = int(req.hints.description_length * 1.6) + 60
    return max(2000, min(32000, 800 + nodes * per_node))


class Cut:
    """Records whether the LLM answer exceeded the shape (too deep or too wide)."""

    def __init__(self) -> None:
        self.depth = False
        self.width = False


def to_nodes(
    items: list[BranchNode], levels_left: int, width: int, cut: Cut, origin: OriginType = OriginType.topic
) -> list[Node]:
    """Convert LLM nodes into working nodes, cutting what exceeds the shape (recorded in `cut`)."""
    if levels_left <= 0:
        cut.depth = cut.depth or bool(items)
        return []
    cut.width = cut.width or len(items) > width
    return [
        Node(
            key=None,
            title=item.title.strip(),
            shorttitle=item.shorttitle.strip(),
            description=item.description.strip(),
            keywords=item.keywords,
            origin=Origin(type=origin),
            children=to_nodes(item.children, levels_left - 1, width, cut, origin),
        )
        for item in items[:width]
    ]


async def _expand_one(main: Node, prefix: str, req: TopicTreeRequestV2, rc: RunContext) -> Cut:
    result = await rc.llm.complete_json(
        STEP, f"{prefix}{_branch_block(main)}", BranchResult, max_tokens=_max_tokens(req, main)
    )
    main.description = result.description.strip()
    main.keywords = result.keywords
    cut = Cut()
    children = to_nodes(result.children, req.shape.depth - 1, req.shape.children.max, cut)
    if children:
        main.children = children
    return cut


async def expand_branches(
    roots: list[Node], req: TopicTreeRequestV2, rc: RunContext, *, context: str, levels: list[str]
) -> None:
    if not roots:
        return
    full = render(
        STEP,
        context=context,
        skeleton=render_skeleton(roots),
        levels=" → ".join(levels) or "wie im Grundgerüst",
        depth_instruction=_depth_instruction(req),
        branch="",
    )
    prefix = full.rstrip() + "\n\n"
    outcomes = await asyncio.gather(*(_expand_one(main, prefix, req, rc) for main in roots), return_exceptions=True)

    deadline_hit = False
    for main, outcome in zip(roots, outcomes, strict=True):
        if isinstance(outcome, LLMStepError):
            if outcome.reason == "deadline":
                deadline_hit = True
            else:
                rc.warn("BRANCH_FAILED", f"Ast „{main.title}“ konnte nicht ausgearbeitet werden.", main.key, STEP)
        elif isinstance(outcome, BaseException):
            raise outcome
        else:
            if outcome.depth:
                rc.warn("SHAPE_DEPTH", f"Ast „{main.title}“ war zu tief und wurde gekürzt.", main.key, STEP)
            if outcome.width:
                rc.warn("SHAPE_WIDTH", f"Ast „{main.title}“ hatte zu viele Kinder; gekürzt.", main.key, STEP)
    if deadline_hit:
        rc.warn("DEADLINE_EXCEEDED", "Die Frist ist abgelaufen; einige Äste sind nicht ausgearbeitet.", step=STEP)
