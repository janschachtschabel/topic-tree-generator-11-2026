"""Turn the working tree into the v2 answer: node properties from the frame, version chain, generation record."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.tree import Node
from app.schemas.common import ItemUse, NodeStatus
from app.schemas.properties import Properties
from app.schemas.request_v2 import FeedbackEntry, Frame, TopicTreeRequestV2
from app.schemas.response_v2 import (
    ChangeRecord,
    Generation,
    InputCounts,
    ItemCounts,
    Metadata,
    NodeOut,
    Question,
    ServiceWarning,
    StructureInfo,
    TopicTreeResponseV2,
    Unassigned,
    Usage,
)
from app.version import service_version
from app.vocab.labels import label, resolve_labels

_VERSION = re.compile(r"^v(\d+)$")
_TEACHER = "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"
_AUDIENCE = {_TEACHER: "Lehrkräfte", "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/learner": "Lernende"}


@dataclass
class FinalizeInput:
    roots: list[Node]
    title: str
    description: str = ""
    structure: StructureInfo | None = None
    unassigned: list[Unassigned] = field(default_factory=list)
    changes: list[ChangeRecord] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    warnings: list[ServiceWarning] = field(default_factory=list)


def next_version(current: str | None) -> tuple[str, str | None]:
    """(new version, based_on). Unknown version strings count as v1."""
    if current is None:
        return "v1", None
    match = _VERSION.match(current)
    return f"v{int(match.group(1)) + 1 if match else 2}", current


def node_properties(node: Node, frame: Frame) -> Properties:
    props = Properties.model_validate(node.properties.dump_v2())
    props.set("cm:title", [node.title])
    props.set("ccm:collectionshorttitle", [node.shorttitle or node.title])
    if node.description:
        props.set("cm:description", [node.description])
    if node.keywords:
        props.set("cclom:general_keyword", node.keywords)
    # Frame values apply to every node unless the node is already scoped more narrowly.
    for key, values in (
        ("ccm:taxonid", frame.discipline_uri),
        ("ccm:educationalcontext", frame.educational_context_uri),
        ("ccm:educationalintendedenduserrole", frame.intended_end_user_role_uri),
    ):
        if values and not props.values(key):
            props.set(key, values)
    return props


def to_node_out(node: Node, frame: Frame) -> NodeOut:
    return NodeOut(
        key=node.key,
        title=node.title,
        shorttitle=node.shorttitle or node.title,
        status=node.status or NodeStatus.new,
        origin=node.origin,
        confidence=node.confidence,
        properties=node_properties(node, frame),
        contents=node.contents,
        subcollections=[to_node_out(child, frame) for child in node.children],
    )


def _input_counts(req: TopicTreeRequestV2) -> InputCounts:
    items = req.items or []
    uses = [req.effective_use(item) for item in items]
    return InputCounts(
        folders=len(req.folders or []),
        items=ItemCounts(
            structure=sum(ItemUse.structure in u for u in uses), content=sum(ItemUse.content in u for u in uses)
        ),
    )


def _feedback_history(req: TopicTreeRequestV2, version: str) -> list[FeedbackEntry]:
    history = list(req.current_tree.generation.feedback) if req.current_tree and req.current_tree.generation else []
    if req.feedback and (req.feedback.text or req.feedback.changes):
        text = req.feedback.text or f"{len(req.feedback.changes)} strukturierte Änderungen"
        history.append(FeedbackEntry(version=version, text=text))
    return history


def _audience(frame: Frame) -> str:
    roles = frame.intended_end_user_role_uri or [_TEACHER]
    return ", ".join(dict.fromkeys(_AUDIENCE.get(r) or label(r) or r.rsplit("/", 1)[-1] for r in roles))


def _collect_vocab_uris(frame: Frame, nodes: list[NodeOut]) -> list[str]:
    uris: list[str] = [
        *frame.discipline_uri,
        *frame.educational_context_uri,
        *frame.intended_end_user_role_uri,
    ]

    def visit(items: list[NodeOut]) -> None:
        for node in items:
            for key in ("ccm:taxonid", "ccm:educationalcontext", "ccm:educationalintendedenduserrole"):
                uris.extend(node.properties.values(key))
            visit(node.subcollections)

    visit(nodes)
    return uris


def finalize(
    req: TopicTreeRequestV2, data: FinalizeInput, *, model: str | None, usage: dict[str, Any], duration_ms: int
) -> TopicTreeResponseV2:
    current = req.current_tree.version if req.current_tree else None
    version, based_on = next_version(current) if req.current_tree else ("v1", None)
    collection = [to_node_out(node, req.frame) for node in data.roots]
    generation = Generation(
        mode=req.mode,
        use_case=req.use_case,
        topic=req.topic,
        frame=req.frame,
        shape=req.shape,
        hints=req.hints,
        options=req.options,
        inputs=_input_counts(req),
        feedback=_feedback_history(req, version),
        structure=data.structure,
        usage=Usage(**{**usage, "duration_ms": duration_ms}),
        generator_version=service_version(),
        model=model,
    )
    metadata = Metadata(
        title=data.title,
        description=data.description,
        target_audience=_audience(req.frame),
        created_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        version=version,
        based_on=based_on,
        vocab_labels=resolve_labels(_collect_vocab_uris(req.frame, collection)),
        generation=generation,
    )
    return TopicTreeResponseV2(
        metadata=metadata,
        collection=collection,
        unassigned=data.unassigned,
        changes=data.changes,
        questions=data.questions,
        warnings=data.warnings,
    )
