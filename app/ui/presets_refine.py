"""Test UI presets for the task "Baum ändern" (`mode: refine`): text feedback, targeted changes, frame change."""

from typing import Any

from app.ui.preset_vocab import CTX_SEK2, DISC_PHYS, FRAME_PHYS_SEK1, ROLE_TEACHER, frame, material, node

_PHYSIK_TREE = [
    node(
        "k-optik",
        "Optik",
        "Grundlagen zu Licht, Schatten, Spiegeln und Linsen.",
        (
            node("k-spiegel", "Spiegel", "Reflexionsgesetz, ebene und gewölbte Spiegel im Alltag."),
            node("k-linsen", "Linsen", "Sammel- und Zerstreuungslinsen, Brennpunkt und Bildentstehung."),
        ),
    ),
    node(
        "k-mechanik",
        "Mechanik",
        "Kräfte und Bewegungen.",
        (
            node("k-kraefte", "Kräfte", "Kraft als Ursache von Verformung und Bewegungsänderung."),
            node("k-bewegung", "Bewegung", "Geschwindigkeit, gleichförmige und beschleunigte Bewegung."),
            node("k-strom", "Elektrischer Strom", "Stromkreise, Spannung und Stromstärke."),
        ),
    ),
    node("k-akustik", "Akustik", "Schall und Schwingungen."),
    node("k-waerme", "Wärmelehre", "Temperatur, Wärme, Wärmetransport und Aggregatzustände."),
    node("k-sonstiges", "Sonstiges", "Material, das noch keinem Thema zugeordnet ist."),
]


def _current(version: str, use_case: str = "topic", tree_frame: dict | None = None) -> dict[str, Any]:
    return {
        "version": version,
        "title": "Physik Sek I",
        "collection": _PHYSIK_TREE,
        "generation": {
            "mode": "create",
            "use_case": use_case,
            "topic": "Physik Sek I",
            "frame": tree_frame or FRAME_PHYS_SEK1,
        },
    }


REFINE_PRESETS: list[dict[str, Any]] = [
    {
        "id": "refine_changes",
        "task": "refine",
        "title": "Gezielte Änderungen (alle Operationen)",
        "summary": "Hinzufügen, umbenennen, Beschreibung ändern, auf die Hauptebene verschieben, zusammenführen, "
        "aufteilen und löschen in einem Aufruf.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": _current("v1"),
            "feedback": {
                "changes": [
                    {"op": "add", "parent": "k-optik", "title": "Farben und Spektren"},
                    {"op": "rename", "key": "k-akustik", "title": "Akustik und Schwingungen"},
                    {
                        "op": "edit",
                        "key": "k-optik",
                        "properties": {
                            "cm:description": [
                                "Licht im Alltag: Ausbreitung, Schatten, Spiegel, Linsen und Farben mit vielen Versuchen."
                            ]
                        },
                    },
                    {"op": "move", "key": "k-strom", "to": None},
                    {"op": "merge", "keys": ["k-kraefte", "k-bewegung"], "title": "Kräfte und Bewegung"},
                    {
                        "op": "split",
                        "key": "k-waerme",
                        "hint": "Temperatur und Wärme; Wärmetransport; Aggregatzustände",
                    },
                    {"op": "remove", "key": "k-sonstiges"},
                ],
            },
            "frame": FRAME_PHYS_SEK1,
        },
    },
    {
        "id": "refine_feedback",
        "task": "refine",
        "title": "Freitext-Rückmeldung + gesperrter Ast",
        "summary": "Der Dienst deutet die Rückmeldung als Änderungen; „Optik“ ist gesperrt und bleibt unverändert.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": _current("v1"),
            "feedback": {
                "text": "Füge Farben und Spektrum als eigenes Hauptthema hinzu, hänge Akustik unter Mechanik "
                "und lösche „Sonstiges“.",
                "locked": ["k-optik"],
            },
            "frame": FRAME_PHYS_SEK1,
        },
    },
    {
        "id": "refine_with_items",
        "task": "refine",
        "title": "Änderungen + neue Materialien einsortieren",
        "summary": "Zwei gezielte Änderungen und drei neue Materialien, die direkt in den geänderten Baum kommen.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": _current("v2"),
            "feedback": {
                "changes": [
                    {"op": "add", "title": "Elektrizität"},
                    {"op": "move", "key": "k-strom", "to": None},
                ],
            },
            "items": [
                material("b1", "Stromkreis mit Batterie und Lampe", ["Stromkreis"]),
                material("b2", "Schallgeschwindigkeit messen", ["Schall", "Experiment"]),
                material("b3", "Thermometer selbst bauen", ["Temperatur"]),
            ],
            "frame": FRAME_PHYS_SEK1,
        },
    },
    {
        "id": "assign_only",
        "task": "refine",
        "title": "Nur Inhalte einsortieren (Struktur bleibt)",
        "summary": "„Nur einsortieren“ lässt die Struktur unverändert; nodeId wird unverändert durchgereicht.",
        "payload": {
            "mode": "refine",
            "use_case": "folders",
            "current_tree": _current("v3", use_case="folders"),
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
    {
        "id": "refine_frame",
        "task": "refine",
        "title": "Rahmen ändern: Sek I → Sek II",
        "summary": "Neue Bildungsstufe ersetzt die alte an allen übernommenen Knoten; gesperrte Äste behalten sie.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": _current("v4"),
            "feedback": {"locked": ["k-akustik"]},
            "frame": frame([DISC_PHYS], CTX_SEK2, ROLE_TEACHER),
        },
    },
]
