"""edu-sharing properties: every value is a list of strings.

Input accepts both spellings (`cm:title` as in the edu-sharing API, `cm_title` as the old service returned it).
Internally and in v2 output the colon form is used; the legacy form is available for old consumers.
"""

import re
from typing import Any

from pydantic import RootModel, model_serializer, model_validator
from pydantic_core import PydanticUndefined

_PREFIXED = re.compile(r"^(cm|ccm|cclom|sys|virtual)_(.+)$")


def to_colon(key: str) -> str:
    if ":" in key:
        return key
    match = _PREFIXED.match(key)
    return f"{match.group(1)}:{match.group(2)}" if match else key


def to_underscore(key: str) -> str:
    return key.replace(":", "_", 1)


def _as_list(key: str, value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in items:
        if isinstance(item, dict | list):
            raise ValueError(f"property '{key}' must contain plain values")  # noqa: TRY004 (pydantic needs ValueError)
        if item is not None:
            result.append(str(item))
    return result


class Properties(RootModel[dict[str, list[str]]]):
    root: dict[str, list[str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if data is None or data is PydanticUndefined:
            return {}
        if isinstance(data, Properties):
            return data.root
        if not isinstance(data, dict):
            raise ValueError("properties must be an object")  # noqa: TRY004 (pydantic needs ValueError)
        return {to_colon(str(k)): _as_list(str(k), v) for k, v in data.items()}

    @model_serializer
    def _serialize(self) -> dict[str, list[str]]:
        return dict(self.root)

    def values(self, key: str) -> list[str]:
        return list(self.root.get(to_colon(key), []))

    def first(self, key: str) -> str | None:
        values = self.values(key)
        return values[0] if values else None

    def set(self, key: str, values: list[str]) -> None:
        self.root[to_colon(key)] = list(values)

    def dump_v2(self) -> dict[str, list[str]]:
        return dict(self.root)

    def dump_legacy(self) -> dict[str, list[str]]:
        return {to_underscore(k): v for k, v in self.root.items()}
