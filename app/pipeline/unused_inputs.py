"""Warnings for inputs that a call accepts but does not use, so nothing a caller sends drops out silently."""

from app.pipeline.run_context import RunContext
from app.schemas.common import ItemUse, Mode, UseCase
from app.schemas.request_v2 import Options, TopicTreeRequestV2


def _shown(ids: list[str]) -> str:
    return ", ".join(ids[:20]) + (" …" if len(ids) > 20 else "")


def _folder_item_ids(req: TopicTreeRequestV2) -> set[str]:
    """Files whose folder assignment is kept as is by use case `folders` (they need no assignment step)."""
    if ItemUse.content not in req.effective_folders_use():
        return set()
    ids: set[str] = set()
    stack = list(req.folders or [])
    while stack:
        folder = stack.pop()
        ids.update(folder.items)
        stack.extend(folder.subcollections)
    return ids


def _tree_content_ids(nodes: list) -> set[str]:
    ids: set[str] = set()
    stack = list(nodes)
    while stack:
        node = stack.pop()
        ids.update(ref.id for ref in node.contents)
        stack.extend(node.subcollections)
    return ids


def warn_unused_inputs(req: TopicTreeRequestV2, rc: RunContext, options: Options | None = None) -> None:
    """`options` are the effective ones (a refine inherits them from `current_tree.generation`)."""
    options = options or req.options
    if req.mode == Mode.refine:
        _refine(req, rc)
        if options.assign_only and req.options.auto_metadata and "auto_metadata" in req.options.model_fields_set:
            rc.warn(
                "INPUT_IGNORED",
                "options.auto_metadata wurde ignoriert: Mit assign_only bleiben die Knoten unverändert.",
                step="input",
            )
        generation = req.current_tree.generation if req.current_tree else None
        if options.assign_only and generation and generation.frame and generation.frame != req.frame:
            rc.warn(
                "INPUT_IGNORED",
                "Der geänderte frame wurde ignoriert: Mit assign_only bleiben Knoten und Rahmen des Baums unverändert.",
                step="input",
            )
    elif req.folders and req.use_case != UseCase.folders and not req.effective_folders_use():
        rc.warn(
            "INPUT_IGNORED",
            "Die Ordnerstruktur wurde mit folders_use [] angenommen, aber weder für die Struktur noch für die "
            "Zuordnung genutzt.",
            step="input",
        )
    if req.folders_use is not None and not req.folders:
        rc.warn("INPUT_IGNORED", "folders_use wurde ohne folders gesendet und ignoriert.", step="input")
    if req.mode == Mode.create and req.use_case != UseCase.topic and req.shape.extra_topics:
        rc.warn(
            "INPUT_IGNORED",
            "shape.extra_topics gilt nur bei use_case 'topic' und wurde ignoriert.",
            step="input",
        )
    if not options.assign_contents:
        kept = _folder_item_ids(req) if req.use_case == UseCase.folders else set()
        if req.mode == Mode.refine and req.current_tree is not None:
            kept |= _tree_content_ids(req.current_tree.collection)  # already placed: they stay where they are
        ids = [i.id for i in req.items or [] if ItemUse.content in req.effective_use(i) and i.id not in kept]
        if ids:
            rc.warn(
                "INPUT_IGNORED",
                f"options.assign_contents ist aus: {len(ids)} Inhalte wurden nicht einsortiert ({_shown(ids)}).",
                step="input",
            )


def _refine(req: TopicTreeRequestV2, rc: RunContext) -> None:
    hint = "Gewünschte Änderungen bitte als Rückmeldung (feedback) formulieren."
    if req.folders:
        rc.warn(
            "INPUT_IGNORED",
            "Beim Weiterentwickeln gilt der bestehende Baum (current_tree); folders prägt die Struktur nicht, "
            f"Ordnerpfade dienen nur als Zuordnungshinweis. {hint}",
            step="input",
        )
    # Only an explicit structure role counts: default roles (e.g. materials of a contents tree) are content here.
    ids = [i.id for i in req.items or [] if i.use is not None and ItemUse.structure in i.use]
    if ids:
        rc.warn(
            "INPUT_IGNORED",
            f"Beim Weiterentwickeln prägen neue Gliederungsdokumente den Baum nicht ({_shown(ids)}); Inhalte darunter "
            f"werden nur einsortiert. {hint}",
            step="input",
        )
