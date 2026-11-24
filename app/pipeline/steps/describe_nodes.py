"""Descriptions and keywords for nodes in parallel batches (topic, folders, documents, refine).

Balanced batches of up to 10 nodes run in parallel (within `LLM_MAX_CONCURRENCY`); the prompt is identical up to
NODES_MARKER across batches (cache prefix including the full tree outline so every node is described in crisp
demarcation from its siblings and cousins).
"""

import asyncio

from loguru import logger
from pydantic import BaseModel, Field

from app.domain.text import truncate_sentences
from app.domain.tree import Node, path, walk
from app.llm.client import LLMStepError
from app.pipeline.key_matching import match_keys
from app.pipeline.run_context import RunContext
from app.prompts import render

STEP = "describe_nodes"
NODES_MARKER = "## Knoten"
BATCH = 10
EXTRA_LIMIT = 1500


class Described(BaseModel):
    key: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class DescribeResult(BaseModel):
    nodes: list[Described]


def render_tree_outline(roots: list[Node], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for node in roots:
        lines.append(f"{prefix}- {node.title}")
        if node.children:
            lines.append(render_tree_outline(node.children, indent + 1))
    return "\n".join(lines)


def _line(node: Node, roots: list[Node], extra: dict[str, str]) -> str:
    line = f"- key: {node.key} | Pfad: {' > '.join(path(roots, node.key))}"
    info = extra.get(node.key)
    if info:
        line += f"\n  {truncate_sentences(info, EXTRA_LIMIT)}"
    return line


async def _describe_batch(
    batch: list[Node], prefix: str, roots: list[Node], rc: RunContext, extra: dict[str, str], words: int
) -> None:
    lines = "\n".join(_line(node, roots, extra) for node in batch)
    tokens = min(16000, 600 + len(batch) * (int(words * 1.8) + 80))
    result = await rc.llm.complete_json(STEP, f"{prefix}{NODES_MARKER}\n{lines}", DescribeResult, max_tokens=tokens)
    by_key = {node.key: node for node in batch}
    tree_keys = {node.key for node, _, _ in walk(roots) if node.key}
    matched = match_keys([item.key for item in result.nodes], list(by_key), elsewhere=tree_keys)
    unknown: list[str] = []
    for i, item in enumerate(result.nodes):
        if i in matched:
            node = by_key[matched[i]]
            node.description = item.description.strip()
            node.keywords = item.keywords
        else:
            unknown.append(item.key.strip())
    missing = [node for node in batch if not node.description]
    if unknown and missing:
        rc.warn(
            "DESCRIBE_UNKNOWN_KEY",
            f"{len(unknown)} unbekannte Knotenschlüssel bei Beschreibungen verworfen "
            f"(z. B. {', '.join(unknown[:3])}); {len(missing)} Knoten dieses Abschnitts bleiben ohne Beschreibung.",
            missing[0].key,
            STEP,
        )
    elif unknown:
        # Surplus entries (the model also described neighbours from the outline): nothing is missing, so no gap.
        logger.bind(step=STEP, keys=unknown[:5]).debug("dropped surplus description entries")


def _balanced_batches(targets: list[Node], max_size: int) -> list[list[Node]]:
    count = (len(targets) + max_size - 1) // max_size
    base, rem = divmod(len(targets), count)
    batches: list[list[Node]] = []
    start = 0
    for i in range(count):
        size = base + (1 if i < rem else 0)
        batches.append(targets[start : start + size])
        start += size
    return batches


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
    outline = render_tree_outline(roots) or "(leer)"
    prefix = render(STEP, context=context, outline=outline, nodes="").rstrip() + "\n\n"
    batches = _balanced_batches(targets, BATCH)
    outcomes = await asyncio.gather(
        *(_describe_batch(b, prefix, roots, rc, extra or {}, description_length) for b in batches),
        return_exceptions=True,
    )
    deadline_hit = False
    for batch, outcome in zip(batches, outcomes, strict=True):
        if isinstance(outcome, LLMStepError):
            if outcome.reason == "deadline":
                deadline_hit = True
            else:
                rc.warn(
                    "DESCRIBE_FAILED", f"{len(batch)} Beschreibungen konnten nicht erzeugt werden.", batch[0].key, STEP
                )
        elif isinstance(outcome, BaseException):
            raise outcome
    if deadline_hit:
        rc.warn("DEADLINE_EXCEEDED", "Die Frist ist abgelaufen; einige Beschreibungen fehlen.", step=STEP)
