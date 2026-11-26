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


def narrowing(topic: str | None) -> str:
    """With a topic, only the sections that belong to it become nodes (the document may cover far more)."""
    if not topic:
        return ""
    return (
        f"\n## Eingrenzung auf das Thema\nDas Thema „{topic}“ grenzt das Dokument ein. Übernimm nur Abschnitte, die "
        f"unmittelbar zu „{topic}“ gehören; Abschnitte, die nur zum übergeordneten Fach passen, fallen weg. Deckt nur "
        "ein Abschnitt das Thema ab, werden seine Unterabschnitte zu Hauptknoten.\n"
    )


async def map_outline(
    outline: str, rc: RunContext, topic: str | None = None, *, inputs_block: str = ""
) -> OutlineMapping:
    prompt = render(STEP, context=rc.context, inputs=inputs_block, outline=outline, narrowing=narrowing(topic))
    line_count = outline.count("\n") + 1
    budget = max(8000, min(32000, 1500 + line_count * 45))
    return await rc.llm.complete_json(STEP, prompt, OutlineMapping, max_tokens=budget)
