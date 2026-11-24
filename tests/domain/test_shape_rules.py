from app.domain.shape_rules import (
    ShapePlan,
    check_descriptions,
    check_shape,
    dedup_titles,
    normalize_shorttitles,
)
from app.domain.tree import Node
from app.schemas.common import NodeStatus, OriginType
from app.schemas.request_v2 import Shape
from app.schemas.response_v2 import Origin


def n(key: str, title: str, *children: Node, generated: bool = True) -> Node:
    origin = Origin(type=OriginType.topic) if generated else Origin(type=OriginType.folder, path=title)
    return Node(key=key, title=title, status=NodeStatus.new, origin=origin, children=list(children))


def codes(warnings) -> list[str]:
    return [w.code for w in warnings]


def test_shape_plan_from_v2_shape_fills_every_level() -> None:
    plan = ShapePlan.from_shape(Shape(depth=3))
    assert plan.depth == 3
    assert (plan.main.min, plan.main.max) == (6, 12)
    assert [(r.min, r.max) for r in plan.children_per_level] == [(3, 8), (3, 8)]


def test_single_child_is_reported() -> None:
    roots = [n("k-a", "A", n("k-b", "B"))]
    warnings = check_shape(roots, ShapePlan.from_shape(Shape(depth=2, main_topics={"min": 1, "max": 5})))
    assert codes(warnings) == ["SHAPE_SINGLE_CHILD"]
    assert warnings[0].key == "k-a"


def test_depth_and_main_width_are_reported() -> None:
    roots = [n("k-a", "A", n("k-b", "B", n("k-c", "C"), n("k-d", "D")), n("k-e", "E"))]
    warnings = check_shape(roots, ShapePlan.from_shape(Shape(depth=1, main_topics={"min": 2, "max": 5})))
    assert set(codes(warnings)) == {"SHAPE_DEPTH", "SHAPE_WIDTH"}


def test_extra_topics_do_not_count_against_main_width() -> None:
    roots = [n(f"k-{i}", str(i)) for i in range(4)]
    plan = ShapePlan.from_shape(Shape(depth=1, main_topics={"min": 3, "max": 3}))
    assert codes(check_shape(roots, plan, extra=1)) == []


def test_too_many_children_are_reported() -> None:
    kids = [n(f"k-c{i}", f"C{i}") for i in range(5)]
    roots = [n("k-a", "A", *kids)]
    plan = ShapePlan.from_shape(Shape(depth=2, main_topics={"min": 1, "max": 3}, children={"min": 2, "max": 4}))
    assert codes(check_shape(roots, plan)) == ["SHAPE_WIDTH"]


def test_shorttitles_are_cleaned_shortened_and_unique_among_siblings() -> None:
    a = Node(key="k-a", title="Elektrische Energieübertragung & Netze")
    b = Node(key="k-b", title="Elektrische Energieübertragung im Haushalt")
    c = Node(key="k-c", title="Optik", shorttitle="Optik/Licht")
    normalize_shorttitles([a, b, c])
    assert a.shorttitle == "Elektrische"
    assert b.shorttitle != a.shorttitle and len(b.shorttitle) <= 20
    assert c.shorttitle == "Optik Licht"
    for node in (a, b, c):
        assert len(node.shorttitle) <= 20


def test_duplicate_generated_siblings_are_merged() -> None:
    a = n("k-a", "Linsen", n("k-x", "X"))
    b = n("k-b", "linsen", n("k-y", "Y"))
    roots = [a, b]
    warnings = dedup_titles(roots)
    assert [r.key for r in roots] == ["k-a"]
    assert [c.key for c in a.children] == ["k-x", "k-y"]
    assert codes(warnings) == ["DUPLICATE_TITLE"]


def test_duplicates_from_input_are_only_reported() -> None:
    roots = [n("k-a", "Linsen", generated=False), n("k-b", "Linsen", generated=False)]
    warnings = dedup_titles(roots)
    assert len(roots) == 2
    assert codes(warnings) == ["DUPLICATE_TITLE"]


def test_duplicates_in_different_branches_are_reported() -> None:
    roots = [n("k-a", "A", n("k-x", "Linsen"), n("k-z", "Z")), n("k-b", "B", n("k-y", "Linsen"), n("k-w", "W"))]
    assert codes(dedup_titles(roots)) == ["DUPLICATE_TITLE"]
    assert len(roots[0].children) == 2


def test_description_length_outliers_are_summarized_in_one_warning() -> None:
    nodes = [
        Node(key="k-a", title="A", description="wort " * 60),
        Node(key="k-b", title="B", description="wort " * 200),
        Node(key="k-c", title="C", description="kurz"),
    ]
    warnings = check_descriptions(nodes, target_words=60)
    assert codes(warnings) == ["DESCRIPTION_LENGTH"]
    assert "2" in warnings[0].message


def test_missing_descriptions_are_reported() -> None:
    warnings = check_descriptions([Node(key="k-a", title="A")], target_words=60)
    assert codes(warnings) == ["DESCRIPTION_MISSING"]
