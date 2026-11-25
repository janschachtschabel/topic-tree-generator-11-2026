"""Apply change operations (Spec: "Änderungen im Feedback") to the working tree, deterministically.

Every change is validated against the current tree before it is applied: unknown keys, locked nodes (and
everything below them) and cycles are rejected with a CHANGE_REJECTED warning instead of being guessed.
`split` needs the LLM and is only collected here.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.domain.keys import make_key
from app.domain.tree import Node, index, parent_of, walk
from app.schemas.common import ChangeOp, ChangeSource, NodeStatus, OriginType
from app.schemas.request_v2 import Change
from app.schemas.response_v2 import ChangeRecord, ContentRef, Origin, ServiceWarning


@dataclass
class ApplyResult:
    applied: list[ChangeRecord] = field(default_factory=list)
    rejected: list[ServiceWarning] = field(default_factory=list)
    released_contents: list[ContentRef] = field(default_factory=list)
    pending_splits: list[Change] = field(default_factory=list)


class _Rejected(Exception):
    pass


def protected_keys(roots: list[Node], locked: set[str]) -> set[str]:
    protected: set[str] = set()
    for node, parent, _ in walk(roots):
        if node.key in locked or (parent is not None and parent.key in protected):
            protected.add(node.key)
    return protected


def _siblings(roots: list[Node], key: str) -> list[Node]:
    parent = parent_of(roots, key)
    return parent.children if parent else roots


def _detach(roots: list[Node], key: str) -> Node:
    siblings = _siblings(roots, key)
    node = next(n for n in siblings if n.key == key)
    siblings.remove(node)
    return node


class _Applier:
    def __init__(self, roots: list[Node], locked: set[str], source: ChangeSource) -> None:
        self.roots = roots
        self.locked = locked
        self.source = source
        self.result = ApplyResult()

    def node(self, key: str | None, editable: bool = True) -> Node:
        found = index(self.roots).get(key or "")
        if found is None:
            raise _Rejected(f"unbekannter Schlüssel {key}")
        if editable and key in protected_keys(self.roots, self.locked):
            raise _Rejected(f"{key} ist gesperrt")
        return found

    def record(self, change: Change, **overrides: object) -> None:
        data = change.model_dump(exclude={"properties", "hint"}) | overrides
        self.result.applied.append(ChangeRecord.model_validate({**data, "from": self.source}))

    def _resolve_parent(self, ref: str) -> Node:
        by_key = index(self.roots)
        if ref in by_key:
            return self.node(ref)
        needle = ref.strip().casefold()
        matches = [n for n, _, _ in walk(self.roots) if n.title.strip().casefold() == needle]
        if len(matches) == 1 and matches[0].key:
            return self.node(matches[0].key)
        return self.node(ref)

    def add(self, change: Change) -> None:
        parent = self._resolve_parent(change.parent) if change.parent else None
        taken = set(index(self.roots))
        new = Node(
            key=make_key(change.title, taken),
            title=change.title,
            status=NodeStatus.new,
            origin=Origin(type=OriginType.feedback),
        )
        (parent.children if parent else self.roots).append(new)
        self.record(change, key=new.key, parent=parent.key if parent else None)

    def remove(self, change: Change) -> None:
        node = self.node(change.key)
        for item, _, _ in walk([node]):
            self.result.released_contents.extend(item.contents)
        _detach(self.roots, node.key)
        self.record(change)

    def rename(self, change: Change) -> None:
        node = self.node(change.key)
        if change.title.strip() == node.title.strip():
            return  # no-op proposal: nothing changes, so nothing is reported
        node.title, node.shorttitle = change.title, ""
        self.record(change)

    def edit(self, change: Change) -> None:
        node = self.node(change.key)
        props = change.properties
        if props.values("cm:description"):
            node.description = props.first("cm:description")
        if props.values("cclom:general_keyword"):
            node.keywords = props.values("cclom:general_keyword")
        for key, values in props.dump_v2().items():
            if key not in ("cm:description", "cclom:general_keyword", "cm:title"):
                node.properties.set(key, values)
        self.record(change)

    def move(self, change: Change) -> None:
        node = self.node(change.key)
        target = self.node(change.to) if change.to else None  # None: the top level
        if target is not None and target.key in {n.key for n, _, _ in walk([node])}:
            raise _Rejected(f"{change.key} kann nicht unter sich selbst verschoben werden")
        destination = target.children if target is not None else self.roots
        if any(child is node for child in destination):
            return  # already there
        _detach(self.roots, node.key)
        destination.append(node)
        self.record(change)

    def merge(self, change: Change) -> None:
        unique_keys = list(dict.fromkeys(change.keys))
        if len(unique_keys) < 2:
            raise _Rejected("mindestens zwei verschiedene Knoten nötig")
        nodes = [self.node(key) for key in unique_keys]
        keys = {n.key for n in nodes}
        for node in nodes:
            below = {n.key for n, _, _ in walk(node.children)}
            if below & keys:
                raise _Rejected("zusammenzulegende Knoten liegen ineinander")
        first, rest = nodes[0], nodes[1:]
        by_id = {ref.id: ref for ref in first.contents}
        for other in rest:
            first.children.extend(other.children)
            for ref in other.contents:
                existing = by_id.get(ref.id)
                if existing is None or ref.confidence > existing.confidence:
                    by_id[ref.id] = ref
            _detach(self.roots, other.key)
        first.contents = list(by_id.values())
        first.title, first.shorttitle = change.title, ""
        self.record(change, key=first.key, keys=unique_keys)

    def split(self, change: Change) -> None:
        self.node(change.key)
        self.result.pending_splits.append(change)

    def apply(self, change: Change) -> None:
        handlers: dict[ChangeOp, Callable[[Change], None]] = {
            ChangeOp.add: self.add,
            ChangeOp.remove: self.remove,
            ChangeOp.rename: self.rename,
            ChangeOp.edit: self.edit,
            ChangeOp.move: self.move,
            ChangeOp.merge: self.merge,
            ChangeOp.split: self.split,
        }
        try:
            handlers[change.op](change)
        except _Rejected as reason:
            self.result.rejected.append(
                ServiceWarning(
                    code="CHANGE_REJECTED",
                    message=f"Änderung {change.op} nicht umgesetzt: {reason}.",
                    key=change.key,
                    step="apply_changes",
                )
            )


def apply_changes(roots: list[Node], changes: list[Change], locked: set[str], source: ChangeSource) -> ApplyResult:
    applier = _Applier(roots, locked, source)
    for change in changes:
        applier.apply(change)
    return applier.result
