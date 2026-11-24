"""Cross-field input requirements per use case (Spec: "Use Case als Wert"). Fails with 422 instead of guessing."""

from collections.abc import Iterator

from app.errors import ApiError
from app.schemas.common import ItemUse, Mode, UseCase
from app.schemas.request_v2 import FolderNode, TopicTreeRequestV2
from app.settings import Settings


def _missing(message: str) -> ApiError:
    return ApiError(422, "MISSING_INPUT", message)


def _folder_item_ids(folders: list[FolderNode]) -> Iterator[str]:
    for folder in folders:
        yield from folder.items
        yield from _folder_item_ids(folder.subcollections)


def _check_items(req: TopicTreeRequestV2, settings: Settings) -> None:
    items = req.items or []
    if len(items) > settings.items_inline_max:
        raise ApiError(
            422, "ITEMS_TOO_LARGE", f"Mehr als {settings.items_inline_max} Einträge inline; bitte items_ref nutzen."
        )
    ids = [item.id for item in items]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ApiError(422, "DUPLICATE_ID", "Item-ids müssen eindeutig sein.", details={"ids": duplicates[:20]})
    if req.folders and not req.items_ref:
        unknown = sorted(set(_folder_item_ids(req.folders)) - set(ids))
        if unknown:
            raise ApiError(422, "UNKNOWN_ITEM", "Ordner verweisen auf unbekannte Items.", details={"ids": unknown[:20]})


def _check_create_inputs(req: TopicTreeRequestV2) -> None:
    has_items = bool(req.items) or req.items_ref is not None
    if req.use_case == UseCase.topic and not req.topic:
        raise _missing("use_case 'topic' braucht 'topic'.")
    if req.use_case == UseCase.folders and not req.folders:
        raise _missing("use_case 'folders' braucht 'folders'.")
    if req.use_case == UseCase.contents and not has_items:
        raise _missing("use_case 'contents' braucht mindestens einen Eintrag in 'items' oder 'items_ref'.")
    if req.use_case == UseCase.document and not req.items_ref:
        structure_docs = [
            item for item in req.items or [] if ItemUse.structure in req.effective_use(item) and item.fulltext
        ]
        if not structure_docs:
            raise _missing("use_case 'document' braucht ein Strukturdokument (use: structure) mit Volltext.")


def check_request(req: TopicTreeRequestV2, settings: Settings) -> None:
    if req.mode == Mode.refine and req.current_tree is None:
        raise _missing("mode 'refine' braucht 'current_tree'.")
    if req.options.assign_only and req.mode != Mode.refine:
        raise ApiError(422, "INVALID_OPTION", "options.assign_only ist nur mit mode 'refine' möglich.")
    _check_items(req, settings)
    if req.mode == Mode.create:
        _check_create_inputs(req)
