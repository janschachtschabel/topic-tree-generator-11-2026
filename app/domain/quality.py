"""Deterministic content and naming quality checks and keyword hygiene.

Inspired by empirical error patterns observed across LLM-free and LLM-generated topic trees:
- Platform/educational stopwords in keywords are stripped deterministically (never touching locked nodes).
- Generic catch-all headings, facet-as-node mistakes, non-history temporal headings, and top-level topic repeats
  are reported as warnings without silently deleting nodes.
"""

import re
from collections.abc import Iterable

from app.domain.tree import Node, walk
from app.schemas.common import OriginType
from app.schemas.response_v2 import ServiceWarning

STEP = "quality_rules"

PLATFORM_STOPWORDS: frozenset[str] = frozenset(
    {
        "allgemeines",
        "anhang",
        "arbeitsauftrag",
        "arbeitsaufträge",
        "arbeitsblatt",
        "arbeitsblätter",
        "aufgabe",
        "aufgaben",
        "datei",
        "didaktik",
        "dokument",
        "einführung",
        "einleitung",
        "kapitel",
        "klassenarbeit",
        "klausur",
        "kompetenz",
        "kompetenzen",
        "lehrplan",
        "lernvideo",
        "lernvideos",
        "lernziel",
        "lernziele",
        "lösung",
        "lösungen",
        "materialien",
        "medien",
        "methodik",
        "online",
        "ordner",
        "pdf",
        "portal",
        "quiz",
        "sammlung",
        "schule",
        "sonstiges",
        "thema",
        "überblick",
        "übersicht",
        "übung",
        "übungen",
        "unterricht",
        "unterrichtsmaterial",
        "video",
        "videos",
    }
)

_GENERIC_TITLES: frozenset[str] = frozenset(
    {
        "allgemeines",
        "anhang",
        "didaktik und methodik",
        "einführung",
        "einleitung",
        "einzelnachweise",
        "fazit",
        "methodik und didaktik",
        "siehe auch",
        "sonstiges",
        "überblick",
        "übersicht",
        "verschiedenes",
        "weblinks",
        "weitere aspekte",
        "weiteres",
        "zusammenfassung",
    }
)

_FACET_TITLES: frozenset[str] = frozenset(
    {
        "arbeitsblatt",
        "arbeitsblätter",
        "aufgaben",
        "didaktik",
        "grundschule",
        "gymnasium",
        "klassenarbeit",
        "klassenarbeiten",
        "klausuren",
        "kompetenzbereich",
        "kompetenzen",
        "lernkontrolle",
        "lernvideo",
        "lernvideos",
        "lernziele",
        "materialien",
        "methodik",
        "mittelstufe",
        "oberstufe",
        "primarstufe",
        "quiz",
        "sekundarstufe",
        "sekundarstufe i",
        "sekundarstufe ii",
        "sozialformen",
        "übung",
        "übungen",
        "unterrichtsmaterial",
        "unterrichtsphasen",
        "unterstufe",
        "video",
        "videos",
    }
)

_TEMPORAL_RE = re.compile(
    r"^(?:"
    r"\d{4}er(?:\s+jahre)?|"
    r"(?:(?:anfang|mitte|ende)\s+des\s+|(?:frühes|spätes)\s+)?\d{1,2}\.\s*jahrhunderts?|"
    r"\d{4}\s*[–-]\s*\d{4}"
    r")$",
    re.IGNORECASE,
)

_FACET_RE = re.compile(
    r"^(?:"
    r"klasse\s+\d+(?:\s*[–-]\s*\d+)?|"
    r"jahrgang(?:sstufe)?\s+\d+(?:\s*[–-]\s*\d+)?|"
    r"lernjahr\s+\d+|"
    r"niveau\s+[abc]\d(?:\.\d)?|"
    r"sekundarstufe\s+(?:i{1,2}|1|2)"
    r")$",
    re.IGNORECASE,
)

_HISTORY_HINTS = ("geschichte", "historisch", "archäolog", "epoche", "zeitalter", "antike", "mittelalter", "neuzeit")
_SPACES = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACES.sub(" ", text).strip().casefold()


def is_history_context(topic: str | None, discipline_labels: Iterable[str] = (), *, order: str | None = None) -> bool:
    """Return True when topic, discipline metadata, or requested order allows temporal headings."""
    if order and "chronolog" in order.casefold():
        return True
    haystack = " ".join(part for part in (topic or "", *discipline_labels) if part).casefold()
    return any(hint in haystack for hint in _HISTORY_HINTS)


def clean_keywords(roots: list[Node], *, protected: set[str] | None = None) -> None:
    """Deduplicate keywords and remove platform stopwords in place (protected keys stay untouched)."""
    locked = protected or set()
    for node, _, _ in walk(roots):
        if (node.key and node.key in locked) or not node.keywords:
            continue
        title_norm = _norm(node.title)
        seen: set[str] = set()
        kept: list[str] = []
        title_match: str | None = None
        for raw in node.keywords:
            cleaned = _SPACES.sub(" ", raw).strip()
            low = cleaned.casefold()
            if not cleaned or low in PLATFORM_STOPWORDS or low in seen:
                continue
            seen.add(low)
            if low == title_norm:
                title_match = cleaned
            else:
                kept.append(cleaned)
        if not kept and title_match is not None:
            kept.append(title_match)
        node.keywords = kept


def _warn(code: str, message: str, key: str | None) -> ServiceWarning:
    return ServiceWarning(code=code, message=message, key=key, step=STEP)


def check_quality(
    roots: list[Node],
    *,
    topic: str | None = None,
    allowed_extra: set[str] | None = None,
    is_history: bool = False,
) -> list[ServiceWarning]:
    """Report naming and taxonomy anti-patterns on generated nodes (caller folder trees are skipped)."""
    allowed = {_norm(a) for a in (allowed_extra or set())}
    topic_norm = _norm(topic) if topic else ""
    warnings: list[ServiceWarning] = []

    for node, _, depth in walk(roots):
        if node.origin is not None and node.origin.type == OriginType.folder:
            continue
        title_norm = _norm(node.title)
        if not title_norm or (depth == 1 and title_norm in allowed):
            continue
        if depth == 1 and topic_norm and title_norm == topic_norm:
            warnings.append(_warn("TOPIC_REPEAT", f"Hauptknoten „{node.title}“ wiederholt das Gesamtthema.", node.key))
            continue
        if title_norm in _GENERIC_TITLES or (not is_history and _TEMPORAL_RE.match(title_norm)):
            warnings.append(
                _warn(
                    "GENERIC_TITLE", f"„{node.title}“ ist eine allgemeine oder zeitliche Sammelüberschrift.", node.key
                )
            )
            continue
        if title_norm in _FACET_TITLES or _FACET_RE.match(title_norm):
            warnings.append(
                _warn("FACET_AS_NODE", f"„{node.title}“ wirkt wie eine Facette statt eines Themenknotens.", node.key)
            )
    return warnings
