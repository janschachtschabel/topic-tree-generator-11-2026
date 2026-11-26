"""Markdown → outline of sections with heading level and page (plan E11). Deterministic; no LLM.

Page markers understood: `<!-- page: N -->`, `<!-- PageNumber="N" -->` (set the page), `<!-- page_break -->`,
`<!-- PageBreak -->` and form feed (advance the page; counting starts at 1). Without markers pages stay None.
"""

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_PAGE_SET = re.compile(r"<!--\s*(?:page:\s*(\d+)|PageNumber=\"(\d+)\")\s*-->", re.IGNORECASE)
_PAGE_BREAK = re.compile(r"<!--\s*(?:page_break|PageBreak)\s*-->", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
# `*` and backticks are always markup; `_` only at word edges, so `snake_case` keeps its underscore.
_EMPHASIS = re.compile(r"[*`]+|(?<!\w)_+|_+(?!\w)")


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


class _Parser:
    def __init__(self, has_breaks: bool) -> None:
        self.page: int | None = 1 if has_breaks else None
        self.sections: list[Section] = []
        self.preamble: list[str] = []
        self.fence: str | None = None

    @property
    def body(self) -> list[str]:
        return self.sections[-1].lines if self.sections else self.preamble

    def heading(self, level: int, raw: str) -> bool:
        title = _EMPHASIS.sub("", raw).strip()
        if title:
            self.sections.append(Section(f"s{len(self.sections) + 1}", level, title, self.page))
        return bool(title)

    def page_markers(self, line: str) -> str:
        """Apply the page markers on the line and return what is left of it."""
        for match in _PAGE_SET.finditer(line):
            self.page = int(match.group(1) or match.group(2))
        for _ in _PAGE_BREAK.finditer(line):
            self.page = (self.page or 1) + 1
        return _PAGE_BREAK.sub("", _PAGE_SET.sub("", line))

    def setext(self, line: str) -> bool:
        """`Title` followed by `===` (level 1) or `---` (level 2); a `---` after a blank line stays a rule."""
        match = _SETEXT.match(line)
        body = self.body
        if not match or not body or not body[-1].strip() or _LIST_ITEM.match(body[-1]):
            return False
        title = body.pop()
        if self.heading(1 if match.group(1)[0] == "=" else 2, title):
            return True
        body.append(title)
        return False

    def feed(self, line: str) -> None:
        if fence := _FENCE.match(line):
            marker = fence.group(1)
            if self.fence is None:
                self.fence = marker
            elif marker[0] == self.fence[0] and len(marker) >= len(self.fence):
                self.fence = None
        elif self.fence is None:
            had_marker = _PAGE_SET.search(line) or _PAGE_BREAK.search(line)
            line = self.page_markers(line)
            if had_marker and not line.strip():
                return
            if (match := _HEADING.match(line)) and self.heading(len(match.group(1)), match.group(2)):
                return
            if self.setext(line):
                return
        self.body.append(line)


def parse_outline(text: str, fallback_title: str = "Dokument") -> list[Section]:
    lines = _split_form_feeds(text)
    parser = _Parser(any(_PAGE_BREAK.search(line) for line in lines))
    for line in lines:
        parser.feed(line)
    if not parser.sections:
        return [Section("s1", 1, fallback_title, parser.page, parser.preamble)]
    return parser.sections
