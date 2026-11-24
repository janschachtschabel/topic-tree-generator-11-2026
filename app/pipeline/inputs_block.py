"""Compact prompt block for supplementary structure inputs (items with `use: structure` outside their own use
case). Only inline full texts are used here; referenced texts are loaded before (see inputs/refs.py)."""

from app.schemas.common import ItemUse
from app.schemas.request_v2 import TopicTreeRequestV2

MAX_ITEMS = 5
EXCERPT = 1500


def structure_inputs_block(req: TopicTreeRequestV2) -> str:
    items = [i for i in req.items or [] if ItemUse.structure in req.effective_use(i)][:MAX_ITEMS]
    if not items:
        return ""
    lines = ["## Ergänzende Eingaben (dürfen zusätzliche Themen anregen)"]
    for item in items:
        title = item.properties.first("cm:title") or item.id
        description = item.properties.first("cm:description")
        lines.append(f"- {title}" + (f": {description}" if description else ""))
        if item.fulltext and item.fulltext.text:
            lines.append(f"  Auszug: {item.fulltext.text[:EXCERPT]}")
    return "\n".join(lines) + "\n"
