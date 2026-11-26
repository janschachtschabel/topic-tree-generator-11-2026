"""Fill omitted request settings from `current_tree.generation` (refine) and target-group or input guidelines.

Guidelines ("Gestaltungs- und Ordnungskriterien für Themenbäume"):
- Without explicit width on input-driven requests (`document`, `contents`, `folders`, or `topic` with structure items),
  width follows the input up to the operator's cap (`2..MAX_NODES_PER_LEVEL`, default `20`).
- Pure `topic` without explicit `shape`:
  - Elementarbereich / Kita: max 2 levels, 5–10 main topics, 3–8 children
  - Fort-/Erwachsenenbildung, Unternehmen/Behörden, Redaktionen/Communities: max 2 levels, 5–12 main topics, 3–8 children
  - Schule / Berufliche Bildung / Hochschule / default: max 3 levels, 5–15 main topics, 3–8 children
Every recommended default is clamped to the operator's hard caps (`MAX_TREE_DEPTH`, `MAX_NODES_PER_LEVEL`).
"""

from pydantic import BaseModel

from app.pipeline.inputs_block import folders_shape_tree
from app.pipeline.run_context import ExplicitShape
from app.schemas.common import ItemUse, UseCase
from app.schemas.request_v2 import ChildRange, MainRange, Shape, TopicTreeRequestV2
from app.settings import Settings

_ORG_HINTS = ("unternehmen", "behörde", "verwaltung", "organisation", "redaktion", "themenwelt", "community")
_ADULT_URIS = ("fortbildung", "erwachsenenbildung")


def _clamp_main(low: int, high: int, cap: int) -> MainRange:
    capped_max = max(1, min(high, cap))
    return MainRange(min=max(1, min(low, capped_max)), max=capped_max)


def _clamp_children(low: int, high: int, cap: int) -> ChildRange:
    capped_max = max(2, min(high, cap))
    return ChildRange(min=max(2, min(low, capped_max)), max=capped_max)


def has_structure_inputs(req: TopicTreeRequestV2) -> bool:
    """True when structure is anchored in supplied documents, folders, or content items."""
    if req.use_case in {UseCase.document, UseCase.contents, UseCase.folders}:
        return True
    if folders_shape_tree(req):
        return True
    return any(ItemUse.structure in req.effective_use(item) for item in (req.items or []))


def explicit_shape(req: TopicTreeRequestV2, settings: Settings | None = None) -> ExplicitShape:
    """Which shape dimensions were explicitly constrained by the caller (or non-default generation)."""
    has_shape = "shape" in req.model_fields_set
    sent = req.shape.model_fields_set if has_shape else set()
    gen = req.current_tree.generation if req.current_tree else None
    gen_sent: set[str] = set()
    if gen and gen.shape is not None:
        gen_sent = set(gen.shape.model_fields_set)
        if has_structure_inputs(req):
            max_w = settings.max_nodes_per_level if settings else 20
            if (gen.shape.main_topics.min, gen.shape.main_topics.max) == (2, max_w):
                gen_sent.discard("main_topics")
            if (gen.shape.children.min, gen.shape.children.max) == (2, max_w):
                gen_sent.discard("children")
    active = sent | gen_sent
    return ExplicitShape(
        depth="depth" in active,
        main_topics="main_topics" in active,
        children="children" in active,
    )


