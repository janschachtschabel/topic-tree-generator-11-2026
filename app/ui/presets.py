"""Ready-to-run German sample scenarios for the built-in test UI (one per use case and refine mode)."""

from typing import Any

_DISC_PHYS = "http://w3id.org/openeduhub/vocabs/discipline/460"
_DISC_TECH = "http://w3id.org/openeduhub/vocabs/discipline/500"
_CTX_SEK1 = "http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"
_CTX_BERUF = "http://w3id.org/openeduhub/vocabs/educationalContext/berufliche_bildung"
_ROLE_TEACHER = "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"

_FRAME_PHYS_SEK1 = {
    "discipline_uri": [_DISC_PHYS],
    "educational_context_uri": [_CTX_SEK1],
    "intended_end_user_role_uri": [_ROLE_TEACHER],
}

_LEHRPLAN_EXCERPT = """<!-- page: 12 -->
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

PRESETS: list[dict[str, Any]] = [
    {
        "id": "topic_sek1",
        "title": "Thema: Physik Optik (Sek I)",
        "badge": "topic",
        "summary": "Vollständiger 3-Ebenen-Themenbaum mit Zusatzthema, Include/Exclude und Experiment-Fokus.",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik für die Sekundarstufe I, alltagsnah, mit Experimenten",
            "frame": _FRAME_PHYS_SEK1,
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
                "description_length": 60,
                "language": "de",
            },
        },
    },
    {
        "id": "topic_beruf",
        "title": "Thema: Berufsbildung (Lernfelder)",
        "badge": "topic",
        "summary": "Automatische Wahl des Ordnungsprinzips für die berufliche Bildung (Handlungs-/Lernfelder).",
        "payload": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Elektromobilität und Hochvoltsysteme in der Kfz-Werkstatt",
            "frame": {
                "discipline_uri": [_DISC_TECH],
                "educational_context_uri": [_CTX_BERUF],
                "intended_end_user_role_uri": [_ROLE_TEACHER],
            },
            "shape": {
                "depth": 2,
                "main_topics": {"min": 5, "max": 8},
                "children": {"min": 3, "max": 5},
                "extra_topics": [],
            },
            "hints": {
                "context": "Ausbildung Kfz-Mechatronik, praxisnahe Arbeits- und Geschäftsprozesse",
                "description_length": 60,
                "language": "de",
            },
        },
    },
    {
        "id": "document_lehrplan",
        "title": "Dokument: Lehrplan Physik (Markdown)",
        "badge": "document",
        "summary": "Strukturdokument mit Überschriften und Seitenmarken plus ein Arbeitsblatt zum Einsortieren.",
        "payload": {
            "mode": "create",
            "use_case": "document",
            "items": [
                {
                    "id": "d1",
                    "nodeId": "9a41c3d0-0001",
                    "use": ["structure"],
                    "properties": {"cm:title": ["Lehrplan Physik Sek I (Auszug)"]},
                    "fulltext": {"format": "markdown", "text": _LEHRPLAN_EXCERPT},
                },
                {
                    "id": "c1",
                    "nodeId": "5c0e1f2a-0001",
                    "use": ["content"],
                    "properties": {
                        "cm:title": ["Versuchsanleitung: Schattenräume und Finsternis"],
                        "cm:description": ["Schülerexperiment zu Kernschatten und Halbschatten"],
                        "cclom:general_keyword": ["Schatten", "Licht", "Experiment"],
                    },
                },
            ],
            "frame": _FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
            "hints": {"exclude": ["Wahlpflicht"], "order": "Themenfelder", "description_length": 60, "language": "de"},
        },
    },
    {
        "id": "folders_upload",
        "title": "Ordner: Upload verbessern",
        "badge": "folders",
        "summary": "Ordnerbaum inkl. „Neuer Ordner (2)“ wird mit options.improve anhand der Dateien verbessert.",
        "payload": {
            "mode": "create",
            "use_case": "folders",
            "folders": [
                {
                    "title": "Optik",
                    "items": ["c1", "c2"],
                    "subcollections": [{"title": "Linsen", "items": ["c3"], "subcollections": []}],
                },
                {"title": "Neuer Ordner (2)", "items": ["c4", "c5"], "subcollections": []},
            ],
            "items": [
                {"id": "c1", "nodeId": "n-c1", "use": ["content"], "properties": {"cm:title": ["Licht und Schatten"]}},
                {"id": "c2", "nodeId": "n-c2", "use": ["content"], "properties": {"cm:title": ["Lochkamera bauen"]}},
                {"id": "c3", "nodeId": "n-c3", "use": ["content"], "properties": {"cm:title": ["Sammellinse & Fokus"]}},
                {
                    "id": "c4",
                    "nodeId": "n-c4",
                    "use": ["content"],
                    "properties": {"cm:title": ["Reflexion am Spiegel"]},
                },
                {"id": "c5", "nodeId": "n-c5", "use": ["content"], "properties": {"cm:title": ["Hohlspiegel-Versuch"]}},
            ],
            "frame": _FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 1, "max": 6}, "children": {"min": 2, "max": 6}},
            "options": {"improve": True, "assign_contents": True},
        },
    },
    {
        "id": "contents_cluster",
        "title": "Inhalte: 12 Materialien gruppieren",
        "badge": "contents",
        "summary": "Unstrukturierte Materialien (11× Optik + 1× Off-Topic) werden automatisch gruppiert und zugeordnet.",
        "payload": {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "items": [
                {
                    "id": "c1",
                    "properties": {"cm:title": ["Lichtquellen und Strahlenmodell"], "cclom:general_keyword": ["Licht"]},
                },
                {
                    "id": "c2",
                    "properties": {"cm:title": ["Kern- und Halbschatten"], "cclom:general_keyword": ["Schatten"]},
                },
                {
                    "id": "c3",
                    "properties": {"cm:title": ["Reflexionsgesetz am Spiegel"], "cclom:general_keyword": ["Spiegel"]},
                },
                {
                    "id": "c4",
                    "properties": {"cm:title": ["Hohlspiegel und Wölbspiegel"], "cclom:general_keyword": ["Spiegel"]},
                },
                {
                    "id": "c5",
                    "properties": {
                        "cm:title": ["Lichtbrechung an Wasser und Glas"],
                        "cclom:general_keyword": ["Brechung"],
                    },
                },
                {
                    "id": "c6",
                    "properties": {
                        "cm:title": ["Totalreflexion in Glasfasern"],
                        "cclom:general_keyword": ["Totalreflexion"],
                    },
                },
                {
                    "id": "c7",
                    "properties": {"cm:title": ["Sammellinsen und Bildentstehung"], "cclom:general_keyword": ["Linse"]},
                },
                {
                    "id": "c8",
                    "properties": {"cm:title": ["Menschliches Auge und Sehfehler"], "cclom:general_keyword": ["Auge"]},
                },
                {
                    "id": "c9",
                    "properties": {"cm:title": ["Spektralfarben am Prisma"], "cclom:general_keyword": ["Farben"]},
                },
                {
                    "id": "c10",
                    "properties": {"cm:title": ["Additive Farbmischung (RGB)"], "cclom:general_keyword": ["Farben"]},
                },
                {
                    "id": "c11",
                    "properties": {
                        "cm:title": ["Mikroskop und Fernrohr"],
                        "cclom:general_keyword": ["Optische Geräte"],
                    },
                },
                {
                    "id": "c12",
                    "properties": {"cm:title": ["Rezept für Apfelkuchen"], "cclom:general_keyword": ["Backen"]},
                },
            ],
            "frame": _FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 3, "max": 6}, "children": {"min": 2, "max": 5}},
            "options": {"assign_contents": True, "multi_assign": True, "min_confidence": 0.6},
        },
    },
    {
        "id": "refine_feedback",
        "title": "Refine: Feedback & gesperrter Ast",
        "badge": "refine",
        "summary": "Bestehenden Entwurf mit Freitext-Feedback weiterentwickeln; „Optik“ ist über locked geschützt.",
        "payload": {
            "mode": "refine",
            "use_case": "topic",
            "topic": "Physik Sek I",
            "current_tree": {
                "version": "v1",
                "collection": [
                    {
                        "key": "k-optik",
                        "title": "Optik",
                        "shorttitle": "Optik",
                        "properties": {
                            "cm:title": ["Optik"],
                            "cm:description": ["Grundlagen zu Licht, Schatten, Spiegeln und Linsen."],
                            "cclom:general_keyword": ["Licht", "Spiegel", "Linsen"],
                        },
                        "subcollections": [
                            {"key": "k-spiegel", "title": "Spiegel", "shorttitle": "Spiegel", "subcollections": []},
                            {"key": "k-linsen", "title": "Linsen", "shorttitle": "Linsen", "subcollections": []},
                        ],
                    },
                    {
                        "key": "k-mechanik",
                        "title": "Mechanik",
                        "shorttitle": "Mechanik",
                        "properties": {"cm:title": ["Mechanik"], "cm:description": ["Kräfte und Bewegungen."]},
                        "subcollections": [],
                    },
                    {
                        "key": "k-akustik",
                        "title": "Akustik",
                        "shorttitle": "Akustik",
                        "properties": {"cm:title": ["Akustik"], "cm:description": ["Schall und Schwingungen."]},
                        "subcollections": [],
                    },
                ],
                "generation": {
                    "mode": "create",
                    "use_case": "topic",
                    "topic": "Physik Sek I",
                    "frame": _FRAME_PHYS_SEK1,
                },
            },
            "feedback": {
                "text": "Füge Farben und Spektrum als eigenes Hauptthema hinzu und hänge Akustik unter Mechanik.",
                "locked": ["k-optik"],
            },
            "frame": _FRAME_PHYS_SEK1,
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
        },
    },
    {
        "id": "assign_only",
        "title": "Refine: Nur Inhalte einsortieren",
        "badge": "assign_only",
        "summary": "Bestehende Struktur bleibt unverändert (`assign_only: true`), nur neue Inhalte werden zugeordnet.",
        "payload": {
            "mode": "refine",
            "use_case": "folders",
            "current_tree": {
                "version": "v3",
                "collection": [
                    {
                        "key": "k-optik",
                        "title": "Optik",
                        "shorttitle": "Optik",
                        "properties": {"cm:title": ["Optik"], "cm:description": ["Licht und optische Phänomene."]},
                        "subcollections": [
                            {
                                "key": "k-linsen",
                                "title": "Linsen",
                                "shorttitle": "Linsen",
                                "properties": {
                                    "cm:title": ["Linsen"],
                                    "cm:description": ["Sammel- und Zerstreuungslinsen."],
                                },
                                "subcollections": [],
                            },
                            {
                                "key": "k-spiegel",
                                "title": "Spiegel",
                                "shorttitle": "Spiegel",
                                "properties": {
                                    "cm:title": ["Spiegel"],
                                    "cm:description": ["Reflexion an ebenen und gewölbten Spiegeln."],
                                },
                                "subcollections": [],
                            },
                        ],
                    }
                ],
                "generation": {"mode": "create", "use_case": "folders", "frame": _FRAME_PHYS_SEK1},
            },
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
            "frame": _FRAME_PHYS_SEK1,
            "options": {"assign_only": True, "assign_contents": True, "min_confidence": 0.6},
        },
    },
]
