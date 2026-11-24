import copy

from app.domain.diff import mark_status_against_folders, mark_status_against_previous
from app.domain.tree import Node, find
from app.schemas.common import NodeStatus, OriginType
from app.schemas.response_v2 import Origin


def old_tree() -> list[Node]:
    return [
        Node(key="k-optik", title="Optik", description="Licht", children=[Node(key="k-linsen", title="Linsen")]),
        Node(key="k-mechanik", title="Mechanik", children=[Node(key="k-spiegel", title="Spiegel")]),
    ]


def test_status_against_previous_version() -> None:
    old = old_tree()
    new = copy.deepcopy(old)
    find(new, "k-optik").description = "Licht und Farben"
    spiegel = find(new, "k-mechanik").children.pop()
    find(new, "k-optik").children.append(spiegel)
    new.append(Node(key="k-farben", title="Farben"))
    new.append(Node(key="k-prisma", title="Prisma", status=NodeStatus.suggested))
    mark_status_against_previous(new, old)
    assert find(new, "k-optik").status == NodeStatus.changed
    assert find(new, "k-linsen").status == NodeStatus.unchanged
    assert find(new, "k-mechanik").status == NodeStatus.unchanged
    assert find(new, "k-spiegel").status == NodeStatus.moved
    assert find(new, "k-farben").status == NodeStatus.new
    assert find(new, "k-prisma").status == NodeStatus.suggested


def test_renamed_node_is_changed() -> None:
    old = old_tree()
    new = copy.deepcopy(old)
    find(new, "k-linsen").title = "Linsensysteme"
    mark_status_against_previous(new, old)
    assert find(new, "k-linsen").status == NodeStatus.changed


def folder_node(key: str, title: str, source_path: str, *children: Node) -> Node:
    return Node(key=key, title=title, origin=Origin(type=OriginType.folder, path=source_path), children=list(children))


def test_status_against_folders() -> None:
    roots = [
        folder_node(
            "k-optik",
            "Optik",
            "Optik",
            folder_node("k-linsen", "Linsen", "Optik/Linsen"),
            folder_node("k-spiegel", "Spiegel", "Neuer Ordner (2)"),
        ),
        folder_node("k-akustik", "Akustik", "Schall"),
        Node(key="k-farben", title="Farben", origin=Origin(type=OriginType.topic)),
    ]
    mark_status_against_folders(roots)
    assert find(roots, "k-optik").status == NodeStatus.unchanged
    assert find(roots, "k-linsen").status == NodeStatus.unchanged
    assert find(roots, "k-spiegel").status == NodeStatus.moved
    assert find(roots, "k-akustik").status == NodeStatus.changed
    assert find(roots, "k-farben").status == NodeStatus.new


def test_without_reference_everything_is_new_except_suggestions() -> None:
    roots = [Node(key="k-a", title="A"), Node(key="k-b", title="B", status=NodeStatus.suggested)]
    mark_status_against_previous(roots, None)
    assert [r.status for r in roots] == [NodeStatus.new, NodeStatus.suggested]


def test_renaming_a_folder_does_not_mark_its_children_as_moved() -> None:
    roots = [folder_node("k-akustik", "Akustik", "Schall", folder_node("k-echo", "Echo", "Schall/Echo"))]
    mark_status_against_folders(roots)
    assert find(roots, "k-akustik").status == NodeStatus.changed
    assert find(roots, "k-echo").status == NodeStatus.unchanged


def test_folder_node_under_a_new_node_counts_as_moved() -> None:
    roots = [Node(key="k-neu", title="Neu", children=[folder_node("k-echo", "Echo", "Echo")])]
    mark_status_against_folders(roots)
    assert find(roots, "k-echo").status == NodeStatus.moved
