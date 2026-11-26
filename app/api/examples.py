"""OpenAPI request examples for POST /v2/topic-tree, from the shortest to the complete call (Leitfaden Kap. 1)."""

_DISC = "http://w3id.org/openeduhub/vocabs/discipline/460"
_SEK1 = "http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"
_TEACHER = "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"
_FRAME = {"discipline_uri": [_DISC], "educational_context_uri": [_SEK1], "intended_end_user_role_uri": [_TEACHER]}

REQUEST_EXAMPLES = {
    "topic_minimal": {
        "summary": "Thema, kürzester Aufruf",
        "value": {"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {"discipline_uri": [_DISC]}},
    },
    "topic_full": {
        "summary": "Thema mit Rahmen, Form, Hinweisen und Optionen",
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
