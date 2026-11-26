"""Fixed values of the v2 format (Spec: "Feldwerte und Vokabulare")."""

from enum import StrEnum


class Mode(StrEnum):
    create = "create"
    refine = "refine"


class UseCase(StrEnum):
    topic = "topic"
    document = "document"
    folders = "folders"
    contents = "contents"


class ItemUse(StrEnum):
    structure = "structure"
    content = "content"


class FulltextFormat(StrEnum):
    markdown = "markdown"
    text = "text"


class ExtraTopic(StrEnum):
    general = "general"
    methodology = "methodology"


class NodeStatus(StrEnum):
    new = "new"
    unchanged = "unchanged"
    changed = "changed"
    moved = "moved"
    suggested = "suggested"


class OriginType(StrEnum):
    topic = "topic"
    document = "document"
    folder = "folder"
    cluster = "cluster"
    feedback = "feedback"


class ChangeOp(StrEnum):
    add = "add"
    remove = "remove"
    rename = "rename"
    edit = "edit"
    move = "move"
    merge = "merge"
    split = "split"
    describe = "describe"


class ChangeSource(StrEnum):
    feedback_text = "feedback_text"
    feedback_changes = "feedback_changes"
    service = "service"


class UnassignedReason(StrEnum):
    off_topic = "off_topic"
    low_confidence = "low_confidence"
    no_matching_node = "no_matching_node"
    excluded = "excluded"
