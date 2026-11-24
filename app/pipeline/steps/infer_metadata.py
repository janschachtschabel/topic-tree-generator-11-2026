"""Automatic node-level vocabulary metadata (`options.auto_metadata`).

Step A (deterministic, zero LLM cost): narrow each node's `ccm:taxonid`, `ccm:educationalcontext`, and
`ccm:educationalintendedenduserrole` from the properties of its assigned items (when narrower than `frame`
or when `frame` is empty).
Step B (LLM, batched with shared cache prefix): only for fields where `frame` is empty or multi-valued and
nodes still lack specific URIs. Prompts list ONLY exact German vocabulary labels (no URIs) and require exact
spelling; returned labels are deterministically mapped back to canonical SkoHub URIs in Python.
"""

import asyncio

from pydantic import BaseModel, Field

from app.domain.keys import assign_missing_keys
from app.domain.tree import Node, path, walk
from app.llm.client import LLMStepError
from app.pipeline.run_context import RunContext
from app.prompts import render
from app.schemas.request_v2 import Frame, TopicTreeRequestV2
from app.vocab.labels import entries, is_known, label

STEP = "infer_metadata"
NODES_MARKER = "## Knoten"
BATCH = 20
_HOCHSCHULE = "http://w3id.org/openeduhub/vocabs/educationalContext/hochschule"
_HS_PREFIX = "http://w3id.org/openeduhub/vocabs/hochschulfaechersystematik/"

_FIELDS = (
    ("discipline", "ccm:taxonid", "Fach (discipline)"),
    ("educational_context", "ccm:educationalcontext", "Bildungsstufe (educational_context)"),
    ("intended_end_user_role", "ccm:educationalintendedenduserrole", "Zielgruppe (intended_end_user_role)"),
)


class NodeMetadata(BaseModel):
    key: str
    discipline: list[str] = Field(default_factory=list)
    educational_context: list[str] = Field(default_factory=list)
    intended_end_user_role: list[str] = Field(default_factory=list)


class MetadataResult(BaseModel):
    nodes: list[NodeMetadata]


def _narrow_from_items(roots: list[Node], req: TopicTreeRequestV2) -> None:
    by_id = {item.id: item for item in req.items or []}
    if not by_id:
        return
    frame = req.frame
    frame_map = {
        "ccm:taxonid": set(frame.discipline_uri),
        "ccm:educationalcontext": set(frame.educational_context_uri),
        "ccm:educationalintendedenduserrole": set(frame.intended_end_user_role_uri),
    }
    for node, _, _ in walk(roots):
        if not node.contents:
            continue
        for prop_key, allowed_frame in frame_map.items():
            if node.properties.values(prop_key):
                continue
            found: list[str] = []
            for ref in node.contents:
                item = by_id.get(ref.id)
                if not item:
                    continue
                for uri in item.properties.values(prop_key):
                    if uri not in found and is_known(uri) and (not allowed_frame or uri in allowed_frame):
                        found.append(uri)
            if found and (not allowed_frame or len(found) < len(allowed_frame)):
                node.properties.set(prop_key, found)


def _use_hochschule(frame: Frame) -> bool:
    return _HOCHSCHULE in frame.educational_context_uri or any(u.startswith(_HS_PREFIX) for u in frame.discipline_uri)


def _candidate_pool(frame: Frame) -> dict[str, list[tuple[str, str]]]:
    """Return `{field_name: [(uri, label), ...]}` only for fields that are ambiguous (empty or >1 in frame)."""
    pools: dict[str, list[tuple[str, str]]] = {}

    if len(frame.discipline_uri) > 1:
        pools["discipline"] = [(u, name) for u in frame.discipline_uri if (name := label(u))]
    elif not frame.discipline_uri:
        if _use_hochschule(frame):
            pools["discipline"] = [(e["uri"], e["label"]) for e in entries("hochschulfaechersystematik", max_depth=2)]
        else:
            pools["discipline"] = [(e["uri"], e["label"]) for e in entries("discipline")]

    if len(frame.educational_context_uri) > 1:
        pools["educational_context"] = [(u, name) for u in frame.educational_context_uri if (name := label(u))]
    elif not frame.educational_context_uri:
        pools["educational_context"] = [(e["uri"], e["label"]) for e in entries("educationalContext")]

    if len(frame.intended_end_user_role_uri) > 1:
        pools["intended_end_user_role"] = [(u, name) for u in frame.intended_end_user_role_uri if (name := label(u))]
    elif not frame.intended_end_user_role_uri:
        pools["intended_end_user_role"] = [(e["uri"], e["label"]) for e in entries("intendedEndUserRole")]

    return {k: v for k, v in pools.items() if v}


