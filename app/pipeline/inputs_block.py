"""Compact prompt blocks for supplementary inputs: items with `use: structure` outside their own use case and the
folder structure when it is not the backbone (`folders_use`). Only inline full texts are used here; referenced texts
are loaded before (see inputs/refs.py)."""

from app.domain.diff import FOLDER_SEPARATOR
from app.domain.text import one_line, truncate_sentences
from app.pipeline.run_context import RunContext
from app.schemas.common import ItemUse, Mode, UseCase
from app.schemas.request_v2 import FolderNode, Item, TopicTreeRequestV2

MAX_ITEMS = 50
MAX_FULLTEXT = 5
MAX_FOLDER_LINES = 200
DESC_LIMIT = 300
EXCERPT = 1500
HEADING = "## Ergänzende Eingaben (dürfen zusätzliche Themen anregen)"


def _item_lines(items: list[Item], fulltext_left: int) -> list[str]:
    lines = []
    for item in items:
        title = one_line(item.properties.first("cm:title") or item.id)
        parts = [f"- {title}"]
        if description := item.properties.first("cm:description"):
            parts.append(one_line(truncate_sentences(description, DESC_LIMIT)))
        if keywords := item.properties.values("cclom:general_keyword"):
            parts.append("Schlagworte: " + ", ".join(map(one_line, keywords[:8])))
        lines.append(
            " | ".join(parts) if len(parts) > 2 else (f"{parts[0]}: {parts[1]}" if len(parts) == 2 else parts[0])
        )
        if fulltext_left > 0 and item.fulltext and item.fulltext.text and item.fulltext.text.strip():
            lines.append(f"  Auszug: {one_line(truncate_sentences(item.fulltext.text, EXCERPT))}")
            fulltext_left -= 1
    return lines


def folders_shape_tree(req: TopicTreeRequestV2) -> bool:
    """The folder structure is a supplementary structure source (not the backbone of use case `folders`)."""
    return (
        bool(req.folders)
        and req.mode == Mode.create
        and req.use_case != UseCase.folders
        and ItemUse.structure in req.effective_folders_use()
    )


def _folder_lines(folders: list[FolderNode], depth: int = 0) -> list[str]:
    lines = []
    for folder in folders:
        files = f" ({len(folder.items)} Dateien)" if folder.items else ""
        lines.append(f"{'  ' * depth}- {one_line(folder.title)}{files}")
        lines.extend(_folder_lines(folder.subcollections, depth + 1))
    return lines


def folders_block(req: TopicTreeRequestV2, rc: RunContext | None = None) -> str:
    if not folders_shape_tree(req):
        return ""
    lines = _folder_lines(req.folders or [])
    if len(lines) > MAX_FOLDER_LINES:
        if rc is not None:
            rc.warn(
                "INPUTS_TRUNCATED", f"Nur {MAX_FOLDER_LINES} Ordner flossen in die Strukturplanung ein.", step="inputs"
            )
        lines = lines[:MAX_FOLDER_LINES]
    return "### Ordnerstruktur des Nutzers (darf Themen und Gliederung anregen)\n" + "\n".join(lines) + "\n"


def structure_inputs_block(
    req: TopicTreeRequestV2, rc: RunContext | None = None, *, items: list[Item] | None = None
) -> str:
    """Structure items (all by default, or the given ones) plus the folder structure where it shapes the tree."""
    if items is None:
        items = [i for i in req.items or [] if ItemUse.structure in req.effective_use(i)]
    folders = folders_block(req, rc)
    if not items and not folders:
        return ""
    if len(items) > MAX_ITEMS and rc is not None:
        rc.warn(
            "INPUTS_TRUNCATED",
            f"Nur {MAX_ITEMS} von {len(items)} ergänzenden Struktur-Items flossen in die Strukturplanung ein.",
            step="inputs",
        )
    with_text = [i.id for i in items[:MAX_ITEMS] if i.fulltext and i.fulltext.text and i.fulltext.text.strip()]
    if len(with_text) > MAX_FULLTEXT and rc is not None:
        rest = with_text[MAX_FULLTEXT:]
        rc.warn(
            "INPUTS_TRUNCATED",
            f"Nur die Volltexte der ersten {MAX_FULLTEXT} Struktur-Items flossen als Auszug ein; von "
            f"{', '.join(rest[:20])}{' …' if len(rest) > 20 else ''} nur Titel und Beschreibung.",
            step="inputs",
        )
    head = "\n".join([HEADING, *_item_lines(items[:MAX_ITEMS], MAX_FULLTEXT)]) + "\n" if items else HEADING + "\n"
    return head + folders


def folder_paths(req: TopicTreeRequestV2) -> dict[str, str]:
    """Item id -> folder path, from `Item.path` and, where the folder assignments count, from `folders`."""
    paths = {item.id: item.path for item in req.items or [] if item.path}
    if not req.folders or ItemUse.content not in req.effective_folders_use():
        return paths

    def visit(folders: list[FolderNode], trail: list[str]) -> None:
        for folder in folders:
            here = [*trail, one_line(folder.title)]
            for item_id in folder.items:
                paths.setdefault(item_id, FOLDER_SEPARATOR.join(here))
            visit(folder.subcollections, here)

    visit(req.folders, [])
    return paths
