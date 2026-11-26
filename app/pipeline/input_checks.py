"""Cross-field input requirements per use case (Spec: "Use Case als Wert"). Fails with 422 instead of guessing."""

from collections import Counter
from collections.abc import Iterator

from app.errors import ApiError
from app.schemas.common import ItemUse, Mode, UseCase
from app.schemas.request_v2 import FolderNode, MainRange, TopicTreeRequestV2, TreeNodeIn
from app.settings import Settings


def _missing(message: str) -> ApiError:
    return ApiError(422, "MISSING_INPUT", message)


def _folder_item_ids(folders: list[FolderNode]) -> Iterator[str]:
    for folder in folders:
        yield from folder.items
        yield from _folder_item_ids(folder.subcollections)


def _check_items(req: TopicTreeRequestV2, settings: Settings, loaded: bool) -> None:
    if not loaded and req.items and req.items_ref is not None:
        raise ApiError(422, "INVALID_INPUT", "Nur 'items' oder 'items_ref' angeben, nicht beides.")
    items = req.items or []
    if not loaded and len(items) > settings.items_inline_max:
        raise ApiError(
            422, "ITEMS_TOO_LARGE", f"Mehr als {settings.items_inline_max} Einträge inline; bitte items_ref nutzen."
        )
    counts = Counter(item.id for item in items)
    duplicates = sorted(item_id for item_id, count in counts.items() if count > 1)
    if duplicates:
        raise ApiError(422, "DUPLICATE_ID", "Item-ids müssen eindeutig sein.", details={"ids": duplicates[:20]})
    if req.folders and not req.items_ref:
        unknown = sorted(set(_folder_item_ids(req.folders)) - set(counts))
        if unknown:
            raise ApiError(422, "UNKNOWN_ITEM", "Ordner verweisen auf unbekannte Items.", details={"ids": unknown[:20]})


def _placed_node_ids(nodes: list[TreeNodeIn], out: dict[str, set[str]]) -> dict[str, set[str]]:
    for node in nodes:
        for ref in node.contents:
            out.setdefault(ref.id, set()).update([ref.node_id] if ref.node_id else [])
        _placed_node_ids(node.subcollections, out)
    return out


def _check_refine_ids(req: TopicTreeRequestV2) -> None:
    """An item id already placed in `current_tree` must name the same material (same nodeId where both are given)."""
    placed = _placed_node_ids(req.current_tree.collection, {})
    conflicts = sorted(
        item.id
        for item in req.items or []
        if item.node_id and placed.get(item.id) and item.node_id not in placed[item.id]
    )
    if conflicts:
        raise ApiError(
            422,
            "ID_CONFLICT",
            "Item-ids sind im bestehenden Baum schon für ein anderes Material (andere nodeId) vergeben.",
            details={"ids": conflicts[:20]},
        )


def _has_fulltext(item) -> bool:
    if not item.fulltext:
        return False
    return item.fulltext.ref is not None or bool(item.fulltext.text and item.fulltext.text.strip())


def _check_create_inputs(req: TopicTreeRequestV2) -> None:
    has_items = bool(req.items) or req.items_ref is not None
    if req.use_case == UseCase.topic and not req.topic:
        raise _missing("use_case 'topic' braucht 'topic'.")
    if req.use_case == UseCase.folders and not req.folders:
        raise _missing("use_case 'folders' braucht 'folders'.")
    if req.use_case == UseCase.folders and ItemUse.structure not in req.effective_folders_use():
        raise ApiError(
            422,
            "INVALID_INPUT",
            "Bei use_case 'folders' bilden die Ordner das Gerüst; folders_use braucht 'structure'.",
        )
    if req.use_case == UseCase.contents:
        if not has_items:
            raise _missing("use_case 'contents' braucht mindestens einen Eintrag in 'items' oder 'items_ref'.")
        if not req.items_ref and not any(ItemUse.structure in req.effective_use(i) for i in req.items or []):
            raise _missing("use_case 'contents' braucht mindestens ein Item mit use 'structure'.")
    if req.use_case == UseCase.document and not req.items_ref:
        structure_docs = [
            item for item in req.items or [] if ItemUse.structure in req.effective_use(item) and _has_fulltext(item)
        ]
        if not structure_docs:
            raise _missing("use_case 'document' braucht ein Strukturdokument (use: structure) mit Volltext.")


def _sent_width(bounds: MainRange) -> int:
    """The largest width the caller asked for: `max` if sent, else `min` (a missing max is filled later)."""
    return bounds.max if "max" in bounds.model_fields_set else bounds.min


def _check_shape_limits(req: TopicTreeRequestV2, settings: Settings) -> None:
    if "shape" not in req.model_fields_set:
        return
    sent = req.shape.model_fields_set
    if "depth" in sent and req.shape.depth > settings.max_tree_depth:
        raise ApiError(
            422,
            "SHAPE_LIMIT_EXCEEDED",
            f"Maximale Baumtiefe ist auf {settings.max_tree_depth} Ebenen begrenzt.",
        )
    if "main_topics" in sent and _sent_width(req.shape.main_topics) > settings.max_nodes_per_level:
        raise ApiError(
            422,
            "SHAPE_LIMIT_EXCEEDED",
            f"Hauptebene darf höchstens {settings.max_nodes_per_level} Knoten anfordern.",
        )
    if "children" in sent and _sent_width(req.shape.children) > settings.max_nodes_per_level:
        raise ApiError(
            422,
            "SHAPE_LIMIT_EXCEEDED",
            f"Je Knoten sind höchstens {settings.max_nodes_per_level} Kinder zulässig.",
        )


def check_request(req: TopicTreeRequestV2, settings: Settings, *, loaded: bool = False) -> None:
    """`loaded=True` re-checks a request after items_ref was resolved (no inline limit then)."""
    if req.mode == Mode.refine and req.current_tree is None:
        raise _missing("mode 'refine' braucht 'current_tree'.")
    if req.mode == Mode.refine:
        _check_refine_ids(req)
    if req.options.assign_only and req.mode != Mode.refine:
        raise ApiError(422, "INVALID_OPTION", "options.assign_only ist nur mit mode 'refine' möglich.")
    _check_shape_limits(req, settings)
    _check_items(req, settings, loaded)
    if req.mode == Mode.create:
        _check_create_inputs(req)
