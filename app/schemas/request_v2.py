"""Request format of POST /v2/topic-tree (Spec: "Anfrage"). Structural validation only; cross-field input
requirements per use case live in `app/pipeline/input_checks.py`."""

from typing import Annotated, Any, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.schemas.common import ChangeOp, ExtraTopic, FulltextFormat, ItemUse, Mode, UseCase
from app.schemas.properties import Properties


def _https_only(url: HttpUrl) -> HttpUrl:
    if url.scheme != "https":
        raise ValueError("only https URLs are allowed")
    return url


HttpsUrl = Annotated[HttpUrl, AfterValidator(_https_only)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
ItemId = Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,100}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Frame(_Model):
    discipline_uri: list[str] = Field(default_factory=list, max_length=20)
    educational_context_uri: list[str] = Field(default_factory=list, max_length=20)
    intended_end_user_role_uri: list[str] = Field(default_factory=list, max_length=20)


class MainRange(_Model):
    min: int = Field(6, ge=1, le=20)
    max: int = Field(12, ge=1, le=20)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class ChildRange(MainRange):
    # A node never gets exactly one child, so the lower bound is 2.
    min: int = Field(3, ge=2, le=20)
    max: int = Field(8, ge=2, le=20)


class Shape(_Model):
    depth: int = Field(3, ge=1, le=4)
    main_topics: MainRange = Field(default_factory=MainRange)
    children: ChildRange = Field(default_factory=ChildRange)
    extra_topics: list[ExtraTopic] = Field(default_factory=list)


class Hints(_Model):
    context: str | None = Field(None, max_length=2000)
    include: list[ShortText] = Field(default_factory=list, max_length=50)
    exclude: list[ShortText] = Field(default_factory=list, max_length=50)
    order: str | None = Field(None, max_length=200)
    description_length: int = Field(60, ge=40, le=200, description="Ziellänge der Beschreibungen in Wörtern")
    language: str = Field("de", pattern=r"^[a-z]{2}$")


class Options(_Model):
    improve: bool = False
    assign_contents: bool = True
    assign_only: bool = False
    multi_assign: bool = True
    min_confidence: float = Field(0.6, ge=0, le=1)
    auto_metadata: bool = False


class Fulltext(_Model):
    format: FulltextFormat = FulltextFormat.markdown
    text: str | None = Field(None, max_length=2_000_000)
    ref: HttpsUrl | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.text is None) == (self.ref is None):
            raise ValueError("exactly one of 'text' or 'ref' is required")
        return self


class Item(_Model):
    id: ItemId
    node_id: str | None = Field(None, alias="nodeId", max_length=200)
    use: list[ItemUse] | None = Field(
        None,
        description="Rolle des Eintrags: ['structure'] Gliederung, ['content'] Inhalt, beide, oder [] keines von "
        "beiden (wird angenommen, aber weder für die Struktur genutzt noch einsortiert). Fehlt use, gilt der Standard "
        "des Use Case.",
    )
    properties: Properties = Field(default_factory=Properties)
    fulltext: Fulltext | None = None
    path: str | None = Field(None, max_length=1000)


class FolderNode(_Model):
    title: ShortText
    items: list[ItemId] = Field(default_factory=list)
    subcollections: list["FolderNode"] = Field(default_factory=list)


class ContentRefIn(_Model):
    id: ItemId
    node_id: str | None = Field(None, alias="nodeId")
    confidence: float | None = Field(None, ge=0, le=1)


class TreeNodeIn(_Model):
    """A node of an earlier answer (v2 or legacy format), possibly edited by hand."""

    key: str | None = Field(None, max_length=200)
    title: ShortText
    shorttitle: str | None = Field(None, max_length=200)
    properties: Properties = Field(default_factory=Properties)
    origin: dict[str, Any] | None = None
    contents: list[ContentRefIn] = Field(default_factory=list)
    subcollections: list["TreeNodeIn"] = Field(default_factory=list)


class FeedbackEntry(_Model):
    version: str | None = None
    text: str | None = None


class GenerationIn(_Model):
    """`metadata.generation` of an earlier answer: defaults for anything the new request leaves out."""

    mode: Mode | None = None
    use_case: UseCase | None = None
    topic: str | None = None
    frame: Frame | None = None
    shape: Shape | None = None
    hints: Hints | None = None
    options: Options | None = None
    structure: dict[str, Any] | None = None
    feedback: list[FeedbackEntry] = Field(default_factory=list)


class CurrentTree(_Model):
    version: str | None = Field(None, max_length=50)
    # `metadata.title` / `metadata.description` of the earlier answer; carried over so refine keeps them.
    title: str | None = Field(None, max_length=2000)
    description: str | None = Field(None, max_length=8000)
    collection: list[TreeNodeIn]
    generation: GenerationIn | None = None


_REQUIRED_BY_OP: dict[ChangeOp, tuple[str, ...]] = {
    ChangeOp.add: ("title",),
    ChangeOp.remove: ("key",),
    ChangeOp.rename: ("key", "title"),
    ChangeOp.edit: ("key", "properties"),
    ChangeOp.move: ("key",),  # `to` omitted or null: move to the top level
    ChangeOp.merge: ("keys", "title"),
    ChangeOp.split: ("key", "hint"),
}


class Change(_Model):
    op: ChangeOp
    key: str | None = None
    keys: list[str] | None = None
    parent: str | None = None
    to: str | None = None
    title: ShortText | None = None
    properties: Properties | None = None
    hint: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _required_fields(self) -> Self:
        missing = [name for name in _REQUIRED_BY_OP[self.op] if getattr(self, name) in (None, "", [])]
        if self.title is not None and not self.title.strip():
            missing.append("title")
        if missing:
            raise ValueError(f"op '{self.op}' requires {', '.join(missing)}")
        if self.op == ChangeOp.merge and len(self.keys or []) < 2:
            raise ValueError("op 'merge' requires at least two keys")
        return self


class Feedback(_Model):
    text: str | None = Field(None, max_length=8000)
    changes: list[Change] = Field(default_factory=list, max_length=200)
    locked: list[str] = Field(default_factory=list, max_length=500)


class TopicTreeRequestV2(_Model):
    mode: Mode
    use_case: UseCase
    topic: str | None = Field(None, min_length=1, max_length=2000)
    folders: list[FolderNode] | None = None
    items: list[Item] | None = None
    items_ref: HttpsUrl | None = None
    current_tree: CurrentTree | None = None
    feedback: Feedback | None = None
    frame: Frame
    shape: Shape = Field(default_factory=Shape)
    hints: Hints = Field(default_factory=Hints)
    options: Options = Field(default_factory=Options)

    def effective_use(self, item: Item) -> set[ItemUse]:
        """Spec: without `use`, contents items are structure and content; everything else is content only.
        An explicit empty list means neither (the item is carried along, e.g. as a folder file, but not used)."""
        if item.use is not None:
            return set(item.use)
        if self.use_case == UseCase.contents:
            return {ItemUse.structure, ItemUse.content}
        return {ItemUse.content}
