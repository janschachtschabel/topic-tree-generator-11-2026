# Aufrufe von POST /v2/topic-tree

Vollständige Beispiele liegen unter `docs/examples/` (Anfragen) und `docs/examples/responses/` (Antwort), jedes Feld
von Anfrage und Antwort mit Typ, Standard und Bedeutung in [`datenformat.md`](datenformat.md), maschinenlesbar unter
`docs/schemas/`. Zum interaktiven Ausprobieren im Browser steht optional die
eingebaute Test-Oberfläche unter `/ui/` bereit (steuerbar über `UI_ENABLED=true|false`). Laufzeit synchron, typisch
5 bis 45 Sekunden (große 3-Ebenen-Bäume ~25–45 s).

## Anmeldung

- Über die b-api: Der Proxy reicht das Delegations-Token (`Authorization: Bearer bdt_…`) durch; nichts weiter zu tun.
- Eigenständig: ohne Anmeldung, oder mit `Authorization: Bearer <Dienst-Schlüssel>`, wenn `SERVICE_API_KEYS` gesetzt ist.

## Kürzester Aufruf

```json
{"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}}
```

Wird `shape` weggelassen, wählt der Dienst Tiefe und Breite passend zum Aufruf:
- **Reine Themenvorgabe (`use_case: "topic"` ohne Struktur-Items):** Empfehlungsrahmen je Zielgruppe (`5–15` Hauptknoten und max. `3` Ebenen für Schule/Berufsbildung/Hochschule; `5–10` bzw. `5–12` und max. `2` Ebenen für Elementarbereich bzw. Fortbildung/Organisationen). Gesetzte `extra_topics` (`general`, `methodology`) zählen regulär zur Gesamtzahl auf Ebene 1.
- **Strukturgetriebene Eingaben (`document`, `contents`, `folders` sowie `topic` mit `"structure"`-Items):** Breite richtet sich nach dem Input bis `MAX_NODES_PER_LEVEL` (Standard `20`, z. B. Lehrplan mit 20 Themenfeldern), Tiefe bleibt auf `MAX_TREE_DEPTH` (Standard `3`) begrenzt.
Eine Spanne mit nur einer Grenze (z. B. `"main_topics": {"max": 4}`) übernimmt die andere aus diesem Rahmen (bzw. aus
`generation` bei `refine`) und passt sie so an, dass die gesendete Grenze gilt.
Serverseitige Obergrenzen (`MAX_TREE_DEPTH`, `MAX_NODES_PER_LEVEL`) können per Anfrage nicht überschritten werden (`422 SHAPE_LIMIT_EXCEEDED`).

## Je Use Case

| Datei | Use Case | Was passiert |
|---|---|---|
| `topic_minimal.json`, `topic_full.json` | topic | Vollständiges Titel-Grundgerüst in einem Aufruf, deterministische Duplikatbereinigung, dann parallele Beschreibungs-Batches (je 10 Knoten mit Gesamtstruktur im Cache-Präfix) |
| `document.json` | document | Gliederung aus den Überschriften, Abschnitt und Seite je Knoten |
| `folders.json` | folders | Ordner bleiben; mit `options.improve` Vorschläge, die als `changes` zurückkommen |
| `contents.json` | contents | Gruppen aus den Inhalten (inkl. Duplikatbereinigung), Zuordnung mit Konfidenz |
| `refine_feedback.json` | refine | Rückmeldung als Text; `locked` schützt Äste |
| `assign_only.json` | refine + `assign_only` | Inhalte in einen bestehenden Baum aus dem Repository einsortieren (`nodeId`, ohne Schlüssel); Knoten bleiben unverändert |
| `describe.json` | refine + `describe` | Beschreibung eines Knotens mit Baum-Kontext und Vorgabe neu schreiben |
| `refine_changes.json` | refine | Sieben gezielte Änderungen (alle außer `describe`), dazu Freitext, gesperrter Ast und ein neuer Inhalt |
| `topic_with_items.json` | topic | Thema und zwei Inhalte; die Antwort dazu: `responses/topic_with_items.json` |
| `combo_topic_folders.json` | topic + Ordner | Ordnerstruktur regt an (`folders_use`), Ordnerpfade und `path` helfen beim Einsortieren |
| `combo_document_topic_contents.json` | document + Thema + Inhalte | Lehrplan als Gerüst, `topic` grenzt ein, Themenliste ohne Text ergänzt, Inhalte werden einsortiert |
| `contents_with_curriculum.json` | contents + Lehrplan | Gruppen aus Inhalten, der Lehrplan-Volltext fließt ein, ein Inhalt wird nur einsortiert |