def _render_candidates(pools: dict[str, list[tuple[str, str]]]) -> str:
    sections: list[str] = []
    for field_name, _, caption in _FIELDS:
        items = pools.get(field_name)
        if not items:
            continue
        lines = [f"### {caption}", *(f"- {name}" for _, name in items)]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _needs_llm(node: Node, pools: dict[str, list[tuple[str, str]]]) -> bool:
    for field_name, prop_key, _ in _FIELDS:
        if field_name in pools and not node.properties.values(prop_key):
            return True
    return False


async def _infer_batch(
    batch: list[Node],
    prefix: str,
    roots: list[Node],
    label_maps: dict[str, dict[str, str]],
    rc: RunContext,
) -> int:
    lines = "\n".join(
        f"- key: {n.key} | Pfad: {' > '.join(path(roots, n.key))}"
        + (f" | {n.description[:140]}" if n.description else "")
        for n in batch
    )
    result = await rc.llm.complete_json(
        STEP, f"{prefix}{NODES_MARKER}\n{lines}", MetadataResult, max_tokens=600 + 80 * len(batch)
    )
    by_key = {n.key: n for n in batch}
    unknown = 0
    for item in result.nodes:
        node = by_key.get(item.key)
        if node is None:
            continue
        for field_name, prop_key, _ in _FIELDS:
            lookup = label_maps.get(field_name)
            if lookup is None or node.properties.values(prop_key):
                continue
            proposed = getattr(item, field_name)
            mapped: list[str] = []
            for raw_label in proposed:
                uri = lookup.get(raw_label.strip().casefold())
                if uri is None:
                    unknown += 1
                elif uri not in mapped:
                    mapped.append(uri)
            if mapped:
                node.properties.set(prop_key, mapped)
    return unknown


async def infer_metadata(roots: list[Node], req: TopicTreeRequestV2, rc: RunContext) -> None:
    """Enrich nodes with specific SkoHub vocabulary URIs when `options.auto_metadata` is enabled."""
    assign_missing_keys(roots)
    _narrow_from_items(roots, req)

    pools = _candidate_pool(req.frame)
    if not pools:
        return
    targets = [node for node, _, _ in walk(roots) if _needs_llm(node, pools)]
    if not targets:
        return

    label_maps = {
        field_name: {name.strip().casefold(): uri for uri, name in items} for field_name, items in pools.items()
    }
    prefix = render(STEP, context=rc.context, candidates=_render_candidates(pools), nodes="").rstrip() + "\n\n"
    batches = [targets[i : i + BATCH] for i in range(0, len(targets), BATCH)]
    outcomes = await asyncio.gather(
        *(_infer_batch(b, prefix, roots, label_maps, rc) for b in batches), return_exceptions=True
    )
    unknown_total = 0
    failed = 0
    for outcome in outcomes:
        if isinstance(outcome, LLMStepError):
            failed += 1
        elif isinstance(outcome, BaseException):
            raise outcome
        else:
            unknown_total += outcome
    if unknown_total:
        rc.warn(
            "METADATA_LABEL_UNKNOWN",
            f"{unknown_total} unbekannte Vokabular-Bezeichnungen bei der automatischen Metadaten-Zuordnung verworfen.",
            step=STEP,
        )
    if failed:
        rc.warn(
            "METADATA_FAILED",
            f"Automatische Metadaten-Zuordnung für {failed} Gruppen fehlgeschlagen; Frame-Vorgaben genutzt.",
            step=STEP,
        )
