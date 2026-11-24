from pathlib import Path

import pytest

from app.pipeline.inputs.outline import parse_outline

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
