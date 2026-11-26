"""Test UI presets for the input-driven tasks: document, folders and contents (all `mode: create`)."""

from typing import Any

from app.ui.preset_vocab import FRAME_PHYS_SEK1, STRUCT, material

LEHRPLAN_EXCERPT = """<!-- page: 12 -->
# Lehrplan Physik Sekundarstufe I (Auszug)

## Themenfeld 1: Licht und Wahrnehmung
Schülerinnen und Schüler untersuchen Lichtquellen, geradlinige Ausbreitung sowie Schattenräume im Alltag.

### Lichtquellen und Ausbreitung
Selbstleuchtende und beleuchtete Körper, Strahlenmodell des Lichts, Lochkamera.

### Schatten und Finsternisse
Kernschatten, Halbschatten, Mondphasen, Sonnen- und Mondfinsternis.

<!-- page: 14 -->
## Themenfeld 2: Optische Phänomene an Grenzflächen
Licht trifft auf Grenzflächen zwischen verschiedenen Stoffen und wird reflektiert, gebrochen oder absorbiert.

### Reflexion und Spiegel
Reflexionsgesetz, ebener Spiegel, Hohl- und Wölbspiegel im Alltag.

### Brechung und Totalreflexion
Übergang Luft–Wasser–Glas, Totalreflexion, Lichtleiter und Endoskopie.

### Linsen und optische Geräte
Sammellinsen, Zerstreuungslinsen, Auge, Brille, Lupe und Mikroskop.

<!-- page: 18 -->
## Themenfeld 3: Farben und Spektren
Zerlegung weißen Lichts am Prisma, Regenbogen, additive und subtraktive Farbmischung.

## Wahlpflicht: Wellenoptik
Beugung und Interferenz am Spalt (nur für vertiefende Kurse).
"""

LEHRPLAN_DOC = {
    "id": "doc1",
    "use": ["structure"],
    "properties": {"cm:title": ["Lehrplan Physik Sek I (Auszug)"]},
    "fulltext": {"format": "markdown", "text": LEHRPLAN_EXCERPT},
}
DOCUMENT_PRESETS: list[dict[str, Any]] = [
    {
        "id": "document_lehrplan",
        "task": "document",
        "title": "Lehrplan Physik mit Seitenmarken + Material",
        "summary": "Gliederung aus den Überschriften (Abschnitt und Seite je Knoten); ein Versuch wird einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "document",
            "items": [
                LEHRPLAN_DOC,
                material(
                    "b1",
                    "Versuchsanleitung: Schattenräume und Finsternis",
                    ["Schatten", "Licht", "Experiment"],
                    "Schülerexperiment zu Kernschatten und Halbschatten",
                ),
            ],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
            "hints": {"exclude": ["Wahlpflicht"], "order": "Themenfelder"},
        },
    },
    {
        "id": "document_with_topic",
        "task": "document",
        "title": "Lehrplan + Thema als Rahmen + mehrere Materialien",
        "summary": "Thema grenzt den Lehrplan ein; vier Materialien, eins davon fachfremd (landet in „nicht zugeordnet“).",
        "payload": {
            "mode": "create",
            "use_case": "document",
            "topic": "Optik: Licht an Grenzflächen",
            "items": [
                LEHRPLAN_DOC,
                material("b1", "Brechung im Wasserglas", ["Brechung"]),
                material("b2", "Endoskopie: Licht im Glasfaserkabel", ["Totalreflexion", "Medizin"]),
                material("b3", "Lupe selbst bauen", ["Linse", "Lupe"]),
                material("b4", "Bruchrechnen üben", ["Mathematik"]),
            ],
            "frame": FRAME_PHYS_SEK1,
        },
    },
]

UPLOAD_FILES = [
    material("c1", "Licht und Schatten", []),
    material("c2", "Lochkamera bauen", []),
    material("c3", "Sammellinse & Fokus", []),
    material("c4", "Reflexion am Spiegel", []),
    material("c5", "Hohlspiegel-Versuch", []),
]
UPLOAD_FOLDERS = [
    {
        "title": "Optik",
        "items": ["c1", "c2"],
        "subcollections": [{"title": "Linsen", "items": ["c3"], "subcollections": []}],
    },
    {"title": "Neuer Ordner (2)", "items": ["c4", "c5"], "subcollections": []},
]

