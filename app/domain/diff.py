"""Node status (Spec: new, unchanged, changed, moved, suggested) against the previous version or the folders."""

from app.domain.tree import Node, index, walk
from app.schemas.common import NodeStatus, OriginType

FOLDER_SEPARATOR = "/"


def _parent_keys(roots: list[Node]) -> dict[str, str | None]:
    return {node.key: (parent.key if parent else None) for node, parent, _ in walk(roots)}


def _content_changed(new: Node, old: Node) -> bool:
    return (new.title, new.description, new.keywords) != (old.title, old.description, old.keywords)


def mark_status_against_previous(roots: list[Node], previous: list[Node] | None) -> None:
    old_nodes = index(previous or [])
    old_parents = _parent_keys(previous or [])
    new_parents = _parent_keys(roots)
    for node, _, _ in walk(roots):
        if node.status == NodeStatus.suggested:
            continue
        old = old_nodes.get(node.key)
        if old is None:
            node.status = NodeStatus.new
        elif old_parents.get(node.key) != new_parents.get(node.key):
            node.status = NodeStatus.moved
        elif _content_changed(node, old):
            node.status = NodeStatus.changed
        else:
            node.status = NodeStatus.unchanged


def _folder_path(node: Node) -> list[str] | None:
    if node.origin is None or node.origin.type != OriginType.folder or not node.origin.path:
        return None
    return node.origin.path.split(FOLDER_SEPARATOR)


def mark_status_against_folders(roots: list[Node]) -> None:
    """Compare each node taken from a folder with its source folder (`origin.path`).

    A node counts as moved when its source folder was not inside the source folder of its current parent, so
    renaming a folder marks only that folder as changed, not its subfolders.
    """

    def visit(nodes: list[Node], parent_source: list[str] | None) -> None:
        for node in nodes:
            source = _folder_path(node)
            if node.status != NodeStatus.suggested:
                if source is None:
                    node.status = NodeStatus.new
                elif source[:-1] != parent_source:
                    node.status = NodeStatus.moved
                elif source[-1] != node.title:
                    node.status = NodeStatus.changed
                else:
                    node.status = NodeStatus.unchanged
            visit(node.children, source)

    visit(roots, [])
