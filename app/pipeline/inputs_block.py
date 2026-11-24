"""Compact prompt block for supplementary structure inputs (items with `use: structure` outside their own use
case). Only inline full texts are used here; referenced texts are loaded before (see inputs/refs.py)."""

from app.domain.text import truncate_sentences
from app.pipeline.run_context import RunContext
from app.schemas.common import ItemUse
from app.schemas.request_v2 import TopicTreeRequestV2

MAX_ITEMS = 50
MAX_FULLTEXT = 5
DESC_LIMIT = 300
EXCERPT = 1500


def structure_inputs_block(req: TopicTreeRequestV2, rc: RunContext | None = None) -> str:
    all_items = [i for i in req.items or [] if ItemUse.structure in req.effective_use(i)]
    if not all_items:
        return ""
    if len(all_items) > MAX_ITEMS and rc is not None:
        rc.warn(
            "INPUTS_TRUNCATED",
            f"Nur {MAX_ITEMS} von {len(all_items)} ergänzenden Struktur-Items flossen in die Strukturplanung ein.",
            step="inputs",
        )
    items = all_items[:MAX_ITEMS]
    lines = ["## Ergänzende Eingaben (dürfen zusätzliche Themen anregen)"]
    fulltext_shown = 0
    for item in items:
        title = item.properties.first("cm:title") or item.id
        parts = [f"- {title}"]
        if description := item.properties.first("cm:description"):
            parts.append(truncate_sentences(description, DESC_LIMIT))
        if keywords := item.properties.values("cclom:general_keyword"):
            parts.append("Schlagworte: " + ", ".join(keywords[:8]))
        lines.append(
            " | ".join(parts) if len(parts) > 2 else (f"{parts[0]}: {parts[1]}" if len(parts) == 2 else parts[0])
        )
        if fulltext_shown < MAX_FULLTEXT and item.fulltext and item.fulltext.text and item.fulltext.text.strip():
            lines.append(f"  Auszug: {truncate_sentences(item.fulltext.text, EXCERPT)}")
            fulltext_shown += 1
    return "\n".join(lines) + "\n"
