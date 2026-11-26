"""Keeps documentation in sync with the code."""

import json
import os
import re
from pathlib import Path

import pytest

from app.pipeline.input_checks import check_request
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_every_setting() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [name.upper() for name in Settings.model_fields if f"{name.upper()}=" not in text]
    assert missing == [], f"undocumented settings: {missing}"


@pytest.mark.parametrize("name", ["README.md", "README.de.md"])
def test_readme_documents_every_setting_ui_toggle_and_all_use_cases(name: str) -> None:
    readme = (ROOT / name).read_text(encoding="utf-8")
    missing = [name.upper() for name in Settings.model_fields if name.upper() not in readme]
    assert missing == [], f"settings missing from README.md: {missing}"
    for marker in ("UI_ENABLED=true", "UI_ENABLED=false", "docker-compose.yml", "docker-compose.build.yml"):
        assert marker in readme, f"README.md missing {marker!r}"
    for use_case in (
        '"use_case": "topic"',
        '"use_case": "document"',
        '"use_case": "folders"',
        '"use_case": "contents"',
    ):
        assert use_case in readme, f"README.md missing example for {use_case}"
    assert '"mode": "refine"' in readme and '"assign_only": true' in readme


def test_docs_examples_validate_against_v2_schema_and_limits() -> None:
    settings = Settings(_env_file=None)
    example_files = sorted((ROOT / "docs" / "examples").glob("*.json"))
    assert example_files
    for path in example_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        req = TopicTreeRequestV2.model_validate(payload)
        check_request(req, settings)


@pytest.mark.parametrize("name", ["README.md", "README.de.md"])
def test_readme_inline_curl_examples_validate_against_v2_schema(name: str) -> None:
    settings = Settings(_env_file=None)
    readme = (ROOT / name).read_text(encoding="utf-8")
    blocks = re.findall(r"-d '(\{.*?\})'", readme, flags=re.DOTALL)
    assert len(blocks) == 7
    for raw in blocks:
        req = TopicTreeRequestV2.model_validate(json.loads(raw))
        check_request(req, settings)


def test_changelog_mentions_the_current_version() -> None:
    from app.version import service_version

    assert f"## {service_version()}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_steckbrief_short_description_equals_openapi_description() -> None:
    # Leitfaden Kap. 6: the Kurzbeschreibung row of the Steckbrief equals info.description.
    from app.api.v2_description import APP_DESCRIPTION as DESCRIPTION

    steckbrief = (ROOT / "docs" / "de" / "steckbrief.md").read_text(encoding="utf-8")
    row = next(line for line in steckbrief.splitlines() if line.startswith("| **Funktionalität / Kurzbeschreibung**"))
    assert row.split("|")[2].strip() == DESCRIPTION


@pytest.mark.parametrize("lang", ["de", "en"])
def test_api_doc_lists_every_warning_and_error_code_the_code_emits(lang: str) -> None:
    # Regression: seven warning codes and six error codes were missing from docs/api.md.
    doc = (ROOT / "docs" / lang / "api.md").read_text(encoding="utf-8")
    codes: set[str] = set()
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        codes |= set(re.findall(r'warn\(\s*"([A-Z][A-Z_]+)"', text))
        codes |= set(re.findall(r'_warning\(\s*"([A-Z][A-Z_]+)"', text))
        codes |= set(re.findall(r'code="([A-Z][A-Z_]+)"', text))
        codes |= set(re.findall(r'ApiError\(\s*(?:\d+|status\.\w+),\s*"([A-Z][A-Z_]+)"', text))
    assert sorted(c for c in codes if f"`{c}`" not in doc) == []


def test_response_examples_validate_against_the_v2_response_model() -> None:
    from app.schemas.response_v2 import TopicTreeResponseV2

    files = sorted((ROOT / "docs" / "examples" / "responses").glob("*.json"))
    assert files
    for path in files:
        TopicTreeResponseV2.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_examples_cover_combinations_and_every_change_op() -> None:
    examples = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "docs" / "examples").glob("*.json")}
    ops = {c["op"] for c in examples["refine_changes"]["feedback"]["changes"]}
    assert ops == {"add", "remove", "rename", "edit", "move", "merge", "split"}
    assert "folders_use" in examples["combo_topic_folders"]
    assert (ROOT / "docs" / "de" / "datenformat.md").exists()


@pytest.mark.parametrize("path", ["de/datenformat.md", "en/data-format.md"])
def test_field_reference_tables_have_five_cells_per_row(path: str) -> None:
    # Re-review: enum types were escaped twice ("\\|"), which split a generated table row.
    rows = [line for line in (ROOT / "docs" / path).read_text(encoding="utf-8").splitlines() if line.startswith("| ")]
    assert rows
    for row in rows:
        cells = re.split(r"(?<!\\)\|", row)[1:-1]
        assert len(cells) == 5 and "\\\\|" not in row, row


# German and English documentation are kept as pairs that link to each other.
DOC_PAIRS = [
    ("README.de.md", "README.md"),
    ("docs/de/api.md", "docs/en/api.md"),
    ("docs/de/datenformat.md", "docs/en/data-format.md"),
    ("docs/de/betrieb.md", "docs/en/operations.md"),
    ("docs/de/steckbrief.md", "docs/en/service-profile.md"),
    ("docs/de/aenderungen-v0.4-zu-v2.0.md", "docs/en/changes-v0.4-to-v2.0.md"),
]


def _maintained_docs() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "README.de.md", ROOT / "docs" / "README.md", ROOT / "CHANGELOG.md"]
    return files + sorted((ROOT / "docs" / "de").glob("*.md")) + sorted((ROOT / "docs" / "en").glob("*.md"))


@pytest.mark.parametrize(("de", "en"), DOC_PAIRS)
def test_every_document_exists_in_german_and_english_and_links_its_counterpart(de: str, en: str) -> None:
    de_path, en_path = ROOT / de, ROOT / en
    assert de_path.exists() and en_path.exists()
    for source, target in ((de_path, en_path), (en_path, de_path)):
        link = Path(os.path.relpath(target, source.parent)).as_posix()
        assert f"]({link})" in source.read_text(encoding="utf-8"), f"{source.name} must link {link}"


def test_german_and_english_docs_have_the_same_sections() -> None:
    # Translations drift silently; equal numbers of second-level headings catch a missing or extra section.
    for de, en in DOC_PAIRS:
        count = [
            sum(1 for line in (ROOT / p).read_text(encoding="utf-8").splitlines() if line.startswith("## "))
            for p in (de, en)
        ]
        assert count[0] == count[1], f"{de} has {count[0]} sections, {en} has {count[1]}"


def test_relative_links_in_maintained_docs_resolve() -> None:
    broken = []
    for doc in _maintained_docs():
        text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.DOTALL)
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (doc.parent / path).exists():
                broken.append(f"{doc.relative_to(ROOT)} → {target}")
    assert broken == []


def test_service_profiles_name_the_same_version() -> None:
    from app.version import service_version

    for path in ("docs/de/steckbrief.md", "docs/en/service-profile.md"):
        assert f"**`{service_version()}`**" in (ROOT / path).read_text(encoding="utf-8"), path
