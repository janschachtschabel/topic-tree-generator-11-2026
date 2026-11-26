"""Turn free-text feedback into change operations or questions (one LLM call)."""

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.domain.text import one_line
from app.domain.tree import Node, walk
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.request_v2 import Change
from app.schemas.response_v2 import ChangeRecord

STEP = "interpret_feedback"


class TextChange(BaseModel):
    op: Literal["add", "remove", "rename", "move", "merge", "split"]
    key: str | None = None
    keys: list[str] | None = None
    parent: str | None = None
    to: str | None = None
    title: str | None = None
    hint: str | None = None


class Interpretation(BaseModel):
    changes: list[TextChange] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


def render_tree(roots: list[Node], protected: set[str]) -> str:
    lines = []
    for node, _, depth in walk(roots):
        mark = " [gesperrt]" if node.key in protected else ""
        lines.append(f"{'  ' * (depth - 1)}- {node.key}: {one_line(node.title)}{mark}")
    return "\n".join(lines)


def _already(records: list[ChangeRecord]) -> str:
    if not records:
        return ""
    lines = [f"- {r.op} {r.key or ', '.join(r.keys or [])}" + (f" → {r.to}" if r.to else "") for r in records]
    return "\n## Bereits umgesetzt (nicht wiederholen, nicht widersprechen)\n" + "\n".join(lines) + "\n"


async def interpret_feedback(
    roots: list[Node], text: str, protected: set[str], rc: RunContext, already: list[ChangeRecord]
) -> tuple[list[Change], list[str]]:
    prompt = render(STEP, context=rc.context, tree=render_tree(roots, protected), already=_already(already), text=text)
    result = await rc.llm.complete_json(STEP, prompt, Interpretation, max_tokens=3000)
    changes: list[Change] = []
    for raw in result.changes:
        try:
            changes.append(Change.model_validate(raw.model_dump()))
        except ValidationError:
            rc.warn("CHANGE_REJECTED", f"Unvollständige Änderung „{raw.op}“ aus der Rückmeldung verworfen.", step=STEP)
    return changes, [q.strip() for q in result.questions if q.strip()]
