"""Tests for sentence- and word-boundary-safe text truncation."""

from app.domain.text import truncate_sentences


def test_returns_stripped_text_when_within_limit() -> None:
    assert truncate_sentences("  Kurzer Satz.  ", 50) == "Kurzer Satz."


def test_truncates_at_sentence_boundary() -> None:
    text = "Erster Satz über Optik. Zweiter Satz über Linsen. Dritter Satz über Spiegel und Prismen."
    result = truncate_sentences(text, 55)
    assert result == "Erster Satz über Optik. Zweiter Satz über Linsen."


def test_does_not_split_after_german_abbreviations_or_ordinals() -> None:
    text = "Im 20. Jahrhundert wurden z. B. Laser entwickelt. Sie bündeln Licht sehr stark. Weitere Anwendungen folgen."
    result = truncate_sentences(text, 85)
    assert result == "Im 20. Jahrhundert wurden z. B. Laser entwickelt. Sie bündeln Licht sehr stark."


def test_falls_back_to_word_boundary_when_single_sentence_exceeds_limit() -> None:
    text = "Dieser eine besonders lange Satz ohne Punkt dazwischen beschreibt optische Phänomene ausführlich"
    result = truncate_sentences(text, 45)
    assert len(result) <= 45
    assert result == "Dieser eine besonders lange Satz ohne Punkt"
    assert not result.endswith(" ")


def test_hard_cuts_unbroken_token() -> None:
    token = "a" * 80
    assert truncate_sentences(token, 20) == "a" * 20


def test_empty_and_zero_limit() -> None:
    assert truncate_sentences("", 100) == ""
    assert truncate_sentences("Hallo Welt.", 0) == ""


def test_does_not_treat_mid_token_dot_or_ellipsis_at_limit_as_sentence_end() -> None:
    text = "Lernmodul zu Python 3.13 und numpy.array im Unterricht"
    result = truncate_sentences(text, 35)
    assert result == "Lernmodul zu Python 3.13 und"

    ellipsis = "Und so geht es weiter... Danach folgt der Rest des Textes."
    assert truncate_sentences(ellipsis, 22) == "Und so geht es"


def test_handles_unicode_whitespace_and_crlf_word_boundaries() -> None:
    text = "Erster\u00a0Abschnitt\r\nZweiter Abschnitt ohne Punkt am Ende"
    assert truncate_sentences(text, 17) == "Erster\u00a0Abschnitt"
    assert truncate_sentences(text, 10) == "Erster"
