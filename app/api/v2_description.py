"""OpenAPI texts of /docs: the service overview and the description of POST /v2/topic-tree (German, user-facing)."""

# Leitfaden Kap. 6: info.description is the Steckbrief's Kurzbeschreibung word for word (tested), so the overview of
# the endpoints lives in the tag descriptions below.
APP_DESCRIPTION = (
    "Erzeugt Themenbäume (Sammlungsstrukturen) für Bildungsinhalte: aus einem Thema, einem Strukturdokument wie "
    "einem Lehrplan, aus Ordnern und Dateien oder aus unstrukturierten Inhalten. Entwürfe lassen sich mit "
    "Rückmeldungen weiterentwickeln, Inhalte werden den Knoten zugeordnet."
)

OPENAPI_TAGS = [
    {
        "name": "Themenbaum v2",
        "description": "Der aktuelle Endpunkt für alle Fälle: neuer Baum aus Thema, Dokument, Ordnern oder Inhalten, "
        "Kombinationen davon, Weiterentwickeln, Einsortieren in einen bestehenden Baum und Knoten neu beschreiben. "
        "Aufklappen für Use Cases, Kombinationen und Optionen; das Auswahlfeld „Examples“ enthält ein Beispiel für "
        "jeden Fall.",
    },
    {
        "name": "Themenbaum-Generator",
        "description": "Alter Endpunkt (v1), im Format unverändert für bestehende Aufrufer. Neue Aufrufer nutzen "
        "`POST /v2/topic-tree`.",
    },
    {
        "name": "Sammlungsbeschreibungen generieren",
        "description": "Alter Endpunkt (v1), im Format unverändert für bestehende Aufrufer. In v2 beschreibt die "
        "Änderung `describe` (`mode: refine`, `feedback.changes`) eine Sammlung mit dem ganzen Baum als Kontext; "
        "siehe Beispiel `describe` bei `POST /v2/topic-tree`.",
    },
]