## Use Cases kombinieren (z. B. Themenvorgabe + Inhalte)

**Grundregel:** `use_case` legt fest, welche Quelle das Gerüst des Baums bildet. Die Rollen (`use` je Eintrag in
`items`, `folders_use` für die ganze Ordnerstruktur) legen fest, wie alle übrigen Quellen einfließen. Alles, was
gesendet und nicht genutzt wird, meldet `INPUT_IGNORED`.

### Für Aufrufer wie einen Chatbot: markierte Elemente → Anfrage

Der Nutzer markiert je Element „Gliederungsdokument“, „Inhalt“, beides oder keins und gibt ggf. eine Ordnerstruktur
an. Den `use_case` wählt der Aufrufer in dieser Reihenfolge; die erste passende Zeile gilt:

| # | Vorliegende Elemente | `use_case` | Weitere Felder |
|---|---|---|---|
| 1 | Ordnerstruktur, die erhalten bleiben soll | `folders` | `options.improve: true`, wenn Gliederungsdokumente oder das Thema sie verbessern sollen; sonst bleibt sie unverändert |
| 2 | Gliederungsdokument mit Text (z. B. Lehrplan) | `document` | `topic` grenzt auf einen Ausschnitt ein; Ordner und Dokumente ohne Text fließen ergänzend ein |
| 3 | Nur Inhalte (ohne Thema als Gerüst) | `contents` | `topic` grenzt ein, fachfremde Inhalte kommen nach `unassigned` |
| 4 | Thema | `topic` | Gliederungsdokumente und Ordner regen nur an (bis 50 Einträge, 5 Volltext-Auszüge à 1.500 Zeichen) |
| – | Ein bestehender Baum soll nur befüllt werden (Struktur bleibt) | `mode: refine` + `current_tree` | `options.assign_only: true`, Inhalte in `items`; `use_case: topic` genügt |
| – | Ein bestehender Baum soll geändert werden | `mode: refine` + `current_tree` | Änderungswunsch als `feedback`; neue Inhalte in `items` |
| – | Eine Sammlung soll (neu) beschrieben werden | `mode: refine` + `current_tree` | `feedback.changes: [{"op": "describe", "key": …, "hint": …}]`; eine einzelne Sammlung als Baum mit einem Knoten |

Rollen übertragen: Gliederungsdokument → `"use": ["structure"]`, Inhalt → `["content"]`, beides →
`["structure", "content"]`, keins → `[]`. Für die Ordnerstruktur dasselbe in `folders_use` (Standard: beides).

| Rolle der Ordnerstruktur (`folders_use`) | bei `use_case: folders` | bei `topic`, `document`, `contents` |
|---|---|---|
| fehlt oder `["structure", "content"]` | Ordner sind das Gerüst, ihre Zuordnungen bleiben (`confidence: 1.0`) | Ordnerbaum regt die Gliederung an; der Ordnerpfad jeder Datei hilft bei der Zuordnung |
| `["structure"]` | Ordner sind das Gerüst, alle Dateien werden neu einsortiert | Ordnerbaum regt die Gliederung an; Dateien ohne Ordnerhinweis |
| `["content"]` | `422 INVALID_INPUT` (Ordner sind hier das Gerüst) | nur der Ordnerpfad hilft bei der Zuordnung |
| `[]` | `422 INVALID_INPUT` | angenommen, nicht genutzt (`INPUT_IGNORED`) |

