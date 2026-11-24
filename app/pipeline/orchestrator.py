"""Runs one v2 request: input checks → strategy → shared post-processing → answer.

Strategies build the tree for their use case; everything that applies to every tree (duplicates, short titles,
keys, status, shape checks) happens here so it is done once and the same way.
"""

import time
from collections.abc import Awaitable, Callable, Mapping

from app.domain.diff import mark_status_against_folders, mark_status_against_previous
from app.domain.keys import assign_missing_keys
from app.domain.shape_rules import ShapePlan, check_descriptions, check_shape, dedup_titles, normalize_shorttitles
from app.domain.tree import from_tree_in, walk
from app.errors import ApiError
from app.llm.client import LLMStepError
from app.pipeline.context_block import build_context_block
from app.pipeline.effective import effective_request
from app.pipeline.finalize import FinalizeInput, finalize
from app.pipeline.input_checks import check_request
from app.pipeline.inputs.refs import resolve_refs
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.assign_contents import assign_contents
from app.pipeline.strategies import document, folders, refine, topic
from app.schemas.common import ItemUse, Mode, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import TopicTreeResponseV2

__all__ = ["STRATEGIES", "Strategy", "StrategyResult", "run"]


Strategy = Callable[[TopicTreeRequestV2, RunContext], Awaitable[StrategyResult]]

# Use cases without an entry answer 501 until their strategy exists.
STRATEGIES: dict[UseCase, Strategy] = {
    UseCase.topic: topic.build,
    UseCase.folders: folders.build,
    UseCase.document: document.build,
}

_RETRYABLE = {429, 500, 502, 503, 504}


def _llm_unavailable(error: LLMStepError) -> ApiError:
    retry = error.status in _RETRYABLE or error.reason in {"timeout", "connection"}
    return ApiError(
        503 if retry else 502,
        "LLM_UNAVAILABLE",
        "Das Sprachmodell hat keine verwertbare Antwort geliefert.",
        details={"step": error.step, "reason": error.reason, "status": error.status},
        headers={"Retry-After": "30"} if retry else None,
    )


async def _assign(req: TopicTreeRequestV2, rc: RunContext, result: StrategyResult) -> None:
    """Assign content items that the strategy did not place itself."""
    if not req.options.assign_contents or result.contents_assigned:
        return
    assign_missing_keys(result.roots)
    placed = {ref.id for node, _, _ in walk(result.roots) for ref in node.contents}
    pending = [i for i in req.items or [] if ItemUse.content in req.effective_use(i) and i.id not in placed]
    if pending:
        result.unassigned.extend(await assign_contents(result.roots, pending, rc, req.options))


def _post_process(req: TopicTreeRequestV2, rc: RunContext, result: StrategyResult) -> None:
    for warning in dedup_titles(result.roots):
        rc.warn(warning.code, warning.message, warning.key, warning.step)
    normalize_shorttitles(result.roots)
    previous = from_tree_in(req.current_tree.collection) if req.current_tree else None
    if previous is not None:
        assign_missing_keys(previous)
    assign_missing_keys(result.roots)
    if req.mode == Mode.refine:
        mark_status_against_previous(result.roots, previous)
    elif req.use_case == UseCase.folders:
        mark_status_against_folders(result.roots)
    else:
        mark_status_against_previous(result.roots, None)
    if result.shape_checked:
        plan = ShapePlan.from_shape(req.shape)
        for warning in check_shape(result.roots, plan, extra=len(req.shape.extra_topics)):
            rc.warn(warning.code, warning.message, warning.key, warning.step)
    for warning in check_descriptions(result.roots, req.hints.description_length):
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
    req = effective_request(req)
    if req.mode == Mode.refine:
        strategy: Strategy | None = refine.build
    else:
        strategy = (strategies if strategies is not None else STRATEGIES).get(req.use_case)
    if strategy is None:
        raise ApiError(501, "NOT_IMPLEMENTED", f"use_case '{req.use_case}' ist noch nicht umgesetzt.")
    rc.context, unknown = build_context_block(req)
    for uri in unknown:
        rc.warn("VOCAB_UNKNOWN", f"Unbekannter Vokabularwert: {uri}", step="context")
    try:
        result = await strategy(req, rc)
        await _assign(req, rc, result)
    except LLMStepError as error:
        raise _llm_unavailable(error) from error
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
