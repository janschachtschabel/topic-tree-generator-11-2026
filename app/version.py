"""Service version, read once from pyproject.toml (the single source of truth)."""

import tomllib
from functools import cache
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@cache
def service_version() -> str:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]
