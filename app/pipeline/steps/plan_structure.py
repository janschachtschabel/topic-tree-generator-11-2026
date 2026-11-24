"""Step 1 of a generated tree: order principle and skeleton (top two levels, titles only). One LLM call."""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.domain.tree import Node
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.common import NodeStatus, OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin, StructureInfo

STEP = "plan_structure"


class PlannedChild(BaseModel):
    title: str
    shorttitle: str


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
    if req.shape.depth < 2:
        return "Erzeuge keine Unterthemen; der Baum hat nur eine Ebene."
    c = req.shape.children
    return f"Erzeuge je Hauptthema {c.min} bis {c.max} Unterthemen (nur Titel), trennscharf und ohne Überschneidung."


def _node(title: str, shorttitle: str, children: list[Node], suggested: bool = False) -> Node:
    return Node(
        key=None,
        title=title.strip(),
        shorttitle=shorttitle.strip(),
        origin=Origin(type=OriginType.topic),
        status=NodeStatus.suggested if suggested else None,
        children=children,
    )


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
    plan = await rc.llm.complete_json(STEP, prompt, StructurePlan, max_tokens=4000)

    mains = plan.main_topics
    if len(mains) > shape.main_topics.max:
        rc.warn("SHAPE_WIDTH", f"{len(mains)} Hauptthemen geplant, auf {shape.main_topics.max} gekürzt.", step=STEP)
        mains = mains[: shape.main_topics.max]
    too_many_children = False
    roots = []
    for main in mains:
        children = main.children if shape.depth >= 2 else []
        if len(children) > shape.children.max:
            too_many_children = True
            children = children[: shape.children.max]
        roots.append(
            _node(main.title, main.shorttitle, [_node(c.title, c.shorttitle, []) for c in children], main.from_inputs)
        )
    if too_many_children:
        rc.warn("SHAPE_WIDTH", f"Unterthemen auf höchstens {shape.children.max} je Hauptthema gekürzt.", step=STEP)

    structure = StructureInfo(
        order=req.hints.order or plan.order,
        levels=plan.levels[: shape.depth],
        source="hint" if req.hints.order else "detected",
    )
    return PlanResult(roots=roots, structure=structure, description=plan.description)
