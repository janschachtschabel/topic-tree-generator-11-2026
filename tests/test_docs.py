"""Keeps documentation in sync with the code."""

from pathlib import Path

from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_every_setting() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [name.upper() for name in Settings.model_fields if f"{name.upper()}=" not in text]
    assert missing == [], f"undocumented settings: {missing}"


def test_changelog_mentions_the_current_version() -> None:
    from app.version import service_version

    assert f"## {service_version()}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
