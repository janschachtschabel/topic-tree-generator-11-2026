"""Boundary-safe text truncation for prompt excerpts."""

import re

_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "abb",
        "abs",
        "allg",
        "bd",
        "bzw",
        "ca",
        "dr",
        "etc",
        "ggf",
        "hrsg",
        "inkl",
        "jh",
        "kap",
        "mio",
        "mrd",
        "nr",
        "prof",
        "tab",
        "usw",
        "vgl",
    }
)
_SENTENCE_END = re.compile(r"([.!?])(?=\s|$)")
_WORD_BEFORE = re.compile(r"([^\W\d_]+|\d+)$")


def _is_sentence_boundary(window: str, dot_index: int, char: str) -> bool:
    if char != ".":
        return True
    match = _WORD_BEFORE.search(window[:dot_index])
    if not match:
        return True
    token = match.group(1)
    if token.isdigit() or len(token) == 1:
        return False
    return token.casefold() not in _ABBREVIATIONS


def truncate_sentences(text: str, max_chars: int) -> str:
    """Shorten `text` to at most `max_chars`, preferring sentence boundaries, then word boundaries."""
    if max_chars <= 0:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    # Probe one char past `max_chars` so lookahead sees real continuation (no false `$` on mid-token dots).
    probe = cleaned[: max_chars + 1]
    min_keep = max(1, max_chars // 2)

    best_sentence = -1
    for match in _SENTENCE_END.finditer(probe):
        end = match.end()
        if min_keep <= end <= max_chars and _is_sentence_boundary(probe, match.start(), match.group(1)):
            best_sentence = end
    if best_sentence != -1:
        return probe[:best_sentence].rstrip()

    space = next((i for i in range(len(probe) - 1, -1, -1) if probe[i].isspace()), -1)
    if space >= min_keep:
        return probe[:space].rstrip()
    return cleaned[:max_chars].rstrip()
