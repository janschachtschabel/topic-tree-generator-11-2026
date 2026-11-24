"""Rebuild the vocabulary snapshot in app/vocab/data from the official SkoHub JSON-LD endpoints.

Run: uv run python -m scripts.build_vocab_snapshot
The service reads only the bundled snapshot at runtime, so it starts without network access.
"""

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SKOHUB_BASE = "https://vocabs.openeduhub.de/w3id.org/openeduhub/vocabs"
SCHEMES: dict[str, str] = {
    "discipline": f"{SKOHUB_BASE}/discipline/index.json",
    "educationalContext": f"{SKOHUB_BASE}/educationalContext/index.json",
    "intendedEndUserRole": f"{SKOHUB_BASE}/intendedEndUserRole/index.json",
    "hochschulfaechersystematik": f"{SKOHUB_BASE}/hochschulfaechersystematik/index.json",
}
TARGET = Path(__file__).resolve().parent.parent / "app" / "vocab" / "data"


def _walk_concepts(
    concepts: list[dict[str, Any]],
    *,
    parent: str | None = None,
    depth: int = 1,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for concept in concepts or []:
        uri = str(concept.get("id") or "").strip()
        pref = (concept.get("prefLabel") or {}).get("de")
        if uri and pref:
            entry: dict[str, Any] = {"uri": uri, "label": str(pref).strip(), "depth": depth}
            if parent:
                entry["parent"] = parent
            alts = [str(a).strip() for a in (concept.get("altLabel") or {}).get("de") or [] if str(a).strip()]
            if alts:
                entry["alt"] = alts
            result.append(entry)
        result.extend(_walk_concepts(concept.get("narrower") or [], parent=uri or parent, depth=depth + 1))
    return result


def fetch_scheme(name: str, url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    entries = _walk_concepts(payload.get("hasTopConcept") or [])
    labels = dict(sorted((e["uri"], e["label"]) for e in entries))
    return {
        "scheme": name,
        "source": url,
        "generated_at": datetime.now(UTC).date().isoformat(),
        "labels": labels,
        "entries": entries,
    }


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, url in SCHEMES.items():
        data = fetch_scheme(name, url)
        path = TARGET / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{path.name}: {len(data['labels'])} concepts")


if __name__ == "__main__":
    main()
