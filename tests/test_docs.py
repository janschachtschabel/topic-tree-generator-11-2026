"""Keeps documentation in sync with the code."""

import json
import re
from pathlib import Path

from app.pipeline.input_checks import check_request
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_every_setting() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [name.upper() for name in Settings.model_fields if f"{name.upper()}=" not in text]
    assert missing == [], f"undocumented settings: {missing}"


def test_readme_documents_every_setting_ui_toggle_and_all_use_cases() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
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


def test_readme_inline_curl_examples_validate_against_v2_schema() -> None:
    settings = Settings(_env_file=None)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
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
    from app.main import DESCRIPTION

    steckbrief = (ROOT / "docs" / "steckbrief.md").read_text(encoding="utf-8")
    row = next(line for line in steckbrief.splitlines() if line.startswith("| **Funktionalität / Kurzbeschreibung**"))
    assert row.split("|")[2].strip() == DESCRIPTION


def test_api_doc_lists_every_warning_and_error_code_the_code_emits() -> None:
    # Regression: seven warning codes and six error codes were missing from docs/api.md.
    import re

    doc = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
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
    assert (ROOT / "docs" / "datenformat.md").exists()
