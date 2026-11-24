"""Use case `topic`: tree from a topic text. Skeleton first, then one call per main topic (plan E1)."""

from app.domain.keys import assign_missing_keys
from app.domain.tree import Node
from app.pipeline.inputs_block import structure_inputs_block
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.expand_branch import expand_branches
from app.pipeline.steps.plan_structure import plan_structure
from app.schemas.common import ExtraTopic, OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin

EXTRA_TITLES = {ExtraTopic.general: "Allgemeines", ExtraTopic.methodology: "Methodik und Didaktik"}


def _extra(kind: ExtraTopic) -> Node:
    return Node(key=None, title=EXTRA_TITLES[kind], origin=Origin(type=OriginType.topic))


def add_extra_topics(roots: list[Node], req: TopicTreeRequestV2) -> list[Node]:
    front = [_extra(ExtraTopic.general)] if ExtraTopic.general in req.shape.extra_topics else []
    back = [_extra(ExtraTopic.methodology)] if ExtraTopic.methodology in req.shape.extra_topics else []
    return [*front, *roots, *back]


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    plan = await plan_structure(req, rc, context=rc.context, inputs_block=structure_inputs_block(req))
    roots = add_extra_topics(plan.roots, req)
    assign_missing_keys(roots)
    if req.shape.depth >= 2:
        await expand_branches(roots, req, rc, context=rc.context, levels=plan.structure.levels)
    else:
        await describe_nodes(roots, roots, rc, context=rc.context, description_length=req.hints.description_length)
    return StrategyResult(
        roots=roots, title=req.topic or "Themenbaum", description=plan.description, structure=plan.structure
    )
