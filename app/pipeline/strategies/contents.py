"""Use case `contents`: groups are induced from the items themselves; assignment with confidence follows."""

import re

from app.domain.keys import assign_missing_keys
from app.domain.quality import PLATFORM_STOPWORDS
from app.domain.shape_rules import eliminate_generated_duplicates
from app.domain.text import truncate_sentences
from app.domain.tree import collapse_single_children
from app.pipeline.inputs_block import structure_inputs_block
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.group_contents import group_contents
from app.pipeline.steps.node_conversion import Cut, to_nodes
from app.schemas.common import ItemUse, OriginType
from app.schemas.request_v2 import Item, TopicTreeRequestV2
from app.schemas.response_v2 import StructureInfo
from app.vocab.labels import label

SAMPLE_SIZE = 300
MAX_TITLES = 2000
_TEXT = 200
_WORD = re.compile(r"[^\W\d_]{4,}")


def _detail(item: Item) -> str:
    p = item.properties
    parts = [f"- id: {item.id}", p.first("cm:title") or "(ohne Titel)"]
    disciplines = list(dict.fromkeys(lbl for uri in p.values("ccm:taxonid") if (lbl := label(uri))))
    if disciplines:
        parts.append("Fach: " + ", ".join(disciplines[:3]))
    if description := p.first("cm:description"):
        parts.append(truncate_sentences(description, _TEXT))
    if keywords := p.values("cclom:general_keyword"):
        parts.append("Schlagworte: " + ", ".join(keywords[:8]))
    return " | ".join(parts)


def _stratum(item: Item) -> str:
    p = item.properties
    discipline = (p.first("ccm:taxonid") or "").strip()
    if discipline:
        canonical = label(discipline) or discipline.rstrip("/").replace("https://", "http://", 1)
        return f"d:{canonical.casefold()}"
    for kw in p.values("cclom:general_keyword"):
        low = kw.strip().casefold()
        if low and low not in PLATFORM_STOPWORDS:
            return f"k:{low}"
    title = p.first("cm:title") or ""
    for match in _WORD.finditer(title):
        low = match.group(0).casefold()
        if low not in PLATFORM_STOPWORDS:
            return f"t:{low}"
    return "_other"


def _even_pick(indices: list[int], count: int) -> list[int]:
    if count <= 0:
        return []
    if count >= len(indices):
        return indices
    step = len(indices) / count
    return [indices[int(i * step)] for i in range(count)]


def _sample(items: list[Item]) -> list[Item]:
    if len(items) <= SAMPLE_SIZE:
        return items
    strata: dict[str, list[int]] = {}
    for idx, item in enumerate(items):
        strata.setdefault(_stratum(item), []).append(idx)
    if len(strata) == 1:
        return [items[i] for i in _even_pick(list(range(len(items))), SAMPLE_SIZE)]

    quotas = {key: 0 for key in strata}
    remaining = SAMPLE_SIZE
    # Prioritize larger strata when > SAMPLE_SIZE distinct strata exist; ties keep insertion order.
    active = sorted(strata.keys(), key=lambda key: -len(strata[key]))
    while remaining > 0 and active:
        next_active: list[str] = []
        for key in active:
            if remaining == 0:
                break
            if quotas[key] < len(strata[key]):
                quotas[key] += 1
                remaining -= 1
                if quotas[key] < len(strata[key]):
                    next_active.append(key)
        active = next_active

    chosen = sorted(idx for key, count in quotas.items() if count > 0 for idx in _even_pick(strata[key], count))
    return [items[i] for i in chosen]


def items_block(items: list[Item], rc: RunContext) -> str:
    sample = _sample(items)
    lines = [_detail(item) for item in sample]
    if len(sample) < len(items):
        chosen = {item.id for item in sample}
        rest = [i for i in items if i.id not in chosen]
        if len(rest) > MAX_TITLES:
            rc.warn("ITEMS_SAMPLED", f"Nur {MAX_TITLES} weitere Titel flossen in die Gruppenbildung ein.", step="group")
            rest = rest[:MAX_TITLES]
        lines.append("\nWeitere Titel:")
        lines.extend(f"- {(i.properties.first('cm:title') or i.id)[:80]}" for i in rest)
    return "\n".join(lines)


def _max_tokens(req: TopicTreeRequestV2) -> int:
    """Output budget for the largest grouping the shape allows, summed over every level."""
    groups = sum(req.shape.main_topics.max * req.shape.children.max**level for level in range(req.shape.depth))
    return min(32000, 1000 + groups * (req.hints.description_length * 2 + 60))


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    shaping = [i for i in req.items or [] if ItemUse.structure in req.effective_use(i)]
    # Full texts of shaping items (e.g. a curriculum) and the folder structure come in as supplementary inputs.
    with_text = [i for i in shaping if i.fulltext and i.fulltext.text and i.fulltext.text.strip()]
    inputs = structure_inputs_block(req, rc, items=with_text)
    grouping = await group_contents(items_block(shaping, rc), rc, max_tokens=_max_tokens(req), inputs_block=inputs)

    cut = Cut()
    shape = req.shape
    roots = to_nodes(
        grouping.groups, shape.depth, shape.main_topics.max, cut, OriginType.cluster, child_width=shape.children.max
    )
    if cut.depth:
        rc.warn("SHAPE_DEPTH", "Die Gruppenbildung war zu tief und wurde gekürzt.", step="group_contents")
    if cut.width:
        rc.warn("SHAPE_WIDTH", "Die Gruppenbildung hatte zu viele Gruppen; gekürzt.", step="group_contents")
    eliminate_generated_duplicates(roots)
    # Invented groups never keep a lone subgroup (system prompt rule); dissolving it is safe before assignment.
    collapse_single_children(roots)
    assign_missing_keys(roots)
    return StrategyResult(
        roots=roots,
        title=req.topic or "Sammlung aus Inhalten",
        description=grouping.description,
        structure=StructureInfo(
            order=req.hints.order or grouping.order,
            levels=grouping.levels[: req.shape.depth],
            source="hint" if req.hints.order else "detected",
        ),
    )
