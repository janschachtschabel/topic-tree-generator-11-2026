"""Response format of POST /v2/topic-tree (Spec: "Antwort"), plus the documented additions (plan E10)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ChangeOp, ChangeSource, Mode, NodeStatus, OriginType, UnassignedReason, UseCase
from app.schemas.properties import Properties
from app.schemas.request_v2 import FeedbackEntry, Frame, Hints, Options, Shape


class _Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ContentRef(_Out):
    id: str = Field(description="id des Inhalts aus der Anfrage")
    node_id: str | None = Field(
        None, alias="nodeId", description="Knoten-ID im Repository, unverändert aus der Anfrage"
    )
    confidence: float = Field(
        1.0, ge=0, le=1, description="Konfidenz der Zuordnung zwischen 0 und 1 (1 bei Übernahme aus folders)"
    )


class Origin(_Out):
    type: OriginType = Field(description="Woher der Knoten stammt: topic, document, folder, cluster oder feedback")
    id: str | None = Field(None, description="id des Eintrags in items, aus dem der Knoten stammt (document)")
    section: str | None = Field(None, description="Abschnitt im Dokument (document)")
    page: int | None = Field(None, description="Seite im Dokument, falls Seitenmarken vorhanden sind (document)")
    path: str | None = Field(None, description="Ordnerpfad (folders)")


class NodeOut(_Out):
    key: str = Field(description="Stabiler Schlüssel des Knotens; bleibt über refine-Läufe erhalten")
    node_id: str | None = Field(
        None, alias="nodeId", description="Knoten-ID der Sammlung im Repository, unverändert aus current_tree"
    )
    title: str = Field(description="Titel des Knotens")
    shorttitle: str = Field(description="Kurztitel, höchstens 20 Zeichen")
    status: NodeStatus = Field(
        description="Änderungsstand gegenüber current_tree: new, unchanged, changed, moved oder suggested"
    )
    origin: Origin | None = Field(None, description="Herkunft des Knotens")
    confidence: float | None = Field(None, ge=0, le=1, description="Konfidenz, falls der Knoten nur vorgeschlagen ist")
    properties: Properties = Field(
        default_factory=Properties,
        description="edu-sharing-Properties des Knotens, etwa cm:title, cclom:general_description, ccm:taxonid",
    )
    contents: list[ContentRef] = Field(default_factory=list, description="Zugeordnete Inhalte")
    subcollections: list["NodeOut"] = Field(default_factory=list, description="Unterknoten")


class Unassigned(_Out):
    id: str = Field(description="id des nicht zugeordneten Inhalts")
    node_id: str | None = Field(
        None, alias="nodeId", description="Knoten-ID im Repository, unverändert aus der Anfrage"
    )
    reason: UnassignedReason = Field(description="Grund: off_topic, low_confidence, no_matching_node oder excluded")


class ChangeRecord(_Out):
    op: ChangeOp = Field(description="Art der Änderung")
    key: str | None = Field(None, description="Schlüssel des betroffenen oder neuen Knotens")
    keys: list[str] | None = Field(None, description="Schlüssel der zusammengeführten Knoten (merge)")
    parent: str | None = Field(None, description="Schlüssel des Elternknotens eines neuen Knotens (add)")
    to: str | None = Field(None, description="Schlüssel des neuen Elternknotens (move)")
    title: str | None = Field(None, description="Neuer Titel")
    source: ChangeSource = Field(
        alias="from", description="Auslöser: feedback_text, feedback_changes oder service (Vorschlag des Dienstes)"
    )


class Question(_Out):
    text: str = Field(description="Rückfrage zu einer unklaren Rückmeldung")
    key: str | None = Field(None, description="Schlüssel des betroffenen Knotens")
    options: list[str] | None = Field(None, description="Antwortmöglichkeiten")


class ServiceWarning(_Out):
    code: str = Field(description="Fester Code, etwa LLM_DEGRADED, DESCRIBE_FAILED oder SHAPE_SINGLE_CHILD")
    message: str = Field(description="Erklärung für Menschen")
    key: str | None = Field(None, description="Schlüssel des betroffenen Knotens")
    step: str | None = Field(None, description="Verarbeitungsschritt, in dem die Warnung entstand")


class StructureInfo(_Out):
    order: str = Field(description="Ordnungsprinzip des Baums")
    levels: list[str] = Field(default_factory=list, description="Bedeutung der Ebenen, von oben nach unten")
    source: Literal["hint", "detected", "input"] = Field(
        description="Herkunft der Ordnung: hint (aus hints.order), detected (erkannt) oder input (aus der Eingabe)"
    )


class ItemCounts(_Out):
    structure: int = Field(0, description="Anzahl der Einträge mit Rolle structure")
    content: int = Field(0, description="Anzahl der Einträge mit Rolle content")


class InputCounts(_Out):
    folders: int = Field(0, description="Anzahl der übergebenen Ordner")
    items: ItemCounts = Field(default_factory=ItemCounts, description="Anzahl der Einträge je Rolle")


class Usage(_Out):
    llm_calls: int = Field(0, description="Anzahl der LLM-Aufrufe")
    failed_calls: int = Field(0, description="Davon fehlgeschlagen")
    prompt_tokens: int = Field(0, description="Eingabe-Tokens")
    cached_tokens: int = Field(0, description="Davon aus dem Prompt-Cache des Anbieters")
    completion_tokens: int = Field(0, description="Ausgabe-Tokens")
    duration_ms: int = Field(0, description="Dauer der Verarbeitung in Millisekunden")


class Generation(_Out):
    mode: Mode = Field(description="Modus dieses Laufs")
    use_case: UseCase = Field(description="Use Case dieses Laufs")
    topic: str | None = Field(None, description="Thema dieses Laufs")
    frame: Frame = Field(description="Wirksamer Rahmen")
    shape: Shape = Field(description="Wirksame Form")
    hints: Hints = Field(description="Wirksame Hinweise")
    options: Options = Field(description="Wirksame Optionen")
    inputs: InputCounts = Field(default_factory=InputCounts, description="Anzahl der Eingaben")
    feedback: list[FeedbackEntry] = Field(default_factory=list, description="Alle bisherigen Rückmeldungen")
    structure: StructureInfo | None = Field(None, description="Erkannte oder vorgegebene Ordnung")
    usage: Usage | None = Field(None, description="Verbrauch dieses Laufs")
    generator_version: str = Field(description="Version des Dienstes")
    model: str | None = Field(None, description="Name der Route bzw. des Modells, die angefragt wurden")


class Metadata(_Out):
    title: str = Field(description="Titel des Baums")
    description: str = Field("", description="Beschreibung des Baums")
    target_audience: str = Field("Lehrkräfte", description="Zielgruppe in Worten")
    created_at: str = Field(description="Zeitpunkt der Erzeugung (ISO 8601)")
    author: str = Field("Themenbaum Generator", description="Erzeuger")
    schema_version: str = Field("2.0", description="Version dieses Antwortformats")
    version: str = Field(description="Version des Baums (v1, v2, …); steigt mit jedem refine")
    based_on: str | None = Field(None, description="Version, auf der dieser Baum aufbaut")
    vocab_labels: dict[str, str] = Field(
        default_factory=dict, description="Deutsche Bezeichnungen der verwendeten Vokabular-URIs"
    )
    generation: Generation = Field(
        description="Wirksame Vorgaben dieses Laufs; für den nächsten refine als current_tree.generation zurückgeben"
    )


class TopicTreeResponseV2(_Out):
    metadata: Metadata = Field(description="Angaben zum Baum und zum Lauf")
    collection: list[NodeOut] = Field(description="Der Baum: Hauptthemen mit Unterknoten")
    unassigned: list[Unassigned] = Field(
        default_factory=list, description="Inhalte, die keinem Knoten zugeordnet wurden, mit Grund"
    )
    changes: list[ChangeRecord] = Field(default_factory=list, description="Angewendete und vorgeschlagene Änderungen")
    questions: list[Question] = Field(
        default_factory=list, description="Rückfragen zu unklarer Rückmeldung; der Baum bleibt dafür unverändert"
    )
    warnings: list[ServiceWarning] = Field(
        default_factory=list,
        description="Was nicht gelungen ist oder auffiel; ein Schritt ohne Ergebnis steht immer hier",
    )

    def dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
