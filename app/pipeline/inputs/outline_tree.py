"""Deterministic help for structure documents: drop a lone title heading and derive a tree from the headings.

The LLM normally selects and names the sections (`map_outline`). When its answer collapses the document (fewer
main nodes than requested although the outline has enough top-level sections), the strategy falls back to the
document's own heading hierarchy built here, so the tree still follows the source.
"""

import re
from dataclasses import replace

from app.pipeline.inputs.outline import Section
from app.pipeline.steps.map_outline import MappedNode

_NUMBERING = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+")


def drop_title_heading(sections: list[Section]) -> list[Section]:
    """Without a lone top heading (the document title) the main sections become level 1; ids stay unchanged."""
    if len(sections) < 2:
        return sections
    top = min(s.level for s in sections)
    first = sections[0]
    if first.level == top and all(s.level > top for s in sections[1:]):
        sections = sections[1:]
    shift = min(s.level for s in sections) - 1
    return [replace(s, level=s.level - shift) for s in sections] if shift else sections


def _excluded(title: str, exclude: list[str]) -> bool:
    low = title.casefold()
    return any(term.strip() and term.strip().casefold() in low for term in exclude)


def outline_mapping(sections: list[tuple[str, Section]], exclude: list[str]) -> list[MappedNode]:
    """Heading hierarchy as mapped nodes (`(ref, section)` pairs in document order); excluded branches are skipped."""
    roots: list[MappedNode] = []
    stack: list[tuple[int, MappedNode | None]] = []  # (level, node); None marks an excluded branch
    for ref, section in sections:
        while stack and stack[-1][0] >= section.level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        if (stack and parent is None) or _excluded(section.title, exclude):
            stack.append((section.level, None))
            continue
        node = MappedNode(title=_NUMBERING.sub("", section.title), shorttitle="", section_ids=[ref])
        (parent.children if parent else roots).append(node)
        stack.append((section.level, node))
    return roots
