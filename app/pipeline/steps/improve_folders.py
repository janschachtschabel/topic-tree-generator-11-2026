"""Optional improvement of uploaded folders (options.improve): the LLM proposes change operations, which are
validated and applied deterministically like feedback (source `service`)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.ops import ApplyResult, apply_changes
from app.domain.tree import Node, walk
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.common import ChangeSource
from app.schemas.request_v2 import Change

STEP = "improve_folders"
_SAMPLE = 5


class FolderChange(BaseModel):
    op: Literal["rename", "move", "merge", "add"]
    key: str | None = None
    keys: list[str] | None = None
    parent: str | None = None
    to: str | None = None
    title: str | None = None


class ImproveResult(BaseModel):
    changes: list[FolderChange] = Field(default_factory=list)


def render_folders(roots: list[Node], titles: dict[str, str]) -> str:
    lines = []
    for node, _, depth in walk(roots):
        sample = ", ".join(titles.get(ref.id, ref.id) for ref in node.contents[:_SAMPLE])
        indent = "  " * (depth - 1)
        lines.append(
            f"{indent}- {node.key}: {node.title} | {len(node.contents)} Inhalte" + (f" | {sample}" if sample else "")
        )
    return "\n".join(lines)


def _to_change(change: FolderChange) -> Change | None:
    try:
        return Change.model_validate(change.model_dump())
    except ValueError:
        return None


async def improve_folders(
    roots: list[Node], titles: dict[str, str], rc: RunContext, *, inputs_block: str = ""
) -> ApplyResult:
    prompt = render(STEP, context=rc.context, inputs=inputs_block, folders=render_folders(roots, titles))
    result = await rc.llm.complete_json(STEP, prompt, ImproveResult, max_tokens=3000)
    changes = [c for c in (_to_change(raw) for raw in result.changes) if c is not None]
    if len(changes) < len(result.changes):
        rc.warn(
            "CHANGE_REJECTED", f"{len(result.changes) - len(changes)} unvollständige Vorschläge verworfen.", step=STEP
        )
    applied = apply_changes(roots, changes, set(), ChangeSource.service)
    for warning in applied.rejected:
        rc.warn(warning.code, warning.message, warning.key, STEP)
    return applied
