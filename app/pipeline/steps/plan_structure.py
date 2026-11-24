"""Step 1 of a generated tree: order principle and full title-only skeleton across all requested levels. One LLM call."""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.domain.shape_rules import EXTRA_TITLES
from app.domain.tree import Node
from app.pipeline.run_context import RunContext
from app.pipeline.steps.node_conversion import Cut
from app.prompts import render
from app.schemas.common import NodeStatus, OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin, StructureInfo

STEP = "plan_structure"


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


def _children_instruction(req: TopicTreeRequestV2) -> str:
    depth = req.shape.depth
    if depth < 2:
        return "Erzeuge keine Unterthemen; der Baum hat nur eine Ebene."
    c = req.shape.children
    if depth == 2:
        return (
            f"Erzeuge je Hauptthema {c.min} bis {c.max} Unterthemen (2 Ebenen gesamt, nur Titel und Kurztitel), "
            "trenn- und fachlich scharf ohne Überschneidung."
        )
    return (
        f"Erzeuge den gesamten Baum über alle {depth} Ebenen (nur Titel und Kurztitel): "
        f"je Elternknoten {c.min} bis {c.max} Kinder auf jeder Unterebene, auf Ebene {depth} ohne weitere Kinder."
    )


def _max_tokens(req: TopicTreeRequestV2) -> int:
    shape = req.shape
    mains = shape.main_topics.max + len(shape.extra_topics)
    width = shape.children.max
    estimated_nodes = sum(mains * (width**level) for level in range(shape.depth))
    return max(4000, min(16000, 1000 + estimated_nodes * 28))


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
    extra_titles = {EXTRA_TITLES[k].casefold() for k in req.shape.extra_topics}
    max_regular = req.shape.main_topics.max
    kept: list[PlannedMain] = []
    regular_count = 0
    for item in mains:
        if item.title.strip().casefold() in extra_titles:
            kept.append(item)
        else:
            regular_count += 1
            if regular_count <= max_regular:
                kept.append(item)
    if regular_count > max_regular:
        rc.warn("SHAPE_WIDTH", f"{regular_count} Hauptthemen geplant, auf {max_regular} gekürzt.", step=STEP)
    return kept


async def plan_structure(
    req: TopicTreeRequestV2, rc: RunContext, *, context: str, inputs_block: str = ""
) -> PlanResult:
    shape = req.shape
    prompt = render(
        STEP,
        context=context,
        inputs=inputs_block,
        order_instruction=_order_instruction(req),
        main_min=str(shape.main_topics.min),
        main_max=str(shape.main_topics.max),
        children_instruction=_children_instruction(req),
    )
    plan = await rc.llm.complete_json(STEP, prompt, StructurePlan, max_tokens=_max_tokens(req))

    mains = _limit_mains(plan.main_topics, req, rc)
    cut = Cut()
    roots = [
        _node(
            main.title,
            main.shorttitle,
            _convert_children(main.children, shape.depth - 1, shape.children.max, cut),
            main.from_inputs,
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
