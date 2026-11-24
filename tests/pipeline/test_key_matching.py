from app.pipeline.key_matching import match_keys

BATCH = ["k-lichtquellen", "k-schatten-und-finsternisse", "k-reflexion"]


def test_exact_and_normalized_keys_match() -> None:
    assert match_keys([" K-Reflexion. ", "lichtquellen"], BATCH) == {0: "k-reflexion", 1: "k-lichtquellen"}


def test_misspelled_key_is_repaired_by_similarity() -> None:
    assert match_keys(["k-schatten-und-finsterniss"], BATCH) == {0: "k-schatten-und-finsternisse"}


def test_single_leftover_pairs_by_elimination() -> None:
    answers = ["k-lichtquellen", "k-reflexion", "k-etwas-ganz-anderes"]
    assert match_keys(answers, BATCH)[2] == "k-schatten-und-finsternisse"


def test_keys_of_other_tree_nodes_are_never_reassigned() -> None:
    answers = ["k-lichtquellen", "k-reflexion", "k-schatten"]
    assert 2 not in match_keys(answers, BATCH, elsewhere={"k-schatten"})


def test_dissimilar_keys_stay_unmatched_when_several_are_missing() -> None:
    assert match_keys(["k-xyz"], BATCH) == {}


def test_each_batch_key_is_used_once() -> None:
    assert match_keys(["k-reflexion", "k-reflexion"], BATCH) == {0: "k-reflexion"}


def test_without_elimination_keys_repeat_and_leftovers_stay_unmatched() -> None:
    tree = ["k-optik", "k-linsen"]
    assert match_keys(["k-optik", "K-Optik", "k-zzz"], tree, elimination=False) == {0: "k-optik", 1: "k-optik"}
