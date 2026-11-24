"""Document outline → tree (one LLM call). The LLM selects and normalizes sections and may only refer to
section ids that exist; the full text never enters this prompt (descriptions use excerpts later)."""

from pydantic import BaseModel, Field

from app.pipeline.run_context import RunContext
from app.prompts import render

STEP = "map_outline"


class MappedNode(BaseModel):
    title: str
    shorttitle: str
    section_ids: list[str] = Field(default_factory=list)
    children: list["MappedNode"] = Field(default_factory=list)


class OutlineMapping(BaseModel):
    order: str
    levels: list[str] = Field(default_factory=list)
    description: str = ""
    nodes: list[MappedNode]


async def map_outline(outline: str, rc: RunContext) -> OutlineMapping:
    prompt = render(STEP, context=rc.context, outline=outline)
    return await rc.llm.complete_json(STEP, prompt, OutlineMapping, max_tokens=8000)