Ein `path` an einem Eintrag (z. B. `"Optik/Linsen"`) wirkt wie ein Ordnerpfad: als Hinweis bei der Zuordnung.

Grenzen, die gemeldet werden (`INPUT_IGNORED`): Bei `mode: refine` prägen neue Gliederungsdokumente und Ordner den
Baum nicht (Änderungswunsch als `feedback` formulieren); bei `options.assign_contents: false` werden Inhalte nicht
einsortiert; `shape.extra_topics` gilt nur bei `use_case: topic`.

### Beispiele

Strukturerzeugung und Inhaltszuordnung sind entkoppelt und lassen sich über das Feld `"use"` je Eintrag in `items` frei kombinieren:

- **`use_case: "topic"` + `items` ohne `use` (oder `"use": ["content"]`)**: Baut den Baum systematisch aus `topic` und sortiert alle `items` anschließend mit Konfidenz ein.
- **`use_case: "topic"` + `items` mit `"use": ["structure", "content"]`**: Übergibt bis zu 50 Materialien (Titel, Schlagworte, Kurzbeschreibung sowie bis zu 5 Volltext-Auszüge; darüber `INPUTS_TRUNCATED`) als ergänzende Anregung an `plan_structure` (zusätzliche Hauptthemen erhalten `status: "suggested"`) und sortiert alle Inhalte in den Baum ein.
- **`use_case: "contents"` + `topic` + `items`**: Bildet Cluster primär aus den Materialien im Rahmen von `topic` (fachfremde Einträge landen mit `off_topic` in `unassigned`; reine `"use": ["content"]`-Einträge werden nur zugeordnet, ohne die Gruppenbildung zu verzerren). Volltexte von Einträgen mit `"structure"` (z. B. ein Lehrplan) fließen als Auszug in die Gruppenbildung ein; Gruppen mit nur einer Untergruppe werden aufgelöst.
- **`use_case: "document"` + optional `topic` + Strukturdokument(e) (`"structure"`) + Materialien (`"content"`)**: Leitet den Baum aus der Dokumentgliederung ab (`origin.document`; mehrere Dokumente werden zu einer Gliederung zusammengeführt) und ordnet die Materialien den Abschnitten zu. Einträge mit `"structure"` ohne Volltext (z. B. eine Themenliste) ergänzen die Gliederung.
- **`use_case: "topic"`, `"document"` oder `"contents"` + `folders`**: Die Ordnerstruktur fließt nach `folders_use` ein (siehe oben).
- **`use_case: "folders"` + `folders` + lose Zusatz-`items` (+ optionales Strukturdokument bei `options.improve: true`)**: Übernimmt bestehende Ordnerzuordnungen (`confidence: 1.0`), verbessert auf Wunsch die Ordnerstruktur und sortiert lose Materialien nach.
- **`mode: "refine"` + `feedback` + neue `items`**: Setzt Strukturänderungen unter Schutz von `locked` um, beschreibt neue/umbenannte Knoten und sortiert neue Materialien im selben Aufruf in den aktualisierten Baum ein.

## Rollen je Eintrag (`use`)

Jeder Eintrag in `items` trägt eine von vier Rollen, unabhängig vom Use Case und zusätzlich zu `folders`:

| `use` | Rolle | Wirkung |
|---|---|---|
| `["structure"]` | Gliederung (z. B. Lehrplan) | prägt die Struktur, wird nicht einsortiert |
| `["content"]` | Inhalt | wird einsortiert, prägt die Struktur nicht |
| `["structure", "content"]` | beides | prägt die Struktur und wird selbst einsortiert |
| `[]` | keines von beiden | wird angenommen, aber weder genutzt noch einsortiert (auch nicht in einem Ordner aus `folders`) |

