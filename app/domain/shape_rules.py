"""Deterministic checks and normalizations of tree shape (design rules from the "Themenbäume" overview).

Checks only report (warnings); the only automatic repairs are short-title normalization and merging duplicate
sibling nodes that the LLM invented. Structure taken from the caller's input is never changed here.
"""

import re
from collections import Counter, deque
from dataclasses import dataclass

from app.domain.tree import Node, walk
from app.schemas.common import ExtraTopic, OriginType
from app.schemas.request_v2 import ChildRange, MainRange, Shape
from app.schemas.response_v2 import ServiceWarning

SHORTTITLE_MAX = 20
EXTRA_TITLES = {ExtraTopic.general: "Allgemeines", ExtraTopic.methodology: "Methodik und Didaktik"}
_NOT_WORD = re.compile(r"[^\w ]|_")
_SPACES = re.compile(r"\s+")
_GENERATED = {OriginType.topic, OriginType.cluster}


@dataclass(frozen=True)
class ShapePlan:
    depth: int
    main: MainRange
    children_per_level: list[ChildRange]

    @classmethod
    def from_shape(cls, shape: Shape) -> "ShapePlan":
        return cls(shape.depth, shape.main_topics, [shape.children] * max(shape.depth - 1, 0))

    def children_at(self, depth: int) -> ChildRange | None:
        """Range for the children of a node at `depth` (1 = top level)."""
        index = depth - 1
        return self.children_per_level[index] if 0 <= index < len(self.children_per_level) else None


def _warning(code: str, message: str, key: str | None = None) -> ServiceWarning:
    return ServiceWarning(code=code, message=message, key=key, step="shape_rules")


def check_shape(roots: list[Node], plan: ShapePlan, extra: int = 0) -> list[ServiceWarning]:
    warnings: list[ServiceWarning] = []
    regular = len(roots) - extra
    if not plan.main.min <= regular <= plan.main.max:
        warnings.append(
            _warning("SHAPE_WIDTH", f"Hauptebene hat {regular} Knoten, vorgesehen {plan.main.min}–{plan.main.max}.")
        )
    deepest = max((depth for _, _, depth in walk(roots)), default=0)
    if deepest > plan.depth:
        warnings.append(_warning("SHAPE_DEPTH", f"Baum hat {deepest} Ebenen, vorgesehen {plan.depth}."))
    if len(roots) >= 2 and deepest >= 2:
        branch_depths = [max(depth for _, _, depth in walk([root])) for root in roots]
        lo, hi = min(branch_depths), max(branch_depths)
        if hi - lo > 1:
            warnings.append(
                _warning(
                    "SHAPE_UNBALANCED",
                    f"Äste sind unterschiedlich tief (Tiefe {lo} bis {hi}; Unterschied höchstens 1 empfohlen).",
                )
            )
    for node, _, depth in walk(roots):
        if len(node.children) == 1:
            warnings.append(_warning("SHAPE_SINGLE_CHILD", f"„{node.title}“ hat genau ein Kind.", node.key))
        allowed = plan.children_at(depth)
        if allowed and len(node.children) > allowed.max:
            warnings.append(
                _warning(
                    "SHAPE_WIDTH", f"„{node.title}“ hat {len(node.children)} Kinder, höchstens {allowed.max}.", node.key
                )
            )
    return warnings


def _clean_shorttitle(text: str) -> str:
    text = _SPACES.sub(" ", _NOT_WORD.sub(" ", text)).strip()
    if len(text) <= SHORTTITLE_MAX:
        return text
    words, result = text.split(" "), ""
    for word in words:
        candidate = f"{result} {word}".strip()
        if len(candidate) > SHORTTITLE_MAX:
            break
        result = candidate
    return result or text[:SHORTTITLE_MAX]


def _unique(text: str, taken: set[str]) -> str:
    candidate, n = text, 2
    while candidate.casefold() in taken:
        suffix = f" {n}"
        candidate = text[: SHORTTITLE_MAX - len(suffix)].rstrip() + suffix
        n += 1
    taken.add(candidate.casefold())
    return candidate


def normalize_shorttitles(nodes: list[Node]) -> None:
    """At most 20 characters, letters/digits/spaces only, unique among siblings; applied recursively."""
    taken: set[str] = set()
    for node in nodes:
        node.shorttitle = _unique(_clean_shorttitle(node.shorttitle or node.title) or "Thema", taken)
        normalize_shorttitles(node.children)


