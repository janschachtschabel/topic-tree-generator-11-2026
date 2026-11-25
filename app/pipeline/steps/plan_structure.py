"""Step 1 of a generated tree: order principle and full title-only skeleton across all requested levels. One LLM call."""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.domain.shape_rules import EXTRA_TITLES, extra_kind
from app.domain.tree import Node
from app.pipeline.run_context import RunContext
from app.pipeline.steps.node_conversion import Cut
from app.prompts import render
from app.schemas.common import ExtraTopic, NodeStatus, OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin, StructureInfo

STEP = "plan_structure"
_EXTRA_POS = {ExtraTopic.general: "vorn", ExtraTopic.methodology: "hinten"}


class PlannedChild(BaseModel):
    title: str
    shorttitle: str
    children: list["PlannedChild"] = Field(default_factory=list)


PlannedChild.model_rebuild()


class PlannedMain(BaseModel):
    title: str
    shorttitle: str
    from_inputs: bool = False
    children: list[PlannedChild] = Field(default_factory=list)


class StructurePlan(BaseModel):
    order: str
    levels: list[str]
    rationale: str
    description: str
    main_topics: list[PlannedMain]


@dataclass
class PlanResult:
    roots: list[Node]
    structure: StructureInfo
    description: str


def _order_instruction(req: TopicTreeRequestV2) -> str:
    if req.hints.order:
        return f"Nutze das vorgegebene Ordnungsprinzip „{req.hints.order}“ für die oberste Ebene."
    return "Es ist keines vorgegeben. Wähle es nach den Regeln für Ordnungsprinzipien im Systemprompt."


def _main_instruction(req: TopicTreeRequestV2, rc: RunContext, *, has_inputs: bool) -> str:
    lo, hi = req.shape.main_topics.min, req.shape.main_topics.max
    extras = req.shape.extra_topics
    n_extra = len(extras)
    explicit = rc.explicit_shape.main_topics
    extra_names = ", ".join(f"„{EXTRA_TITLES[e]}“ ({_EXTRA_POS[e]})" for e in extras)

    if not explicit and has_inputs:
        extra_clause = f" einschließlich {extra_names}" if extras else ""
        return (
            f"Es ist keine feste Breite vorgegeben: Richte die Hauptthemen stark an den ergänzenden Eingaben aus "
            f"(bis höchstens {hi} Hauptthemen insgesamt{extra_clause}); geben die Eingaben keinen klaren Umfang vor, "
            "bewege dich im Empfehlungsrahmen von 5 bis 15 fachlich trennscharfen Hauptthemen."
        )

    if extras:
        reg_lo, reg_hi = max(0, lo - n_extra), max(0, hi - n_extra)
        return (
            f"Die Hauptebene umfasst insgesamt {lo} bis {hi} Hauptthemen einschließlich {extra_names}: "
            f"Erzeuge {reg_lo} bis {reg_hi} fachliche Hauptthemen plus {extra_names} (jeweils mit passenden "
            f"Unterthemen), sodass `main_topics` insgesamt {lo} bis {hi} Einträge hat. "
            f"Bewege dich in diesem Korridor ({lo}–{hi}); wähle innerhalb der Spanne nur so viele Knoten, "
            "wie fachlich trennscharf sind."
        )

    frame_kind = "verbindlichen Korridor" if explicit else "Empfehlungsrahmen"
    return (
        f"Erzeuge {lo} bis {hi} Hauptthemen. Bewege dich in diesem {frame_kind} ({lo}–{hi}) und wähle innerhalb "
        "der Spanne nur so viele Knoten, wie fachlich trennscharf sind."
    )


def _children_instruction(req: TopicTreeRequestV2, rc: RunContext, *, has_inputs: bool) -> str:
    depth = req.shape.depth
    if depth < 2:
        return "Erzeuge keine Unterthemen; der Baum hat nur eine Ebene."
    c = req.shape.children
    span = (
        f"nach Struktur der Eingaben (2 bis höchstens {c.max})"
        if (not rc.explicit_shape.children and has_inputs)
        else f"{c.min} bis {c.max}"
    )
    if depth == 2:
        return (
            f"Erzeuge je Hauptthema {span} Unterthemen (2 Ebenen gesamt, nur Titel und Kurztitel), "
            "trenn- und fachlich scharf ohne Überschneidung."
        )
    return (
        f"Erzeuge den gesamten Baum über alle {depth} Ebenen (nur Titel und Kurztitel): "
        f"je Elternknoten {span} Kinder auf jeder Unterebene, auf Ebene {depth} ohne weitere Kinder."
    )