V2_DESCRIPTION = """
Erzeugt einen Themenbaum oder entwickelt einen bestehenden weiter. Synchron, je nach Baumgröße 10 bis 120 Sekunden.
Die Feldtabelle steht unter „Schema“; jedes Beispiel im Auswahlfeld „Examples“ hat eine eigene Erklärung.

### 1. Gerüst wählen: `use_case` (bei `mode: create`)

| `use_case` | Gerüst des Baums | Pflicht außer `frame` |
|---|---|---|
| `topic` | ein Thema; das Sprachmodell plant die Gliederung | `topic` |
| `document` | die Überschriften eines Gliederungsdokuments (z. B. Lehrplan, Markdown mit Seitenmarken) | ein Eintrag in `items` mit `use: ["structure"]` und `fulltext` |
| `folders` | eine vorhandene Ordnerstruktur, auf Wunsch verbessert (`options.improve`) | `folders` |
| `contents` | Gruppen, die aus den Inhalten selbst entstehen | `items` |

`frame` (Fach, Bildungsstufe, Zielgruppe als SkoHub-URIs, Listen dürfen leer sein) steuert Sprache, Tiefe und Breite
und landet als Metadatum an jedem Knoten.

### 2. Weitere Eingaben kombinieren: Rollen

Alles, was nicht das Gerüst ist, fließt nach seiner Rolle ein:

* `use` je Eintrag in `items`: `["structure"]` prägt die Gliederung (Gliederungsdokument), `["content"]` wird nur
  einsortiert (Material), `["structure", "content"]` beides, `[]` keins. Ohne `use` gilt bei `contents` beides,
  sonst `["content"]`.
* `folders_use` für die ganze Ordnerstruktur, mit denselben Werten: Standard ist beides (Ordner regen die Gliederung
  an, der Ordnerpfad hilft beim Einsortieren); `["content"]` nur Ablagehinweis; `[]` angenommen, nicht genutzt.
* `topic` grenzt bei `document`, `contents` und `folders` ein. `path` an einem Eintrag wirkt wie ein Ordnerpfad.

Häufige Kombinationen (Name des Beispiels im Auswahlfeld):

| Ziel | Aufbau | Beispiel |
|---|---|---|
| Thema vorgeben, Material einsortieren | `topic` + `items` mit `["content"]` | `combo_topic_contents` |
| Thema, Material regt zusätzlich Themen an | `topic` + `items` mit `["structure", "content"]` | `combo_topic_contents_inspire` |
| Thema, Lehrplan nur als Anregung | `topic` + Dokument mit `["structure"]` | `combo_topic_document` |
| Thema, vorhandene Ordner einbeziehen | `topic` + `folders` (ohne `folders_use`) | `combo_topic_folders` |
| Lehrplan als Gerüst, Thema grenzt ein, Material hinein | `document` + `topic` + `items` | `combo_document_topic_contents` |
| Material gruppieren, Lehrplan orientiert | `contents` + Dokument mit `["structure"]` | `combo_contents_document` |
| Material gruppieren, Ordner nur als Hinweis | `contents` + `folders_use: ["content"]` | `combo_contents_folders_hint` |
| Ordner verbessern nach Lehrplan, lose Dateien hinein | `folders` + `options.improve` + Dokument | `combo_folders_improve_document` |
| Ordner als Gliederung, alle Dateien neu verteilen | `folders` + `folders_use: ["structure"]` | `combo_folders_outline_only` |

Was gesendet, aber nicht genutzt wird, meldet `warnings` mit `INPUT_IGNORED`.

### 3. Einen bestehenden Baum bearbeiten: `mode: refine`

Den Baum als `current_tree` schicken (das letzte Ergebnis: `collection`, `metadata.version`, `metadata.generation`;
oder einen beliebigen Baum, je Knoten genügt `title`, `key` und `nodeId` sind optional). Fehlende Vorgaben übernimmt
der Dienst aus `current_tree.generation`.

* `feedback.text`: Wunsch als Freitext; Unklares kommt als `questions` zurück.
* `feedback.changes`: gezielte Änderungen `add`, `remove`, `rename`, `edit`, `move`, `merge`, `split` und
  `describe` (Beschreibung eines Knotens mit Baum-Kontext neu schreiben, Nachfolger von
  `/generate-collection-description`).
* `feedback.locked`: Schlüssel, deren Ast unverändert bleibt.
* `options.assign_only: true`: nur neue `items` einsortieren; Struktur, `properties` und `nodeId` jedes Knotens
  bleiben, auch bei einem Baum aus dem Repository.

### 4. Wichtige Optionen

| Feld | Standard | Wirkung |
|---|---|---|
| `options.assign_contents` | `true` | Inhalte mit Rolle `content` den Knoten zuordnen |
| `options.multi_assign` | `true` | ein Inhalt darf an mehreren Knoten hängen |
| `options.min_confidence` | `0.6` | darunter kommt ein Inhalt mit `low_confidence` nach `unassigned` |
| `options.improve` | `false` | nur `folders`: Verbesserungen als `changes` vorschlagen |
| `options.auto_metadata` | `false` | Fach, Stufe und Zielgruppe je Knoten verengen, wenn `frame` leer oder mehrwertig ist |
| `options.assign_only` | `false` | nur `refine`: nur einsortieren, Knoten bleiben unverändert |
| `shape` | nach Zielgruppe | `depth` (1–3), `main_topics` und `children` als Bereich, `extra_topics` (nur `topic`) |
| `hints` | – | `context`, `include`, `exclude`, `order`, `description_length` (Wörter), `language` |

### 5. Antwort

* `collection`: der Baum; je Knoten `key` (bleibt über `refine` stabil), `nodeId` (falls gesendet), `title`,
  `shorttitle`, `status`, `origin`, edu-sharing-`properties`, `contents` (`id`, `nodeId`, `confidence`).
* `unassigned`: nicht einsortierte Inhalte mit Grund (`off_topic`, `low_confidence`, `no_matching_node`, `excluded`).
* `changes` (umgesetzt oder vorgeschlagen), `questions` (Rückfragen), `warnings` (alles, was nicht gelang oder
  auffiel, mit festem `code`; nie eine stille Lücke).
* `metadata`: Titel, Beschreibung, `version`, `vocab_labels` und `generation` (alle Vorgaben des Laufs; für den
  nächsten Durchlauf mit `collection` als `current_tree` zurückschicken).

Fehler kommen als `{"error": {"code", "message", "trace_id"}}`. Eine `nodeId` liest der Dienst nie, er reicht sie
nur durch.
"""
