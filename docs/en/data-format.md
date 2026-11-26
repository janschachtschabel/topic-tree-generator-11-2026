# Data format of POST /v2/topic-tree

> 🇩🇪 Deutsche Fassung: [`../de/datenformat.md`](../de/datenformat.md)

Generated from the Pydantic models (`uv run python -m scripts.export_schemas`); do not edit by hand.
Patterns for single and combined use cases and for changes to trees: [`api.md`](api.md) and
[`examples/`](../examples/). Machine-readable: [`schemas/`](../schemas/).

Columns: **Required** = must be sent; **Default** = value when the field is missing. The *Meaning* column holds the
field descriptions exactly as the API publishes them in `/openapi.json`, which are German.

## Request

### Request: top level

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode) | yes |  | create: neuer Baum; refine: current_tree mit feedback oder neuen items weiterentwickeln |
| `use_case` | [`UseCase`](#usecase) | yes |  | Quelle der Struktur: topic, document (Gliederung), folders oder contents |
| `topic` | string or null (min. length 1, max. length 2000) |  | – | Thema des Baums; Pflicht bei topic, sonst optional (Eingrenzung, Titel, Rahmen) |
| `folders` | list of [`FolderNode`](#foldernode) or null |  | – | Bestehende Ordnerstruktur; Gerüst bei use_case folders, sonst ergänzende Quelle |
| `folders_use` | list of [`ItemUse`](#itemuse) or null |  | – | Rolle der ganzen Ordnerstruktur, Werte wie bei use: ['structure'] prägt den Baum, ['content'] Ordnerzuordnung der Dateien wird übernommen bzw. dient als Hinweis, beide (Standard) oder [] keines. |
| `items` | list of [`Item`](#item) or null |  | – | Materialien und Dokumente, je mit Rolle in use |
| `items_ref` | string or null (min. length 1, max. length 2083) |  | – | HTTPS-Adresse einer JSON-Liste von items; nur von Hosts in REF_ALLOWED_HOSTS |
| `current_tree` | [`CurrentTree`](#currenttree) or null |  | – | Früheres Ergebnis (mode refine) |
| `feedback` | [`Feedback`](#feedback) or null |  | – | Rückmeldung zum current_tree (mode refine) |
| `frame` | [`Frame`](#frame) | yes |  | Fachlicher Rahmen als SkoHub-URIs; übernommen in die Knoten-Metadaten |
| `shape` | [`Shape`](#shape) |  |  | Form des Baums: Tiefe und Breite |
| `hints` | [`Hints`](#hints) |  |  | Inhaltliche Hinweise |
| `options` | [`Options`](#options) |  |  | Schalter für Zuordnung, Verbesserung und Metadaten |

### Change

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `op` | [`ChangeOp`](#changeop) | yes |  | Art der Änderung: add, remove, rename, edit, move, merge, split oder describe (neu beschreiben) |
| `key` | string or null |  | – | Schlüssel des betroffenen Knotens (remove, rename, edit, move, split, describe) |
| `keys` | list of string or null |  | – | Schlüssel der zusammenzuführenden Knoten, mindestens zwei (merge) |
| `parent` | string or null |  | – | add: Schlüssel oder Titel des Elternknotens; ohne Angabe Hauptebene |
| `to` | string or null |  | – | move: Schlüssel des neuen Elternknotens; ohne Angabe oder null Hauptebene |
| `title` | string or null (min. length 1, max. length 200) |  | – | Neuer Titel (add, rename, merge) |
| `properties` | [`Properties`](#properties) or null |  | – | Zu setzende Properties (edit) |
| `hint` | string or null (max. length 1000) |  | – | split: wie der Knoten aufgeteilt werden soll; describe: Grundlage oder Wunsch für die Beschreibung |

### ChangeOp

Values: `add`, `remove`, `rename`, `edit`, `move`, `merge`, `split`, `describe`

### ChildRange

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `min` | integer (≥ 2, ≤ 20) |  | `3` | Mindestzahl der Unterthemen je Knoten (nie genau eines) |
| `max` | integer (≥ 2, ≤ 20) |  | `8` | Höchstzahl der Unterthemen je Knoten; begrenzt durch MAX_NODES_PER_LEVEL |

### ContentRefIn

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `id` | string | yes |  | id des zugeordneten Inhalts |
| `nodeId` | string or null |  | – | Knoten-ID im Repository, unverändert durchgereicht |
| `confidence` | number or null (≥ 0, ≤ 1) |  | – | Konfidenz der Zuordnung zwischen 0 und 1 |

### CurrentTree

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `version` | string or null (max. length 50) |  | – | metadata.version der früheren Antwort (ohne Angabe: v1) |
| `title` | string or null (max. length 2000) |  | – | metadata.title der früheren Antwort |
| `description` | string or null (max. length 8000) |  | – | metadata.description der früheren Antwort |
| `collection` | list of [`TreeNodeIn`](#treenodein) | yes |  | collection der früheren Antwort, gern von Hand bearbeitet |
| `generation` | [`GenerationIn`](#generationin) or null |  | – | metadata.generation der früheren Antwort; liefert Vorgaben für alles, was die Anfrage weglässt |

### ExtraTopic

Values: `general`, `methodology`

### Feedback

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `text` | string or null (max. length 8000) |  | – | Rückmeldung als Freitext; das Sprachmodell setzt sie in Änderungen um oder stellt Rückfragen |
| `changes` | list of [`Change`](#change) (max. 200 entries) |  |  | Gezielte Änderungen; Struktur ohne Sprachmodell (außer split), neue Knoten danach beschrieben |
| `locked` | list of string (max. 500 entries) |  |  | Schlüssel gesperrter Knoten; sie und ihr Ast bleiben unverändert |

### FeedbackEntry

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `version` | string or null |  | – | Version des Baums, auf die sich die Rückmeldung bezog |
| `text` | string or null |  | – | Text der Rückmeldung |

### FolderNode

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `title` | string (min. length 1, max. length 200) | yes |  | Name des Ordners |
| `items` | list of string |  |  | ids der Einträge aus items, die in diesem Ordner liegen |
| `subcollections` | list of [`FolderNode`](#foldernode) |  |  | Unterordner |

### Frame

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `discipline_uri` | list of string (max. 20 entries) |  |  | Fächer als SkoHub-URIs (Vokabular discipline); prägen Inhalt und Knoten-Metadaten |
| `educational_context_uri` | list of string (max. 20 entries) |  |  | Bildungsstufen als SkoHub-URIs (educationalContext); bestimmen den Rahmen für die Form |
| `intended_end_user_role_uri` | list of string (max. 20 entries) |  |  | Zielgruppen als SkoHub-URIs (intendedEndUserRole), etwa Lehrkräfte oder Lernende |

### Fulltext

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `format` | [`FulltextFormat`](#fulltextformat) |  | `"markdown"` | Format von text bzw. des geladenen Verweises |
| `text` | string or null (max. length 2000000) |  | – | Volltext direkt in der Anfrage (genau eines von text und ref) |
| `ref` | string or null (min. length 1, max. length 2083) |  | – | HTTPS-Adresse des Volltexts; nur Hosts aus REF_ALLOWED_HOSTS |

### FulltextFormat

Values: `markdown`, `text`

### GenerationIn

`metadata.generation` of an earlier answer: defaults for anything the new request leaves out.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode) or null |  | – | Modus des früheren Laufs |
| `use_case` | [`UseCase`](#usecase) or null |  | – | Use Case des früheren Laufs |
| `topic` | string or null |  | – | Thema des früheren Laufs |
| `frame` | [`Frame`](#frame) or null |  | – | Rahmen des früheren Laufs |
| `shape` | [`Shape`](#shape) or null |  | – | Form des früheren Laufs |
| `hints` | [`Hints`](#hints) or null |  | – | Hinweise des früheren Laufs |
| `options` | [`Options`](#options) or null |  | – | Optionen des früheren Laufs (assign_only wird nie geerbt) |
| `structure` | object or null |  | – | Erkannte Ordnung des früheren Laufs |
| `feedback` | list of [`FeedbackEntry`](#feedbackentry) |  |  | Bisherige Rückmeldungen |

### Hints

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `context` | string or null (max. length 2000) |  | – | Freitext zu Zweck und Kontext des Baums, etwa Zielgruppe oder Einsatz |
| `include` | list of string (max. 50 entries) |  |  | Begriffe, die im Baum vorkommen sollen |
| `exclude` | list of string (max. 50 entries) |  |  | Begriffe, die nicht vorkommen sollen |
| `order` | string or null (max. length 200) |  | – | Gewünschtes Ordnungsprinzip, etwa „chronologisch“ oder „nach Kompetenzen“ |
| `description_length` | integer (≥ 40, ≤ 200) |  | `60` | Ziellänge der Beschreibungen in Wörtern |
| `language` | string |  | `"de"` | Sprache der Titel und Beschreibungen als ISO-639-1-Code |

### Item

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `id` | string | yes |  | Eindeutige id des Eintrags in dieser Anfrage; erscheint in contents und unassigned |
| `nodeId` | string or null (max. length 200) |  | – | Knoten-ID im Repository; wird unverändert durchgereicht, der Dienst liest den Knoten nie |
| `use` | list of [`ItemUse`](#itemuse) or null |  | – | Rolle des Eintrags: ['structure'] Gliederung, ['content'] Inhalt, beide, oder [] keines von beiden (wird angenommen, aber weder für die Struktur genutzt noch einsortiert). Fehlt use, gilt der Standard des Use Case. |
| `properties` | [`Properties`](#properties) |  |  | edu-sharing-Properties wie cm:title oder cclom:general_keyword, Werte als Listen |
| `fulltext` | [`Fulltext`](#fulltext) or null |  | – | Volltext des Eintrags, etwa ein Lehrplan als Markdown |
| `path` | string or null (max. length 1000) |  | – | Ablageort des Eintrags (z. B. Optik/Linsen); Hinweis bei der Zuordnung |

### ItemUse

Values: `structure`, `content`

### MainRange

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `min` | integer (≥ 1, ≤ 20) |  | `6` | Mindestzahl der Hauptthemen (Ebene 1) |
| `max` | integer (≥ 1, ≤ 20) |  | `12` | Höchstzahl der Hauptthemen (Ebene 1); begrenzt durch MAX_NODES_PER_LEVEL |

### Mode

Values: `create`, `refine`

### Options

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `improve` | boolean |  | `False` | Nur use_case folders: Umbenennen, Zusammenlegen und Umstellen der Ordner vorschlagen (auch nach einem Gliederungsdokument in items). Die Vorschläge sind im Baum umgesetzt und stehen als changes mit from service in der Antwort; ohne improve bleiben die Ordner wie gesendet. |
| `assign_contents` | boolean |  | `True` | Einträge mit Rolle content den Knoten zuordnen (mit Konfidenz). false: nur die Struktur erzeugen; gesendete Inhalte meldet INPUT_IGNORED. |
| `assign_only` | boolean |  | `False` | Nur mode refine: nur neue Inhalte in den current_tree einsortieren. Struktur, Titel, properties und nodeId jedes Knotens bleiben (auch bei einem Baum aus dem Repository); feedback wird nicht umgesetzt. Gilt nur für diesen Aufruf und wird nicht geerbt. |
| `multi_assign` | boolean |  | `True` | true: Ein Inhalt darf an mehreren passenden Knoten hängen. false: nur am besten passenden Knoten. |
| `min_confidence` | number (≥ 0, ≤ 1) |  | `0.6` | Mindestkonfidenz (0 bis 1) einer Zuordnung. Darunter kommt der Inhalt mit Grund low_confidence nach unassigned; höher heißt strenger, weniger Zuordnungen. |
| `auto_metadata` | boolean |  | `False` | Fach, Bildungsstufe und Zielgruppe je Knoten bestimmen und als Vokabular-URIs setzen; sinnvoll, wenn frame leer oder mehrwertig ist (z. B. fächerübergreifend). Nur dann kostet es zusätzliche Aufrufe des Sprachmodells. |

### Properties

Free keys; values: list of string.

### Shape

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `depth` | integer (≥ 1, ≤ 4) |  | `3` | Anzahl der Ebenen, höchstens MAX_TREE_DEPTH; ohne shape nach Bildungsstufe und Eingabe |
| `main_topics` | [`MainRange`](#mainrange) |  |  | Spanne der Hauptthemen; eine einzelne Grenze übernimmt die andere aus dem Empfehlungsrahmen |
| `children` | [`ChildRange`](#childrange) |  |  | Spanne der Unterthemen je Knoten |
| `extra_topics` | list of [`ExtraTopic`](#extratopic) |  |  | Zusätzliche Hauptthemen: general (Allgemeines) und/oder methodology (Methodik und Didaktik) |

### TreeNodeIn

A node of an earlier answer (v2 or legacy format), possibly edited by hand.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `key` | string or null (max. length 200) |  | – | Schlüssel des Knotens aus der früheren Antwort; fehlt er, vergibt der Dienst einen |
| `nodeId` | string or null (max. length 200) |  | – | Knoten-ID der Sammlung im Repository, unverändert durchgereicht |
| `title` | string (min. length 1, max. length 200) | yes |  | Titel des Knotens |
| `shorttitle` | string or null (max. length 200) |  | – | Kurztitel (höchstens 20 Zeichen in der Antwort) |
| `properties` | [`Properties`](#properties) |  |  | edu-sharing-Properties des Knotens |
| `origin` | object or null |  | – | Herkunft des Knotens aus der früheren Antwort |
| `contents` | list of [`ContentRefIn`](#contentrefin) |  |  | Bereits zugeordnete Inhalte |
| `subcollections` | list of [`TreeNodeIn`](#treenodein) |  |  | Unterknoten |

### UseCase

Values: `topic`, `document`, `folders`, `contents`

## Response

### Response: top level

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `metadata` | [`Metadata`](#metadata-response) | yes |  | Angaben zum Baum und zum Lauf |
| `collection` | list of [`NodeOut`](#nodeout-response) | yes |  | Der Baum: Hauptthemen mit Unterknoten |
| `unassigned` | list of [`Unassigned`](#unassigned-response) |  |  | Inhalte, die keinem Knoten zugeordnet wurden, mit Grund |
| `changes` | list of [`ChangeRecord`](#changerecord-response) |  |  | Angewendete und vorgeschlagene Änderungen |
| `questions` | list of [`Question`](#question-response) |  |  | Rückfragen zu unklarer Rückmeldung; der Baum bleibt dafür unverändert |
| `warnings` | list of [`ServiceWarning`](#servicewarning-response) |  |  | Was nicht gelungen ist oder auffiel; ein Schritt ohne Ergebnis steht immer hier |

### ChangeOp (Response)

Values: `add`, `remove`, `rename`, `edit`, `move`, `merge`, `split`, `describe`

### ChangeRecord (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `op` | [`ChangeOp`](#changeop-response) | yes |  | Art der Änderung |
| `key` | string or null |  | – | Schlüssel des betroffenen oder neuen Knotens |
| `keys` | list of string or null |  | – | Schlüssel der zusammengeführten Knoten (merge) |
| `parent` | string or null |  | – | Schlüssel des Elternknotens eines neuen Knotens (add) |
| `to` | string or null |  | – | Schlüssel des neuen Elternknotens (move) |
| `title` | string or null |  | – | Neuer Titel |
| `from` | [`ChangeSource`](#changesource-response) | yes |  | Auslöser: feedback_text, feedback_changes oder service (Vorschlag des Dienstes) |

### ChangeSource (Response)

Values: `feedback_text`, `feedback_changes`, `service`

### ChildRange (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `min` | integer (≥ 2, ≤ 20) |  | `3` | Mindestzahl der Unterthemen je Knoten (nie genau eines) |
| `max` | integer (≥ 2, ≤ 20) |  | `8` | Höchstzahl der Unterthemen je Knoten; begrenzt durch MAX_NODES_PER_LEVEL |

### ContentRef (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `id` | string | yes |  | id des Inhalts aus der Anfrage |
| `nodeId` | string or null |  | – | Knoten-ID im Repository, unverändert aus der Anfrage |
| `confidence` | number (≥ 0, ≤ 1) |  | `1.0` | Konfidenz der Zuordnung zwischen 0 und 1 (1 bei Übernahme aus folders) |

### ExtraTopic (Response)

Values: `general`, `methodology`

### FeedbackEntry (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `version` | string or null |  | – | Version des Baums, auf die sich die Rückmeldung bezog |
| `text` | string or null |  | – | Text der Rückmeldung |

### Frame (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `discipline_uri` | list of string (max. 20 entries) |  |  | Fächer als SkoHub-URIs (Vokabular discipline); prägen Inhalt und Knoten-Metadaten |
| `educational_context_uri` | list of string (max. 20 entries) |  |  | Bildungsstufen als SkoHub-URIs (educationalContext); bestimmen den Rahmen für die Form |
| `intended_end_user_role_uri` | list of string (max. 20 entries) |  |  | Zielgruppen als SkoHub-URIs (intendedEndUserRole), etwa Lehrkräfte oder Lernende |

### Generation (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode-response) | yes |  | Modus dieses Laufs |
| `use_case` | [`UseCase`](#usecase-response) | yes |  | Use Case dieses Laufs |
| `topic` | string or null |  | – | Thema dieses Laufs |
| `frame` | [`Frame`](#frame-response) | yes |  | Wirksamer Rahmen |
| `shape` | [`Shape`](#shape-response) | yes |  | Wirksame Form |
| `hints` | [`Hints`](#hints-response) | yes |  | Wirksame Hinweise |
| `options` | [`Options`](#options-response) | yes |  | Wirksame Optionen |
| `inputs` | [`InputCounts`](#inputcounts-response) |  |  | Anzahl der Eingaben |
| `feedback` | list of [`FeedbackEntry`](#feedbackentry-response) |  |  | Alle bisherigen Rückmeldungen |
| `structure` | [`StructureInfo`](#structureinfo-response) or null |  | – | Erkannte oder vorgegebene Ordnung |
| `usage` | [`Usage`](#usage-response) or null |  | – | Verbrauch dieses Laufs |
| `generator_version` | string | yes |  | Version des Dienstes |
| `model` | string or null |  | – | Name der Route bzw. des Modells, die angefragt wurden |

### Hints (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `context` | string or null (max. length 2000) |  | – | Freitext zu Zweck und Kontext des Baums, etwa Zielgruppe oder Einsatz |
| `include` | list of string (max. 50 entries) |  |  | Begriffe, die im Baum vorkommen sollen |
| `exclude` | list of string (max. 50 entries) |  |  | Begriffe, die nicht vorkommen sollen |
| `order` | string or null (max. length 200) |  | – | Gewünschtes Ordnungsprinzip, etwa „chronologisch“ oder „nach Kompetenzen“ |
| `description_length` | integer (≥ 40, ≤ 200) |  | `60` | Ziellänge der Beschreibungen in Wörtern |
| `language` | string |  | `"de"` | Sprache der Titel und Beschreibungen als ISO-639-1-Code |

### InputCounts (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `folders` | integer |  | `0` | Anzahl der übergebenen Ordner |
| `items` | [`ItemCounts`](#itemcounts-response) |  |  | Anzahl der Einträge je Rolle |

### ItemCounts (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `structure` | integer |  | `0` | Anzahl der Einträge mit Rolle structure |
| `content` | integer |  | `0` | Anzahl der Einträge mit Rolle content |

### MainRange (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `min` | integer (≥ 1, ≤ 20) |  | `6` | Mindestzahl der Hauptthemen (Ebene 1) |
| `max` | integer (≥ 1, ≤ 20) |  | `12` | Höchstzahl der Hauptthemen (Ebene 1); begrenzt durch MAX_NODES_PER_LEVEL |

### Metadata (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `title` | string | yes |  | Titel des Baums |
| `description` | string |  | `""` | Beschreibung des Baums |
| `target_audience` | string |  | `"Lehrkräfte"` | Zielgruppe in Worten |
| `created_at` | string | yes |  | Zeitpunkt der Erzeugung (ISO 8601) |
| `author` | string |  | `"Themenbaum Generator"` | Erzeuger |
| `schema_version` | string |  | `"2.0"` | Version dieses Antwortformats |
| `version` | string | yes |  | Version des Baums (v1, v2, …); steigt mit jedem refine |
| `based_on` | string or null |  | – | Version, auf der dieser Baum aufbaut |
| `vocab_labels` | object (values: string) |  |  | Deutsche Bezeichnungen der verwendeten Vokabular-URIs |
| `generation` | [`Generation`](#generation-response) | yes |  | Wirksame Vorgaben dieses Laufs; für den nächsten refine als current_tree.generation zurückgeben |

### Mode (Response)

Values: `create`, `refine`

### NodeOut (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `key` | string | yes |  | Stabiler Schlüssel des Knotens; bleibt über refine-Läufe erhalten |
| `nodeId` | string or null |  | – | Knoten-ID der Sammlung im Repository, unverändert aus current_tree |
| `title` | string | yes |  | Titel des Knotens |
| `shorttitle` | string | yes |  | Kurztitel, höchstens 20 Zeichen |
| `status` | [`NodeStatus`](#nodestatus-response) | yes |  | Änderungsstand gegenüber current_tree: new, unchanged, changed, moved oder suggested |
| `origin` | [`Origin`](#origin-response) or null |  | – | Herkunft des Knotens |
| `confidence` | number or null (≥ 0, ≤ 1) |  | – | Konfidenz, falls der Knoten nur vorgeschlagen ist |
| `properties` | [`Properties`](#properties-response) |  |  | edu-sharing-Properties des Knotens, etwa cm:title, cclom:general_description, ccm:taxonid |
| `contents` | list of [`ContentRef`](#contentref-response) |  |  | Zugeordnete Inhalte |
| `subcollections` | list of [`NodeOut`](#nodeout-response) |  |  | Unterknoten |

### NodeStatus (Response)

Values: `new`, `unchanged`, `changed`, `moved`, `suggested`

### Options (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `improve` | boolean |  | `False` | Nur use_case folders: Umbenennen, Zusammenlegen und Umstellen der Ordner vorschlagen (auch nach einem Gliederungsdokument in items). Die Vorschläge sind im Baum umgesetzt und stehen als changes mit from service in der Antwort; ohne improve bleiben die Ordner wie gesendet. |
| `assign_contents` | boolean |  | `True` | Einträge mit Rolle content den Knoten zuordnen (mit Konfidenz). false: nur die Struktur erzeugen; gesendete Inhalte meldet INPUT_IGNORED. |
| `assign_only` | boolean |  | `False` | Nur mode refine: nur neue Inhalte in den current_tree einsortieren. Struktur, Titel, properties und nodeId jedes Knotens bleiben (auch bei einem Baum aus dem Repository); feedback wird nicht umgesetzt. Gilt nur für diesen Aufruf und wird nicht geerbt. |
| `multi_assign` | boolean |  | `True` | true: Ein Inhalt darf an mehreren passenden Knoten hängen. false: nur am besten passenden Knoten. |
| `min_confidence` | number (≥ 0, ≤ 1) |  | `0.6` | Mindestkonfidenz (0 bis 1) einer Zuordnung. Darunter kommt der Inhalt mit Grund low_confidence nach unassigned; höher heißt strenger, weniger Zuordnungen. |
| `auto_metadata` | boolean |  | `False` | Fach, Bildungsstufe und Zielgruppe je Knoten bestimmen und als Vokabular-URIs setzen; sinnvoll, wenn frame leer oder mehrwertig ist (z. B. fächerübergreifend). Nur dann kostet es zusätzliche Aufrufe des Sprachmodells. |

### Origin (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `type` | [`OriginType`](#origintype-response) | yes |  | Woher der Knoten stammt: topic, document, folder, cluster oder feedback |
| `id` | string or null |  | – | id des Eintrags in items, aus dem der Knoten stammt (document) |
| `section` | string or null |  | – | Abschnitt im Dokument (document) |
| `page` | integer or null |  | – | Seite im Dokument, falls Seitenmarken vorhanden sind (document) |
| `path` | string or null |  | – | Ordnerpfad (folders) |

### OriginType (Response)

Values: `topic`, `document`, `folder`, `cluster`, `feedback`

### Properties (Response)

Free keys; values: list of string.

### Question (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `text` | string | yes |  | Rückfrage zu einer unklaren Rückmeldung |
| `key` | string or null |  | – | Schlüssel des betroffenen Knotens |
| `options` | list of string or null |  | – | Antwortmöglichkeiten |

### ServiceWarning (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `code` | string | yes |  | Fester Code, etwa LLM_DEGRADED, DESCRIBE_FAILED oder SHAPE_SINGLE_CHILD |
| `message` | string | yes |  | Erklärung für Menschen |
| `key` | string or null |  | – | Schlüssel des betroffenen Knotens |
| `step` | string or null |  | – | Verarbeitungsschritt, in dem die Warnung entstand |

### Shape (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `depth` | integer (≥ 1, ≤ 4) |  | `3` | Anzahl der Ebenen, höchstens MAX_TREE_DEPTH; ohne shape nach Bildungsstufe und Eingabe |
| `main_topics` | [`MainRange`](#mainrange-response) |  |  | Spanne der Hauptthemen; eine einzelne Grenze übernimmt die andere aus dem Empfehlungsrahmen |
| `children` | [`ChildRange`](#childrange-response) |  |  | Spanne der Unterthemen je Knoten |
| `extra_topics` | list of [`ExtraTopic`](#extratopic-response) |  |  | Zusätzliche Hauptthemen: general (Allgemeines) und/oder methodology (Methodik und Didaktik) |

### StructureInfo (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `order` | string | yes |  | Ordnungsprinzip des Baums |
| `levels` | list of string |  |  | Bedeutung der Ebenen, von oben nach unten |
| `source` | `hint` \| `detected` \| `input` | yes |  | Herkunft der Ordnung: hint (aus hints.order), detected (erkannt) oder input (aus der Eingabe) |

### Unassigned (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `id` | string | yes |  | id des nicht zugeordneten Inhalts |
| `nodeId` | string or null |  | – | Knoten-ID im Repository, unverändert aus der Anfrage |
| `reason` | [`UnassignedReason`](#unassignedreason-response) | yes |  | Grund: off_topic, low_confidence, no_matching_node oder excluded |

### UnassignedReason (Response)

Values: `off_topic`, `low_confidence`, `no_matching_node`, `excluded`

### Usage (Response)

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `llm_calls` | integer |  | `0` | Anzahl der LLM-Aufrufe |
| `failed_calls` | integer |  | `0` | Davon fehlgeschlagen |
| `prompt_tokens` | integer |  | `0` | Eingabe-Tokens |
| `cached_tokens` | integer |  | `0` | Davon aus dem Prompt-Cache des Anbieters |
| `completion_tokens` | integer |  | `0` | Ausgabe-Tokens |
| `duration_ms` | integer |  | `0` | Dauer der Verarbeitung in Millisekunden |

### UseCase (Response)

Values: `topic`, `document`, `folders`, `contents`
