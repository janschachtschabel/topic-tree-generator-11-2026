from app.domain.ops import apply_changes
from app.domain.tree import Node, find, index, parent_of
from app.schemas.common import ChangeSource, OriginType
from app.schemas.request_v2 import Change
from app.schemas.response_v2 import ContentRef


def tree() -> list[Node]:
    akustik = Node(key="k-akustik", title="Akustik", contents=[ContentRef(id="c1")])
    linsen = Node(key="k-linsen", title="Linsen", contents=[ContentRef(id="c2", nodeId="n2")])
    optik = Node(key="k-optik", title="Optik", children=[linsen, Node(key="k-spiegel", title="Spiegel")])
    mechanik = Node(key="k-mechanik", title="Mechanik", children=[Node(key="k-kraft", title="Kraft")])
    return [optik, mechanik, akustik]


def ch(**kw) -> Change:
    return Change.model_validate(kw)


def run(changes: list[Change], locked: set[str] | None = None, roots: list[Node] | None = None):
    roots = roots if roots is not None else tree()
    result = apply_changes(roots, changes, locked or set(), ChangeSource.feedback_changes)
    return roots, result


def test_add_at_root_and_under_parent() -> None:
    roots, result = run([ch(op="add", parent=None, title="Farben"), ch(op="add", parent="k-optik", title="Prismen")])
    assert roots[-1].title == "Farben" and roots[-1].key == "k-farben"
    assert roots[-1].origin.type == OriginType.feedback
    assert find(roots, "k-optik").children[-1].title == "Prismen"
    assert [r.op for r in result.applied] == ["add", "add"]
    assert result.applied[0].key == "k-farben"
    assert result.applied[0].source == ChangeSource.feedback_changes


def test_remove_releases_contents_of_the_whole_branch() -> None:
    roots, result = run([ch(op="remove", key="k-optik")])
    assert find(roots, "k-optik") is None and find(roots, "k-linsen") is None
    assert [c.id for c in result.released_contents] == ["c2"]


def test_rename_and_edit() -> None:
    roots, _ = run(
        [
            ch(op="rename", key="k-spiegel", title="Spiegelungen"),
            ch(op="edit", key="k-kraft", properties={"cm:description": ["Neu"], "cclom:general_keyword": ["F"]}),
        ]
    )
    assert find(roots, "k-spiegel").title == "Spiegelungen"
    kraft = find(roots, "k-kraft")
    assert (kraft.description, kraft.keywords) == ("Neu", ["F"])


def test_move_keeps_children_and_key() -> None:
    roots, _ = run([ch(op="move", key="k-akustik", to="k-mechanik")])
    assert parent_of(roots, "k-akustik").key == "k-mechanik"
    assert [r.key for r in roots] == ["k-optik", "k-mechanik"]


def test_move_without_target_lifts_the_node_to_the_top_level() -> None:
    # Decided with Jan (audit 2026-11-25, open point 3): `to` omitted or null means the top level.
    roots, result = run([ch(op="move", key="k-linsen"), ch(op="move", key="k-spiegel", to=None)])
    assert [r.key for r in roots] == ["k-optik", "k-mechanik", "k-akustik", "k-linsen", "k-spiegel"]
    assert find(roots, "k-optik").children == []
    assert [(r.op, r.key, r.to) for r in result.applied] == [("move", "k-linsen", None), ("move", "k-spiegel", None)]


def test_move_of_a_top_level_node_to_the_top_level_changes_nothing() -> None:
    roots, result = run([ch(op="move", key="k-optik")])
    assert [r.key for r in roots] == ["k-optik", "k-mechanik", "k-akustik"]
    assert result.applied == [] and result.rejected == []


def test_move_into_own_descendant_is_rejected() -> None:
    roots, result = run([ch(op="move", key="k-optik", to="k-linsen")])
    assert parent_of(roots, "k-optik") is None
    assert [w.code for w in result.rejected] == ["CHANGE_REJECTED"]


