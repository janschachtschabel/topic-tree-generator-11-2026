"""Use case `topic`: full title-only skeleton first, deterministic dedup, then parallel node descriptions."""

from app.domain.keys import assign_missing_keys
from app.domain.shape_rules import EXTRA_TITLES, eliminate_generated_duplicates, extra_kind
from app.domain.tree import Node, walk
from app.pipeline.inputs_block import structure_inputs_block
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.plan_structure import plan_structure
from app.schemas.common import ExtraTopic, OriginType
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin


def _extra(kind: ExtraTopic) -> Node:
    return Node(key=None, title=EXTRA_TITLES[kind], origin=Origin(type=OriginType.topic))


def _pop_extra(roots: list[Node], kind: ExtraTopic) -> Node | None:
    """Remove the planned node for `kind` (any accepted spelling) and give it the canonical title."""
    for i, node in enumerate(roots):
        if extra_kind(node.title) == kind:
            found = roots.pop(i)
            found.title = EXTRA_TITLES[kind]
            return found
    return None


def add_extra_topics(roots: list[Node], req: TopicTreeRequestV2) -> list[Node]:
    """Ensure requested extra topics appear first (`general`) and last (`methodology`), reusing planned ones."""
    remaining = list(roots)
    front: list[Node] = []
    back: list[Node] = []
    if ExtraTopic.general in req.shape.extra_topics:
        front.append(_pop_extra(remaining, ExtraTopic.general) or _extra(ExtraTopic.general))
    if ExtraTopic.methodology in req.shape.extra_topics:
        back.append(_pop_extra(remaining, ExtraTopic.methodology) or _extra(ExtraTopic.methodology))
    return [*front, *remaining, *back]


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    plan = await plan_structure(req, rc, context=rc.context, inputs_block=structure_inputs_block(req))
    roots = add_extra_topics(plan.roots, req)
    eliminate_generated_duplicates(roots)
    assign_missing_keys(roots)
    targets = [node for node, _, _ in walk(roots)]
    await describe_nodes(targets, roots, rc, context=rc.context, description_length=req.hints.description_length)
    return StrategyResult(
        roots=roots, title=req.topic or "Themenbaum", description=plan.description, structure=plan.structure
    )
