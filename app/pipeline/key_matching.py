"""Deterministic repair of node keys the model echoes back (no LLM involved).

Batch steps send nodes with their keys and expect the same keys back. Models sometimes alter them slightly. In
order of reliability: normalized exact match, then high string similarity, then elimination when exactly one key
and one answer are left over. Keys of other tree nodes (the model also answered for a neighbour) are never
reassigned, and every batch key is used at most once.
"""

from difflib import SequenceMatcher

_SIMILARITY = 0.85


def norm_key(key: str | None) -> str:
    """Tolerate case, whitespace, trailing punctuation and a missing `k-` prefix."""
    text = (key or "").strip().casefold().rstrip(".,;:")
    return text if text.startswith("k-") else f"k-{text}"


def match_keys(
    answers: list[str], batch: list[str], elsewhere: set[str] | None = None, *, elimination: bool = True
) -> dict[int, str]:
    """Map answer positions to batch keys; answers that cannot be matched safely are left out.

    With `elimination=False` (choices among the whole tree, e.g. content assignment) a key may be chosen by
    several answers and no leftover pairing happens.
    """
    by_norm = {norm_key(key): key for key in batch}
    foreign = {norm_key(key) for key in elsewhere or set()} - set(by_norm)
    matched: dict[int, str] = {}
    for i, answer in enumerate(answers):
        key = by_norm.get(norm_key(answer))
        if key is not None and (not elimination or key not in matched.values()):
            matched[i] = key

    def open_answers() -> list[int]:
        return [i for i, a in enumerate(answers) if i not in matched and norm_key(a) not in foreign]

    def open_keys() -> list[str]:
        return [key for key in batch if not elimination or key not in matched.values()]

    for i in open_answers():
        scored = sorted(
            ((SequenceMatcher(None, norm_key(answers[i]), norm_key(k)).ratio(), k) for k in open_keys()), reverse=True
        )
        if scored and scored[0][0] >= _SIMILARITY and (len(scored) == 1 or scored[1][0] < scored[0][0]):
            matched[i] = scored[0][1]
    rest_answers, rest_keys = open_answers(), open_keys()
    if elimination and len(rest_answers) == 1 and len(rest_keys) == 1:
        matched[rest_answers[0]] = rest_keys[0]
    return matched