def _merge_generated_siblings(nodes: list[Node], warnings: list[ServiceWarning]) -> None:
    kept: dict[str, Node] = {}
    result: list[Node] = []
    for node in nodes:
        title = node.title.casefold()
        first = kept.get(title)
        if first is None:
            kept[title] = node
            result.append(node)
            continue
        if _is_generated(first) and _is_generated(node):
            first.children.extend(node.children)
            first.contents.extend(node.contents)
            warnings.append(_warning("DUPLICATE_TITLE", f"Doppelte „{node.title}“ zusammengelegt.", first.key))
        else:
            result.append(node)
    nodes[:] = result
    for node in nodes:
        _merge_generated_siblings(node.children, warnings)


def _is_generated(node: Node) -> bool:
    return node.origin is not None and node.origin.type in _GENERATED


def _disambiguate_title(node: Node, parent: Node | None, seen: set[str]) -> str:
    base = node.title.strip()
    parent_title = parent.title.strip() if parent is not None else ""
    if parent_title and parent_title.casefold() not in base.casefold():
        candidate = f"{base} ({parent_title})"
        if candidate.casefold() not in seen:
            return candidate
        base = candidate
    n = 2
    while f"{base} {n}".casefold() in seen:
        n += 1
    return f"{base} {n}"


def eliminate_generated_duplicates(roots: list[Node]) -> int:
    """Remove or disambiguate duplicate titles among generated nodes across the whole tree.

    Traverses breadth-first so higher-level concepts keep their titles. Leaves are dropped when their parent
    retains at least two children and no contents are attached; otherwise the duplicate is disambiguated with
    parent context. Caller-owned nodes are never modified. Returns the number of resolved duplicates.
    """
    before = sum(1 for _ in walk(roots))
    _merge_generated_siblings(roots, [])
    changed = before - sum(1 for _ in walk(roots))

    seen: set[str] = set()
    queue: deque[tuple[Node, Node | None]] = deque((root, None) for root in roots)
    while queue:
        node, parent = queue.popleft()
        key = node.title.strip().casefold()
        if key not in seen:
            seen.add(key)
            for child in node.children:
                queue.append((child, node))
            continue
        if not _is_generated(node):
            for child in node.children:
                queue.append((child, node))
            continue
        if not node.children and not node.contents and parent is not None and len(parent.children) >= 3:
            parent.children.remove(node)
            changed += 1
            continue
        node.title = _disambiguate_title(node, parent, seen)
        node.shorttitle = ""
        seen.add(node.title.casefold())
        changed += 1
        for child in node.children:
            queue.append((child, node))
    return changed


def dedup_titles(roots: list[Node]) -> list[ServiceWarning]:
    warnings: list[ServiceWarning] = []
    _merge_generated_siblings(roots, warnings)
    counts = Counter(node.title.casefold() for node, _, _ in walk(roots))
    reported = set()
    for node, _, _ in walk(roots):
        title = node.title.casefold()
        if counts[title] > 1 and title not in reported:
            reported.add(title)
            warnings.append(_warning("DUPLICATE_TITLE", f"„{node.title}“ kommt mehrfach im Baum vor.", node.key))
    return warnings


def check_descriptions(
    roots: list[Node], target_words: int, *, skip_keys: set[str] | None = None
) -> list[ServiceWarning]:
    skipped = skip_keys or set()
    nodes = [node for node, _, _ in walk(roots) if not (node.key and node.key in skipped)]
    missing = [n for n in nodes if not n.description.strip()]
    outliers = [
        n
        for n in nodes
        if n.description.strip() and not 0.5 * target_words <= len(n.description.split()) <= 1.5 * target_words
    ]
    warnings: list[ServiceWarning] = []
    if missing:
        warnings.append(_warning("DESCRIPTION_MISSING", f"{len(missing)} Knoten ohne Beschreibung.", missing[0].key))
    if outliers:
        warnings.append(
            _warning(
                "DESCRIPTION_LENGTH", f"{len(outliers)} Beschreibungen weichen deutlich von {target_words} Wörtern ab."
            )
        )
    return warnings
