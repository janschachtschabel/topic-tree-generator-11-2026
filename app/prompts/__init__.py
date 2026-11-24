"""Prompt files live next to this module. Placeholders use `{{name}}` so JSON braces need no escaping."""

import re
from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@cache
def load(name: str) -> str:
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")


def render(name: str, **fields: str) -> str:
    return render_text(load(name), name, **fields)


def render_text(template: str, name: str = "<inline>", **fields: str) -> str:
    needed = set(_PLACEHOLDER.findall(template))
    unknown = set(fields) - needed
    if unknown:
        raise ValueError(f"unknown prompt fields for '{name}': {sorted(unknown)}")
    return _PLACEHOLDER.sub(lambda m: str(fields[m.group(1)]), template)
