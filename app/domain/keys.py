"""Stable node keys: `k-<slug>`, unique within a tree, never changed once assigned."""

import re
import unicodedata

from app.domain.tree import Node, walk

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MAX_SLUG = 40


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower().translate(_UMLAUTS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _NON_ALNUM.sub("-", text).strip("-")[:_MAX_SLUG].strip("-")
    return slug or "knoten"


def make_key(title: str, taken: set[str]) -> str:
    base = f"k-{slugify(title)}"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    taken.add(key)
    return key


def assign_missing_keys(roots: list[Node]) -> None:
    """Give every node without a key (or with a duplicate key) a fresh one; existing unique keys stay."""
    taken: set[str] = set()
    pending: list[Node] = []
    for node, _, _ in walk(roots):
        if node.key and node.key not in taken:
            taken.add(node.key)
        else:
            pending.append(node)
    for node in pending:
        node.key = make_key(node.title, taken)
