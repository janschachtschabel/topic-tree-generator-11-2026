"""Runs one v2 request: input checks → strategy → shared post-processing → answer.

Strategies build the tree for their use case; everything that applies to every tree (duplicates, short titles,
keys, status, shape checks) happens here so it is done once and the same way.
"""

import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from app.domain.diff import mark_status_against_folders, mark_status_against_previous
from app.domain.keys import assign_missing_keys
from app.domain.shape_rules import ShapePlan, check_descriptions, check_shape, dedup_titles, normalize_shorttitles
from app.domain.tree import Node, from_tree_in
from app.errors import ApiError
from app.llm.client import LLMStepError
from app.pipeline.finalize import FinalizeInput, finalize
from app.pipeline.input_checks import check_request
from app.pipeline.run_context import RunContext
from app.schemas.common import Mode, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import ChangeRecord, Question, StructureInfo, TopicTreeResponseV2, Unassigned


@dataclass
class StrategyResult:
    roots: list[Node]
    title: str
    description: str = ""
    structure: StructureInfo | None = None
    unassigned: list[Unassigned] = field(default_factory=list)
    changes: list[ChangeRecord] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    shape_checked: bool = True


Strategy = Callable[[TopicTreeRequestV2, RunContext], Awaitable[StrategyResult]]

# Filled by the strategy modules (phase 3/4); a missing entry answers 501.
STRATEGIES: dict[UseCase, Strategy] = {}

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
    strategy = (strategies if strategies is not None else STRATEGIES).get(req.use_case)
    if strategy is None:
        raise ApiError(501, "NOT_IMPLEMENTED", f"use_case '{req.use_case}' ist noch nicht umgesetzt.")
    try:
        result = await strategy(req, rc)
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
