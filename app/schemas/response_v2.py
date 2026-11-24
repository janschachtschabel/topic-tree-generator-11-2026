"""Response format of POST /v2/topic-tree (Spec: "Antwort"), plus the documented additions (plan E10)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ChangeOp, ChangeSource, Mode, NodeStatus, OriginType, UnassignedReason, UseCase
from app.schemas.properties import Properties
from app.schemas.request_v2 import FeedbackEntry, Frame, Hints, Options, Shape


class _Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ContentRef(_Out):
    id: str
    node_id: str | None = Field(None, alias="nodeId")
    confidence: float = Field(1.0, ge=0, le=1)


class Origin(_Out):
    type: OriginType
    id: str | None = None
    section: str | None = None
    page: int | None = None
    path: str | None = None


class NodeOut(_Out):
    key: str
    title: str
    shorttitle: str
    status: NodeStatus
    origin: Origin | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    properties: Properties = Field(default_factory=Properties)
    contents: list[ContentRef] = Field(default_factory=list)
    subcollections: list["NodeOut"] = Field(default_factory=list)


class Unassigned(_Out):
    id: str
    node_id: str | None = Field(None, alias="nodeId")
    reason: UnassignedReason


class ChangeRecord(_Out):
    op: ChangeOp
    key: str | None = None
    keys: list[str] | None = None
    parent: str | None = None
    to: str | None = None
    title: str | None = None
    source: ChangeSource = Field(alias="from")


class Question(_Out):
    text: str
    key: str | None = None
    options: list[str] | None = None


class ServiceWarning(_Out):
    code: str
    message: str
    key: str | None = None
    step: str | None = None


class StructureInfo(_Out):
    order: str
    levels: list[str] = Field(default_factory=list)
    source: Literal["hint", "detected", "input"]


class ItemCounts(_Out):
    structure: int = 0
    content: int = 0


class InputCounts(_Out):
    folders: int = 0
    items: ItemCounts = Field(default_factory=ItemCounts)


class Usage(_Out):
    llm_calls: int = 0
    failed_calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0


class Generation(_Out):
    mode: Mode
    use_case: UseCase
    topic: str | None = None
    frame: Frame
    shape: Shape
    hints: Hints
    options: Options
    inputs: InputCounts = Field(default_factory=InputCounts)
    feedback: list[FeedbackEntry] = Field(default_factory=list)
    structure: StructureInfo | None = None
    usage: Usage | None = None
    generator_version: str
    model: str | None = None


class Metadata(_Out):
    title: str
    description: str = ""
    target_audience: str = "Lehrkräfte"
    created_at: str
    author: str = "Themenbaum Generator"
    schema_version: str = "2.0"
    version: str
    based_on: str | None = None
    vocab_labels: dict[str, str] = Field(default_factory=dict)
    generation: Generation


class TopicTreeResponseV2(_Out):
    metadata: Metadata
    collection: list[NodeOut]
    unassigned: list[Unassigned] = Field(default_factory=list)
    changes: list[ChangeRecord] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    warnings: list[ServiceWarning] = Field(default_factory=list)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
