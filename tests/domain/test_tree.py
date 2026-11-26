from app.domain.keys import assign_missing_keys, make_key, slugify
from app.domain.tree import Node, drop_untitled, find, from_tree_in, index, parent_of, path, walk
from app.schemas.request_v2 import TreeNodeIn


def sample() -> list[Node]:
    linsen = Node(key="k-linsen", title="Linsen")
    optik = Node(key="k-optik", title="Optik", children=[linsen, Node(key="k-spiegel", title="Spiegel")])
    return [optik, Node(key="k-mechanik", title="Mechanik")]


def test_slugify_handles_umlauts_and_punctuation() -> None:
    assert slugify("Wärme & Energie (Grundlagen)") == "waerme-energie-grundlagen"
    assert slugify("Größen") == "groessen"
    assert slugify("!!!") == "knoten"
    assert len(slugify("x" * 200)) <= 40


def test_make_key_avoids_collisions() -> None:
    taken: set[str] = set()
    assert make_key("Optik", taken) == "k-optik"
    assert make_key("Optik", taken) == "k-optik-2"
    assert make_key("Optik", taken) == "k-optik-3"
    assert taken == {"k-optik", "k-optik-2", "k-optik-3"}


def test_assign_missing_keys_keeps_existing_and_fixes_duplicates() -> None:
    roots = [Node(key="k-a", title="A"), Node(key=None, title="A"), Node(key="k-a", title="B")]
    assign_missing_keys(roots)
    assert [n.key for n in roots] == ["k-a", "k-a-2", "k-b"]


def test_walk_index_find_parent_and_path() -> None:
    roots = sample()
    assert [(n.key, depth) for n, _, depth in walk(roots)] == [
        ("k-optik", 1),
        ("k-linsen", 2),
        ("k-spiegel", 2),
        ("k-mechanik", 1),
    ]
    assert set(index(roots)) == {"k-optik", "k-linsen", "k-spiegel", "k-mechanik"}
    assert find(roots, "k-linsen").title == "Linsen"
    assert find(roots, "nope") is None
    assert parent_of(roots, "k-linsen").key == "k-optik"
    assert parent_of(roots, "k-optik") is None
    assert path(roots, "k-linsen") == ["Optik", "Linsen"]


def test_from_tree_in_reads_v2_and_legacy_nodes() -> None:
    nodes = [
        TreeNodeIn.model_validate(
            {
                "key": "k-optik",
                "title": "Optik",
                "shorttitle": "Optik",
                "origin": {"type": "folder", "path": "Optik"},
                "properties": {"cm:description": ["Licht"], "cclom:general_keyword": ["Licht"], "ccm:oeh_x": ["y"]},
                "contents": [{"id": "c1", "nodeId": "n1", "confidence": 0.9}],
                "subcollections": [{"title": "Linsen", "properties": {"cm_title": ["Linsen"]}}],
            }
        )
    ]
    roots = from_tree_in(nodes)
    optik = roots[0]
    assert (optik.key, optik.description, optik.keywords) == ("k-optik", "Licht", ["Licht"])
    assert optik.origin.path == "Optik"
    assert optik.contents[0].node_id == "n1"
    assert optik.properties.first("ccm:oeh_x") == "y"
    assert optik.children[0].key is None
    assert optik.children[0].shorttitle == "Linsen"


def test_invalid_origin_in_input_is_dropped() -> None:
    roots = from_tree_in([TreeNodeIn.model_validate({"title": "A", "origin": {"type": "nonsense"}})])
    assert roots[0].origin is None


def test_from_tree_in_preserves_zero_confidence() -> None:
    roots = from_tree_in([TreeNodeIn.model_validate({"title": "A", "contents": [{"id": "c1", "confidence": 0.0}]})])
    assert roots[0].contents[0].confidence == 0.0


def test_untitled_nodes_are_removed_and_their_children_take_their_place() -> None:
    blank = Node(key="k-b", title="  ", children=[Node(key="k-c1", title="C1"), Node(key="k-c2", title="C2")])
    roots = [Node(key="k-a", title="A"), blank, Node(key="k-z", title="Z")]
    removed = drop_untitled(roots)
    assert [n.key for n in removed] == ["k-b"]
    assert [n.key for n in roots] == ["k-a", "k-c1", "k-c2", "k-z"]


def test_nested_untitled_nodes_are_removed_too() -> None:
    roots = [Node(key="k-a", title="A", children=[Node(key="k-x", title=""), Node(key="k-y", title="Y")])]
    assert [n.key for n in drop_untitled(roots)] == ["k-x"]
    assert [c.key for c in roots[0].children] == ["k-y"]


def test_collapse_single_children_lifts_the_only_child_into_its_parent() -> None:
    from app.domain.tree import collapse_single_children
    from app.schemas.response_v2 import ContentRef

    grandchildren = [Node(key="g1", title="G1"), Node(key="g2", title="G2")]
    only = Node(key="c", title="C", contents=[ContentRef(id="x", confidence=0.8)], children=grandchildren)
    lone = Node(key="l", title="L", children=[Node(key="l1", title="L1")])
    pair = Node(key="p", title="P", children=[Node(key="p1", title="P1"), Node(key="p2", title="P2")])
    roots = [Node(key="a", title="A", children=[only]), lone, pair]

    assert collapse_single_children(roots) == 2
    assert [n.key for n in roots[0].children] == ["g1", "g2"]
    assert [c.id for c in roots[0].contents] == ["x"]
    assert roots[1].children == []
    assert [n.key for n in roots[2].children] == ["p1", "p2"]


def test_collapse_single_children_repeats_down_a_chain() -> None:
    from app.domain.tree import collapse_single_children

    chain = Node(key="a", title="A", children=[Node(key="b", title="B", children=[Node(key="c", title="C")])])
    roots = [chain]
    assert collapse_single_children(roots) == 2
    assert roots[0].children == []