Fehlt `use`, gilt der Standard des Use Case: `["structure", "content"]` bei `contents`, sonst `["content"]`. Ein
Strukturdokument mit Volltext darf zugleich Inhalt sein (`["structure", "content"]`): Es liefert die Gliederung und
wird anschließend selbst einem Knoten zugeordnet. Einträge mit `[]` erscheinen nicht in `unassigned`.

## Automatische Knoten-Metadaten (`options.auto_metadata`)

Ist `options.auto_metadata: true` gesetzt und ein Feld im `frame` leer oder mehrwertig (z. B. fächerübergreifendes
Thema), verengt der Dienst `ccm:taxonid`, `ccm:educationalcontext` und `ccm:educationalintendedenduserrole` je Knoten
zunächst deterministisch aus zugeordneten Inhalten und klassifiziert verbleibende Knoten über exakte deutsche
Vokabular-Bezeichnungen, die deterministisch auf kanonische SkoHub-URIs abgebildet werden.

## Nächster Durchlauf

`collection` als `current_tree.collection`, `metadata.generation` als `current_tree.generation`, `metadata.version`
als `current_tree.version` sowie (optional) `metadata.title`/`metadata.description` als `current_tree.title`/
`current_tree.description` zurückgeben und nur das neue `feedback` ergänzen. Fehlende Vorgaben übernimmt der Dienst
aus `generation` (außer `options.assign_only`, das nur für den einen Aufruf gilt). Das gilt Feld für Feld: Wer nur
`options: {"assign_only": true}` oder `hints: {"context": …}` schickt, behält alle übrigen Optionen und Hinweise aus
`generation`. Ein `current_tree` ohne `version` zählt als `v1`. Bei `mode: create` wird ein mitgeschickter
`current_tree` ignoriert (Warnung `INPUT_IGNORED`).

Ein geänderter `frame` ersetzt die alten Frame-Werte an bestehenden Knoten; gezielt eingegrenzte Knoten und gesperrte
Äste (`locked`) behalten ihre Werte.

Neue `items` beim Weiterentwickeln brauchen eigene ids: Eine id, die im Baum schon einsortiert ist, gilt als dasselbe
Material und bleibt an ihrem Platz (Warnung `ITEM_ALREADY_PLACED`); trägt sie eine andere `nodeId` als im Baum,
antwortet der Dienst mit `422 ID_CONFLICT`.

Legt eine Text-Rückmeldung einen neuen Knoten neben tieferen Ästen an, ergänzt der Dienst dessen Unterthemen bis zur
Tiefe der Nachbaräste (Warnung `EXPAND_FAILED` oder `EXPAND_INCOMPLETE`, falls das nicht gelingt). Strukturierte `add`-Änderungen legen genau
den einen Knoten an.

Änderungsoperationen in `feedback.changes`: `move` ohne `to` (oder mit `to: null`) verschiebt einen Knoten auf die
Hauptebene. `remove`, `split` und das Einschmelzen eines Knotens per `merge` (alle außer dem ersten Schlüssel) werden
abgelehnt (`CHANGE_REJECTED`), wenn darunter ein gesperrter Knoten liegt; ebenso ein `split`, dessen Knoten eine
frühere Änderung derselben Anfrage schon entfernt oder aufgeteilt hat. Scheitert das Aufteilen am Sprachmodell, kommt
`SPLIT_FAILED` und der Rest der Rückmeldung wird trotzdem umgesetzt. Schlüssel entfernter Knoten werden in derselben
Anfrage nicht neu vergeben.

