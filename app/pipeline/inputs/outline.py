"""Markdown → outline of sections with heading level and page (plan E11). Deterministic; no LLM.

Page markers understood: `<!-- page: N -->`, `<!-- PageNumber="N" -->` (set the page), `<!-- page_break -->`,
`<!-- PageBreak -->` and form feed (advance the page; counting starts at 1). Without markers pages stay None.
"""

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_PAGE_SET = re.compile(r"<!--\s*(?:page:\s*(\d+)|PageNumber=\"(\d+)\")\s*-->", re.IGNORECASE)
_PAGE_BREAK = re.compile(r"<!--\s*(?:page_break|PageBreak)\s*-->", re.IGNORECASE)
_FENCE = re.compile(r"^\s*(```|~~~)")
_EMPHASIS = re.compile(r"[*_`]+")


@dataclass
class Section:
    id: str
    level: int
    title: str
    page: int | None
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


def _split_form_feeds(text: str) -> list[str]:
    # A form feed separates pages; turn it into a break marker on its own line.
    return text.replace("\f", "\n<!-- page_break -->\n").splitlines()


def parse_outline(text: str, fallback_title: str = "Dokument") -> list[Section]:
    lines = _split_form_feeds(text)
    has_breaks = any(_PAGE_BREAK.search(line) for line in lines)
    page: int | None = 1 if has_breaks else None
    sections: list[Section] = []
    preamble: list[str] = []
    in_fence = False

    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            if match := _PAGE_SET.search(line):
                page = int(match.group(1) or match.group(2))
                continue
            if _PAGE_BREAK.search(line):
                page = (page or 1) + 1
                continue
            if match := _HEADING.match(line):
                title = _EMPHASIS.sub("", match.group(2)).strip()
                if title:
                    sections.append(Section(f"s{len(sections) + 1}", len(match.group(1)), title, page))
                    continue
        (sections[-1].lines if sections else preamble).append(line)

    if not sections:
        return [Section("s1", 1, fallback_title, page, preamble)]
    return sections
