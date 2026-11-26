"""OpenAPI request examples that combine inputs: `use_case` is the backbone, roles say how the rest flows in."""

from typing import Any

from app.api.examples_values import FRAME

_CURRICULUM = (
    "## Themenfeld 1: Licht und Schatten\nLichtquellen, Lichtausbreitung, Schattenbildung.\n"
    "## Themenfeld 2: Optische Phänomene\nReflexion am Spiegel, Brechung, Linsen und optische Geräte.\n"
    "## Themenfeld 3: Farben\nSpektrum, Farbmischung, Farbensehen."
)


def _item(item_id: str, title: str, use: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"id": item_id, "properties": {"cm:title": [title]}, **extra}
    if use is not None:
        item["use"] = use
    return item


def _curriculum(use: list[str]) -> dict[str, Any]:
    return _item("d1", "Lehrplan Physik 7/8, Optik", use, fulltext={"format": "markdown", "text": _CURRICULUM})


_CONTENTS = [
    _item("c1", "Arbeitsblatt Reflexionsgesetz", ["content"], nodeId="n-c1"),
    _item("c2", "Video: Wie entsteht ein Regenbogen?", ["content"], nodeId="n-c2"),
    _item("c3", "Bruchrechnen üben", ["content"], nodeId="n-c3"),
]

