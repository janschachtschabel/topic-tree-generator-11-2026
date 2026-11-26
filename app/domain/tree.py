"""The working tree used by every pipeline step. Mutable on purpose; serialization happens in `finalize`."""

from collections.abc import Iterator
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas.common import NodeStatus
from app.schemas.properties import Properties
from app.schemas.request_v2 import TreeNodeIn
from app.schemas.response_v2 import ContentRef, Origin


@dataclass
class Node:
    key: str | None
    title: str
    shorttitle: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    properties: Properties = field(default_factory=Properties)
    status: NodeStatus | None = None
    origin: Origin | None = None
    confidence: float | None = None
    contents: list[ContentRef] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)


def walk(roots: list[Node]) -> Iterator[tuple[Node, Node | None, int]]:
    """Depth-first, pre-order: (node, parent, depth) with depth 1 for the top level."""
    stack: list[tuple[Node, Node | None, int]] = [(n, None, 1) for n in reversed(roots)]
    while stack:
        node, parent, depth = stack.pop()
        yield node, parent, depth
        stack.extend((child, node, depth + 1) for child in reversed(node.children))


def index(roots: list[Node]) -> dict[str, Node]:
    return {node.key: node for node, _, _ in walk(roots) if node.key}


def find(roots: list[Node], key: str) -> Node | None:
    return index(roots).get(key)


def parent_of(roots: list[Node], key: str) -> Node | None:
    for node, parent, _ in walk(roots):
        if node.key == key:
            return parent
    return None


def path(roots: list[Node], key: str) -> list[str]:
    def search(nodes: list[Node], trail: list[str]) -> list[str] | None:
        for node in nodes:
            here = [*trail, node.title]
            if node.key == key:
                return here
            found = search(node.children, here)
            if found:
                return found
        return None

    return search(roots, []) or []


def _origin(data: dict | None) -> Origin | None:
    if not data:
        return None
    try:
        return Origin.model_validate(data)
    except ValidationError:
        return None


def from_tree_in(nodes: list[TreeNodeIn]) -> list[Node]:
    """Convert an earlier answer (v2 or legacy) into working nodes. Missing keys stay None (see keys.py)."""
    result: list[Node] = []
    for item in nodes:
        props = item.properties
        result.append(
            Node(
                key=item.key,
                title=item.title,
                shorttitle=item.shorttitle or props.first("ccm:collectionshorttitle") or item.title,
                description=props.first("cm:description") or "",
                keywords=props.values("cclom:general_keyword"),
                properties=props,
                origin=_origin(item.origin),
                contents=[
                    ContentRef(id=c.id, nodeId=c.node_id, confidence=1.0 if c.confidence is None else c.confidence)
                    for c in item.contents
                ],
                children=from_tree_in(item.subcollections),
            )
        )
    return result


def drop_untitled(roots: list[Node]) -> list[Node]:
    """Remove nodes whose title is empty or blank; their children take their place. Returns the removed nodes.

    A collection without a name is unusable in edu-sharing, so such nodes never reach the answer.
    """
    removed: list[Node] = []

    def clean(nodes: list[Node]) -> list[Node]:
        result: list[Node] = []
        for node in nodes:
            node.children = clean(node.children)
            if node.title.strip():
                result.append(node)
            else:
                removed.append(node)
                result.extend(node.children)
        return result

    roots[:] = clean(roots)
    return removed


def collapse_single_children(roots: list[Node]) -> int:
    """A node never has exactly one child: the only child dissolves into its parent, which takes over the child's
    contents and children. Returns the number of dissolved nodes."""
    dissolved = 0
    for node, _, _ in walk(roots):
        while len(node.children) == 1:
            only = node.children[0]
            known = {ref.id for ref in node.contents}
            node.contents.extend(ref for ref in only.contents if ref.id not in known)
            node.children = only.children
            dissolved += 1
    return dissolved
