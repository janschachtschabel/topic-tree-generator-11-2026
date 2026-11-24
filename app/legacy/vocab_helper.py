"""Label lookup for the legacy endpoints, now backed by the bundled vocabulary snapshot.

Same function names and return shape as before (a list of labels or None); the labels are reliably German.
"""

from app.vocab.labels import label


def get_educational_context_pref_labels(educational_context_id_uri: str) -> list[str] | None:
    value = label(educational_context_id_uri)
    return [value] if value else None


def get_discipline_pref_labels(discipline_id_uri: str) -> list[str] | None:
    value = label(discipline_id_uri)
    return [value] if value else None
