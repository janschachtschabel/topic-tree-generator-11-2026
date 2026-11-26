"""The `split` change: the LLM proposes 2–4 parts; children and contents are redistributed deterministically."""

from pydantic import BaseModel, Field

from app.domain.keys import make_key
from app.domain.text import one_line
from app.domain.tree import Node, index, parent_of
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.common import ChangeSource, OriginType
from app.schemas.request_v2 import Change
from app.schemas.response_v2 import ChangeRecord, Origin

STEP = "split_node"


class SplitPart(BaseModel):
    title: str
    child_keys: list[str] = Field(default_factory=list)
    content_ids: list[str] = Field(default_factory=list)


class SplitResult(BaseModel):
    parts: list[SplitPart]


def _describe(node: Node) -> str:
    children = "\n".join(f"- Kind {c.key}: {one_line(c.title)}" for c in node.children) or "- (keine Kinder)"
    contents = "\n".join(f"- Inhalt {r.id}" for r in node.contents)
    return f"{node.key}: {one_line(node.title)}\n{children}" + (f"\n{contents}" if contents else "")


async def split_node(
    roots: list[Node], change: Change, source: ChangeSource, rc: RunContext, taken: set[str] | None = None
) -> tuple[ChangeRecord, list[str]] | None:
    """Replace the node by its parts. Returns (record, new keys) or None if the answer was unusable.

    `taken` holds keys the parts must not get (e.g. of nodes removed earlier in the request)."""
    node = index(roots)[change.key]
    prompt = render(STEP, context=rc.context, node=_describe(node), hint=change.hint or "")
    result = await rc.llm.complete_json(STEP, prompt, SplitResult, max_tokens=1500)
    parts = result.parts[:4]
    if len(parts) < 2:
        rc.warn("CHANGE_REJECTED", f"„{node.title}“ konnte nicht sinnvoll aufgeteilt werden.", node.key, STEP)
        return None

    taken = (taken if taken is not None else set()) | set(index(roots))
    new_nodes = [
        Node(key=make_key(p.title, taken), title=p.title.strip(), origin=Origin(type=OriginType.feedback))
        for p in parts
    ]
    children = {c.key: c for c in node.children}
    contents = {r.id: r for r in node.contents}
    for part, new in zip(parts, new_nodes, strict=True):
        new.children = [children.pop(k) for k in part.child_keys if k in children]
        new.contents = [contents.pop(i) for i in part.content_ids if i in contents]
    new_nodes[0].children.extend(children.values())
    new_nodes[0].contents.extend(contents.values())

    parent = parent_of(roots, node.key)
    siblings = parent.children if parent else roots
    position = siblings.index(node)
    siblings[position : position + 1] = new_nodes
    record = ChangeRecord.model_validate({"op": "split", "key": node.key, "from": source})
    return record, [n.key for n in new_nodes]
