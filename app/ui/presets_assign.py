"""Test UI presets for the task "Inhalte einsortieren": `mode: refine` + `options.assign_only` on an existing tree."""

from typing import Any

from app.ui.preset_vocab import FRAME_PHYS_SEK1, material
from app.ui.presets_refine import current_tree

# A tree as it comes from the repository: collection nodeIds, no service keys, no generation record.
_FOREIGN_TREE = {
    "title": "Physik Klasse 7/8",
    "collection": [
        {
            "nodeId": "4f1c2a9e-0b7d-4c55-9a21-6d3e8f0a1b01",
            "title": "Licht und Optik",
            "properties": {"cm:title": ["Licht und Optik"], "cm:description": ["Ausbreitung von Licht, Schatten."]},
            "subcollections": [
                {
                    "nodeId": "4f1c2a9e-0b7d-4c55-9a21-6d3e8f0a1b02",
                    "title": "Spiegel und Reflexion",
                    "properties": {"cm:title": ["Spiegel und Reflexion"]},
                },
                {
                    "nodeId": "4f1c2a9e-0b7d-4c55-9a21-6d3e8f0a1b03",
                    "title": "Linsen",
                    "properties": {"cm:title": ["Linsen"]},
                },
            ],
        },
        {
            "nodeId": "4f1c2a9e-0b7d-4c55-9a21-6d3e8f0a1b04",
            "title": "Schall",
            "properties": {"cm:title": ["Schall"]},
        },
    ],
}

ASSIGN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "assign_foreign",
        "task": "assign",
        "title": "Bestehenden edu-sharing-Baum befüllen",
        "summary": "Fremder Baum mit nodeId und ohne Schlüssel: Nur Inhalte kommen hinzu, Struktur, Properties und "
        "nodeId bleiben; Fachfremdes landet in „nicht zugeordnet“.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": _FOREIGN_TREE,
            "items": [
                material("b1", "Brennweite einer Lupe bestimmen", ["Linse", "Experiment"]),
                material("b2", "Echo und Schallgeschwindigkeit", ["Schall"]),
                material("b3", "Lochkamera bauen", ["Licht", "Schatten"]),
                material("b4", "Bruchrechnen üben", ["Mathematik"]),
            ],
            "frame": FRAME_PHYS_SEK1,
            "options": {"assign_only": True},
        },
    },
    {
        "id": "assign_only",
        "task": "assign",
        "title": "In einen Baum des Dienstes einsortieren",
        "summary": "Früheres Ergebnis als Basis; die Struktur bleibt, die nodeId der Materialien wird durchgereicht.",
        "payload": {
            "mode": "refine",
            "use_case": "folders",
            "current_tree": current_tree("v3", use_case="folders"),
            "items": [
                {
                    "id": "c9",
                    "nodeId": "n-c9",
                    "use": ["content"],
                    "properties": {"cm:title": ["Brennweite einer Sammellinse bestimmen"]},
                },
                {
                    "id": "c10",
                    "nodeId": "n-c10",
                    "use": ["content"],
                    "properties": {"cm:title": ["Spiegelbilder am Kosmetikspiegel"]},
                },
                {
                    "id": "c11",
                    "nodeId": "n-c11",
                    "use": ["content"],
                    "properties": {"cm:title": ["Gedichtanalyse Romantik"]},
                },
            ],
            "frame": FRAME_PHYS_SEK1,
            "options": {"assign_only": True},
        },
    },
]
