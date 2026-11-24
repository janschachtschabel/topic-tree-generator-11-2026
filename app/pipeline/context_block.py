"""The request context block: identical in every prompt of one request, placed right after the static system
prompt so the provider's prefix cache covers both (plan E2). Must be deterministic."""

from app.schemas.common import ExtraTopic
from app.schemas.request_v2 import TopicTreeRequestV2
from app.vocab.labels import label

_EXTRA = {ExtraTopic.general: "„Allgemeines“ (vorn)", ExtraTopic.methodology: "„Methodik und Didaktik“ (hinten)"}


def _labels(uris: list[str], unknown: list[str]) -> str:
    names = []
    for uri in uris:
        name = label(uri)
        if name is None:
            unknown.append(uri)
            name = uri.rstrip("/").rsplit("/", 1)[-1]
        names.append(name)
    return ", ".join(names)


def build_context_block(req: TopicTreeRequestV2, topic: str | None = None) -> tuple[str, list[str]]:
    """Return (block, unknown vocabulary URIs)."""
    unknown: list[str] = []
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
    lines.append(
        f"Form: {shape.depth} Ebenen; Hauptebene {shape.main_topics.min} bis {shape.main_topics.max} Knoten; "
        f"je Knoten {shape.children.min} bis {shape.children.max} Kinder"
    )
    if shape.extra_topics:
        extras = ", ".join(_EXTRA[e] for e in shape.extra_topics)
        lines.append(f"Zusatzthemen (fügt der Dienst selbst ein, nicht erzeugen): {extras}")
    words = hints.description_length
    lo, hi = max(20, int(words * 0.75)), int(words * 1.2)
    lines.append(f"Beschreibungen: {lo} bis {hi} Wörter (Ziel {words} Wörter) je Knoten, auch auf der untersten Ebene")
    lines.append(f"Sprache: {hints.language}")
    return "\n".join(lines), unknown
