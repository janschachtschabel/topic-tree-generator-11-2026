"""German labels for OEH vocabulary URIs, read from the bundled snapshot (no network at runtime).

Rebuild the snapshot with `scripts/build_vocab_snapshot.py`.
"""

import json
from functools import cache
from pathlib import Path

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


def snapshot_date() -> str:
    return _snapshot()[1]


@cache
def scheme_options(scheme: str) -> list[dict[str, str]]:
    """Return sorted `{uri, label}` entries for a bundled vocabulary scheme."""
    path = _DATA / f"{scheme}.json"
    if not path.exists():
        return []
    labels: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))["labels"]
    return [{"uri": uri, "label": name} for uri, name in sorted(labels.items(), key=lambda kv: kv[1].casefold())]
