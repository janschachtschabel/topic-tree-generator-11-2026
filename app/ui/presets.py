"""Ready-to-run German sample scenarios for the built-in test UI, grouped by task (the UI's navigation).

`task` is the UI entry the preset belongs to: `topic`, `document`, `folders`, `contents` (mode create) or `refine`.
Items use the shape of the UI's line editor where possible, so a preset loads into the form instead of raw JSON.
"""

from typing import Any

from app.ui.preset_vocab import (
    CTX_BERUF,
    CTX_ELEMENTAR,
    CTX_HOCHSCHULE,
    CTX_SEK1,
    DISC_BIO,
    DISC_CHEM,
    DISC_ELEKTRO,
    DISC_GEO,
    DISC_MECHATRONIK,
    DISC_POL,
    DISC_SACHUNTERRICHT,
    FRAME_PHYS_SEK1,
    ROLE_LEARNER,
    STRUCT,
    UNI_MATHEMATIK,
    frame,
    material,
)
from app.ui.presets_inputs import CONTENTS_PRESETS, DOCUMENT_PRESETS, FOLDERS_PRESETS, LEHRPLAN_DOC
from app.ui.presets_refine import REFINE_PRESETS

TOPIC_PRESETS: list[dict[str, Any]] = [
    {
        "id": "topic_sek1",
        "task": "topic",
        "title": "Optik Sek I – mit Zusatzthema und Ein-/Ausschluss",
        "summary": "3 Ebenen, „Allgemeines“ vorn, Farben erzwungen, Wellenoptik ausgeschlossen, Experiment-Fokus.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik für die Sekundarstufe I, alltagsnah, mit Experimenten",
            "frame": FRAME_PHYS_SEK1,
            "shape": {
                "depth": 3,
                "main_topics": {"min": 6, "max": 10},
                "children": {"min": 3, "max": 6},
                "extra_topics": ["general"],
            },
            "hints": {
                "context": "Unterricht Klasse 7 bis 9, viele Schülerexperimente",
                "include": ["Farben"],
                "exclude": ["Wellenoptik"],
            },
        },
    },
    {
        "id": "topic_kita",
        "task": "topic",
        "title": "Kita: Jahreszeiten erleben",
        "summary": "Elementarbereich ohne Form-Vorgabe: Der Dienst wählt flache 2 Ebenen und kindgerechte Themen.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Jahreszeiten in der Kita: Natur, Wetter und Feste im Jahreslauf",
            "frame": frame([DISC_SACHUNTERRICHT], CTX_ELEMENTAR),
            "hints": {"context": "Kinder von 3 bis 6 Jahren, Projektarbeit draußen", "description_length": 40},
        },
    },
    {
        "id": "topic_hochschule",
        "task": "topic",
        "title": "Hochschule: Einführung in die Statistik",
        "summary": "Hochschulfach aus der Hochschulfächersystematik, Studierende als Zielgruppe, „Methodik“ hinten.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Einführung in die Statistik für Studierende im ersten Semester",
            "frame": frame([UNI_MATHEMATIK], CTX_HOCHSCHULE, ROLE_LEARNER),
            "shape": {"depth": 2, "extra_topics": ["methodology"]},
            "hints": {"order": "vom Beschreiben zum Schließen", "exclude": ["Bayes-Statistik"]},
        },
    },
    {
        "id": "topic_beruf",
        "task": "topic",
        "title": "Berufsbildung: Elektromobilität (Lernfelder)",
        "summary": "Automatische Wahl des Ordnungsprinzips für die berufliche Bildung (Handlungs-/Lernfelder).",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Elektromobilität und Hochvoltsysteme in der Kfz-Werkstatt",
            "frame": frame([DISC_MECHATRONIK, DISC_ELEKTRO], CTX_BERUF),
            "shape": {"depth": 2, "main_topics": {"min": 5, "max": 8}, "children": {"min": 3, "max": 5}},
            "hints": {"context": "Ausbildung Kfz-Mechatronik, praxisnahe Arbeits- und Geschäftsprozesse"},
        },
    },
    {
        "id": "topic_bne_auto_meta",
        "task": "topic",
        "title": "BNE / Klima fächerübergreifend (Metadaten je Knoten)",
        "summary": "Vier Fächer im Rahmen; auto_metadata setzt je Knoten das passende Fach.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Klimawandel und nachhaltige Entwicklung (BNE)",
            "frame": frame([DISC_BIO, DISC_CHEM, DISC_GEO, DISC_POL], CTX_SEK1),
            "shape": {"depth": 2, "main_topics": {"min": 4, "max": 8}, "children": {"min": 3, "max": 5}},
            "hints": {"context": "Fächerübergreifendes Projekt Sekundarstufe I"},
            "options": {"auto_metadata": True},
        },
    },
    {
        "id": "topic_with_contents",
        "task": "topic",
        "title": "Thema + Materialien (Anregung und Einsortieren)",
        "summary": "Zwei Materialien regen Themen an und werden einsortiert; zwei weitere werden nur einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik in der Sekundarstufe I",
            "frame": FRAME_PHYS_SEK1,
            "items": [
                material("a1", "Schülerexperiment: Lochkamera bauen", ["Lochkamera", "Lichtausbreitung"], use=STRUCT),
                material("a2", "Optische Täuschungen und Wahrnehmung", ["Auge", "Optische Täuschung"], use=STRUCT),
                material("b1", "Arbeitsblatt Reflexionsgesetz am ebenen Spiegel", ["Reflexion", "Spiegel"]),
                material("b2", "Video: Wie entsteht ein Regenbogen?", ["Regenbogen", "Farben"]),
            ],
            "shape": {"depth": 2, "main_topics": {"min": 4, "max": 7}, "children": {"min": 2, "max": 5}},
        },
    },
    {
        "id": "topic_with_document",
        "task": "topic",
        "title": "Thema + Lehrplanauszug als Anregung",
        "summary": "Der Baum folgt dem Thema; der Lehrplan liefert nur Anregungen (zusätzliche Themen als „suggested“).",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Licht und Sehen im Alltag",
            "frame": FRAME_PHYS_SEK1,
            "items": [LEHRPLAN_DOC],
            "shape": {"depth": 2},
        },
    },
]

PRESETS: list[dict[str, Any]] = [
    *TOPIC_PRESETS,
    *DOCUMENT_PRESETS,
    *FOLDERS_PRESETS,
    *CONTENTS_PRESETS,
    *REFINE_PRESETS,
]
