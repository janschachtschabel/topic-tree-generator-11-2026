"""OpenAPI request examples for POST /v2/topic-tree, from the shortest to the complete call (Leitfaden Kap. 1)."""

from app.api.examples_combos import COMBO_EXAMPLES, REFINE_EXAMPLES
from app.api.examples_values import DISC as _DISC
from app.api.examples_values import FRAME as _FRAME

_EXAMPLES = {
    "topic_minimal": {
        "summary": "Thema, kürzester Aufruf",
        "description": "Nur `topic` und ein Fach. Form (Ebenen, Breite) und Beschreibungslänge wählt der Dienst nach der Zielgruppe; alle übrigen Felder haben Standardwerte.",
        "value": {"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {"discipline_uri": [_DISC]}},
    },
    "topic_full": {
        "summary": "Thema mit Rahmen, Form, Hinweisen und Optionen",
        "description": "Alle Stellschrauben eines Themenbaums: `frame` (Fach, Stufe, Zielgruppe als SkoHub-URIs), `shape` (Ebenen, Haupt- und Unterthemen, Zusatzthema „Allgemeines“) und `hints` (Kontext, Ein- und Ausschluss, Wortzahl der Beschreibungen).",
        "value": {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik für die Sekundarstufe I, alltagsnah, mit Experimenten",
            "frame": _FRAME,
            "shape": {
                "depth": 3,
                "main_topics": {"min": 6, "max": 12},
                "children": {"min": 3, "max": 8},
                "extra_topics": ["general"],
            },
            "hints": {
                "context": "Unterricht Klasse 7 bis 9, viele Schülerexperimente",
                "include": ["Farben"],
                "exclude": ["Wellenoptik"],
                "description_length": 60,
            },
        },
    },
    "document": {
        "summary": "Strukturdokument (Lehrplan) plus eigene Inhalte",
        "description": '`use_case: document`: Die Überschriften des Lehrplans (Eintrag mit `use: ["structure"]` und Volltext) werden zum Baum, Abschnitt und Seite stehen in `origin`. Der Eintrag mit `use: ["content"]` wird nur einsortiert; seine `nodeId` kommt unverändert zurück.',
        "value": {
            "mode": "create",
            "use_case": "document",
            "items": [
                {
                    "id": "d1",
                    "use": ["structure"],
                    "properties": {"cm:title": ["Lehrplan Physik, Klassen 7 bis 10"]},
                    "fulltext": {
                        "format": "markdown",
                        "text": "<!-- page: 12 -->\n## Themenfeld 2: Optische Phänomene\nLicht trifft auf Grenzflächen …",
                    },
                },
                {
                    "id": "c1",
                    "nodeId": "5c0e1f2a-…",
                    "use": ["content"],
                    "properties": {"cm:title": ["Licht und Schatten"]},
                },
            ],
            "frame": _FRAME,
            "hints": {"exclude": ["Wahlpflicht"], "order": "Themenfelder"},
        },
    },
    "folders": {
        "summary": "Ordner und Dateien übernehmen und verbessern",
        "description": "`use_case: folders`: Die Ordner bleiben das Gerüst, die Dateien bleiben in ihren Ordnern (`confidence` 1). Mit `options.improve` schlägt der Dienst Umbenennungen und Umstellungen vor; sie stehen in `changes`.",
        "value": {
            "mode": "create",
            "use_case": "folders",
            "folders": [
                {"title": "Optik", "items": ["c1"], "subcollections": []},
                {"title": "Neuer Ordner (2)", "items": ["c2"], "subcollections": []},
            ],
            "items": [
                {"id": "c1", "nodeId": "5c0e1f2a-…", "properties": {"cm:title": ["Licht und Schatten"]}},
                {"id": "c2", "nodeId": "71bd09e4-…", "properties": {"cm:title": ["Spiegelbilder"]}},
            ],
            "frame": _FRAME,
            "options": {"improve": True},
        },
    },
    "contents": {
        "summary": "Unstrukturierte Inhalte gruppieren",
        "description": "`use_case: contents`: Gruppen entstehen aus den Inhalten selbst; `topic` grenzt nur ein. Fachfremdes landet mit `off_topic` in `unassigned`.",
        "value": {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "items": [
                {"id": "c1", "properties": {"cm:title": ["Licht und Schatten"]}},
                {"id": "c2", "properties": {"cm:title": ["Linsen im Alltag"]}},
            ],
            "frame": _FRAME,
        },
    },
    "refine_feedback": {
        "summary": "Entwurf mit Rückmeldung weiterentwickeln",
        "description": "`mode: refine`: das letzte Ergebnis als `current_tree`, der Wunsch als Freitext (`feedback.text`). `locked` schützt Äste. Unklares kommt als `questions` zurück und wird nicht umgesetzt.",
        "value": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": {
                "version": "v1",
                "collection": [
                    {"key": "k-optik", "title": "Optik", "subcollections": []},
                    {"key": "k-akustik", "title": "Akustik", "subcollections": []},
                ],
            },
            "feedback": {"text": "Farben als eigenes Hauptthema", "locked": ["k-optik"]},
            "frame": _FRAME,
        },
    },
    "assign_only": {
        "summary": "Inhalte in einen bestehenden (auch fremden) Baum einsortieren; Knoten bleiben unverändert",
        "description": "Nur einsortieren: Struktur, Titel, `properties` und `nodeId` jedes Knotens bleiben, es kommen nur `contents` hinzu. Der Baum darf aus dem Repository stammen (ohne `key`, ohne `generation`); `use_case` spielt keine Rolle.",
        "value": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": {
                "collection": [
                    {
                        "nodeId": "n-optik",
                        "title": "Optik",
                        "subcollections": [{"nodeId": "n-linsen", "title": "Linsen"}],
                    }
                ]
            },
            "items": [{"id": "c9", "use": ["content"], "properties": {"cm:title": ["Brechung am Prisma"]}}],
            "frame": _FRAME,
            "options": {"assign_only": True},
        },
    },
    "describe": {
        "summary": "Beschreibung eines Knotens mit Baum-Kontext neu schreiben (statt /generate-collection-description)",
        "description": "Die Änderung `describe` schreibt Beschreibung und Schlagworte eines Knotens neu. Das Modell kennt Pfad, Geschwister und den ganzen Baum; `hint` ist Grundlage oder Wunsch (früher `text_context` des alten Endpunkts). Für eine einzelne Sammlung genügt ein Baum mit einem Knoten.",
        "value": {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": {
                "collection": [
                    {"key": "k-optik", "title": "Optik", "subcollections": [{"key": "k-linsen", "title": "Linsen"}]}
                ]
            },
            "feedback": {
                "changes": [{"op": "describe", "key": "k-linsen", "hint": "Alltagsbeispiele wie Lupe und Brille"}]
            },
            "frame": _FRAME,
        },
    },
}


_REFINE = ("refine_feedback", "refine_changes_items", "assign_only", "describe")
# Order of the Swagger drop-down: single use cases, combinations, then the calls on an existing tree.
REQUEST_EXAMPLES = {
    **{k: v for k, v in _EXAMPLES.items() if k not in _REFINE},
    **COMBO_EXAMPLES,
    **{k: ({**_EXAMPLES, **REFINE_EXAMPLES})[k] for k in _REFINE},
}
