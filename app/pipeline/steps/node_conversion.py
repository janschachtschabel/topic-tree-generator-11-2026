"""Shared conversion of LLM-shaped tree answers into working nodes, cut to the requested shape.

Used by `plan_structure` (`Cut`) and the `contents` use case (`BranchNode`, `to_nodes`).
"""

from pydantic import BaseModel, Field

from app.domain.tree import Node
from app.schemas.common import OriginType
from app.schemas.response_v2 import Origin


class BranchNode(BaseModel):
    title: str
    shorttitle: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    children: list["BranchNode"] = Field(default_factory=list)


class Cut:
    """Records whether the LLM answer exceeded the shape (too deep or too wide)."""

    def __init__(self) -> None:
        self.depth = False
        self.width = False


def to_nodes(
    items: list[BranchNode],
    levels_left: int,
    width: int,
    cut: Cut,
    origin: OriginType = OriginType.topic,
    child_width: int | None = None,
) -> list[Node]:
    """Convert LLM nodes into working nodes, cutting what exceeds the shape (recorded in `cut`).

    `width` limits this level; `child_width` (default: `width`) limits every level below it, so the top level
    can follow `shape.main_topics.max` while deeper levels follow `shape.children.max`.
    """
    if levels_left <= 0:
        cut.depth = cut.depth or bool(items)
        return []
    below = width if child_width is None else child_width
    cut.width = cut.width or len(items) > width
    return [
        Node(
            key=None,
            title=item.title.strip(),
            shorttitle=item.shorttitle.strip(),
            description=item.description.strip(),
            keywords=item.keywords,
            origin=Origin(type=origin),
            children=to_nodes(item.children, levels_left - 1, below, cut, origin),
        )
        for item in items[:width]
    ]
