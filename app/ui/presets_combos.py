"""Test UI presets that combine several inputs in one call (Thema, Gliederungsdokument, Inhalte, Ordner).

Each preset belongs to the task of its backbone source (`use_case`); the other inputs come in through
"Zusätzlich einbeziehen", so every value shows up in the form.
"""

from typing import Any

from app.ui.preset_vocab import FRAME_PHYS_SEK1, STRUCT, material
from app.ui.presets_inputs import LEHRPLAN_DOC, UPLOAD_FILES, UPLOAD_FOLDERS

_SCHULCURRICULUM = {
    "id": "doc2",
    "use": ["structure"],
    "properties": {"cm:title": ["Schulcurriculum Physik Klasse 7"]},
    "fulltext": {
        "format": "markdown",
        "text": "# Schulcurriculum Physik Klasse 7\n\n## Optik im Alltag\nSehen, Spiegel und Linsen an Alltagsgeräten."
        "\n\n## Projekt: Wir bauen eine Kamera\nLochkamera und Sammellinse im Vergleich.",
    },
}

_MATERIALS = [
    ("Lichtquellen und Strahlenmodell", ["Licht"]),
    ("Kern- und Halbschatten", ["Schatten"]),
    ("Reflexionsgesetz am Spiegel", ["Spiegel"]),
    ("Sammellinsen und Bildentstehung", ["Linse"]),
    ("Spektralfarben am Prisma", ["Farben"]),
    ("Additive Farbmischung (RGB)", ["Farben"]),
]

COMBO_PRESETS: list[dict[str, Any]] = [
    {
        "id": "combo_topic_document_contents",
        "task": "topic",
        "title": "Kombination: Thema + Lehrplan als Anregung + Materialien",
        "summary": "Das Thema bildet das Gerüst, der Lehrplan regt Themen an, ein Material prägt mit, drei werden "
        "nur einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik",
            "items": [
                LEHRPLAN_DOC,
                material("a1", "Projekt: Kamera obscura im Schuhkarton", ["Lochkamera", "Projekt"], use=STRUCT),
                material("b1", "Brechung im Wasserglas", ["Brechung"]),
                material("b2", "Regenbogen mit dem Gartenschlauch", ["Farben", "Spektrum"]),
                material("b3", "Bruchrechnen üben", ["Mathematik"]),
            ],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2},
        },
    },
    {
        "id": "combo_document_as_content",
        "task": "document",
        "title": "Kombination: Lehrplan als Gerüst und Inhalt + Thema + Materialien",
        "summary": "Der Lehrplan liefert die Gliederung und wird selbst einsortiert; das Thema grenzt ein, zwei "
        "Materialien kommen dazu.",
        "payload": {
            "mode": "create",
            "use_case": "document",
            "topic": "Optik ohne Wellenoptik",
            "items": [
                {**LEHRPLAN_DOC, "use": ["structure", "content"]},
                material("b1", "Schattentheater im Klassenraum", ["Schatten"]),
                material("b2", "Farbkreisel basteln", ["Farben", "Farbmischung"]),
            ],
            "frame": FRAME_PHYS_SEK1,
        },
    },
    {
        "id": "combo_folders_document_loose",
        "task": "folders",
        "title": "Kombination: Ordner verbessern mit Lehrplan + lose Dateien",
        "summary": "Die Ordner bleiben das Gerüst und werden am Lehrplan ausgerichtet; zwei lose Dateien werden "
        "einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "folders",
            "topic": "Optik",
            "folders": UPLOAD_FOLDERS,
            "items": [
                *UPLOAD_FILES,
                LEHRPLAN_DOC,
                material("b1", "Brennweite einer Lupe bestimmen", ["Linse"]),
                material("b2", "Spiegelschrift lesen", ["Spiegel"]),
            ],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
            "options": {"improve": True},
        },
    },
    {
        "id": "combo_topic_folders",
        "task": "topic",
        "title": "Kombination: Thema + Ordnerstruktur + lose Materialien",
        "summary": "Das Thema bildet das Gerüst, die Ordner regen die Gliederung an und ihre Dateien werden mit dem "
        "Ordnerpfad als Hinweis einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik",
            "folders": UPLOAD_FOLDERS,
            "items": [*UPLOAD_FILES, material("b1", "Regenbogen im Klassenzimmer", ["Farben"])],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2},
        },
    },
    {
        "id": "combo_document_two_docs_folders",
        "task": "document",
        "title": "Kombination: zwei Lehrpläne + Themenliste + Ordner als Ablage",
        "summary": "Landeslehrplan und Schulcurriculum ergeben eine Gliederung, eine Themenliste ergänzt sie, die Ordner "
        "zählen nur als Ablage der Dateien.",
        "payload": {
            "mode": "create",
            "use_case": "document",
            "folders": UPLOAD_FOLDERS,
            "folders_use": ["content"],
            "items": [
                *UPLOAD_FILES,
                LEHRPLAN_DOC,
                _SCHULCURRICULUM,
                material("a1", "Themenliste Fachkonferenz", ["Lichtgeschwindigkeit", "Auge"], use=("structure",)),
            ],
            "frame": FRAME_PHYS_SEK1,
            "hints": {"exclude": ["Wahlpflicht"]},
        },
    },
    {
        "id": "combo_contents_folders",
        "task": "contents",
        "title": "Kombination: Materialien gruppieren + Ordner als Gliederungshinweis",
        "summary": "Die Gruppen entstehen aus den Materialien, die Ordnerstruktur regt sie an; Ordnerdateien werden "
        "neu einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "folders": UPLOAD_FOLDERS,
            "folders_use": ["structure"],
            "items": [
                *UPLOAD_FILES,
                *[material(f"a{i}", t, k, use=STRUCT) for i, (t, k) in enumerate(_MATERIALS, start=1)],
            ],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 3, "max": 6}, "children": {"min": 2, "max": 5}},
        },
    },
    {
        "id": "combo_folders_outline_only",
        "task": "folders",
        "title": "Kombination: Ordner nur als Gliederung + Lehrplan, alle Dateien neu einsortieren",
        "summary": "Die Ordner bleiben das Gerüst und werden am Lehrplan verbessert; ihre bisherige Zuordnung zählt "
        "nicht, alle Dateien werden neu einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "folders",
            "folders": UPLOAD_FOLDERS,
            "folders_use": ["structure"],
            "items": [*UPLOAD_FILES, LEHRPLAN_DOC],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
            "options": {"improve": True},
        },
    },
]
