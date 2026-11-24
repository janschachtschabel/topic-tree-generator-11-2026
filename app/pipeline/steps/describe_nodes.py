"""Descriptions and keywords for nodes that do not have them (folders, documents, depth-1 trees, refine).

Batches of 30 run in parallel; the prompt is identical up to NODES_MARKER across batches (cache prefix).
"""

import asyncio

from pydantic import BaseModel, Field

from app.domain.tree import Node, path
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.prompts import render

STEP = "describe_nodes"
NODES_MARKER = "## Knoten"
BATCH = 30
EXTRA_LIMIT = 1500


class Described(BaseModel):
    key: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class DescribeResult(BaseModel):
    nodes: list[Described]


def _line(node: Node, roots: list[Node], extra: dict[str, str]) -> str:
    line = f"- key: {node.key} | Pfad: {' > '.join(path(roots, node.key))}"
    info = extra.get(node.key)
    if info:
        line += f"\n  {info[:EXTRA_LIMIT]}"
    return line


async def _describe_batch(
    batch: list[Node], prefix: str, roots: list[Node], rc: RunContext, extra: dict[str, str], words: int
) -> None:
    lines = "\n".join(_line(node, roots, extra) for node in batch)
    tokens = 600 + len(batch) * (int(words * 1.6) + 80)
    result = await rc.llm.complete_json(STEP, f"{prefix}{NODES_MARKER}\n{lines}", DescribeResult, max_tokens=tokens)
    by_key = {node.key: node for node in batch}
    for item in result.nodes:
        node = by_key.get(item.key)
        if node is not None:
            node.description = item.description.strip()
            node.keywords = item.keywords


async def describe_nodes(
    targets: list[Node],
    roots: list[Node],
    rc: RunContext,
    *,
    context: str,
    description_length: int = 60,
    extra: dict[str, str] | None = None,
) -> None:
    """Fill `description` and `keywords` of `targets` (keys must be assigned). Failures become warnings."""
    if not targets:
        return
    prefix = render(STEP, context=context, nodes="").rstrip() + "\n\n"
    batches = [targets[i : i + BATCH] for i in range(0, len(targets), BATCH)]
    outcomes = await asyncio.gather(
        *(_describe_batch(b, prefix, roots, rc, extra or {}, description_length) for b in batches),
        return_exceptions=True,
    )
    for batch, outcome in zip(batches, outcomes, strict=True):
        if isinstance(outcome, LLMStepError):
            rc.warn("DESCRIBE_FAILED", f"{len(batch)} Beschreibungen konnten nicht erzeugt werden.", batch[0].key, STEP)
        elif isinstance(outcome, BaseException):
            raise outcome