In der Test-UI (`/ui/`) heißt das „Baum ändern“: Basis aus einem Beispiel, dem letzten Ergebnis oder JSON, alle acht
Operationen (`add`, `remove`, `rename`, `edit`, `describe`, `move`, `merge`, `split`) als Zeilen mit Knotenauswahl, dazu Freitext,
gesperrte Äste und neue Materialien. Kombinationen der Use Cases (z. B. Thema + Materialien) laufen dort über
„Zusätzlich einbeziehen“.

## Änderungen an einem Baum einreichen (`mode: refine`)

1. Das letzte Ergebnis zurückgeben: `collection` → `current_tree.collection`, `metadata.version` →
   `current_tree.version`, `metadata.generation` → `current_tree.generation` (siehe „Nächster Durchlauf“).
2. Den Wunsch in `feedback` beschreiben, frei oder gezielt (beides geht in einer Anfrage):
   - `feedback.text`: Freitext, z. B. „Farben als eigenes Hauptthema“. Das Sprachmodell setzt ihn in Änderungen um;
     was daran unklar ist, kommt als `questions` zurück und wird nicht umgesetzt (der Rest schon).
   - `feedback.changes`: gezielte Änderungen, ohne Sprachmodell umgesetzt (außer `split`).
   - `feedback.locked`: Schlüssel von Knoten, die mit ihrem Ast unverändert bleiben.
3. Neue Inhalte zum Einsortieren als `items` mitschicken (eigene ids).

| `op` | Pflichtfelder | Wirkung |
|---|---|---|
| `add` | `title` | Neuer Knoten unter `parent` (Schlüssel oder Titel); ohne `parent` auf der Hauptebene |
| `remove` | `key` | Knoten samt Ast entfernen; seine Inhalte stehen danach in `unassigned` (`no_matching_node`), sofern sie nicht noch an einem anderen Knoten hängen |
| `rename` | `key`, `title` | Titel ändern; Kurztitel und Beschreibung werden neu geschrieben |
| `edit` | `key`, `properties` | Properties setzen, z. B. `cclom:general_keyword` oder `ccm:taxonid` |
| `move` | `key` | Unter `to` verschieben; ohne `to` oder mit `null` auf die Hauptebene |
| `merge` | `keys` (mind. 2), `title` | Knoten zusammenführen; der erste Schlüssel bleibt |
| `split` | `key`, `hint` | Knoten nach dem Hinweis in mehrere aufteilen (Sprachmodell) |
| `describe` | `key` | Beschreibung und Schlagworte mit Baum-Kontext neu schreiben; `hint` (optional, bis 1.000 Zeichen) ist Grundlage oder Wunsch (Sprachmodell) |

```json
{
  "mode": "refine",
  "use_case": "topic",
  "current_tree": {"version": "v1", "collection": [{"key": "k-optik", "title": "Optik", "subcollections": []}]},
  "feedback": {
    "changes": [
      {"op": "add", "title": "Farben"},
      {"op": "rename", "key": "k-optik", "title": "Geometrische Optik"}
    ],
    "text": "Beschreibungen alltagsnäher formulieren",
    "locked": []
  },
  "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}
}
```

Sieben Operationen zusammen: `docs/examples/refine_changes.json`; `describe` allein: `docs/examples/describe.json`. In der Antwort steht jede umgesetzte Änderung
in `changes` (mit `from`: `feedback_changes`, `feedback_text` oder `service`), jeder Knoten trägt `status` (`new`,
`changed`, `moved`, `unchanged`, `suggested`), die Version zählt hoch (`v1` → `v2`, `metadata.based_on` nennt die Vorversion).
Abgelehnte Änderungen melden `CHANGE_REJECTED`.

## Inhalte in einen bestehenden Baum einsortieren (`options.assign_only`)

Für einen Baum, der schon existiert (z. B. Sammlungen aus edu-sharing), und neue Inhalte, die nur hineinsollen:

- `mode: refine`, den Baum als `current_tree.collection`, die Inhalte als `items` (Rolle `["content"]`),
  `options.assign_only: true`. `use_case` spielt keine Rolle (`topic` genügt), `generation` und `version` sind optional.