COMBO_EXAMPLES: dict[str, dict[str, Any]] = {
    "combo_topic_contents": {
        "summary": "Kombination: Thema + Inhalte einsortieren (top-down)",
        "description": 'Der Baum entsteht nur aus `topic`; die Inhalte (`use: ["content"]`, ohne `use` ebenso) werden '
        "danach mit Konfidenz einsortiert. Fachfremdes („Bruchrechnen“) steht in `unassigned`. Typisch, wenn ein "
        "Thema vorgegeben ist und vorhandenes Material hinein soll.",
        "value": {"mode": "create", "use_case": "topic", "topic": "Optik", "items": _CONTENTS, "frame": FRAME},
    },
    "combo_topic_contents_inspire": {
        "summary": "Kombination: Thema + Inhalte, die auch Themen anregen",
        "description": 'Inhalte mit `use: ["structure", "content"]` regen zusätzliche Hauptthemen an (sie kommen '
        "mit `status: suggested`) und werden einsortiert; reine `content`-Einträge werden nur einsortiert. Das Thema "
        "bleibt das Gerüst.",
        "value": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik",
            "items": [
                _item("a1", "Schülerexperiment: Lochkamera bauen", ["structure", "content"]),
                _item("a2", "Optische Täuschungen", ["structure", "content"]),
                _CONTENTS[0],
            ],
            "frame": FRAME,
        },
    },
    "combo_topic_document": {
        "summary": "Kombination: Thema + Lehrplan als Anregung",
        "description": 'Bei `use_case: topic` regt ein Gliederungsdokument (`use: ["structure"]`) nur an: Der Baum '
        "folgt dem Thema, Auszüge des Lehrplans fließen in die Planung ein. Soll der Lehrplan das Gerüst sein, "
        "`use_case: document` wählen.",
        "value": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Licht und Sehen im Alltag",
            "items": [_curriculum(["structure"]), _CONTENTS[1]],
            "frame": FRAME,
        },
    },
    "combo_topic_folders": {
        "summary": "Kombination: Thema + Ordnerstruktur + lose Inhalte",
        "description": "Ohne `folders_use` (Standard: Struktur und Inhalt) regt der Ordnerbaum die Gliederung an, und "
        "der Ordnerpfad jeder Datei hilft beim Einsortieren. Ein `path` an einem losen Eintrag wirkt genauso.",
        "value": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik",
            "folders": [{"title": "Spiegel", "items": ["f1"], "subcollections": []}],
            "items": [_item("f1", "Spiegelbilder zeichnen"), _item("c4", "Linsen im Alltag", path="Optik/Linsen")],
            "frame": FRAME,
        },
    },
    "combo_document_topic_contents": {
        "summary": "Kombination: Lehrplan als Gerüst + Thema grenzt ein + Inhalte",
        "description": "`use_case: document`: Der Lehrplan bildet den Baum, `topic` grenzt auf passende Abschnitte ein, "
        'die Inhalte werden den Abschnitten zugeordnet. Mit `use: ["structure", "content"]` würde der Lehrplan '
        "selbst auch einsortiert.",
        "value": {
            "mode": "create",
            "use_case": "document",
            "topic": "Optische Phänomene",
            "items": [_curriculum(["structure"]), *_CONTENTS[:2]],
            "frame": FRAME,
        },
    },
    "combo_contents_document": {
        "summary": "Kombination: Inhalte gruppieren + Lehrplan als Orientierung",
        "description": "`use_case: contents`: Die Gruppen entstehen aus den Inhalten (ohne `use` prägen sie die Gruppen "
        'und werden einsortiert); der Lehrplan-Volltext fließt als Auszug ein. Der Eintrag mit `use: ["content"]` '
        "wird nur einsortiert und verzerrt die Gruppen nicht.",
        "value": {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "items": [
                _curriculum(["structure"]),
                _item("m1", "Lochkamera bauen"),
                _item("m2", "Schatten im Sonnenlicht"),
                _item("m3", "Brennweite einer Lupe"),
                _item("m4", "Spiegelschrift lesen"),
                _CONTENTS[1],
            ],
            "frame": FRAME,
        },
    },
    "combo_contents_folders_hint": {
        "summary": "Kombination: Inhalte gruppieren + Ordner nur als Ablagehinweis",
        "description": '`folders_use: ["content"]`: Die Ordner prägen die Gruppen nicht, ihr Pfad hilft nur beim '
        "Einsortieren der Dateien. Mit `folders_use: []` würden die Ordner angenommen, aber nicht genutzt "
        "(`INPUT_IGNORED`).",
        "value": {
            "mode": "create",
            "use_case": "contents",
            "folders": [{"title": "Altes Material", "items": ["m1", "m2"], "subcollections": []}],
            "folders_use": ["content"],
            "items": [_item("m1", "Lochkamera bauen"), _item("m2", "Spiegelschrift lesen"), _item("m3", "Regenbogen")],
            "frame": FRAME,
        },
    },
    "combo_folders_improve_document": {
        "summary": "Kombination: Ordner verbessern mit Lehrplan + lose Dateien",
        "description": "`use_case: folders` mit `options.improve`: Der Lehrplan liefert Maßstäbe für die "
        "Verbesserungsvorschläge (`changes`), lose Dateien ohne Ordner werden einsortiert.",
        "value": {
            "mode": "create",
            "use_case": "folders",
            "folders": [{"title": "Neuer Ordner (2)", "items": ["f1"], "subcollections": []}],
            "items": [_item("f1", "Spiegelbilder zeichnen"), _curriculum(["structure"]), _item("c5", "Linsen")],
            "frame": FRAME,
            "options": {"improve": True},
        },
    },
    "combo_folders_outline_only": {
        "summary": "Kombination: Ordner nur als Gliederung, alle Dateien neu einsortieren",
        "description": '`folders_use: ["structure"]`: Die Ordner bleiben das Gerüst, ihre Dateizuordnung zählt aber '
        "nicht; alle Dateien werden neu nach Inhalt einsortiert.",
        "value": {
            "mode": "create",
            "use_case": "folders",
            "folders": [
                {"title": "Optik", "items": ["f1", "f2"], "subcollections": []},
                {"title": "Akustik", "items": [], "subcollections": []},
            ],
            "folders_use": ["structure"],
            "items": [_item("f1", "Spiegelbilder zeichnen"), _item("f2", "Echo messen")],
            "frame": FRAME,
        },
    },
}

REFINE_EXAMPLES: dict[str, dict[str, Any]] = {
    "refine_changes_items": {
        "summary": "Entwurf gezielt ändern und neue Inhalte einsortieren",
        "description": "`feedback.changes` setzt Änderungen ohne Sprachmodell um (hier `add`, `move`), neue Knoten "
        "werden beschrieben, und die neuen Inhalte kommen im selben Aufruf in den geänderten Baum.",
        "value": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": {
                "version": "v2",
                "collection": [
                    {"key": "k-optik", "title": "Optik", "subcollections": [{"key": "k-strom", "title": "Strom"}]}
                ],
            },
            "feedback": {"changes": [{"op": "add", "title": "Elektrizität"}, {"op": "move", "key": "k-strom"}]},
            "items": [_item("b1", "Stromkreis mit Batterie und Lampe", ["content"])],
            "frame": FRAME,
        },
    },
}
