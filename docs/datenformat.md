# Datenformat von POST /v2/topic-tree

Automatisch erzeugt aus den Pydantic-Modellen (`uv run python -m scripts.export_schemas`); nicht von Hand ändern.
Muster für einzelne und kombinierte Use Cases und für Änderungen an Bäumen: [`api.md`](api.md) und
[`examples/`](examples/). Maschinenlesbar: [`schemas/`](schemas/).

Spalten: **Pflicht** = muss gesendet werden; **Standard** = Wert, wenn das Feld fehlt.

## Anfrage

### Anfrage: oberste Ebene

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode) | ja |  | create: neuer Baum; refine: current_tree mit feedback oder neuen items weiterentwickeln |
| `use_case` | [`UseCase`](#usecase) | ja |  | Quelle der Struktur: topic, document (Gliederung), folders oder contents |
| `topic` | Text oder null (min. Länge 1, max. Länge 2000) |  | – | Thema des Baums; Pflicht bei topic, sonst optional (Eingrenzung, Titel, Rahmen) |
| `folders` | Liste von [`FolderNode`](#foldernode) oder null |  | – | Bestehende Ordnerstruktur; Gerüst bei use_case folders, sonst ergänzende Quelle |
| `folders_use` | Liste von [`ItemUse`](#itemuse) oder null |  | – | Rolle der ganzen Ordnerstruktur, Werte wie bei use: ['structure'] prägt den Baum, ['content'] Ordnerzuordnung der Dateien wird übernommen bzw. dient als Hinweis, beide (Standard) oder [] keines. |
| `items` | Liste von [`Item`](#item) oder null |  | – | Materialien und Dokumente, je mit Rolle in use |
| `items_ref` | Text oder null (min. Länge 1, max. Länge 2083) |  | – | HTTPS-Adresse einer JSON-Liste von items; nur von Hosts in REF_ALLOWED_HOSTS |
| `current_tree` | [`CurrentTree`](#currenttree) oder null |  | – | Früheres Ergebnis (mode refine) |
| `feedback` | [`Feedback`](#feedback) oder null |  | – | Rückmeldung zum current_tree (mode refine) |
| `frame` | [`Frame`](#frame) | ja |  | Fachlicher Rahmen als SkoHub-URIs; übernommen in die Knoten-Metadaten |
| `shape` | [`Shape`](#shape) |  |  | Form des Baums: Tiefe und Breite |
| `hints` | [`Hints`](#hints) |  |  | Inhaltliche Hinweise |
| `options` | [`Options`](#options) |  |  | Schalter für Zuordnung, Verbesserung und Metadaten |

### Change

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `op` | [`ChangeOp`](#changeop) | ja |  | Art der Änderung: add, remove, rename, edit, move, merge oder split |
| `key` | Text oder null |  | – | Schlüssel des betroffenen Knotens (remove, rename, edit, move, split) |
| `keys` | Liste von Text oder null |  | – | Schlüssel der zusammenzuführenden Knoten, mindestens zwei (merge) |
| `parent` | Text oder null |  | – | add: Schlüssel oder Titel des Elternknotens; ohne Angabe Hauptebene |
| `to` | Text oder null |  | – | move: Schlüssel des neuen Elternknotens; ohne Angabe oder null Hauptebene |
| `title` | Text oder null (min. Länge 1, max. Länge 200) |  | – | Neuer Titel (add, rename, merge) |
| `properties` | [`Properties`](#properties) oder null |  | – | Zu setzende Properties (edit) |
| `hint` | Text oder null (max. Länge 1000) |  | – | Wie der Knoten aufgeteilt werden soll (split) |

### ChangeOp

Werte: `add`, `remove`, `rename`, `edit`, `move`, `merge`, `split`

### ChildRange

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `min` | Ganzzahl (≥ 2, ≤ 20) |  | `3` | Mindestzahl der Unterthemen je Knoten (nie genau eines) |
| `max` | Ganzzahl (≥ 2, ≤ 20) |  | `8` | Höchstzahl der Unterthemen je Knoten; begrenzt durch MAX_NODES_PER_LEVEL |

### ContentRefIn

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `id` | Text | ja |  | id des zugeordneten Inhalts |
| `nodeId` | Text oder null |  | – | Knoten-ID im Repository, unverändert durchgereicht |
| `confidence` | Zahl oder null (≥ 0, ≤ 1) |  | – | Konfidenz der Zuordnung zwischen 0 und 1 |

### CurrentTree

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `version` | Text oder null (max. Länge 50) |  | – | metadata.version der früheren Antwort (ohne Angabe: v1) |
| `title` | Text oder null (max. Länge 2000) |  | – | metadata.title der früheren Antwort |
| `description` | Text oder null (max. Länge 8000) |  | – | metadata.description der früheren Antwort |
| `collection` | Liste von [`TreeNodeIn`](#treenodein) | ja |  | collection der früheren Antwort, gern von Hand bearbeitet |
| `generation` | [`GenerationIn`](#generationin) oder null |  | – | metadata.generation der früheren Antwort; liefert Vorgaben für alles, was die Anfrage weglässt |

### ExtraTopic

Werte: `general`, `methodology`

### Feedback

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `text` | Text oder null (max. Länge 8000) |  | – | Rückmeldung als Freitext; das Sprachmodell setzt sie in Änderungen um oder stellt Rückfragen |
| `changes` | Liste von [`Change`](#change) (max. 200 Einträge) |  |  | Gezielte Änderungen; Struktur ohne Sprachmodell (außer split), neue Knoten danach beschrieben |
| `locked` | Liste von Text (max. 500 Einträge) |  |  | Schlüssel gesperrter Knoten; sie und ihr Ast bleiben unverändert |

### FeedbackEntry

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `version` | Text oder null |  | – | Version des Baums, auf die sich die Rückmeldung bezog |
| `text` | Text oder null |  | – | Text der Rückmeldung |

### FolderNode

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `title` | Text (min. Länge 1, max. Länge 200) | ja |  | Name des Ordners |
| `items` | Liste von Text |  |  | ids der Einträge aus items, die in diesem Ordner liegen |
| `subcollections` | Liste von [`FolderNode`](#foldernode) |  |  | Unterordner |

### Frame

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `discipline_uri` | Liste von Text (max. 20 Einträge) |  |  | Fächer als SkoHub-URIs (Vokabular discipline); prägen Inhalt und Knoten-Metadaten |
| `educational_context_uri` | Liste von Text (max. 20 Einträge) |  |  | Bildungsstufen als SkoHub-URIs (educationalContext); bestimmen den Rahmen für die Form |
| `intended_end_user_role_uri` | Liste von Text (max. 20 Einträge) |  |  | Zielgruppen als SkoHub-URIs (intendedEndUserRole), etwa Lehrkräfte oder Lernende |

### Fulltext

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `format` | [`FulltextFormat`](#fulltextformat) |  | `"markdown"` | Format von text bzw. des geladenen Verweises |
| `text` | Text oder null (max. Länge 2000000) |  | – | Volltext direkt in der Anfrage (genau eines von text und ref) |
| `ref` | Text oder null (min. Länge 1, max. Länge 2083) |  | – | HTTPS-Adresse des Volltexts; nur Hosts aus REF_ALLOWED_HOSTS |

### FulltextFormat

Werte: `markdown`, `text`

### GenerationIn

`metadata.generation` of an earlier answer: defaults for anything the new request leaves out.

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode) oder null |  | – | Modus des früheren Laufs |
| `use_case` | [`UseCase`](#usecase) oder null |  | – | Use Case des früheren Laufs |
| `topic` | Text oder null |  | – | Thema des früheren Laufs |
| `frame` | [`Frame`](#frame) oder null |  | – | Rahmen des früheren Laufs |
| `shape` | [`Shape`](#shape) oder null |  | – | Form des früheren Laufs |
| `hints` | [`Hints`](#hints) oder null |  | – | Hinweise des früheren Laufs |
| `options` | [`Options`](#options) oder null |  | – | Optionen des früheren Laufs (assign_only wird nie geerbt) |
| `structure` | Objekt oder null |  | – | Erkannte Ordnung des früheren Laufs |
| `feedback` | Liste von [`FeedbackEntry`](#feedbackentry) |  |  | Bisherige Rückmeldungen |

### Hints

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `context` | Text oder null (max. Länge 2000) |  | – | Freitext zu Zweck und Kontext des Baums, etwa Zielgruppe oder Einsatz |
| `include` | Liste von Text (max. 50 Einträge) |  |  | Begriffe, die im Baum vorkommen sollen |
| `exclude` | Liste von Text (max. 50 Einträge) |  |  | Begriffe, die nicht vorkommen sollen |
| `order` | Text oder null (max. Länge 200) |  | – | Gewünschtes Ordnungsprinzip, etwa „chronologisch“ oder „nach Kompetenzen“ |
| `description_length` | Ganzzahl (≥ 40, ≤ 200) |  | `60` | Ziellänge der Beschreibungen in Wörtern |
| `language` | Text |  | `"de"` | Sprache der Titel und Beschreibungen als ISO-639-1-Code |

### Item

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `id` | Text | ja |  | Eindeutige id des Eintrags in dieser Anfrage; erscheint in contents und unassigned |
| `nodeId` | Text oder null (max. Länge 200) |  | – | Knoten-ID im Repository; wird unverändert durchgereicht, der Dienst liest den Knoten nie |
| `use` | Liste von [`ItemUse`](#itemuse) oder null |  | – | Rolle des Eintrags: ['structure'] Gliederung, ['content'] Inhalt, beide, oder [] keines von beiden (wird angenommen, aber weder für die Struktur genutzt noch einsortiert). Fehlt use, gilt der Standard des Use Case. |
| `properties` | [`Properties`](#properties) |  |  | edu-sharing-Properties wie cm:title oder cclom:general_keyword, Werte als Listen |
| `fulltext` | [`Fulltext`](#fulltext) oder null |  | – | Volltext des Eintrags, etwa ein Lehrplan als Markdown |
| `path` | Text oder null (max. Länge 1000) |  | – | Ablageort des Eintrags (z. B. Optik/Linsen); Hinweis bei der Zuordnung |

### ItemUse

Werte: `structure`, `content`

### MainRange

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `min` | Ganzzahl (≥ 1, ≤ 20) |  | `6` | Mindestzahl der Hauptthemen (Ebene 1) |
| `max` | Ganzzahl (≥ 1, ≤ 20) |  | `12` | Höchstzahl der Hauptthemen (Ebene 1); begrenzt durch MAX_NODES_PER_LEVEL |

### Mode

Werte: `create`, `refine`

### Options

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `improve` | ja/nein |  | `False` | folders: Verbesserungen der Ordnerstruktur vorschlagen; sie kommen als changes zurück |
| `assign_contents` | ja/nein |  | `True` | Inhalte aus items den Knoten zuordnen |
| `assign_only` | ja/nein |  | `False` | refine: nur neue Inhalte einsortieren; Struktur und Knoten-Properties bleiben, gilt nur für diesen Aufruf |
| `multi_assign` | ja/nein |  | `True` | Ein Inhalt darf mehreren Knoten zugeordnet werden |
| `min_confidence` | Zahl (≥ 0, ≤ 1) |  | `0.6` | Mindestkonfidenz einer Zuordnung; darunter landet der Inhalt mit low_confidence in unassigned |
| `auto_metadata` | ja/nein |  | `False` | Fach, Bildungsstufe und Zielgruppe je Knoten verengen, wenn frame leer oder mehrwertig ist |

### Properties

Freie Schlüssel; Werte: Liste von Text.

### Shape

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `depth` | Ganzzahl (≥ 1, ≤ 4) |  | `3` | Anzahl der Ebenen, höchstens MAX_TREE_DEPTH; ohne shape nach Bildungsstufe und Eingabe |
| `main_topics` | [`MainRange`](#mainrange) |  |  | Spanne der Hauptthemen; eine einzelne Grenze übernimmt die andere aus dem Empfehlungsrahmen |
| `children` | [`ChildRange`](#childrange) |  |  | Spanne der Unterthemen je Knoten |
| `extra_topics` | Liste von [`ExtraTopic`](#extratopic) |  |  | Zusätzliche Hauptthemen: general (Allgemeines) und/oder methodology (Methodik und Didaktik) |

### TreeNodeIn

A node of an earlier answer (v2 or legacy format), possibly edited by hand.

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `key` | Text oder null (max. Länge 200) |  | – | Schlüssel des Knotens aus der früheren Antwort; fehlt er, vergibt der Dienst einen |
| `nodeId` | Text oder null (max. Länge 200) |  | – | Knoten-ID der Sammlung im Repository, unverändert durchgereicht |
| `title` | Text (min. Länge 1, max. Länge 200) | ja |  | Titel des Knotens |
| `shorttitle` | Text oder null (max. Länge 200) |  | – | Kurztitel (höchstens 20 Zeichen in der Antwort) |
| `properties` | [`Properties`](#properties) |  |  | edu-sharing-Properties des Knotens |
| `origin` | Objekt oder null |  | – | Herkunft des Knotens aus der früheren Antwort |
| `contents` | Liste von [`ContentRefIn`](#contentrefin) |  |  | Bereits zugeordnete Inhalte |
| `subcollections` | Liste von [`TreeNodeIn`](#treenodein) |  |  | Unterknoten |

### UseCase

Werte: `topic`, `document`, `folders`, `contents`

## Antwort

### Antwort: oberste Ebene

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `metadata` | [`Metadata`](#metadata-antwort) | ja |  | Angaben zum Baum und zum Lauf |
| `collection` | Liste von [`NodeOut`](#nodeout-antwort) | ja |  | Der Baum: Hauptthemen mit Unterknoten |
| `unassigned` | Liste von [`Unassigned`](#unassigned-antwort) |  |  | Inhalte, die keinem Knoten zugeordnet wurden, mit Grund |
| `changes` | Liste von [`ChangeRecord`](#changerecord-antwort) |  |  | Angewendete und vorgeschlagene Änderungen |
| `questions` | Liste von [`Question`](#question-antwort) |  |  | Rückfragen zu unklarer Rückmeldung; der Baum bleibt dafür unverändert |
| `warnings` | Liste von [`ServiceWarning`](#servicewarning-antwort) |  |  | Was nicht gelungen ist oder auffiel; ein Schritt ohne Ergebnis steht immer hier |

### ChangeOp (Antwort)

Werte: `add`, `remove`, `rename`, `edit`, `move`, `merge`, `split`

### ChangeRecord (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `op` | [`ChangeOp`](#changeop-antwort) | ja |  | Art der Änderung |
| `key` | Text oder null |  | – | Schlüssel des betroffenen oder neuen Knotens |
| `keys` | Liste von Text oder null |  | – | Schlüssel der zusammengeführten Knoten (merge) |
| `parent` | Text oder null |  | – | Schlüssel des Elternknotens eines neuen Knotens (add) |
| `to` | Text oder null |  | – | Schlüssel des neuen Elternknotens (move) |
| `title` | Text oder null |  | – | Neuer Titel |
| `from` | [`ChangeSource`](#changesource-antwort) | ja |  | Auslöser: feedback_text, feedback_changes oder service (Vorschlag des Dienstes) |

### ChangeSource (Antwort)

Werte: `feedback_text`, `feedback_changes`, `service`

### ChildRange (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `min` | Ganzzahl (≥ 2, ≤ 20) |  | `3` | Mindestzahl der Unterthemen je Knoten (nie genau eines) |
| `max` | Ganzzahl (≥ 2, ≤ 20) |  | `8` | Höchstzahl der Unterthemen je Knoten; begrenzt durch MAX_NODES_PER_LEVEL |

### ContentRef (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `id` | Text | ja |  | id des Inhalts aus der Anfrage |
| `nodeId` | Text oder null |  | – | Knoten-ID im Repository, unverändert aus der Anfrage |
| `confidence` | Zahl (≥ 0, ≤ 1) |  | `1.0` | Konfidenz der Zuordnung zwischen 0 und 1 (1 bei Übernahme aus folders) |

### ExtraTopic (Antwort)

Werte: `general`, `methodology`

### FeedbackEntry (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `version` | Text oder null |  | – | Version des Baums, auf die sich die Rückmeldung bezog |
| `text` | Text oder null |  | – | Text der Rückmeldung |

### Frame (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `discipline_uri` | Liste von Text (max. 20 Einträge) |  |  | Fächer als SkoHub-URIs (Vokabular discipline); prägen Inhalt und Knoten-Metadaten |
| `educational_context_uri` | Liste von Text (max. 20 Einträge) |  |  | Bildungsstufen als SkoHub-URIs (educationalContext); bestimmen den Rahmen für die Form |
| `intended_end_user_role_uri` | Liste von Text (max. 20 Einträge) |  |  | Zielgruppen als SkoHub-URIs (intendedEndUserRole), etwa Lehrkräfte oder Lernende |

### Generation (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `mode` | [`Mode`](#mode-antwort) | ja |  | Modus dieses Laufs |
| `use_case` | [`UseCase`](#usecase-antwort) | ja |  | Use Case dieses Laufs |
| `topic` | Text oder null |  | – | Thema dieses Laufs |
| `frame` | [`Frame`](#frame-antwort) | ja |  | Wirksamer Rahmen |
| `shape` | [`Shape`](#shape-antwort) | ja |  | Wirksame Form |
| `hints` | [`Hints`](#hints-antwort) | ja |  | Wirksame Hinweise |
| `options` | [`Options`](#options-antwort) | ja |  | Wirksame Optionen |
| `inputs` | [`InputCounts`](#inputcounts-antwort) |  |  | Anzahl der Eingaben |
| `feedback` | Liste von [`FeedbackEntry`](#feedbackentry-antwort) |  |  | Alle bisherigen Rückmeldungen |
| `structure` | [`StructureInfo`](#structureinfo-antwort) oder null |  | – | Erkannte oder vorgegebene Ordnung |
| `usage` | [`Usage`](#usage-antwort) oder null |  | – | Verbrauch dieses Laufs |
| `generator_version` | Text | ja |  | Version des Dienstes |
| `model` | Text oder null |  | – | Name der Route bzw. des Modells, die angefragt wurden |

### Hints (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `context` | Text oder null (max. Länge 2000) |  | – | Freitext zu Zweck und Kontext des Baums, etwa Zielgruppe oder Einsatz |
| `include` | Liste von Text (max. 50 Einträge) |  |  | Begriffe, die im Baum vorkommen sollen |
| `exclude` | Liste von Text (max. 50 Einträge) |  |  | Begriffe, die nicht vorkommen sollen |
| `order` | Text oder null (max. Länge 200) |  | – | Gewünschtes Ordnungsprinzip, etwa „chronologisch“ oder „nach Kompetenzen“ |
| `description_length` | Ganzzahl (≥ 40, ≤ 200) |  | `60` | Ziellänge der Beschreibungen in Wörtern |
| `language` | Text |  | `"de"` | Sprache der Titel und Beschreibungen als ISO-639-1-Code |

### InputCounts (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `folders` | Ganzzahl |  | `0` | Anzahl der übergebenen Ordner |
| `items` | [`ItemCounts`](#itemcounts-antwort) |  |  | Anzahl der Einträge je Rolle |

### ItemCounts (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `structure` | Ganzzahl |  | `0` | Anzahl der Einträge mit Rolle structure |
| `content` | Ganzzahl |  | `0` | Anzahl der Einträge mit Rolle content |

### MainRange (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `min` | Ganzzahl (≥ 1, ≤ 20) |  | `6` | Mindestzahl der Hauptthemen (Ebene 1) |
| `max` | Ganzzahl (≥ 1, ≤ 20) |  | `12` | Höchstzahl der Hauptthemen (Ebene 1); begrenzt durch MAX_NODES_PER_LEVEL |

### Metadata (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `title` | Text | ja |  | Titel des Baums |
| `description` | Text |  | `""` | Beschreibung des Baums |
| `target_audience` | Text |  | `"Lehrkräfte"` | Zielgruppe in Worten |
| `created_at` | Text | ja |  | Zeitpunkt der Erzeugung (ISO 8601) |
| `author` | Text |  | `"Themenbaum Generator"` | Erzeuger |
| `schema_version` | Text |  | `"2.0"` | Version dieses Antwortformats |
| `version` | Text | ja |  | Version des Baums (v1, v2, …); steigt mit jedem refine |
| `based_on` | Text oder null |  | – | Version, auf der dieser Baum aufbaut |
| `vocab_labels` | Objekt (Werte: Text) |  |  | Deutsche Bezeichnungen der verwendeten Vokabular-URIs |
| `generation` | [`Generation`](#generation-antwort) | ja |  | Wirksame Vorgaben dieses Laufs; für den nächsten refine als current_tree.generation zurückgeben |

### Mode (Antwort)

Werte: `create`, `refine`

### NodeOut (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `key` | Text | ja |  | Stabiler Schlüssel des Knotens; bleibt über refine-Läufe erhalten |
| `nodeId` | Text oder null |  | – | Knoten-ID der Sammlung im Repository, unverändert aus current_tree |
| `title` | Text | ja |  | Titel des Knotens |
| `shorttitle` | Text | ja |  | Kurztitel, höchstens 20 Zeichen |
| `status` | [`NodeStatus`](#nodestatus-antwort) | ja |  | Änderungsstand gegenüber current_tree: new, unchanged, changed, moved oder suggested |
| `origin` | [`Origin`](#origin-antwort) oder null |  | – | Herkunft des Knotens |
| `confidence` | Zahl oder null (≥ 0, ≤ 1) |  | – | Konfidenz, falls der Knoten nur vorgeschlagen ist |
| `properties` | [`Properties`](#properties-antwort) |  |  | edu-sharing-Properties des Knotens, etwa cm:title, cclom:general_description, ccm:taxonid |
| `contents` | Liste von [`ContentRef`](#contentref-antwort) |  |  | Zugeordnete Inhalte |
| `subcollections` | Liste von [`NodeOut`](#nodeout-antwort) |  |  | Unterknoten |

### NodeStatus (Antwort)

Werte: `new`, `unchanged`, `changed`, `moved`, `suggested`

### Options (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `improve` | ja/nein |  | `False` | folders: Verbesserungen der Ordnerstruktur vorschlagen; sie kommen als changes zurück |
| `assign_contents` | ja/nein |  | `True` | Inhalte aus items den Knoten zuordnen |
| `assign_only` | ja/nein |  | `False` | refine: nur neue Inhalte einsortieren; Struktur und Knoten-Properties bleiben, gilt nur für diesen Aufruf |
| `multi_assign` | ja/nein |  | `True` | Ein Inhalt darf mehreren Knoten zugeordnet werden |
| `min_confidence` | Zahl (≥ 0, ≤ 1) |  | `0.6` | Mindestkonfidenz einer Zuordnung; darunter landet der Inhalt mit low_confidence in unassigned |
| `auto_metadata` | ja/nein |  | `False` | Fach, Bildungsstufe und Zielgruppe je Knoten verengen, wenn frame leer oder mehrwertig ist |

### Origin (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `type` | [`OriginType`](#origintype-antwort) | ja |  | Woher der Knoten stammt: topic, document, folder, cluster oder feedback |
| `id` | Text oder null |  | – | id des Eintrags in items, aus dem der Knoten stammt (document) |
| `section` | Text oder null |  | – | Abschnitt im Dokument (document) |
| `page` | Ganzzahl oder null |  | – | Seite im Dokument, falls Seitenmarken vorhanden sind (document) |
| `path` | Text oder null |  | – | Ordnerpfad (folders) |

### OriginType (Antwort)

Werte: `topic`, `document`, `folder`, `cluster`, `feedback`

### Properties (Antwort)

Freie Schlüssel; Werte: Liste von Text.

### Question (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `text` | Text | ja |  | Rückfrage zu einer unklaren Rückmeldung |
| `key` | Text oder null |  | – | Schlüssel des betroffenen Knotens |
| `options` | Liste von Text oder null |  | – | Antwortmöglichkeiten |

### ServiceWarning (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `code` | Text | ja |  | Fester Code, etwa LLM_DEGRADED, DESCRIBE_FAILED oder SHAPE_SINGLE_CHILD |
| `message` | Text | ja |  | Erklärung für Menschen |
| `key` | Text oder null |  | – | Schlüssel des betroffenen Knotens |
| `step` | Text oder null |  | – | Verarbeitungsschritt, in dem die Warnung entstand |

### Shape (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `depth` | Ganzzahl (≥ 1, ≤ 4) |  | `3` | Anzahl der Ebenen, höchstens MAX_TREE_DEPTH; ohne shape nach Bildungsstufe und Eingabe |
| `main_topics` | [`MainRange`](#mainrange-antwort) |  |  | Spanne der Hauptthemen; eine einzelne Grenze übernimmt die andere aus dem Empfehlungsrahmen |
| `children` | [`ChildRange`](#childrange-antwort) |  |  | Spanne der Unterthemen je Knoten |
| `extra_topics` | Liste von [`ExtraTopic`](#extratopic-antwort) |  |  | Zusätzliche Hauptthemen: general (Allgemeines) und/oder methodology (Methodik und Didaktik) |

### StructureInfo (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `order` | Text | ja |  | Ordnungsprinzip des Baums |
| `levels` | Liste von Text |  |  | Bedeutung der Ebenen, von oben nach unten |
| `source` | `hint` \| `detected` \| `input` | ja |  | Herkunft der Ordnung: hint (aus hints.order), detected (erkannt) oder input (aus der Eingabe) |

### Unassigned (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `id` | Text | ja |  | id des nicht zugeordneten Inhalts |
| `nodeId` | Text oder null |  | – | Knoten-ID im Repository, unverändert aus der Anfrage |
| `reason` | [`UnassignedReason`](#unassignedreason-antwort) | ja |  | Grund: off_topic, low_confidence, no_matching_node oder excluded |

### UnassignedReason (Antwort)

Werte: `off_topic`, `low_confidence`, `no_matching_node`, `excluded`

### Usage (Antwort)

| Feld | Typ | Pflicht | Standard | Bedeutung |
|---|---|---|---|---|
| `llm_calls` | Ganzzahl |  | `0` | Anzahl der LLM-Aufrufe |
| `failed_calls` | Ganzzahl |  | `0` | Davon fehlgeschlagen |
| `prompt_tokens` | Ganzzahl |  | `0` | Eingabe-Tokens |
| `cached_tokens` | Ganzzahl |  | `0` | Davon aus dem Prompt-Cache des Anbieters |
| `completion_tokens` | Ganzzahl |  | `0` | Ausgabe-Tokens |
| `duration_ms` | Ganzzahl |  | `0` | Dauer der Verarbeitung in Millisekunden |

### UseCase (Antwort)

Werte: `topic`, `document`, `folders`, `contents`
