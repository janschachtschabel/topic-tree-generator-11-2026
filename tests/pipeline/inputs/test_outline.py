from pathlib import Path

import pytest

from app.pipeline.inputs.outline import parse_outline
from app.pipeline.inputs.outline_tree import drop_title_heading, outline_mapping

FIXTURE = (Path(__file__).parents[2] / "fixtures" / "lehrplan_physik_auszug.md").read_text(encoding="utf-8")


def test_headings_become_sections_with_level_page_and_text() -> None:
    sections = parse_outline(FIXTURE)
    assert [(s.id, s.level, s.title, s.page) for s in sections] == [
        ("s1", 1, "Lehrplan Physik, Klassen 7 bis 10", 11),
        ("s2", 2, "Themenfeld 1: Wahrnehmung", 12),
        ("s3", 3, "Kompetenzen", 12),
        ("s4", 2, "Themenfeld 2: Optische Phänomene an Grenzflächen", 14),
        ("s5", 3, "Fachbegriffe", 14),
        ("s6", 2, "Wahlpflicht: Astronomie", 14),
    ]
    assert sections[3].text == "Reflexion, Brechung, Absorption."
    assert "keine Überschrift" in sections[2].text


@pytest.mark.parametrize(
    "marker",
    ["<!-- page_break -->", "<!-- PageBreak -->", "\f"],
)
def test_break_markers_count_pages_from_one(marker: str) -> None:
    text = f"# A\nText\n{marker}\n# B\nText\n{marker}\n# C\n"
    assert [s.page for s in parse_outline(text)] == [1, 2, 3]


def test_azure_page_number_comments_set_the_page() -> None:
    text = '<!-- PageNumber="7" -->\n# A\n<!-- PageNumber="8" -->\n# B\n'
    assert [s.page for s in parse_outline(text)] == [7, 8]


def test_without_markers_pages_stay_empty() -> None:
    assert [s.page for s in parse_outline("# A\n## B\n")] == [None, None]


def test_document_without_headings_is_one_section() -> None:
    (section,) = parse_outline("Nur Fließtext ohne Gliederung.", fallback_title="Dokument X")
    assert (section.id, section.level, section.title, section.text) == (
        "s1",
        1,
        "Dokument X",
        "Nur Fließtext ohne Gliederung.",
    )


def test_trailing_hashes_and_emphasis_are_stripped_from_titles() -> None:
    (section,) = parse_outline("## **Themenfeld 3** ##\n")
    assert section.title == "Themenfeld 3"


def test_drop_title_heading_only_removes_a_lone_top_heading() -> None:
    kept = drop_title_heading(parse_outline("# A\n# B\n## C"))
    assert [(s.title, s.level) for s in kept] == [("A", 1), ("B", 1), ("C", 2)]
    dropped = drop_title_heading(parse_outline("# Titel\n## A\n### B"))
    assert [(s.id, s.title, s.level) for s in dropped] == [("s2", "A", 1), ("s3", "B", 2)]
    assert [s.title for s in drop_title_heading(parse_outline("# Nur Titel"))] == ["Nur Titel"]


def test_outline_mapping_follows_headings_and_skips_excluded_branches() -> None:
    sections = parse_outline("## 1. Licht\n### Quellen\n## Wahlpflicht\n### Beugung\n## 2. Farben")
    nodes = outline_mapping([(f"d:{s.id}", s) for s in sections], ["wahlpflicht"])
    assert [(n.title, [c.title for c in n.children]) for n in nodes] == [("Licht", ["Quellen"]), ("Farben", [])]
    assert nodes[0].section_ids == ["d:s1"]


def test_a_closing_hash_needs_a_space_before_it() -> None:
    titles = [s.title for s in parse_outline("# C#\n\n## F# und C# ##\n")]
    assert titles == ["C#", "F# und C#"]


def test_inner_underscores_stay_and_emphasis_markers_go() -> None:
    (section,) = parse_outline("## _Begriff_ snake_case und __fett__\n")
    assert section.title == "Begriff snake_case und fett"


def test_a_fence_closes_only_with_its_own_marker() -> None:
    text = "# Eins\n```\n~~~\n# kein Titel\n```\n# Zwei\n"
    assert [s.title for s in parse_outline(text)] == ["Eins", "Zwei"]


def test_setext_headings_are_recognised() -> None:
    text = "Kapitel A\n=========\nText\n\nAbschnitt B\n-----------\nMehr\n\n---\n"
    sections = parse_outline(text)
    assert [(s.level, s.title) for s in sections] == [(1, "Kapitel A"), (2, "Abschnitt B")]
    assert sections[0].text == "Text"


def test_text_on_a_line_with_a_page_marker_is_kept() -> None:
    (section,) = parse_outline("# Eins\nWichtiger Satz <!-- page: 4 -->\nDanach\n")
    assert "Wichtiger Satz" in section.text
    assert parse_outline("# Eins\nx <!-- page: 4 -->\n# Zwei\n")[1].page == 4


def test_exclude_terms_match_at_word_starts_only() -> None:
    sections = [
        ("d:s1", parse_outline("# Funktionen\n")[0]),
        ("d:s2", parse_outline("# Ionen\n")[0]),
        ("d:s3", parse_outline("# Ionenbindung\n")[0]),
    ]
    titles = [n.title for n in outline_mapping(sections, ["Ion"])]
    assert titles == ["Funktionen"]
