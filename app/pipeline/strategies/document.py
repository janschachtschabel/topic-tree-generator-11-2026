"""Use case `document`: the outline of structure documents (e.g. a curriculum) becomes the tree."""

from dataclasses import dataclass

from app.domain.keys import assign_missing_keys
from app.domain.text import truncate_sentences
from app.domain.tree import Node, walk
from app.llm.client import LLMStepError
from app.pipeline.inputs.outline import Section, parse_outline
from app.pipeline.inputs.outline_tree import drop_title_heading, outline_mapping
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.pipeline.steps.describe_nodes import describe_nodes
from app.pipeline.steps.map_outline import MappedNode, map_outline
from app.schemas.common import FulltextFormat, ItemUse, OriginType
from app.schemas.request_v2 import Item, TopicTreeRequestV2
from app.schemas.response_v2 import Origin, StructureInfo

MAX_SECTIONS = 600
EXCERPT_CHARS = 12000
SECTION_EXCERPT = 1500


@dataclass
class DocSection:
    doc_id: str
    section: Section

    @property
    def ref(self) -> str:
        return f"{self.doc_id}:{self.section.id}"


def structure_documents(req: TopicTreeRequestV2) -> list[Item]:
    return [
        i
        for i in req.items or []
        if ItemUse.structure in req.effective_use(i) and i.fulltext and i.fulltext.text and i.fulltext.text.strip()
    ]


def _sections(doc: Item) -> list[DocSection]:
    title = doc.properties.first("cm:title") or doc.id
    text = doc.fulltext.text or ""
    if doc.fulltext.format != FulltextFormat.markdown:
        # Plain text has no headings: the whole document is one section, so it still enters the outline.
        return [DocSection(doc.id, Section("s1", 1, title, None, text.splitlines()))]
    return [DocSection(doc.id, s) for s in drop_title_heading(parse_outline(text, fallback_title=title))]


def _outline_text(sections: list[DocSection], docs: list[Item], rc: RunContext) -> str:
    if len(sections) <= len(docs):
        # No usable headings: hand over a text excerpt instead of an outline.
        return "\n\n".join(f"Dokument {d.id}:\n{truncate_sentences(d.fulltext.text, EXCERPT_CHARS)}" for d in docs)
    if len(sections) > MAX_SECTIONS:
        rc.warn("OUTLINE_TRUNCATED", f"Gliederung auf {MAX_SECTIONS} Abschnitte gekürzt.", step="document")
        sections = sections[:MAX_SECTIONS]
    lines = []
    for s in sections:
        page = f" | Seite {s.section.page}" if s.section.page is not None else ""
        lines.append(f"{s.ref} | Ebene {s.section.level}{page} | {s.section.title}")
    return "\n".join(lines)


class _Converter:
    def __init__(self, sections: dict[str, DocSection], default_doc: str, req: TopicTreeRequestV2) -> None:
        self.sections = sections
        self.default_doc = default_doc
        self.req = req
        self.unknown = 0
        self.too_deep = False
        self.too_wide = False
        self.excerpts: dict[int, str] = {}

    def nodes(self, items: list[MappedNode], levels_left: int, width: int) -> list[Node]:
        if levels_left <= 0:
            self.too_deep = self.too_deep or bool(items)
            return []
        self.too_wide = self.too_wide or len(items) > width
        return [self.node(item, levels_left, width) for item in items[:width]]

    def node(self, item: MappedNode, levels_left: int, width: int) -> Node:
        known = [self.sections[i] for i in item.section_ids if i in self.sections]
        self.unknown += len(item.section_ids) - len(known)
        first = known[0] if known else None
        origin = Origin(
            type=OriginType.document,
            id=first.doc_id if first else self.default_doc,
            section=first.section.title if first else None,
            page=first.section.page if first else None,
        )
        node = Node(
            key=None,
            title=item.title.strip(),
            shorttitle=item.shorttitle.strip(),
            origin=origin,
            children=self.nodes(item.children, levels_left - 1, self.req.shape.children.max),
        )
        excerpt = truncate_sentences("\n".join(s.section.text for s in known), SECTION_EXCERPT)
        if excerpt:
            self.excerpts[id(node)] = excerpt
        return node


def _checked_mapping(
    nodes: list[MappedNode], sections: list[DocSection], req: TopicTreeRequestV2, rc: RunContext
) -> list[MappedNode]:
    """The LLM mapping, or the document's own headings when the mapping collapsed the outline.

    With a topic the mapping may keep only the matching sections, so only an empty mapping counts as collapsed."""
    outline = outline_mapping([(s.ref, s.section) for s in sections], req.hints.exclude)
    if nodes and req.topic:
        return nodes
    if len(nodes) >= min(req.shape.main_topics.min, len(outline)):
        return nodes
    rc.warn(
        "OUTLINE_FALLBACK",
        f"Die Zuordnung ergab nur {len(nodes)} Hauptknoten; der Baum folgt deshalb direkt der Gliederung "
        f"des Dokuments ({len(outline)} Hauptabschnitte).",
        step="map_outline",
    )
    return outline


async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    docs = structure_documents(req)
    sections = [s for doc in docs for s in _sections(doc)]
    try:
        mapping = await map_outline(_outline_text(sections, docs, rc), rc, req.topic)
        mapped = _checked_mapping(mapping.nodes, sections, req, rc)
        order, levels, description = mapping.order, mapping.levels, mapping.description
        if req.topic and mapped is mapping.nodes and len(mapped) == 1 and mapped[0].children:
            # One section covers the topic: its subsections become the main topics.
            mapped, levels = mapped[0].children, levels[1:]
    except LLMStepError as err:
        fallback = outline_mapping([(s.ref, s.section) for s in sections], req.hints.exclude)
        if not fallback or len(sections) <= len(docs):
            raise
        rc.warn(
            "LLM_DEGRADED",
            f"Sprachmodell für Gliederung nicht verfügbar ({err.status or err.reason}); "
            "der Baum folgt direkt den Überschriften des Dokuments.",
            step="map_outline",
        )
        mapped = fallback
        order, levels, description = "Gliederung", [], ""

    converter = _Converter({s.ref: s for s in sections}, docs[0].id, req)
    roots = converter.nodes(mapped, req.shape.depth, req.shape.main_topics.max)
    if converter.too_deep:
        rc.warn("SHAPE_DEPTH", "Der abgeleitete Baum war zu tief und wurde gekürzt.", step="map_outline")
    if converter.too_wide:
        rc.warn("SHAPE_WIDTH", "Der abgeleitete Baum hatte zu viele Knoten je Ebene; gekürzt.", step="map_outline")
    if converter.unknown:
        rc.warn("SECTION_UNKNOWN", f"{converter.unknown} unbekannte Abschnittsverweise verworfen.", step="map_outline")
    assign_missing_keys(roots)

    extra = {
        n.key: f"Textauszug: {converter.excerpts[id(n)]}" for n, _, _ in walk(roots) if id(n) in converter.excerpts
    }
    await describe_nodes(
        [n for n, _, _ in walk(roots)],
        roots,
        rc,
        context=rc.context,
        description_length=req.hints.description_length,
        extra=extra,
    )
    title = req.topic or ", ".join(d.properties.first("cm:title") or d.id for d in docs)
    return StrategyResult(
        roots=roots,
        title=title,
        description=description,
        structure=StructureInfo(
            order=req.hints.order or order,
            levels=levels[: req.shape.depth],
            source="hint" if req.hints.order else "input",
        ),
    )
