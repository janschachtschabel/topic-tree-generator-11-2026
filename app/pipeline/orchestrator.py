"""Runs one v2 request: input checks → strategy → shared post-processing → answer.

Strategies build the tree for their use case; everything that applies to every tree (duplicates, short titles,
keys, status, shape checks) happens here so it is done once and the same way.
"""

import time
from collections.abc import Awaitable, Callable, Mapping

from app.domain.diff import mark_status_against_folders, mark_status_against_previous
from app.domain.keys import assign_missing_keys
from app.domain.ops import protected_keys
from app.domain.quality import check_quality, clean_keywords, is_history_context
from app.domain.shape_rules import (
    EXTRA_TITLES,
    ShapePlan,
    check_descriptions,
    check_shape,
    dedup_titles,
    extra_kind,
    normalize_shorttitles,
)
from app.domain.tree import Node, drop_untitled, from_tree_in, index, walk
from app.errors import ApiError
from app.llm.client import LLMStepError
from app.pipeline.context_block import build_context_block
from app.pipeline.effective import effective_request, explicit_shape, has_structure_inputs
from app.pipeline.finalize import FinalizeInput, finalize
from app.pipeline.input_checks import check_request
from app.pipeline.inputs.refs import resolve_refs
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.assign_contents import assign_contents
from app.pipeline.steps.infer_metadata import infer_metadata
from app.pipeline.strategies import contents, document, folders, refine, topic
from app.schemas.common import ChangeOp, ItemUse, Mode, UnassignedReason, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import TopicTreeResponseV2, Unassigned
from app.vocab.labels import label

__all__ = ["STRATEGIES", "Strategy", "StrategyResult", "run"]


Strategy = Callable[[TopicTreeRequestV2, RunContext], Awaitable[StrategyResult]]

STRATEGIES: dict[UseCase, Strategy] = {
    UseCase.topic: topic.build,
    UseCase.folders: folders.build,
    UseCase.document: document.build,
    UseCase.contents: contents.build,
}

_RETRYABLE = {429, 500, 502, 503, 504}
# Upstream rejections that point to a configuration mismatch (unknown route/model, unsupported parameters).
_CONFIG_REJECTIONS = {400, 404, 422}
# Leitfaden Kap. 2.1: permanent 503 errors from the b-api that clients must not retry.
_PERMANENT_503_MARKERS = ("model pricing unavailable", "not_eligible")


