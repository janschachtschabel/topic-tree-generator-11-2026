from app.pipeline.steps.node_conversion import BranchNode, Cut, to_nodes
from app.schemas.common import OriginType


def branch(title: str, children: list[BranchNode] | None = None) -> BranchNode:
    return BranchNode(title=f" {title} ", shorttitle=title[:5], description=" D ", children=children or [])


def test_converts_and_strips_with_origin() -> None:
    nodes = to_nodes([branch("A", [branch("A1")])], 2, 5, Cut(), OriginType.cluster)
    assert nodes[0].title == "A" and nodes[0].description == "D"
    assert nodes[0].origin.type == OriginType.cluster
    assert nodes[0].children[0].origin.type == OriginType.cluster


def test_cuts_depth_and_records_it() -> None:
    cut = Cut()
    nodes = to_nodes([branch("A", [branch("A1", [branch("A11")])])], 2, 5, cut)
    assert nodes[0].children[0].children == []
    assert cut.depth and not cut.width


def test_child_width_limits_lower_levels_only() -> None:
    cut = Cut()
    items = [branch(f"M{i}", [branch(f"C{i}.{j}") for j in range(4)]) for i in range(3)]
    nodes = to_nodes(items, 2, 3, cut, child_width=2)
    assert len(nodes) == 3
    assert all(len(n.children) == 2 for n in nodes)
    assert cut.width
