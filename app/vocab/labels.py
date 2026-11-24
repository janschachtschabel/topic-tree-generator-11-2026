"""German labels for OEH/SkoHub vocabulary URIs, read from the bundled snapshot (no network at runtime).

Rebuild the snapshot with `uv run python -m scripts.build_vocab_snapshot`.
"""

import json
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).parent / "data"


@cache
def _snapshot() -> tuple[dict[str, str], str]:
    merged: dict[str, str] = {}
    dates: list[str] = []
    for path in sorted(_DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        merged.update(data["labels"])
        dates.append(data["generated_at"])
    return merged, min(dates) if dates else ""


def _normalize(uri: str) -> str:
    uri = uri.strip().rstrip("/")
    if uri.startswith("https://w3id.org/"):
        uri = "http://" + uri.removeprefix("https://")
    return uri


def label(uri: str) -> str | None:
    """German prefLabel for a vocabulary URI, or None if unknown."""
    if not uri:
        return None
    return _snapshot()[0].get(_normalize(uri))


def is_known(uri: str) -> bool:
    return label(uri) is not None


def resolve_labels(uris: Iterable[str]) -> dict[str, str]:
    """Map every known URI in `uris` to its German prefLabel (preserving insertion order)."""
    resolved: dict[str, str] = {}
    for uri in uris:
        if uri in resolved:
            continue
        name = label(uri)
        if name is not None:
            resolved[uri] = name
    return resolved


def snapshot_date() -> str:
    return _snapshot()[1]


@cache
def _scheme_raw(scheme: str) -> dict[str, Any] | None:
    path = _DATA / f"{scheme}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def entries(scheme: str, *, max_depth: int | None = None) -> list[dict[str, Any]]:
    """Return structured concept entries (`uri`, `label`, `depth`, optional `parent`/`alt`) for a scheme."""
    data = _scheme_raw(scheme)
    if data is None:
        return []
    raw_entries: list[dict[str, Any]] = data.get("entries") or [
        {"uri": uri, "label": name, "depth": 1} for uri, name in sorted(data["labels"].items(), key=lambda kv: kv[1])
    ]
    if max_depth is None:
        return list(raw_entries)
    return [e for e in raw_entries if int(e.get("depth", 1)) <= max_depth]


def scheme_options(scheme: str, *, max_depth: int | None = None) -> list[dict[str, str]]:
    """Return `{uri, label}` options for UI selectors (hierarchical schemes keep tree order with indentation)."""
    items = entries(scheme, max_depth=max_depth)
    hierarchical = any(int(e.get("depth", 1)) > 1 for e in items)
    if hierarchical:
        return [{"uri": e["uri"], "label": f"{'— ' * (int(e.get('depth', 1)) - 1)}{e['label']}"} for e in items]
    return [{"uri": e["uri"], "label": e["label"]} for e in sorted(items, key=lambda e: e["label"].casefold())]