FOLDERS_PRESETS: list[dict[str, Any]] = [
    {
        "id": "folders_upload",
        "task": "folders",
        "title": "Upload verbessern (Ordner umbenennen und ordnen)",
        "summary": "„Neuer Ordner (2)“ und Co. werden mit „Ordnerstruktur verbessern“ anhand der Dateien verbessert.",
        "payload": {
            "mode": "create",
            "use_case": "folders",
            "folders": UPLOAD_FOLDERS,
            "items": UPLOAD_FILES,
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 1, "max": 6}, "children": {"min": 2, "max": 6}},
            "options": {"improve": True},
        },
    },
    {
        "id": "folders_loose",
        "task": "folders",
        "title": "Ordner bleiben + lose Dateien einsortieren",
        "summary": "Ordner bleiben unverändert; drei lose Dateien werden mit Konfidenz in die Ordner einsortiert.",
        "payload": {
            "mode": "create",
            "use_case": "folders",
            "folders": UPLOAD_FOLDERS,
            "items": [
                *UPLOAD_FILES,
                material("b1", "Brennweite einer Lupe bestimmen", ["Linse"]),
                material("b2", "Schattentheater im Klassenraum", ["Schatten"]),
                material("b3", "Spiegelschrift lesen", ["Spiegel"]),
            ],
            "frame": FRAME_PHYS_SEK1,
        },
    },
]

_OPTIK_MATERIALS = [
    ("Lichtquellen und Strahlenmodell", ["Licht"]),
    ("Kern- und Halbschatten", ["Schatten"]),
    ("Reflexionsgesetz am Spiegel", ["Spiegel"]),
    ("Hohlspiegel und Wölbspiegel", ["Spiegel"]),
    ("Lichtbrechung an Wasser und Glas", ["Brechung"]),
    ("Totalreflexion in Glasfasern", ["Totalreflexion"]),
    ("Sammellinsen und Bildentstehung", ["Linse"]),
    ("Menschliches Auge und Sehfehler", ["Auge"]),
    ("Spektralfarben am Prisma", ["Farben"]),
    ("Additive Farbmischung (RGB)", ["Farben"]),
    ("Mikroskop und Fernrohr", ["Optische Geräte"]),
    ("Rezept für Apfelkuchen", ["Backen"]),
]

CONTENTS_PRESETS: list[dict[str, Any]] = [
    {
        "id": "contents_cluster",
        "task": "contents",
        "title": "12 Materialien gruppieren (eins fachfremd)",
        "summary": "Gruppen entstehen aus den Materialien im Rahmen „Optik“; der Apfelkuchen bleibt draußen.",
        "payload": {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "items": [material(f"a{i}", t, k, use=STRUCT) for i, (t, k) in enumerate(_OPTIK_MATERIALS, start=1)],
            "frame": FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 3, "max": 6}, "children": {"min": 2, "max": 5}},
        },
    },
    {
        "id": "contents_mixed",
        "task": "contents",
        "title": "Materialien teils nur einsortieren",
        "summary": "Acht Materialien bilden die Gruppen; drei Arbeitsblätter werden nur einsortiert, ohne Gruppen zu prägen.",
        "payload": {
            "mode": "create",
            "use_case": "contents",
            "items": [
                *[material(f"a{i}", t, k, use=STRUCT) for i, (t, k) in enumerate(_OPTIK_MATERIALS[:8], start=1)],
                material("b1", "Arbeitsblatt: Strahlengang zeichnen", ["Linse"]),
                material("b2", "Quiz: Spiegel im Alltag", ["Spiegel"]),
                material("b3", "Test: Schatten und Licht", ["Schatten"]),
            ],
            "frame": FRAME_PHYS_SEK1,
            "options": {"min_confidence": 0.5},
        },
    },
]