def test_merge_combines_children_and_contents_under_the_first_key() -> None:
    roots, result = run([ch(op="merge", keys=["k-optik", "k-akustik"], title="Optik und Akustik")])
    merged = find(roots, "k-optik")
    assert merged.title == "Optik und Akustik"
    assert find(roots, "k-akustik") is None
    assert [c.id for c in merged.contents] == ["c1"]
    assert result.applied[0].keys == ["k-optik", "k-akustik"]


def test_split_is_collected_for_the_llm_step() -> None:
    _, result = run([ch(op="split", key="k-optik", hint="geometrische und physiologische Optik")])
    assert [c.key for c in result.pending_splits] == ["k-optik"]
    assert result.applied == []


def test_unknown_keys_are_rejected() -> None:
    _, result = run(
        [
            ch(op="remove", key="k-nope"),
            ch(op="move", key="k-optik", to="k-nope"),
            ch(op="add", parent="k-x", title="Y"),
        ]
    )
    assert [w.code for w in result.rejected] == ["CHANGE_REJECTED"] * 3
    assert result.applied == []


def test_locked_nodes_and_their_descendants_are_protected() -> None:
    roots, result = run(
        [
            ch(op="rename", key="k-linsen", title="X"),
            ch(op="add", parent="k-optik", title="Y"),
            ch(op="move", key="k-akustik", to="k-spiegel"),
            ch(op="remove", key="k-optik"),
            ch(op="merge", keys=["k-mechanik", "k-optik"], title="Z"),
        ],
        locked={"k-optik"},
    )
    assert len(result.rejected) == 5
    assert set(index(roots)) == set(index(tree()))
    assert find(roots, "k-linsen").title == "Linsen"


def test_changes_apply_in_order() -> None:
    roots, _ = run([ch(op="add", parent=None, title="Farben"), ch(op="move", key="k-akustik", to="k-farben")])
    assert parent_of(roots, "k-akustik").key == "k-farben"


def test_merge_with_duplicate_keys_is_rejected_without_deleting_node() -> None:
    roots, result = run([ch(op="merge", keys=["k-optik", "k-optik"], title="Optik")])
    assert find(roots, "k-optik") is not None
    assert [c.key for c in find(roots, "k-optik").children] == ["k-linsen", "k-spiegel"]
    assert [w.code for w in result.rejected] == ["CHANGE_REJECTED"]
    assert result.applied == []


def test_merge_deduplicates_shared_contents_keeping_max_confidence() -> None:
    roots = tree()
    find(roots, "k-optik").contents = [ContentRef(id="c1", confidence=0.6)]
    find(roots, "k-akustik").contents = [ContentRef(id="c1", confidence=0.9), ContentRef(id="c3", confidence=0.8)]
    roots, _ = run([ch(op="merge", keys=["k-optik", "k-akustik"], title="Optik und Akustik")], roots=roots)
    merged = find(roots, "k-optik")
    assert [(c.id, c.confidence) for c in merged.contents] == [("c1", 0.9), ("c3", 0.8)]


def test_no_op_rename_and_move_are_not_recorded() -> None:
    roots, result = run(
        [ch(op="rename", key="k-linsen", title=" Linsen "), ch(op="move", key="k-linsen", to="k-optik")]
    )
    assert result.applied == [] and result.rejected == []
    assert [c.key for c in find(roots, "k-optik").children] == ["k-linsen", "k-spiegel"]


def test_nested_add_resolves_newly_added_parent_by_title_or_key() -> None:
    roots, result = run(
        [
            ch(op="add", parent=None, title="Farben und Spektrum"),
            ch(op="add", parent="Farben und Spektrum", title="Spektralfarben"),
            ch(op="add", parent="k-farben-und-spektrum", title="Farbmischung"),
        ]
    )
    assert result.rejected == []
    farben = find(roots, "k-farben-und-spektrum")
    assert farben is not None
    assert [c.title for c in farben.children] == ["Spektralfarben", "Farbmischung"]
    assert result.applied[1].parent == "k-farben-und-spektrum"
