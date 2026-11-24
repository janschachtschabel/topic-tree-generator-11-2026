"""Turn a Pydantic model into a schema accepted by OpenAI's strict structured outputs.

Strict mode requires `additionalProperties: false` and every property listed in `required` (optional fields stay
nullable). Annotation-only keywords (`title`, `default`, `examples`) are removed at schema-node level; property
*names* such as "title" are untouched.
"""

import copy
from typing import Any

from pydantic import BaseModel

_DROP = ("title", "default", "examples")
_SCHEMA_MAPS = ("properties", "$defs", "definitions", "patternProperties")


def _walk(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _walk(item)
        return
    if not isinstance(node, dict):
        return
    for key in _DROP:
        node.pop(key, None)
    if node.get("type") == "object" or "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node.get("properties", {}).keys())
    for key, value in node.items():
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            for sub in value.values():
                _walk(sub)
        elif isinstance(value, dict | list):
            _walk(value)


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = copy.deepcopy(model.model_json_schema())
    _walk(schema)
    return schema
