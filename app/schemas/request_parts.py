"""Generation settings of a v2 request: frame, shape, hints and options (also echoed in `metadata.generation`)."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ExtraTopic

ShortText = Annotated[str, Field(min_length=1, max_length=200)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Frame(RequestModel):
    discipline_uri: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Fächer als SkoHub-URIs (Vokabular discipline); prägen Inhalt und Knoten-Metadaten",
    )
    educational_context_uri: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Bildungsstufen als SkoHub-URIs (educationalContext); bestimmen den Rahmen für die Form",
    )
    intended_end_user_role_uri: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Zielgruppen als SkoHub-URIs (intendedEndUserRole), etwa Lehrkräfte oder Lernende",
    )


class MainRange(RequestModel):
    min: int = Field(6, ge=1, le=20, description="Mindestzahl der Hauptthemen (Ebene 1)")
    max: int = Field(
        12, ge=1, le=20, description="Höchstzahl der Hauptthemen (Ebene 1); begrenzt durch MAX_NODES_PER_LEVEL"
    )

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        # With one bound sent, the default of the other one yields (e.g. {"max": 4} gives min 4, not an error);
        # the service later fills it from the recommended or inherited range.
        # Written to __dict__ so the clamped bound does not count as sent (model_fields_set stays as it was).
        sent = self.model_fields_set
        if self.min > self.max and sent == {"max"}:
            self.__dict__["min"] = self.max
        elif self.min > self.max and sent == {"min"}:
            self.__dict__["max"] = self.min
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class ChildRange(MainRange):
    # A node never gets exactly one child, so the lower bound is 2.
    min: int = Field(3, ge=2, le=20, description="Mindestzahl der Unterthemen je Knoten (nie genau eines)")
    max: int = Field(
        8, ge=2, le=20, description="Höchstzahl der Unterthemen je Knoten; begrenzt durch MAX_NODES_PER_LEVEL"
    )


class Shape(RequestModel):
    depth: int = Field(
        3,
        ge=1,
        le=4,
        description="Anzahl der Ebenen, höchstens MAX_TREE_DEPTH; ohne shape nach Bildungsstufe und Eingabe",
    )
    main_topics: MainRange = Field(
        default_factory=MainRange,
        description="Spanne der Hauptthemen; eine einzelne Grenze übernimmt die andere aus dem Empfehlungsrahmen",
    )
    children: ChildRange = Field(default_factory=ChildRange, description="Spanne der Unterthemen je Knoten")
    extra_topics: list[ExtraTopic] = Field(
        default_factory=list,
        description="Zusätzliche Hauptthemen: general (Allgemeines) und/oder methodology (Methodik und Didaktik)",
    )


class Hints(RequestModel):
    context: str | None = Field(
        None, max_length=2000, description="Freitext zu Zweck und Kontext des Baums, etwa Zielgruppe oder Einsatz"
    )
    include: list[ShortText] = Field(
        default_factory=list, max_length=50, description="Begriffe, die im Baum vorkommen sollen"
    )
    exclude: list[ShortText] = Field(
        default_factory=list, max_length=50, description="Begriffe, die nicht vorkommen sollen"
    )
    order: str | None = Field(
        None, max_length=200, description="Gewünschtes Ordnungsprinzip, etwa „chronologisch“ oder „nach Kompetenzen“"
    )
    description_length: int = Field(60, ge=40, le=200, description="Ziellänge der Beschreibungen in Wörtern")
    language: str = Field(
        "de", pattern=r"^[a-z]{2}$", description="Sprache der Titel und Beschreibungen als ISO-639-1-Code"
    )


class Options(RequestModel):
    improve: bool = Field(
        False, description="folders: Verbesserungen der Ordnerstruktur vorschlagen; sie kommen als changes zurück"
    )
    assign_contents: bool = Field(True, description="Inhalte aus items den Knoten zuordnen")
    assign_only: bool = Field(
        False,
        description="refine: nur neue Inhalte einsortieren, Struktur bleibt; gilt nur für diesen Aufruf",
    )
    multi_assign: bool = Field(True, description="Ein Inhalt darf mehreren Knoten zugeordnet werden")
    min_confidence: float = Field(
        0.6,
        ge=0,
        le=1,
        description="Mindestkonfidenz einer Zuordnung; darunter landet der Inhalt mit low_confidence in unassigned",
    )
    auto_metadata: bool = Field(
        False, description="Fach, Bildungsstufe und Zielgruppe je Knoten verengen, wenn frame leer oder mehrwertig ist"
    )
