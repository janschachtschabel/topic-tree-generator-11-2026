"""Export the v2 request/response JSON Schemas to docs/schemas and the field references docs/de/datenformat.md and
docs/en/data-format.md (a test checks all are current).

Run: uv run python -m scripts.export_schemas
"""

import json
from pathlib import Path

from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import TopicTreeResponseV2
from scripts.field_reference import render

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
SCHEMA_DIR = DOCS_DIR / "schemas"
FIELD_REFERENCES = {"de": DOCS_DIR / "de" / "datenformat.md", "en": DOCS_DIR / "en" / "data-format.md"}


def schemas() -> dict[str, dict]:
    return {
        "request-v2.schema.json": TopicTreeRequestV2.model_json_schema(by_alias=True, mode="validation"),
        "response-v2.schema.json": TopicTreeResponseV2.model_json_schema(by_alias=True, mode="serialization"),
    }


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        (SCHEMA_DIR / name).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote docs/schemas/{name}")
    for lang, path in FIELD_REFERENCES.items():
        path.write_text(field_reference(lang), encoding="utf-8")
        print(f"wrote {path.relative_to(DOCS_DIR.parent)}")


def field_reference(lang: str = "de") -> str:
    current = schemas()
    return render(current["request-v2.schema.json"], current["response-v2.schema.json"], lang)


if __name__ == "__main__":
    main()
