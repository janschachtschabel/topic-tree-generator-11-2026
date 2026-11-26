"""Assign content items to tree nodes with confidence (Spec: `contents`, `unassigned`, options.*).

Batches of 40 items share one prompt prefix (context + tree). Answers are checked against known keys and ids;
anything unknown is dropped and reported, never guessed.
"""

import asyncio

from pydantic import BaseModel, Field

from app.domain.text import truncate_sentences
from app.domain.tree import Node, index, path, walk
from app.llm.client import LLMStepError
from app.pipeline.key_matching import match_keys
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.common import UnassignedReason
from app.schemas.request_v2 import Item, Options
from app.schemas.response_v2 import ContentRef, Unassigned

STEP = "assign_contents"
ITEMS_MARKER = "## Inhalte"
BATCH = 40
_TEXT_LIMIT = 300


class NodeScore(BaseModel):
    key: str
    confidence: float = Field(ge=0, le=1)


class Assignment(BaseModel):
    id: str
    nodes: list[NodeScore] = Field(default_factory=list)
    off_topic: bool = False
    excluded: bool = False


class AssignResult(BaseModel):
    items: list[Assignment]


def render_tree(roots: list[Node]) -> str:
    return "\n".join(f"{node.key}: {' > '.join(path(roots, node.key))}" for node, _, _ in walk(roots))


def _item_line(item: Item, folder: str | None = None) -> str:
    props = item.properties
    parts = [f"- id: {item.id}", props.first("cm:title") or "(ohne Titel)"]
    if description := props.first("cm:description"):
        parts.append(truncate_sentences(description, _TEXT_LIMIT))
    if keywords := props.values("cclom:general_keyword"):
        parts.append("Schlagworte: " + ", ".join(keywords[:10]))
    if folder:
        parts.append(f"Ordner: {folder}")
    return " | ".join(parts)


def _attach(node: Node, ref: ContentRef) -> None:
    if all(existing.id != ref.id for existing in node.contents):
        node.contents.append(ref)


class _Outcome:
    def __init__(self) -> None:
        self.unassigned: list[Unassigned] = []
        self.dropped = 0
        self.failed_batches = 0
        self.unanswered = 0


def _apply(answer: Assignment, item: Item, nodes: dict[str, Node], options: Options, out: _Outcome) -> None:
    def unassigned(reason: UnassignedReason) -> None:
        out.unassigned.append(Unassigned(id=item.id, nodeId=item.node_id, reason=reason))

    if answer.excluded:
        return unassigned(UnassignedReason.excluded)
    if answer.off_topic:
        return unassigned(UnassignedReason.off_topic)
    # Repair slightly altered keys deterministically; elimination is off because any tree node may be chosen.
    matched = match_keys([score.key for score in answer.nodes], list(nodes), elimination=False)
    known = [score.model_copy(update={"key": matched[i]}) for i, score in enumerate(answer.nodes) if i in matched]
    out.dropped += len(answer.nodes) - len(known)
    accepted = sorted((s for s in known if s.confidence >= options.min_confidence), key=lambda s: -s.confidence)
    if not options.multi_assign:
        accepted = accepted[:1]
    if not accepted:
        return unassigned(UnassignedReason.low_confidence if known else UnassignedReason.no_matching_node)
    for score in accepted:
        _attach(nodes[score.key], ContentRef(id=item.id, nodeId=item.node_id, confidence=score.confidence))
    return None


async def _batch(items: list[Item], prefix: str, rc: RunContext, paths: dict[str, str]) -> AssignResult:
    lines = "\n".join(_item_line(item, paths.get(item.id)) for item in items)
    return await rc.llm.complete_json(
        STEP, f"{prefix}{ITEMS_MARKER}\n{lines}", AssignResult, max_tokens=600 + 60 * len(items)
    )


async def assign_contents(
    roots: list[Node], items: list[Item], rc: RunContext, options: Options, *, paths: dict[str, str] | None = None
) -> list[Unassigned]:
    """Attach items to nodes (keys must be assigned). Returns the items that found no node.

    `paths` maps item ids to the caller's folder path, a hint where the material was filed."""
    if not items:
        return []
    nodes = index(roots)
    prefix = render(STEP, context=rc.context, tree=render_tree(roots), items="").rstrip() + "\n\n"
    batches = [items[i : i + BATCH] for i in range(0, len(items), BATCH)]
    results = await asyncio.gather(*(_batch(b, prefix, rc, paths or {}) for b in batches), return_exceptions=True)

    out = _Outcome()
    for batch, result in zip(batches, results, strict=True):
        if isinstance(result, LLMStepError):
            out.failed_batches += 1
            out.unassigned.extend(
                Unassigned(id=i.id, nodeId=i.node_id, reason=UnassignedReason.no_matching_node) for i in batch
            )
            continue
        if isinstance(result, BaseException):
            raise result
        answers = {a.id: a for a in result.items}
        for item in batch:
            # An item the model left out was never judged: it is unassigned, but the gap is reported.
            out.unanswered += item.id not in answers
            _apply(answers.get(item.id, Assignment(id=item.id)), item, nodes, options, out)

    if out.failed_batches or out.dropped or out.unanswered:
        rc.warn(
            "ASSIGN_FAILED",
            f"Zuordnung unvollständig: {out.failed_batches} Gruppen fehlgeschlagen, {out.dropped} unbekannte Knoten "
            f"verworfen, {out.unanswered} Inhalte ohne Antwort.",
            step=STEP,
        )
    return out.unassigned