_TOKENS_PER_NODE = 32  # title + shorttitle + JSON punctuation of one skeleton node, with headroom
_MAX_PLAN_TOKENS = 32000  # same ceiling as the other tree-producing steps


def _max_tokens(req: TopicTreeRequestV2) -> int:
    """Output budget for the worst case the shape allows; a truncated skeleton would fail the whole request."""
    shape = req.shape
    mains = max(shape.main_topics.max, len(shape.extra_topics))
    width = shape.children.max
    estimated_nodes = sum(mains * (width**level) for level in range(shape.depth))
    return max(4000, min(_MAX_PLAN_TOKENS, 1000 + estimated_nodes * _TOKENS_PER_NODE))


def _node(title: str, shorttitle: str, children: list[Node], suggested: bool = False) -> Node:
    return Node(
        key=None,
        title=title.strip(),
        shorttitle=shorttitle.strip(),
        origin=Origin(type=OriginType.topic),
        status=NodeStatus.suggested if suggested else None,
        children=children,
    )


def _convert_children(items: list[PlannedChild], levels_left: int, width: int, cut: Cut) -> list[Node]:
    if levels_left <= 0:
        cut.depth = cut.depth or bool(items)
        return []
    cut.width = cut.width or len(items) > width
    return [
        _node(item.title, item.shorttitle, _convert_children(item.children, levels_left - 1, width, cut))
        for item in items[:width]
    ]


def _limit_mains(mains: list[PlannedMain], req: TopicTreeRequestV2, rc: RunContext) -> list[PlannedMain]:
    extras = set(req.shape.extra_topics)
    max_regular = max(0, req.shape.main_topics.max - len(extras))
    kept: list[PlannedMain] = []
    regular_count = 0
    seen_extras: set[ExtraTopic] = set()
    for item in mains:
        kind = extra_kind(item.title)
        if kind in extras and kind not in seen_extras:
            seen_extras.add(kind)
            kept.append(item)
        else:
            regular_count += 1
            if regular_count <= max_regular:
                kept.append(item)
    if regular_count > max_regular:
        rc.warn(
            "SHAPE_WIDTH",
            f"Hauptthemen auf insgesamt höchstens {max(req.shape.main_topics.max, len(extras))} gekürzt.",
            step=STEP,
        )
    return kept


async def plan_structure(
    req: TopicTreeRequestV2, rc: RunContext, *, context: str, inputs_block: str = ""
) -> PlanResult:
    shape = req.shape
    has_inputs = bool(inputs_block.strip())
    prompt = render(
        STEP,
        context=context,
        inputs=inputs_block,
        order_instruction=_order_instruction(req),
        main_instruction=_main_instruction(req, rc, has_inputs=has_inputs),
        children_instruction=_children_instruction(req, rc, has_inputs=has_inputs),
    )
    plan = await rc.llm.complete_json(STEP, prompt, StructurePlan, max_tokens=_max_tokens(req))

    mains = _limit_mains(plan.main_topics, req, rc)
    cut = Cut()
    # `from_inputs` only means something when supplementary inputs were actually given.
    has_inputs = bool(inputs_block.strip())
    roots = [
        _node(
            main.title,
            main.shorttitle,
            _convert_children(main.children, shape.depth - 1, shape.children.max, cut),
            main.from_inputs and has_inputs,
        )
        for main in mains
    ]
    if cut.depth and shape.depth >= 2:
        rc.warn("SHAPE_DEPTH", f"Grundgerüst war tiefer als {shape.depth} Ebenen und wurde gekürzt.", step=STEP)
    if cut.width:
        rc.warn("SHAPE_WIDTH", f"Unterthemen auf höchstens {shape.children.max} je Knoten gekürzt.", step=STEP)

    structure = StructureInfo(
        order=req.hints.order or plan.order,
        levels=plan.levels[: shape.depth],
        source="hint" if req.hints.order else "detected",
    )
    return PlanResult(roots=roots, structure=structure, description=plan.description)
