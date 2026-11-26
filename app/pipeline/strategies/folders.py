"""Use case `folders`: take the uploaded folder tree as is (or improved on request) and keep its assignments."""

from app.domain.diff import FOLDER_SEPARATOR
from app.domain.keys import assign_missing_keys
from app.domain.text import one_line
from app.domain.tree import Node, walk
from app.llm.client import LLMStepError
from app.pipeline.inputs_block import structure_inputs_block
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.improve_folders import improve_folders
from app.schemas.common import ItemUse, OriginType
from app.schemas.request_v2 import FolderNode, Item, TopicTreeRequestV2
from app.schemas.response_v2 import ContentRef, Origin, StructureInfo

_DESCRIBE_TITLES = 10


def item_titles(items: list[Item]) -> dict[str, str]:
    return {item.id: one_line(item.properties.first("cm:title") or item.id) for item in items}


def folders_to_nodes(folders: list[FolderNode], req: TopicTreeRequestV2, trail: list[str] | None = None) -> list[Node]:
    by_id = {item.id: item for item in req.items or []}
    keep = ItemUse.content in req.effective_folders_use()  # without it, the files are assigned anew afterwards
    nodes = []
    for folder in folders:
        here = [*(trail or []), folder.title]
        contents = [
            ContentRef(id=i, nodeId=by_id[i].node_id if i in by_id else None, confidence=1.0)
            for i in folder.items
            if keep and (i not in by_id or ItemUse.content in req.effective_use(by_id[i]))
        ]
        nodes.append(
            Node(
                key=None,
                title=folder.title,
                origin=Origin(type=OriginType.folder, path=FOLDER_SEPARATOR.join(here)),
                confidence=1.0,
                contents=contents,
                children=folders_to_nodes(folder.subcollections, req, here),
            )
        )
    return nodes


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    roots = folders_to_nodes(req.folders or [], req)
    assign_missing_keys(roots)
    titles = item_titles(req.items or [])
    changes = []
    shaping = [i.id for i in req.items or [] if ItemUse.structure in req.effective_use(i)]
    if not req.options.improve and shaping:
        rc.warn(
            "INPUT_IGNORED",
            "Einträge mit Rolle Gliederung prägen bei use_case 'folders' die Struktur nur mit options.improve; "
            f"ihre Gliederungsrolle wurde ignoriert, Inhalte darunter werden trotzdem einsortiert ({', '.join(shaping[:20])}).",
            step="folders",
        )
    if req.options.improve:
        try:
            applied = await improve_folders(roots, titles, rc, inputs_block=structure_inputs_block(req, rc))
            changes = applied.applied
            assign_missing_keys(roots)
        except LLMStepError as err:
            rc.warn(
                "LLM_DEGRADED",
                f"Sprachmodell für Ordner-Verbesserung nicht verfügbar ({err.status or err.reason}); "
                "Ordnerstruktur unverändert übernommen.",
                step="improve_folders",
            )
    extra = {
        node.key: "Inhalte: " + ", ".join(titles.get(ref.id, ref.id) for ref in node.contents[:_DESCRIBE_TITLES])
        for node, _, _ in walk(roots)
        if node.contents
    }
    targets = [node for node, _, _ in walk(roots) if not node.description]
    await describe_nodes(
        targets, roots, rc, context=rc.context, description_length=req.hints.description_length, extra=extra
    )
    return StrategyResult(
        roots=roots,
        title=req.topic or (roots[0].title if len(roots) == 1 else "Sammlung aus Ordnern"),
        structure=StructureInfo(order="Ordner", levels=[], source="input"),
        changes=changes,
        shape_checked=req.options.improve,
    )
