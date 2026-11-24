from app.domain.shape_rules import (
    ShapePlan,
    check_descriptions,
    check_shape,
    dedup_titles,
    eliminate_generated_duplicates,
    extra_kind,
    normalize_shorttitles,
)
from app.domain.tree import Node
from app.schemas.common import ExtraTopic, NodeStatus, OriginType
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


def test_check_descriptions_skips_protected_or_unchanged_keys() -> None:
    nodes = [
        Node(key="k-locked", title="Optik"),
        Node(key="k-old", title="Mechanik", description="kurz"),
        Node(key="k-new", title="Farben", description="wort " * 60),
    ]
    assert check_descriptions(nodes, target_words=60, skip_keys={"k-locked", "k-old"}) == []


def test_unbalanced_branch_depths_are_reported() -> None:
    deep = n("k-a", "A", n("k-a1", "A1", n("k-a11", "A11"), n("k-a12", "A12")), n("k-a2", "A2"))
    shallow = n("k-b", "B")
    plan = ShapePlan.from_shape(Shape(depth=3, main_topics={"min": 2, "max": 6}, children={"min": 2, "max": 6}))
    assert "SHAPE_UNBALANCED" in codes(check_shape([deep, shallow], plan))

    balanced = [deep, n("k-b", "B", n("k-b1", "B1"), n("k-b2", "B2"))]
    assert "SHAPE_UNBALANCED" not in codes(check_shape(balanced, plan))


def test_eliminate_generated_duplicates_drops_leaf_when_parent_keeps_two_children() -> None:
    roots = [
        n("k-a", "Reflexion", n("k-a1", "Einfallswinkel"), n("k-a2", "Spiegelbild")),
        n("k-b", "Brechung", n("k-b1", "Einfallswinkel"), n("k-b2", "Brechungsgesetz"), n("k-b3", "Totalreflexion")),
    ]
    changed = eliminate_generated_duplicates(roots)
    assert changed == 1
    assert [c.title for c in roots[1].children] == ["Brechungsgesetz", "Totalreflexion"]
    assert dedup_titles(roots) == []


def test_eliminate_generated_duplicates_disambiguates_when_removal_would_leave_single_child() -> None:
    roots = [
        n("k-a", "Hohlspiegel", n("k-a1", "Bildgröße"), n("k-a2", "Brennpunkt")),
        n("k-b", "Sammellinse", n("k-b1", "Bildgröße"), n("k-b2", "Brennweite")),
    ]
    changed = eliminate_generated_duplicates(roots)
    assert changed == 1
    assert [c.title for c in roots[1].children] == ["Bildgröße (Sammellinse)", "Brennweite"]
    assert roots[1].children[0].shorttitle == ""
    assert dedup_titles(roots) == []


def test_eliminate_generated_duplicates_prefers_higher_level_and_preserves_caller_nodes() -> None:
    roots = [
        n("k-a", "Licht", n("k-a1", "Schatten", n("k-a11", "Farben"), n("k-a12", "Lichtstrahl")), n("k-a2", "Spiegel")),
        n("k-b", "Farben", n("k-b1", "Spektrum"), n("k-b2", "Farbmischung")),
        n("k-c", "Farben", generated=False),
    ]
    changed = eliminate_generated_duplicates(roots)
    assert changed == 1
    # Level-1 "Farben" wins over level-3 "Farben"; level-3 gets disambiguated because parent has only 2 kids.
    assert roots[1].title == "Farben"
    assert roots[0].children[0].children[0].title == "Farben (Schatten)"
    # Caller-owned folder node is never renamed or dropped.
    assert roots[2].title == "Farben"


def test_extra_kind_tolerates_ampersand_and_word_order() -> None:
    assert extra_kind("Methodik  &  Didaktik") == ExtraTopic.methodology
    assert extra_kind("Didaktik und Methodik") == ExtraTopic.methodology
    assert extra_kind(" allgemeines ") == ExtraTopic.general
    assert extra_kind("Didaktik") is None
