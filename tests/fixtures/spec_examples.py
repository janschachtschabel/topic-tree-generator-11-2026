"""Request examples from the spec ("Themenbaum-Dienst: Use Cases und Datenformat"), placeholders filled minimally."""

DISC = "http://w3id.org/openeduhub/vocabs/discipline/460"
SEK1 = "http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"
TEACHER = "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"

FRAME = {"discipline_uri": [DISC], "educational_context_uri": [SEK1], "intended_end_user_role_uri": [TEACHER]}

FULL_OPTIONS_BLOCK = {
    "frame": FRAME,
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
        "order": "Themen",
        "description_length": 60,
        "language": "de",
    },
    "options": {
        "improve": False,
        "assign_contents": True,
        "assign_only": False,
        "multi_assign": True,
        "min_confidence": 0.6,
    },
}

TOPIC = {
    "mode": "create",
    "use_case": "topic",
    "topic": "Optik für die Sekundarstufe I, alltagsnah, mit Experimenten",
    "frame": FRAME,
    "shape": {"depth": 3, "main_topics": {"min": 6, "max": 12}, "children": {"min": 3, "max": 8}},
    "hints": {"context": "Unterricht Klasse 7 bis 9", "exclude": ["Wellenoptik"]},
}

ITEM_DOC = {
    "id": "d1",
    "nodeId": "9a41c3d0-0000",
    "use": ["structure"],
    "properties": {"cm:title": ["Lehrplan Physik Rheinland-Pfalz, Klassen 7 bis 10"], "ccm:taxonid": [DISC]},
    "fulltext": {"format": "markdown", "text": "# Lehrplan\n## Themenfeld 1\nText\n## Themenfeld 2\nText"},
}
ITEM_CONTENT = {
    "id": "c1",
    "nodeId": "5c0e1f2a-0000",
    "use": ["content"],
    "properties": {
        "cm:title": ["Licht und Schatten"],
        "cm:description": ["Arbeitsblatt zu Kernschatten und Halbschatten"],
        "cclom:general_keyword": ["Schatten", "Licht"],
        "ccm:taxonid": [DISC],
        "ccm:educationalcontext": [SEK1],
    },
}

DOCUMENT = {
    "mode": "create",
    "use_case": "document",
    "items": [ITEM_DOC, ITEM_CONTENT],
    "frame": FRAME,
    "hints": {"include": ["Themenfelder 1 bis 6"], "exclude": ["Wahlpflicht"], "order": "Themenfelder"},
}

FOLDERS_TREE = [
    {
        "title": "Optik",
        "items": ["c1", "c2"],
        "subcollections": [{"title": "Linsen", "items": ["c3"], "subcollections": []}],
    },
    {"title": "Neuer Ordner (2)", "items": ["c4"], "subcollections": []},
]


def content_item(item_id: str, title: str) -> dict:
    return {"id": item_id, "use": ["content"], "properties": {"cm:title": [title]}}


FOLDER_ITEMS = [
    content_item(i, t) for i, t in [("c1", "Licht"), ("c2", "Schatten"), ("c3", "Sammellinse"), ("c4", "Spiegelbild")]
]

CURRENT_TREE = {
    "version": "v1",
    "collection": [
        {
            "key": "k-optik",
            "title": "Optik",
            "shorttitle": "Optik",
            "properties": {"cm:title": ["Optik"]},
            "subcollections": [{"key": "k-linsen", "title": "Linsen", "shorttitle": "Linsen", "subcollections": []}],
        },
        {"key": "k-neuer-ordner-2", "title": "Neuer Ordner (2)", "shorttitle": "Neuer Ordner 2", "subcollections": []},
    ],
    "generation": {"mode": "create", "use_case": "folders", "frame": FRAME},
}

FOLDERS_REFINE = {
    "mode": "refine",
    "use_case": "folders",
    "folders": FOLDERS_TREE,
    "items": FOLDER_ITEMS,
    "current_tree": CURRENT_TREE,
    "feedback": {"text": "Neuer Ordner (2) ist eigentlich Spiegel und gehört zu Optik.", "locked": ["k-optik"]},
    "frame": FRAME,
    "options": {"improve": True},
}

CONTENTS = {
    "mode": "create",
    "use_case": "contents",
    "topic": "Optik",
    "items": [
        {"id": "c1", "properties": {"cm:title": ["Licht"]}},
        {"id": "c77", "use": ["content"], "properties": {"cm:title": ["Sammelmappe Optik 2019 bis 2024"]}},
    ],
    "frame": FRAME,
    "shape": {"main_topics": {"min": 5, "max": 10}},
}

ASSIGN_ONLY = {
    "mode": "refine",
    "use_case": "folders",
    "current_tree": {**CURRENT_TREE, "version": "v3"},
    "items": [content_item("c9", "Brechung am Prisma")],
    "frame": FRAME,
    "options": {"assign_only": True},
}

FEEDBACK_WITH_CHANGES = {
    "text": "Akustik bitte unter Mechanik, Farben als eigenes Hauptthema",
    "changes": [
        {"op": "move", "key": "k-akustik", "to": "k-mechanik"},
        {"op": "add", "parent": None, "title": "Farben und Spektrum"},
    ],
    "locked": ["k-optik", "k-elektrizitaet"],
}

ALL_REQUESTS = {
    "topic": TOPIC,
    "document": DOCUMENT,
    "folders_refine": FOLDERS_REFINE,
    "contents": CONTENTS,
    "assign_only": ASSIGN_ONLY,
    "full_options": {"mode": "create", "use_case": "topic", "topic": "Optik", **FULL_OPTIONS_BLOCK},
}
