"""mode `refine`: develop an earlier answer further. Structured changes first, then interpreted text feedback,
then fresh descriptions for new, renamed, merged and split nodes. `assign_only` leaves the structure alone."""

from pydantic import ValidationError

from app.domain.keys import assign_missing_keys
from app.domain.ops import apply_changes, protected_keys
from app.domain.tree import Node, from_tree_in, walk
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.interpret_feedback import interpret_feedback
from app.pipeline.steps.split_node import split_node
from app.schemas.common import ChangeOp, ChangeSource, UnassignedReason, UseCase
from app.schemas.request_v2 import Change, TopicTreeRequestV2
from app.schemas.response_v2 import ChangeRecord, Question, StructureInfo, Unassigned

_REFRESH_OPS = {ChangeOp.add, ChangeOp.rename, ChangeOp.merge}


def _structure(req: TopicTreeRequestV2) -> StructureInfo | None:
    generation = req.current_tree.generation
    if generation is None or not generation.structure:
        return None
    try:
        return StructureInfo.model_validate(generation.structure)
    except ValidationError:
        return None


def _keys_of(item: Change | ChangeRecord) -> set[str]:
    return {k for k in (item.key, item.to, item.parent, *(item.keys or [])) if k}


class _Refiner:
    def __init__(self, roots: list[Node], locked: set[str], rc: RunContext, result: StrategyResult) -> None:
        self.roots = roots
        self.locked = locked
        self.rc = rc
        self.result = result
        self.refresh: set[str] = set()

    async def apply(self, changes: list[Change], source: ChangeSource) -> None:
        applied = apply_changes(self.roots, changes, self.locked, source)
        self.result.changes.extend(applied.applied)
        for warning in applied.rejected:
            self.rc.warn(warning.code, warning.message, warning.key, warning.step)
        # With multi-assignment a released item can still sit in another node; only report truly homeless ones.
        placed = {ref.id for node, _, _ in walk(self.roots) for ref in node.contents}
        reported = {u.id for u in self.result.unassigned}
        for ref in applied.released_contents:
            if ref.id not in placed and ref.id not in reported:
                reported.add(ref.id)
                self.result.unassigned.append(
                    Unassigned(id=ref.id, nodeId=ref.node_id, reason=UnassignedReason.no_matching_node)
                )
        self.refresh.update(r.key for r in applied.applied if r.op in _REFRESH_OPS and r.key)
        for change in applied.pending_splits:
            outcome = await split_node(self.roots, change, source, self.rc)
            if outcome:
                record, new_keys = outcome
                self.result.changes.append(record)
                self.refresh.update(new_keys)

    async def apply_text(self, text: str) -> None:
        protected = protected_keys(self.roots, self.locked)
        changes, questions = await interpret_feedback(self.roots, text, protected, self.rc, self.result.changes)
        self.result.questions.extend(Question(text=q) for q in questions)
        touched = {k for record in self.result.changes for k in _keys_of(record)}
        allowed = []
        for change in changes:
            if _keys_of(change) & touched:
                self.rc.warn(
                    "CHANGE_REJECTED",
                    f"Änderung {change.op} aus dem Text widerspricht einer strukturierten Änderung.",
                    change.key,
                    "interpret_feedback",
                )
            else:
                allowed.append(change)
        await self.apply(allowed, ChangeSource.feedback_text)


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    current = req.current_tree
    roots = from_tree_in(current.collection)
    assign_missing_keys(roots)
    result = StrategyResult(
        roots=roots,
        title=current.title or req.topic or (roots[0].title if len(roots) == 1 else "Themenbaum"),
        description=current.description or "",
        structure=_structure(req),
        shape_checked=not (req.use_case == UseCase.folders and not req.options.improve),
    )
    feedback = req.feedback
    if feedback is None:
        return result
    if req.options.assign_only:
        if feedback.text or feedback.changes:
            rc.warn(
                "FEEDBACK_IGNORED",
                "options.assign_only ist gesetzt: Die Rückmeldung wurde nicht umgesetzt, nur Inhalte zugeordnet.",
                step="refine",
            )
        return result
    refiner = _Refiner(roots, set(feedback.locked), rc, result)
    if feedback.changes:
        await refiner.apply(feedback.changes, ChangeSource.feedback_changes)
    if feedback.text:
        await refiner.apply_text(feedback.text)
    protected = protected_keys(roots, set(feedback.locked))
    targets = [
        node
        for node, _, _ in walk(roots)
        if node.key not in protected and (node.key in refiner.refresh or not node.description)
    ]
    await describe_nodes(targets, roots, rc, context=rc.context, description_length=req.hints.description_length)
    return result
