"""Request format of POST /v2/topic-tree (Spec: "Anfrage"). Structural validation only; cross-field input
requirements per use case live in `app/pipeline/input_checks.py`."""

from typing import Annotated, Any, Self

from pydantic import AfterValidator, Field, HttpUrl, model_validator

from app.schemas.common import ChangeOp, FulltextFormat, ItemUse, Mode, UseCase
from app.schemas.properties import Properties
from app.schemas.request_parts import ChildRange, Frame, Hints, MainRange, Options, RequestModel, Shape, ShortText

__all__ = [
    "Change",
    "ChildRange",
    "ContentRefIn",
    "CurrentTree",
    "Feedback",
    "FeedbackEntry",
    "FolderNode",
    "Frame",
    "Fulltext",
    "GenerationIn",
    "Hints",
    "Item",
    "MainRange",
    "Options",
    "Shape",
    "TopicTreeRequestV2",
    "TreeNodeIn",
]


def _https_only(url: HttpUrl) -> HttpUrl:
    if url.scheme != "https":
        raise ValueError("only https URLs are allowed")
    return url


HttpsUrl = Annotated[HttpUrl, AfterValidator(_https_only)]
ItemId = Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,100}$")]


class Fulltext(RequestModel):
    format: FulltextFormat = Field(FulltextFormat.markdown, description="Format von text bzw. des geladenen Verweises")
    text: str | None = Field(
        None, max_length=2_000_000, description="Volltext direkt in der Anfrage (genau eines von text und ref)"
    )
    ref: HttpsUrl | None = Field(None, description="HTTPS-Adresse des Volltexts; nur Hosts aus REF_ALLOWED_HOSTS")

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.text is None) == (self.ref is None):
            raise ValueError("exactly one of 'text' or 'ref' is required")
        return self


class Item(RequestModel):
    id: ItemId = Field(description="Eindeutige id des Eintrags in dieser Anfrage; erscheint in contents und unassigned")
    node_id: str | None = Field(
        None,
        alias="nodeId",
        max_length=200,
        description="Knoten-ID im Repository; wird unverändert durchgereicht, der Dienst liest den Knoten nie",
    )
    use: list[ItemUse] | None = Field(
        None,
        description="Rolle des Eintrags: ['structure'] Gliederung, ['content'] Inhalt, beide, oder [] keines von "
        "beiden (wird angenommen, aber weder für die Struktur genutzt noch einsortiert). Fehlt use, gilt der Standard "
        "des Use Case.",
    )
    properties: Properties = Field(
        default_factory=Properties,
        description="edu-sharing-Properties wie cm:title oder cclom:general_keyword, Werte als Listen",
    )
    fulltext: Fulltext | None = Field(None, description="Volltext des Eintrags, etwa ein Lehrplan als Markdown")
    path: str | None = Field(None, max_length=1000, description="Ablageort des Eintrags, nur zur Information")


class FolderNode(RequestModel):
    title: ShortText = Field(description="Name des Ordners")
    items: list[ItemId] = Field(
        default_factory=list, description="ids der Einträge aus items, die in diesem Ordner liegen"
    )
    subcollections: list["FolderNode"] = Field(default_factory=list, description="Unterordner")


class ContentRefIn(RequestModel):
    id: ItemId = Field(description="id des zugeordneten Inhalts")
    node_id: str | None = Field(None, alias="nodeId", description="Knoten-ID im Repository, unverändert durchgereicht")
    confidence: float | None = Field(None, ge=0, le=1, description="Konfidenz der Zuordnung zwischen 0 und 1")


class TreeNodeIn(RequestModel):
    """A node of an earlier answer (v2 or legacy format), possibly edited by hand."""

    key: str | None = Field(
        None,
        max_length=200,
        description="Schlüssel des Knotens aus der früheren Antwort; fehlt er, vergibt der Dienst einen",
    )
    title: ShortText = Field(description="Titel des Knotens")
    shorttitle: str | None = Field(None, max_length=200, description="Kurztitel (höchstens 20 Zeichen in der Antwort)")
    properties: Properties = Field(default_factory=Properties, description="edu-sharing-Properties des Knotens")
    origin: dict[str, Any] | None = Field(None, description="Herkunft des Knotens aus der früheren Antwort")
    contents: list[ContentRefIn] = Field(default_factory=list, description="Bereits zugeordnete Inhalte")
    subcollections: list["TreeNodeIn"] = Field(default_factory=list, description="Unterknoten")


class FeedbackEntry(RequestModel):
    version: str | None = Field(None, description="Version des Baums, auf die sich die Rückmeldung bezog")
    text: str | None = Field(None, description="Text der Rückmeldung")


class GenerationIn(RequestModel):
    """`metadata.generation` of an earlier answer: defaults for anything the new request leaves out."""

    mode: Mode | None = Field(None, description="Modus des früheren Laufs")
    use_case: UseCase | None = Field(None, description="Use Case des früheren Laufs")
    topic: str | None = Field(None, description="Thema des früheren Laufs")
    frame: Frame | None = Field(None, description="Rahmen des früheren Laufs")
    shape: Shape | None = Field(None, description="Form des früheren Laufs")
    hints: Hints | None = Field(None, description="Hinweise des früheren Laufs")
    options: Options | None = Field(None, description="Optionen des früheren Laufs (assign_only wird nie geerbt)")
    structure: dict[str, Any] | None = Field(None, description="Erkannte Ordnung des früheren Laufs")
    feedback: list[FeedbackEntry] = Field(default_factory=list, description="Bisherige Rückmeldungen")