- Je Knoten reichen `title` und `subcollections`; fehlende `key` vergibt der Dienst. Eine `nodeId` am Knoten kommt
  unverändert zurück, so lässt sich jede Zuordnung der Sammlung zuordnen. (Bei späteren Strukturänderungen gilt: `merge`
behält die `nodeId` des ersten Knotens, Teile aus `split` und neue Knoten haben keine; welche Sammlungen wegfallen,
zeigen die Schlüssel in `changes`.)
- Unverändert bleiben Struktur, Titel und `properties` jedes Knotens (auch bei geändertem `frame`; der Rahmen hilft
  nur bei der Zuordnung). Es entstehen keine Beschreibungen und keine Formprüfungen. Nur `shorttitle` folgt der
  Antwortregel (höchstens 20 Zeichen, unter Geschwistern eindeutig); `properties` behalten den gesendeten Kurztitel.
- `metadata.generation.frame` behält den Rahmen, mit dem der Baum entstand (er wurde ja nicht übernommen).
- `feedback` wird nicht umgesetzt (`FEEDBACK_IGNORED`), ein gesendetes `options.auto_metadata` nicht ausgeführt
  (`INPUT_IGNORED`). Nicht passende Inhalte stehen in `unassigned`.

In der Test-UI ist das die Aufgabe „Inhalte einsortieren“.

## Knoten beschreiben (`describe`, Nachfolger von `/generate-collection-description`)

`{"op": "describe", "key": "k-linsen", "hint": "Für Klasse 8, mit Alltagsbeispielen"}` in `feedback.changes`
schreibt Beschreibung und Schlagworte des Knotens neu. Anders als der alte Endpunkt kennt das Sprachmodell Pfad,
Geschwister und den ganzen Baum und grenzt den Text davon ab; die Länge folgt `hints.description_length` (Wörter).
`hint` nimmt den Freitext auf, den der alte Endpunkt als `text_context` bekam (einzeilig, bis 1.000 Zeichen).
Gesperrte Knoten und Knoten, die eine spätere Änderung derselben Anfrage entfernt, einschmilzt oder aufteilt, werden
abgelehnt (`CHANGE_REJECTED`); lässt das Sprachmodell den Knoten aus, kommt `DESCRIBE_FAILED`. Wie bei jedem `refine`
mit Rückmeldung werden Knoten ganz ohne Beschreibung im selben Lauf mitbeschrieben (bei einem großen Baum ohne Texte
ein Aufruf je 10 Knoten), der `frame` an Knoten ohne eigene Werte gesetzt und Schlagworte bereinigt. Der alte Endpunkt bleibt für
bestehende Aufrufer unverändert.

## Seitenmarken im Markdown (use_case document)

Erkannt werden `<!-- page: N -->`, `<!-- PageNumber="N" -->` (setzen die Seite) sowie `<!-- page_break -->`,
`<!-- PageBreak -->` und Seitenvorschub (zählen ab Seite 1 hoch). Ohne Marken bleibt `origin.page` leer.

## Antwort lesen

