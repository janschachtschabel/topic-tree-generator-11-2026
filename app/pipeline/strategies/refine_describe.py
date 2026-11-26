"""The `describe` change in refine: hints for describe_nodes and reporting of describes that did not happen."""

from app.domain.text import one_line
from app.domain.tree import Node, index
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.schemas.common import ChangeOp
from app.schemas.request_v2 import Change
from app.schemas.response_v2 import ChangeRecord


def describe_hints(changes: list[Change], applied: list[ChangeRecord]) -> dict[str, str]:
    """Hints of applied `describe` changes, per key, as one-line extra prompt text for describe_nodes."""
    done = {r.key for r in applied if r.op == ChangeOp.describe}
    hints: dict[str, list[str]] = {}
    for c in changes:
        if c.op == ChangeOp.describe and c.key in done and c.hint and c.hint.strip():
            hints.setdefault(c.key, []).append(one_line(c.hint))  # two describes of one node: both hints count
    return {key: f"Vorgabe für die Beschreibung: {' / '.join(texts)}" for key, texts in hints.items()}


def drop_vanished_describes(roots: list[Node], result: StrategyResult, rc: RunContext) -> None:
    """A later remove, merge or split in the same request took the node away: its describe did not happen."""
    keys = set(index(roots))
    kept: list[ChangeRecord] = []
    for record in result.changes:
        if record.op == ChangeOp.describe and record.key not in keys:
            rc.warn(
                "CHANGE_REJECTED",
                f"Änderung describe nicht umgesetzt: {record.key} gibt es nach den späteren Änderungen nicht mehr.",
                record.key,
                "apply_changes",
            )
        else:
            kept.append(record)
    result.changes[:] = kept


def edited_texts(changes: list[Change], applied: list[ChangeRecord]) -> dict[str, set[str]]:
    """Per key, the text fields (`description`, `keywords`) the caller set with `edit`: they win over any rewrite."""
    done = {r.key for r in applied if r.op == ChangeOp.edit}
    edited: dict[str, set[str]] = {}
    for c in changes:
        if c.op != ChangeOp.edit or c.key not in done or c.properties is None:
            continue
        fields = {
            f
            for f, p in (("description", "cm:description"), ("keywords", "cclom:general_keyword"))
            if c.properties.values(p)
        }
        if fields:
            edited.setdefault(c.key, set()).update(fields)
    return edited


def reject_describes_of_edited(edited: dict[str, set[str]], result: StrategyResult, rc: RunContext) -> set[str]:
    """`describe` and an `edit` of the description on one node contradict each other; the explicit text wins."""
    kept: list[ChangeRecord] = []
    rejected: set[str] = set()
    for record in result.changes:
        if record.op == ChangeOp.describe and record.key in edited:
            rejected.add(record.key)
            rc.warn(
                "CHANGE_REJECTED",
                f"Änderung describe nicht umgesetzt: Beschreibung oder Schlagworte von {record.key} wurden im selben "
                "Aufruf mit edit gesetzt.",
                record.key,
                "apply_changes",
            )
        else:
            kept.append(record)
    result.changes[:] = kept
    return rejected


def keep_edited_texts(roots: list[Node], edited: dict[str, set[str]]) -> dict[str, dict[str, object]]:
    nodes = index(roots)
    return {
        key: {f: list(getattr(nodes[key], f)) if f == "keywords" else getattr(nodes[key], f) for f in fields}
        for key, fields in edited.items()
        if key in nodes
    }


def restore_edited_texts(roots: list[Node], saved: dict[str, dict[str, object]]) -> None:
    nodes = index(roots)
    for key, fields in saved.items():
        for name, value in fields.items():
            if key in nodes:
                setattr(nodes[key], name, value)


def described_before(targets: list[Node], refresh: set[str], edited: dict[str, set[str]]) -> dict[str, str]:
    """Descriptions of the nodes to describe anew (describe, rename, merge, split), to tell afterwards whether they
    were rewritten. Nodes without a description are covered by DESCRIPTION_MISSING; an edited description stays."""
    return {
        n.key: n.description
        for n in targets
        if n.key in refresh and "description" not in edited.get(n.key, set()) and n.description
    }


def warn_not_described(roots: list[Node], before: dict[str, str], failed: set[str], rc: RunContext) -> None:
    """`failed`: keys of batches that already got a DESCRIBE_FAILED warning."""
    nodes = index(roots)
    for key, old in before.items():
        node = nodes.get(key)
        if node is not None and node.description == old and key not in failed:
            rc.warn(
                "DESCRIBE_FAILED",
                f"{key} wurde nicht neu beschrieben; die bisherige Beschreibung bleibt.",
                key,
                "describe_nodes",
            )
