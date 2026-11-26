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
    return {
        c.key: f"Vorgabe für die Beschreibung: {one_line(c.hint)}"
        for c in changes
        if c.op == ChangeOp.describe and c.key in done and c.hint and c.hint.strip()
    }


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


def described_before(roots: list[Node], result: StrategyResult) -> dict[str, str]:
    """Descriptions of the nodes to describe anew, to tell afterwards whether they were rewritten."""
    nodes = index(roots)
    return {r.key: nodes[r.key].description for r in result.changes if r.op == ChangeOp.describe and r.key in nodes}


def warn_not_described(roots: list[Node], before: dict[str, str], rc: RunContext) -> None:
    nodes = index(roots)
    for key, old in before.items():
        node = nodes.get(key)
        if node is not None and node.description == old:
            rc.warn("DESCRIBE_FAILED", f"{key} wurde nicht neu beschrieben; die bisherige Beschreibung bleibt.", key)
