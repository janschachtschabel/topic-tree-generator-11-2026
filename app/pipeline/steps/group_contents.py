"""Build groups (the tree scheme) from content metadata in one call. Assignment happens afterwards."""

from pydantic import BaseModel, Field

from app.pipeline.run_context import RunContext
from app.pipeline.steps.node_conversion import BranchNode
from app.prompts import render

STEP = "group_contents"


class Grouping(BaseModel):
    order: str
    levels: list[str] = Field(default_factory=list)
    description: str = ""
    groups: list[BranchNode]


async def group_contents(items_block: str, rc: RunContext, max_tokens: int) -> Grouping:
    prompt = render(STEP, context=rc.context, items=items_block)
    return await rc.llm.complete_json(STEP, prompt, Grouping, max_tokens=max_tokens)