class CurrentTree(RequestModel):
    version: str | None = Field(
        None, max_length=50, description="metadata.version der früheren Antwort (ohne Angabe: v1)"
    )
    # `metadata.title` / `metadata.description` of the earlier answer; carried over so refine keeps them.
    title: str | None = Field(None, max_length=2000, description="metadata.title der früheren Antwort")
    description: str | None = Field(None, max_length=8000, description="metadata.description der früheren Antwort")
    collection: list[TreeNodeIn] = Field(description="collection der früheren Antwort, gern von Hand bearbeitet")
    generation: GenerationIn | None = Field(
        None,
        description="metadata.generation der früheren Antwort; liefert Vorgaben für alles, was die Anfrage weglässt",
    )


_REQUIRED_BY_OP: dict[ChangeOp, tuple[str, ...]] = {
    ChangeOp.add: ("title",),
    ChangeOp.remove: ("key",),
    ChangeOp.rename: ("key", "title"),
    ChangeOp.edit: ("key", "properties"),
    ChangeOp.move: ("key",),  # `to` omitted or null: move to the top level
    ChangeOp.merge: ("keys", "title"),
    ChangeOp.split: ("key", "hint"),
}


class Change(RequestModel):
    op: ChangeOp = Field(description="Art der Änderung: add, remove, rename, edit, move, merge oder split")
    key: str | None = Field(None, description="Schlüssel des betroffenen Knotens (remove, rename, edit, move, split)")
    keys: list[str] | None = Field(
        None, description="Schlüssel der zusammenzuführenden Knoten, mindestens zwei (merge)"
    )
    parent: str | None = Field(None, description="add: Schlüssel oder Titel des Elternknotens; ohne Angabe Hauptebene")
    to: str | None = Field(
        None, description="move: Schlüssel des neuen Elternknotens; ohne Angabe oder null Hauptebene"
    )
    title: ShortText | None = Field(None, description="Neuer Titel (add, rename, merge)")
    properties: Properties | None = Field(None, description="Zu setzende Properties (edit)")
    hint: str | None = Field(None, max_length=1000, description="Wie der Knoten aufgeteilt werden soll (split)")

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


class Feedback(RequestModel):
    text: str | None = Field(
        None,
        max_length=8000,
        description="Rückmeldung als Freitext; das Sprachmodell setzt sie in Änderungen um oder stellt Rückfragen",
    )
    changes: list[Change] = Field(
        default_factory=list,
        max_length=200,
        description="Gezielte Änderungen; Struktur ohne Sprachmodell (außer split), neue Knoten danach beschrieben",
    )
    locked: list[str] = Field(
        default_factory=list,
        max_length=500,
        description="Schlüssel gesperrter Knoten; sie und ihr Ast bleiben unverändert",
    )


class TopicTreeRequestV2(RequestModel):
    mode: Mode = Field(
        description="create: neuer Baum; refine: current_tree mit feedback oder neuen items weiterentwickeln"
    )
    use_case: UseCase = Field(description="Quelle der Struktur: topic, document (Gliederung), folders oder contents")
    topic: str | None = Field(
        None,
        min_length=1,
        max_length=2000,
        description="Thema des Baums; Pflicht bei topic, bei document und contents optional zur Eingrenzung",
    )
    folders: list[FolderNode] | None = Field(None, description="Bestehende Ordnerstruktur (use_case folders)")
    items: list[Item] | None = Field(None, description="Materialien und Dokumente, je mit Rolle in use")
    items_ref: HttpsUrl | None = Field(
        None, description="HTTPS-Adresse einer JSON-Liste von items; nur von Hosts in REF_ALLOWED_HOSTS"
    )
    current_tree: CurrentTree | None = Field(None, description="Früheres Ergebnis (mode refine)")
    feedback: Feedback | None = Field(None, description="Rückmeldung zum current_tree (mode refine)")
    frame: Frame = Field(description="Fachlicher Rahmen als SkoHub-URIs; übernommen in die Knoten-Metadaten")
    shape: Shape = Field(default_factory=Shape, description="Form des Baums: Tiefe und Breite")
    hints: Hints = Field(default_factory=Hints, description="Inhaltliche Hinweise")
    options: Options = Field(default_factory=Options, description="Schalter für Zuordnung, Verbesserung und Metadaten")

    def effective_use(self, item: Item) -> set[ItemUse]:
        """Spec: without `use`, contents items are structure and content; everything else is content only.
        An explicit empty list means neither (the item is carried along, e.g. as a folder file, but not used)."""
        if item.use is not None:
            return set(item.use)
        if self.use_case == UseCase.contents:
            return {ItemUse.structure, ItemUse.content}
        return {ItemUse.content}
