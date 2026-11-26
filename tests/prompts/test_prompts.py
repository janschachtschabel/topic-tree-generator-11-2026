import re

import pytest

from app.prompts import load, render_text

TEMPLATE = "Thema: {{topic}}\nSchema: {{schema}}\nLiteral braces stay: {json: example}\n"


def test_render_replaces_double_brace_placeholders_only() -> None:
    text = render_text(TEMPLATE, topic="Optik", schema='{"a": {"b": 1}}')
    assert "Optik" in text
    assert '{"a": {"b": 1}}' in text
    assert "{json: example}" in text


def test_missing_placeholder_raises() -> None:
    with pytest.raises(KeyError):
        render_text(TEMPLATE, topic="Optik")


def test_unknown_field_raises() -> None:
    with pytest.raises(ValueError):
        render_text(TEMPLATE, topic="Optik", schema="x", typo="y")


def test_system_prompt_is_static_and_long_enough_for_prefix_caching() -> None:
    system = load("system")
    assert not re.search(r"\{\{\w+\}\}", system)
    # ~1,024 tokens is the provider's minimum cacheable prefix; German text runs at roughly 4 characters per token.
    assert len(system) >= 4500


def test_system_prompt_is_loaded_byte_identically() -> None:
    assert load("system") == load("system")


def test_descriptions_use_one_neutral_voice_without_direct_address() -> None:
    # Live run 2026-11-26: parallel describe batches mixed "du", "Sie", imperatives and "Lehrkräfte können" in one tree.
    text = load("system")
    assert "ohne Anrede" in text
    assert "„Dieser Bereich …“" in text