def _llm_unavailable(error: LLMStepError, mode: str) -> ApiError:
    if mode == "bapi" and error.status == 401:
        return ApiError(
            401,
            "UNAUTHORIZED",
            "Delegations-Token von der b-api abgelehnt (abgelaufen oder außerhalb der Scopes).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if mode == "bapi" and error.status == 403:
        return ApiError(403, "FORBIDDEN", "Fehlende Berechtigung an der b-api für diesen LLM-Aufruf.")
    detail_low = (error.detail or "").casefold()
    permanent_503 = error.status == 503 and any(marker in detail_low for marker in _PERMANENT_503_MARKERS)
    retry = not permanent_503 and (error.status in _RETRYABLE or error.reason in {"timeout", "connection"})
    message = "Das Sprachmodell hat keine verwertbare Antwort geliefert."
    if error.status in _CONFIG_REJECTIONS or permanent_503:
        message = (
            f"Der LLM-Endpunkt hat die Anfrage abgelehnt (HTTP {error.status}). Wahrscheinlich passen Modell bzw. Route "
            "und Endpunkt nicht zusammen: B_API_ROUTE (Route) bzw. B_API_MODEL/B_API_MODEL_PROVIDER (einzelnes Modell) "
            "an der b-api oder OPENAI_MODEL prüfen."
        )
    return ApiError(
        503 if retry else 502,
        "LLM_UNAVAILABLE",
        message,
        details={"step": error.step, "reason": error.reason, "status": error.status},
        headers={"Retry-After": "30"} if retry else None,
    )


def _drop_untitled(rc: RunContext, result: StrategyResult) -> None:
    """Untitled nodes (e.g. a blank LLM title) are removed; their own contents count as unassigned."""
    removed = drop_untitled(result.roots)
    if not removed:
        return
    rc.warn("UNTITLED_NODE", f"{len(removed)} Knoten ohne Titel verworfen; ihre Unterknoten rücken auf.")
    placed = {ref.id for node, _, _ in walk(result.roots) for ref in node.contents}
    reported = {u.id for u in result.unassigned}
    for ref in (ref for node in removed for ref in node.contents):
        if ref.id not in placed and ref.id not in reported:
            reported.add(ref.id)
            result.unassigned.append(
                Unassigned(id=ref.id, nodeId=ref.node_id, reason=UnassignedReason.no_matching_node)
            )


def _warn_already_placed(rc: RunContext, ids: list[str]) -> None:
    """refine: an item id that already sits in the tree keeps its place; say so instead of skipping it silently."""
    if not ids:
        return
    shown = ", ".join(ids[:20]) + (" …" if len(ids) > 20 else "")
    rc.warn(
        "ITEM_ALREADY_PLACED",
        f"{len(ids)} Material(ien) sind mit dieser id schon im Baum einsortiert und bleiben dort: {shown}. "
        "Ist es ein anderes Material, bitte eine eigene id vergeben.",
        step="assign_contents",
    )


async def _assign(req: TopicTreeRequestV2, rc: RunContext, result: StrategyResult) -> None:
    """Assign content items that the strategy did not place itself."""
    if not req.options.assign_contents:
        return
    assign_missing_keys(result.roots)
    placed = {ref.id for node, _, _ in walk(result.roots) for ref in node.contents}
    already_unassigned = {u.id for u in result.unassigned}
    content_items = [i for i in req.items or [] if ItemUse.content in req.effective_use(i)]
    if req.mode == Mode.refine:
        _warn_already_placed(rc, [i.id for i in content_items if i.id in placed])
    pending = [i for i in content_items if i.id not in placed and i.id not in already_unassigned]
    if pending:
        result.unassigned.extend(await assign_contents(result.roots, pending, rc, req.options))


def _protected_keyword_keys(req: TopicTreeRequestV2, result: StrategyResult, previous: list[Node] | None) -> set[str]:
    protected = protected_keys(result.roots, set(req.feedback.locked)) if req.feedback else set()
    if previous is None:
        return protected
    old_by_key = index(previous)
    # In refine mode, leave carried-over untouched keywords and explicit user `edit`s intact.
    for node, _, _ in walk(result.roots):
        old = old_by_key.get(node.key or "")
        if old is not None and old.keywords == node.keywords:
            protected.add(node.key)
    protected.update(record.key for record in result.changes if record.op == ChangeOp.edit and record.key)
    return protected


def _skip_description_keys(req: TopicTreeRequestV2, roots: list[Node], previous: list[Node] | None) -> set[str]:
    if previous is None:
        return set()
    skipped = protected_keys(roots, set(req.feedback.locked)) if req.feedback else set()
    old_by_key = index(previous)
    for node, _, _ in walk(roots):
        old = old_by_key.get(node.key or "")
        if old is not None and old.description == node.description:
            skipped.add(node.key)
    return skipped


def _post_process(req: TopicTreeRequestV2, rc: RunContext, result: StrategyResult) -> None:
    for warning in dedup_titles(result.roots, merge=req.mode != Mode.refine):
        rc.warn(warning.code, warning.message, warning.key, warning.step)
    normalize_shorttitles(result.roots)
    previous = from_tree_in(req.current_tree.collection) if req.current_tree else None
    if previous is not None:
        assign_missing_keys(previous)
    assign_missing_keys(result.roots)
    if not req.options.assign_only:
        clean_keywords(result.roots, protected=_protected_keyword_keys(req, result, previous))
    if req.mode == Mode.refine:
        mark_status_against_previous(result.roots, previous)
    elif req.use_case == UseCase.folders:
        mark_status_against_folders(result.roots)
    else:
        mark_status_against_previous(result.roots, None)
    if req.options.assign_only:
        return
    if result.shape_checked:
        plan = ShapePlan.from_shape(req.shape)
        requested_extra = set(req.shape.extra_topics)
        actual_extra = sum(1 for r in result.roots if extra_kind(r.title) in requested_extra)
        check_min = rc.explicit_shape.main_topics or not has_structure_inputs(req)
        for warning in check_shape(result.roots, plan, extra=actual_extra, check_main_min=check_min):
            rc.warn(warning.code, warning.message, warning.key, warning.step)
    allowed_extra = {EXTRA_TITLES[kind].casefold() for kind in req.shape.extra_topics}
    history = is_history_context(
        req.topic, (label(uri) or "" for uri in req.frame.discipline_uri), order=req.hints.order
    )
    for warning in check_quality(result.roots, topic=req.topic, allowed_extra=allowed_extra, is_history=history):
        rc.warn(warning.code, warning.message, warning.key, warning.step)
    skip_desc = _skip_description_keys(req, result.roots, previous)
    for warning in check_descriptions(result.roots, req.hints.description_length, skip_keys=skip_desc):
        rc.warn(warning.code, warning.message, warning.key, warning.step)


async def run(
    req: TopicTreeRequestV2, rc: RunContext, strategies: Mapping[UseCase, Strategy] | None = None
) -> TopicTreeResponseV2:
    started = time.perf_counter()
    check_request(req, rc.settings)
    resolved = await resolve_refs(req, rc.settings)
    if resolved is not req:
        req = resolved
        check_request(req, rc.settings, loaded=True)
    rc.explicit_shape = explicit_shape(req, rc.settings)
    req = effective_request(req, rc.settings)
    if req.mode == Mode.refine:
        strategy: Strategy | None = refine.build
    else:
        strategy = (strategies if strategies is not None else STRATEGIES).get(req.use_case)
    if strategy is None:
        raise ApiError(501, "NOT_IMPLEMENTED", f"use_case '{req.use_case}' ist noch nicht umgesetzt.")
    rc.context, unknown = build_context_block(req, explicit=rc.explicit_shape)
    for uri in unknown:
        rc.warn("VOCAB_UNKNOWN", f"Unbekannter Vokabularwert: {uri}", step="context")
    try:
        result = await strategy(req, rc)
        _drop_untitled(rc, result)
        await _assign(req, rc, result)
        if req.options.auto_metadata:
            await infer_metadata(result.roots, req, rc)
    except LLMStepError as error:
        raise _llm_unavailable(error, rc.mode) from error
    if rc.expired() and not any(w.code == "DEADLINE_EXCEEDED" for w in rc.warnings):
        rc.warn("DEADLINE_EXCEEDED", "Die Frist ist abgelaufen; der Baum ist unvollständig.")
    _post_process(req, rc, result)
    data = FinalizeInput(
        roots=result.roots,
        title=result.title,
        description=result.description,
        structure=result.structure,
        unassigned=result.unassigned,
        changes=result.changes,
        questions=result.questions,
        warnings=rc.warnings,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    return finalize(req, data, model=rc.llm.model_name, usage=rc.llm.usage.snapshot(), duration_ms=duration_ms)