Beispiel: `docs/examples/responses/topic_with_items.json`; alle Felder: [`datenformat.md`](datenformat.md#antwort).

- `metadata`: Titel, Beschreibung, Version (`v1`, `v2`, …), Bezeichnungen der Vokabular-URIs und `generation`
  (alle Einstellungen des Laufs, für den nächsten Durchlauf zurückgeben).
- `collection[]`: der Baum. Je Knoten `key` (stabil über refine-Läufe), `title`, `shorttitle`, `status`, `origin`
  (Herkunft: `topic`, `document` mit Abschnitt und Seite, `folder`, `cluster`, `feedback`), `properties` (edu-sharing:
  `cm:title`, `cm:description`, `cclom:general_keyword`, `ccm:taxonid`, …), `contents[]` (`id`, `nodeId`,
  `confidence`) und `subcollections[]`.
- `unassigned[]`: nicht einsortierte Inhalte mit Grund (`off_topic`, `low_confidence`, `no_matching_node`,
  `excluded`).
- `changes[]`: umgesetzte (refine) oder vorgeschlagene (`folders` mit `improve`) Änderungen.
- `warnings[]`: `{code, message, key?, step?}` – was nicht gelungen ist oder auffiel (z. B. `LLM_DEGRADED`,
  `DESCRIBE_FAILED`, `DESCRIBE_UNKNOWN_KEY`, `METADATA_LABEL_UNKNOWN`, `METADATA_FAILED`, `INPUTS_TRUNCATED`,
  `OUTLINE_FALLBACK`, `DEADLINE_EXCEEDED`, `SHAPE_SINGLE_CHILD`, `SHAPE_UNBALANCED`, `DUPLICATE_TITLE`, `GENERIC_TITLE`,
  `FACET_AS_NODE`, `TOPIC_REPEAT`, `CHANGE_REJECTED`, `SPLIT_FAILED`, `EXPAND_FAILED`, `EXPAND_INCOMPLETE`,
  `FEEDBACK_IGNORED`, `INPUT_IGNORED`, `OUTLINE_TRUNCATED`, `ITEM_ALREADY_PLACED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`,
  `SHAPE_DEPTH`, `SHAPE_WIDTH` (Antwort des Sprachmodells zu tief bzw. zu breit, gekürzt), `SECTION_UNKNOWN`,
  `ITEMS_SAMPLED`, `UNTITLED_NODE`, `DESCRIPTION_MISSING`, `DESCRIPTION_LENGTH`).
  `ASSIGN_FAILED` nennt auch Inhalte, zu denen das Sprachmodell keine Antwort gab; sie stehen in `unassigned`.
  `INPUT_IGNORED` meldet gesendete, aber nicht genutzte Eingaben (z. B. Gliederungsdokumente bei `folders` ohne
  `options.improve`, Ordner mit `folders_use: []`, Inhalte bei `assign_contents: false`). `OUTLINE_TRUNCATED` meldet
  auch ein Dokument ohne Überschriften, von dem nur ein Auszug einfloss.
- `questions[]`: Rückfragen zu unklarem Feedback; der unklare Teil wird nicht umgesetzt.
- `metadata.generation.usage`: LLM-Aufrufe, Tokens (davon aus dem Cache), Dauer.

## Fehler

`{"error": {"code", "message", "trace_id", "details"?}}`. 422 ungültige oder unvollständige Anfrage
(`MISSING_INPUT`, `INVALID_INPUT`, `INVALID_OPTION`, `SHAPE_LIMIT_EXCEEDED`, `DUPLICATE_ID`, `ID_CONFLICT`, `UNKNOWN_ITEM`,
`ITEMS_TOO_LARGE`, `REF_NOT_ALLOWED`, `REF_INVALID`, `REF_TOO_LARGE` – ein Verweis oder alle Volltexte einer Anfrage
zusammen (über 10 Mio. Zeichen) zu groß –, `REF_FAILED` – auch wenn Verweise nicht innerhalb von `REQUEST_TIMEOUT_SECONDS` geladen sind …),
404 `NOT_FOUND` und 405 `METHOD_NOT_ALLOWED` für unbekannte Pfade oder Methoden unter `/v2/`,
413 `REQUEST_TOO_LARGE` (Anfrage größer als `MAX_REQUEST_BYTES`, Standard 32 MiB),
401 `UNAUTHORIZED` / 403 `FORBIDDEN` Anmeldung bzw. fehlende b-api-Berechtigung, 501 `NOT_IMPLEMENTED`, 502/503 `LLM_UNAVAILABLE` (503 mit `Retry-After` bei vorübergehenden Fehlern), 503 `LLM_NOT_CONFIGURED`.
