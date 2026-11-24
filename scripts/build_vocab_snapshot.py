"""Rebuild the vocabulary label snapshot in app/vocab/data from the OEH vocabularies on GitHub.

Run: uv run python scripts/build_vocab_snapshot.py
The service reads only the snapshot at runtime, so it starts without network access.
"""

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from rdflib import SKOS, Graph, URIRef

SOURCE = "https://raw.githubusercontent.com/openeduhub/oeh-metadata-vocabs/master/{name}.ttl"
SCHEMES = ("discipline", "educationalContext", "intendedEndUserRole")
TARGET = Path(__file__).resolve().parent.parent / "app" / "vocab" / "data"


def labels(name: str) -> dict[str, str]:
    with urllib.request.urlopen(SOURCE.format(name=name), timeout=30) as response:
        graph = Graph().parse(data=response.read().decode("utf-8"), format="turtle")
    result: dict[str, str] = {}
    for subject, label in graph.subject_objects(SKOS.prefLabel):
        if isinstance(subject, URIRef) and getattr(label, "language", None) == "de":
            result[str(subject)] = str(label)
    return dict(sorted(result.items()))


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).date().isoformat()
    for name in SCHEMES:
        data = {
            "scheme": name,
            "source": SOURCE.format(name=name),
            "generated_at": generated_at,
            "labels": labels(name),
        }
        path = TARGET / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{path.name}: {len(data['labels'])} labels")


if __name__ == "__main__":
    main()
