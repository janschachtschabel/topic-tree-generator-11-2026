"""mode `refine`: develop an earlier answer further. Structured changes first, then interpreted text feedback,
then fresh descriptions for new, renamed, merged and split nodes. `assign_only` leaves the structure alone."""

from pydantic import ValidationError

from app.domain.keys import assign_missing_keys
from app.domain.ops import apply_changes, protected_keys
from app.domain.tree import Node, from_tree_in, index, parent_of, walk
from app.llm.client import LLMStepError
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.expand_nodes import expand_nodes, shallow_leaves
from app.pipeline.steps.interpret_feedback import interpret_feedback
from app.pipeline.steps.split_node import split_node
from app.pipeline.strategies.refine_describe import (
    describe_hints,
    described_before,
    drop_vanished_describes,
    warn_not_described,
)
from app.schemas.common import ChangeOp, ChangeSource, UnassignedReason, UseCase
from app.schemas.request_v2 import Change, Frame, TopicTreeRequestV2
from app.schemas.response_v2 import ChangeRecord, Question, StructureInfo, Unassigned

_REFRESH_OPS = {ChangeOp.add, ChangeOp.rename, ChangeOp.merge, ChangeOp.describe}


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
    def __init__(
        self, roots: list[Node], locked: set[str], rc: RunContext, result: StrategyResult, width: tuple[int, int]
    ) -> None:
        self.roots = roots
        self.width = width
        self.locked = locked
        self.rc = rc
        self.result = result
        self.refresh: set[str] = set()
        self.taken: set[str] = set(index(roots))  # keys of removed nodes are never handed out again

    async def apply(self, changes: list[Change], source: ChangeSource) -> None:
        applied = apply_changes(self.roots, changes, self.locked, source, self.taken)
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
            await self.split(change, source)

    async def split(self, change: Change, source: ChangeSource) -> None:
        """A split collected earlier in the batch; later changes may have removed or replaced the node since."""
        if change.key not in index(self.roots):
            self.rc.warn(
                "CHANGE_REJECTED",
                f"Änderung split nicht umgesetzt: {change.key} gibt es nach den vorherigen Änderungen nicht mehr.",
                change.key,
                "apply_changes",
            )
            return
        try:
            outcome = await split_node(self.roots, change, source, self.rc, self.taken)
        except LLMStepError as err:
            self.rc.warn("SPLIT_FAILED", f"Aufteilen nicht möglich ({err.reason}).", change.key, "split_node")
            return
        if outcome:
            record, new_keys = outcome
            self.result.changes.append(record)
            self.refresh.update(new_keys)
            self.taken.update(new_keys)

    async def apply_text(self, text: str) -> None:
        protected = protected_keys(self.roots, self.locked)
        changes, questions = await interpret_feedback(self.roots, text, protected, self.rc, self.result.changes)
        self.result.questions.extend(Question(text=q) for q in questions)
        # A describe only rewrites text, so free-text changes to the same node do not contradict it.
        touched = {k for r in self.result.changes if r.op != ChangeOp.describe for k in _keys_of(r)}
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
        await self.expand_new_leaves()

    async def expand_new_leaves(self) -> None:
        """Nodes added from text get subtopics down to their neighbours' depth (one call for all of them)."""
        nodes = index(self.roots)
        targets = []
        for record in self.result.changes:
            node = nodes.get(record.key or "")
            if record.op != ChangeOp.add or record.source != ChangeSource.feedback_text or node is None:
                continue
            parent = parent_of(self.roots, node.key)
            for leaf, levels in shallow_leaves(node, parent.children if parent else self.roots):
                if all(leaf is not known for known, _ in targets):
                    targets.append((leaf, levels))
        if not targets:
            return
        try:
            await expand_nodes(targets, self.roots, self.rc, self.width)
        except LLMStepError as err:
            self.rc.warn(
                "EXPAND_FAILED",
                f"Unterthemen für {len(targets)} neue Knoten konnten nicht erzeugt werden ({err.reason}).",
                targets[0][0].key,
                "expand_nodes",
            )
            return
        assign_missing_keys(self.roots, self.taken)
        still_bare = [node for node, _ in targets if not node.children]
        if still_bare:
            self.rc.warn(
                "EXPAND_INCOMPLETE",
                f"{len(still_bare)} neue Knoten blieben ohne Unterthemen, obwohl die Nachbaräste tiefer sind.",
                still_bare[0].key,
                "expand_nodes",
            )


_FRAME_FIELDS = (
    ("ccm:taxonid", "discipline_uri"),
    ("ccm:educationalcontext", "educational_context_uri"),
    ("ccm:educationalintendedenduserrole", "intended_end_user_role_uri"),
)


def apply_changed_frame(roots: list[Node], old: Frame | None, new: Frame, locked: set[str]) -> None:
    """A changed `frame` replaces the old frame values on carried-over nodes.

    Only nodes that still carry exactly the old values change; nodes narrowed on purpose (auto_metadata, `edit`)
    and locked branches keep theirs. An emptied frame field removes the old values.
    """
    if old is None:
        return
    protected = protected_keys(roots, locked)
    for prop_key, attr in _FRAME_FIELDS:
        before, after = getattr(old, attr), getattr(new, attr)
        if not before or before == after:
            continue
        for node, _, _ in walk(roots):
            if node.key not in protected and node.properties.values(prop_key) == before:
                if after:
                    node.properties.set(prop_key, after)
                else:
                    node.properties.root.pop(prop_key, None)


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    current = req.current_tree
    roots = from_tree_in(current.collection)
    assign_missing_keys(roots)
    locked = set(req.feedback.locked) if req.feedback else set()
    if not req.options.assign_only:  # only sorting in: the caller's node properties stay as they are
        apply_changed_frame(roots, current.generation.frame if current.generation else None, req.frame, locked)
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
    width = (req.shape.children.min, req.shape.children.max)
    refiner = _Refiner(roots, set(feedback.locked), rc, result, width)
    if feedback.changes:
        await refiner.apply(feedback.changes, ChangeSource.feedback_changes)
    if feedback.text:
        await refiner.apply_text(feedback.text)
    drop_vanished_describes(roots, result, rc)
    protected = protected_keys(roots, set(feedback.locked))
    targets = [
        node
        for node, _, _ in walk(roots)
        if node.key not in protected and (node.key in refiner.refresh or not node.description)
    ]
    before = described_before(roots, result)
    await describe_nodes(
        targets,
        roots,
        rc,
        context=rc.context,
        description_length=req.hints.description_length,
        extra=describe_hints(feedback.changes, result.changes),
    )
    warn_not_described(roots, before, rc)
    return result
