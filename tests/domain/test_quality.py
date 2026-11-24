"""Tests for deterministic naming quality checks and keyword hygiene."""

from app.domain.quality import check_quality, clean_keywords
from app.domain.tree import Node
from app.schemas.common import NodeStatus, OriginType
from app.schemas.response_v2 import Origin


def _node(
    key: str,
    title: str,
    *children: Node,
    origin_type: OriginType = OriginType.topic,
    keywords: list[str] | None = None,
) -> Node:
    origin = Origin(type=origin_type, path=title if origin_type == OriginType.folder else None)
    return Node(
        key=key,
        title=title,
        status=NodeStatus.new,
        origin=origin,
        keywords=list(keywords or []),
        children=list(children),
    )


def _codes(warnings) -> list[tuple[str, str | None]]:
    return [(w.code, w.key) for w in warnings]


def test_clean_keywords_removes_platform_stopwords_and_duplicates() -> None:
    node = _node(
        "k-optik",
        "Brechung",
        keywords=["Brechung", "Arbeitsblatt", "Lichtbrechung", "Unterricht", "Snellius", "lichtbrechung", "  "],
    )
    clean_keywords([node])
    assert node.keywords == ["Lichtbrechung", "Snellius"]


def test_clean_keywords_keeps_title_when_it_is_the_only_remaining_keyword() -> None:
    node = _node("k-optik", "Brechung", keywords=["Brechung", "Arbeitsblatt", "Unterricht"])
    clean_keywords([node])
    assert node.keywords == ["Brechung"]


def test_clean_keywords_leaves_locked_nodes_untouched() -> None:
    node = _node("k-lock", "Brechung", keywords=["Arbeitsblatt", "Brechung"])
    clean_keywords([node], protected={"k-lock"})
    assert node.keywords == ["Arbeitsblatt", "Brechung"]


def test_check_quality_flags_generic_catchall_titles() -> None:
    roots = [
        _node("k-1", "Sonstiges"),
        _node("k-2", "Geometrische Optik", _node("k-2a", "Überblick"), _node("k-2b", "Linsen")),
        _node("k-3", "Weiteres"),
    ]
    warnings = check_quality(roots, topic="Optik")
    assert _codes(warnings) == [
        ("GENERIC_TITLE", "k-1"),
        ("GENERIC_TITLE", "k-2a"),
        ("GENERIC_TITLE", "k-3"),
    ]


def test_check_quality_does_not_flag_legitimate_domain_headings() -> None:
    roots = [_node("k-1", "Literatur"), _node("k-2", "Rezeption")]
    assert check_quality(roots, topic="Deutsch") == []


def test_check_quality_allows_requested_extra_topics_only_on_top_level() -> None:
    roots = [
        _node("k-allg", "Allgemeines"),
        _node("k-opt", "Linsen", _node("k-nested", "Allgemeines")),
        _node("k-meth", "Methodik und Didaktik"),
    ]
    warnings = check_quality(roots, topic="Optik", allowed_extra={"allgemeines", "methodik und didaktik"})
    assert _codes(warnings) == [("GENERIC_TITLE", "k-nested")]


def test_check_quality_flags_unrequested_extra_topics() -> None:
    roots = [_node("k-allg", "Allgemeines"), _node("k-meth", "Methodik und Didaktik")]
    warnings = check_quality(roots, topic="Optik")
    assert _codes(warnings) == [("GENERIC_TITLE", "k-allg"), ("GENERIC_TITLE", "k-meth")]


def test_check_quality_flags_temporal_headings_only_outside_history() -> None:
    roots = [
        _node("k-1", "1960er Jahre"),
        _node("k-2", "Anfang des 20. Jahrhunderts"),
        _node("k-3", "Frühes 19. Jahrhundert"),
        _node("k-4", "Spätes 20. Jahrhundert"),
        _node("k-5", "Treibhauseffekt"),
    ]
    non_history = check_quality(roots, topic="Klimawandel", is_history=False)
    assert _codes(non_history) == [
        ("GENERIC_TITLE", "k-1"),
        ("GENERIC_TITLE", "k-2"),
        ("GENERIC_TITLE", "k-3"),
        ("GENERIC_TITLE", "k-4"),
    ]

    history = check_quality(roots, topic="Deutsche Geschichte", is_history=True)
    assert history == []


def test_clean_keywords_keeps_domain_bearing_terms() -> None:
    node = _node("k-inf", "Objektorientierung", keywords=["Klasse", "Medium", "Material", "Test", "Arbeitsblatt"])
    clean_keywords([node])
    assert node.keywords == ["Klasse", "Medium", "Material", "Test"]


def test_check_quality_flags_facet_nodes() -> None:
    roots = [
        _node("k-1", "Arbeitsblätter"),
        _node("k-2", "Klasse 8"),
        _node("k-3", "Kompetenzen"),
        _node("k-4", "Sekundarstufe I"),
        _node("k-5", "Lichtausbreitung"),
    ]
    warnings = check_quality(roots, topic="Optik")
    assert _codes(warnings) == [
        ("FACET_AS_NODE", "k-1"),
        ("FACET_AS_NODE", "k-2"),
        ("FACET_AS_NODE", "k-3"),
        ("FACET_AS_NODE", "k-4"),
    ]


def test_check_quality_flags_top_level_topic_repeat_only() -> None:
    roots = [
        _node("k-1", "Optik"),
        _node("k-2", "Wellenlehre", _node("k-2a", "Optik")),
    ]
    warnings = check_quality(roots, topic="Optik")
    assert _codes(warnings) == [("TOPIC_REPEAT", "k-1")]


def test_check_quality_skips_caller_folder_nodes() -> None:
    roots = [
        _node("k-1", "Sonstiges", origin_type=OriginType.folder),
        _node("k-2", "Arbeitsblätter", origin_type=OriginType.folder),
        _node("k-3", "Optik", origin_type=OriginType.folder),
    ]
    assert check_quality(roots, topic="Optik") == []
