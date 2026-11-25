"""The request context block: identical in every prompt of one request, placed right after the static system
prompt so the provider's prefix cache covers both (plan E2). Must be deterministic."""

from app.domain.shape_rules import EXTRA_TITLES
from app.pipeline.effective import ExplicitShape, explicit_shape, has_structure_inputs
from app.schemas.common import ExtraTopic, Mode, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.vocab.labels import label

_EXTRA_POSITION = {ExtraTopic.general: "vorn", ExtraTopic.methodology: "hinten"}


def _labels(uris: list[str], unknown: list[str]) -> str:
    names = []
    for uri in uris:
        name = label(uri)
        if name is None:
            unknown.append(uri)
            name = uri.rstrip("/").rsplit("/", 1)[-1]
        names.append(name)
    return ", ".join(names)


def _shape_line(req: TopicTreeRequestV2, explicit: ExplicitShape) -> str:
    shape = req.shape
    input_driven = has_structure_inputs(req)
    depth_part = f"{shape.depth} Ebenen (Vorgabe)" if explicit.depth else f"höchstens {shape.depth} Ebenen"
    if explicit.main_topics:
        main_part = f"Hauptebene {shape.main_topics.min} bis {shape.main_topics.max} Knoten insgesamt (Vorgabe)"
    elif input_driven:
        main_part = f"Hauptebene nach Struktur der Eingaben (bis höchstens {shape.main_topics.max} Knoten)"
    else:
        main_part = f"Hauptebene {shape.main_topics.min} bis {shape.main_topics.max} Knoten (Empfehlungsrahmen)"

    if explicit.children:
        child_part = f"je Knoten {shape.children.min} bis {shape.children.max} Kinder (Vorgabe)"
    elif input_driven:
        child_part = f"je Knoten nach Struktur der Eingaben (2 bis höchstens {shape.children.max} Kinder)"
    else:
        child_part = f"je Knoten {shape.children.min} bis {shape.children.max} Kinder (Empfehlungsrahmen)"
    return f"Form: {depth_part}; {main_part}; {child_part}"


def build_context_block(
    req: TopicTreeRequestV2, topic: str | None = None, *, explicit: ExplicitShape | None = None
) -> tuple[str, list[str]]:
    """Return (block, unknown vocabulary URIs)."""
    unknown: list[str] = []
    exp = explicit if explicit is not None else explicit_shape(req)
    hints, shape, frame = req.hints, req.shape, req.frame
    lines = ["## Anfragekontext"]
    if topic or req.topic:
        lines.append(f"Thema: {topic or req.topic}")
    for caption, uris in (
        ("Fach", frame.discipline_uri),
        ("Bildungsstufe", frame.educational_context_uri),
        ("Zielgruppe", frame.intended_end_user_role_uri),
    ):
        if uris:
            lines.append(f"{caption}: {_labels(uris, unknown)}")
    if hints.context:
        lines.append(f"Zweck und Kontext: {hints.context}")
    if hints.include:
        lines.append(f"Unbedingt aufnehmen: {'; '.join(hints.include)}")
    if hints.exclude:
        lines.append(f"Ausschließen: {'; '.join(hints.exclude)}")
    lines.append(f"Ordnungsprinzip (Vorgabe): {hints.order}" if hints.order else "Ordnungsprinzip: keine Vorgabe")
    lines.append(_shape_line(req, exp))
    if shape.extra_topics and req.mode == Mode.create and req.use_case == UseCase.topic:
        extras = ", ".join(f"„{EXTRA_TITLES[e]}“ ({_EXTRA_POSITION[e]})" for e in shape.extra_topics)
        lines.append(
            f"Zusatzthemen auf der Hauptebene (zählen zur Gesamtzahl der Hauptebene dazu, samt Unterthemen): {extras}"
        )
    words = hints.description_length
    lo, hi = max(20, int(words * 0.75)), int(words * 1.2)
    lines.append(f"Beschreibungen: {lo} bis {hi} Wörter (Ziel {words} Wörter) je Knoten, auch auf der untersten Ebene")
    lines.append(f"Sprache: {hints.language}")
    return "\n".join(lines), unknown