def recommended_shape(req: TopicTreeRequestV2, settings: Settings | None = None) -> Shape:
    """Recommended shape derived from input kind and educational context, clamped to operator limits."""
    max_depth = settings.max_tree_depth if settings else 3
    max_width = settings.max_nodes_per_level if settings else 20

    contexts = " ".join(req.frame.educational_context_uri).casefold()
    hint_ctx = (req.hints.context or "").casefold()

    if "elementarbereich" in contexts or "kita" in hint_ctx:
        depth, main_lo, main_hi, child_lo, child_hi = 2, 5, 10, 3, 8
    elif any(k in contexts for k in _ADULT_URIS) or any(k in hint_ctx for k in _ORG_HINTS):
        depth, main_lo, main_hi, child_lo, child_hi = 2, 5, 12, 3, 8
    else:
        depth, main_lo, main_hi, child_lo, child_hi = 3, 5, 15, 3, 8

    if has_structure_inputs(req):
        # Input-driven requests (e.g. a curriculum with 20 main areas) may use the full operator width ceiling.
        main_lo, main_hi = 2, max_width
        child_lo, child_hi = 2, max_width

    return Shape(
        depth=min(depth, max_depth),
        main_topics=_clamp_main(main_lo, main_hi, max_width),
        children=_clamp_children(child_lo, child_hi, max_width),
    )


def _clamp_shape(shape: Shape, settings: Settings | None) -> Shape:
    if settings is None:
        return shape
    return shape.model_copy(
        update={
            "depth": min(shape.depth, settings.max_tree_depth),
            "main_topics": _clamp_main(shape.main_topics.min, shape.main_topics.max, settings.max_nodes_per_level),
            "children": _clamp_children(shape.children.min, shape.children.max, settings.max_nodes_per_level),
        }
    )


def _complete_range[R: MainRange](sent: R, base: R) -> R:
    """A range with one bound sent takes the other from the base range, moved so the sent bound holds."""
    given = sent.model_fields_set
    if given >= {"min", "max"} or not given:
        return sent
    if given == {"min"}:
        return sent.model_copy(update={"max": max(base.max, sent.min)})
    return sent.model_copy(update={"min": min(base.min, sent.max)})


def _resolve_shape(
    req: TopicTreeRequestV2, merged: TopicTreeRequestV2, inherited: Shape | None, settings: Settings | None
) -> Shape:
    if "shape" not in req.model_fields_set:
        if inherited is not None:
            return _clamp_shape(inherited, settings)
        return recommended_shape(merged, settings)

    sent = req.shape.model_fields_set
    rec = recommended_shape(merged, settings)
    base = _clamp_shape(inherited, settings) if inherited is not None else rec
    updates = {}
    if "depth" not in sent:
        updates["depth"] = base.depth
    for name in ("main_topics", "children"):
        updates[name] = (
            _complete_range(getattr(req.shape, name), getattr(base, name)) if name in sent else getattr(base, name)
        )
    return req.shape.model_copy(update=updates) if updates else req.shape


def _inherit[M: BaseModel](inherited: M, sent: M, was_sent: bool) -> M:
    """The inherited settings, overridden field by field by the ones the request actually sent."""
    if not was_sent:
        return inherited
    return inherited.model_copy(update={name: getattr(sent, name) for name in sent.model_fields_set})


def effective_request(req: TopicTreeRequestV2, settings: Settings | None = None) -> TopicTreeRequestV2:
    generation = req.current_tree.generation if req.current_tree else None
    sent = req.model_fields_set
    updates: dict = {}
    if generation is not None:
        if "topic" not in sent and generation.topic:
            updates["topic"] = generation.topic
        if generation.hints is not None:
            updates["hints"] = _inherit(generation.hints, req.hints, "hints" in sent)
        if generation.options is not None:
            options = _inherit(generation.options, req.options, "options" in sent)
            # `assign_only` describes one call, not the tree: inheriting it would silently drop the next feedback.
            sent_assign_only = "options" in sent and "assign_only" in req.options.model_fields_set
            updates["options"] = options.model_copy(
                update={"assign_only": sent_assign_only and req.options.assign_only}
            )
        if "frame" in sent and not any(req.frame.model_dump().values()) and generation.frame is not None:
            updates["frame"] = generation.frame

    merged = req.model_copy(update=updates) if updates else req
    inherited_shape = generation.shape if generation is not None else None
    resolved_shape = _resolve_shape(req, merged, inherited_shape, settings)
    if resolved_shape != merged.shape:
        merged = merged.model_copy(update={"shape": resolved_shape})
    return merged
