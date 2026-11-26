"""Export the v2 request/response JSON Schemas to docs/schemas and the field reference docs/datenformat.md
(a test checks both are current).

Run: uv run python -m scripts.export_schemas
"""

import json
from pathlib import Path

from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import TopicTreeResponseV2
from scripts.field_reference import render

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "docs" / "schemas"
FIELD_REFERENCE = SCHEMA_DIR.parent / "datenformat.md"


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
    FIELD_REFERENCE.write_text(field_reference(), encoding="utf-8")
    print("wrote docs/datenformat.md")


def field_reference() -> str:
    current = schemas()
    return render(current["request-v2.schema.json"], current["response-v2.schema.json"])


if __name__ == "__main__":
    main()
