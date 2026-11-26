# Aufrufe von POST /v2/topic-tree

Vollständige Beispiele liegen unter `docs/examples/`, das Format unter `docs/schemas/`, die Feldbedeutungen in der
Spec „Themenbaum-Dienst: Use Cases und Datenformat“. Zum interaktiven Ausprobieren im Browser steht optional die
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
| `assign_only.json` | refine | Nur neue Inhalte einsortieren, Struktur bleibt |

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
| – | Ein bestehender Baum soll geändert werden | `mode: refine` + `current_tree` | Änderungswunsch als `feedback`; neue Inhalte in `items` |

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

In der Test-UI (`/ui/`) heißt das „Baum ändern“: Basis aus einem Beispiel, dem letzten Ergebnis oder JSON, alle sieben
Operationen (`add`, `remove`, `rename`, `edit`, `move`, `merge`, `split`) als Zeilen mit Knotenauswahl, dazu Freitext,
gesperrte Äste und neue Materialien. Kombinationen der Use Cases (z. B. Thema + Materialien) laufen dort über
„Zusätzlich einbeziehen“.

## Seitenmarken im Markdown (use_case document)

Erkannt werden `<!-- page: N -->`, `<!-- PageNumber="N" -->` (setzen die Seite) sowie `<!-- page_break -->`,
`<!-- PageBreak -->` und Seitenvorschub (zählen ab Seite 1 hoch). Ohne Marken bleibt `origin.page` leer.

## Antwort lesen

- `warnings[]`: `{code, message, key?, step?}` – was nicht gelungen ist oder auffiel (z. B. `LLM_DEGRADED`,
  `DESCRIBE_FAILED`, `DESCRIBE_UNKNOWN_KEY`, `METADATA_LABEL_UNKNOWN`, `METADATA_FAILED`, `INPUTS_TRUNCATED`,
  `OUTLINE_FALLBACK`, `DEADLINE_EXCEEDED`, `SHAPE_SINGLE_CHILD`, `SHAPE_UNBALANCED`, `DUPLICATE_TITLE`, `GENERIC_TITLE`,
  `FACET_AS_NODE`, `TOPIC_REPEAT`, `CHANGE_REJECTED`, `SPLIT_FAILED`, `EXPAND_FAILED`, `EXPAND_INCOMPLETE`,
  `FEEDBACK_IGNORED`, `INPUT_IGNORED`, `OUTLINE_TRUNCATED`, `ITEM_ALREADY_PLACED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`).
  `ASSIGN_FAILED` nennt auch Inhalte, zu denen das Sprachmodell keine Antwort gab; sie stehen in `unassigned`.
  `INPUT_IGNORED` meldet gesendete, aber nicht genutzte Eingaben (z. B. Gliederungsdokumente bei `folders` ohne
  `options.improve`, Ordner mit `folders_use: []`, Inhalte bei `assign_contents: false`). `OUTLINE_TRUNCATED` meldet
  auch ein Dokument ohne Überschriften, von dem nur ein Auszug einfloss.
- `questions[]`: Rückfragen zu unklarem Feedback; der Baum bleibt dafür unverändert.
- `metadata.generation.usage`: LLM-Aufrufe, Tokens (davon aus dem Cache), Dauer.

## Fehler

`{"error": {"code", "message", "trace_id", "details"?}}`. 422 ungültige oder unvollständige Anfrage
(`MISSING_INPUT`, `INVALID_INPUT`, `SHAPE_LIMIT_EXCEEDED`, `DUPLICATE_ID`, `ID_CONFLICT`, `UNKNOWN_ITEM`, `ITEMS_TOO_LARGE`,
`REF_NOT_ALLOWED`, `REF_FAILED` – auch wenn Verweise nicht innerhalb von `REQUEST_TIMEOUT_SECONDS` geladen sind …),
404 `NOT_FOUND` und 405 `METHOD_NOT_ALLOWED` für unbekannte Pfade oder Methoden unter `/v2/`,
413 `REQUEST_TOO_LARGE` (Anfrage größer als `MAX_REQUEST_BYTES`, Standard 32 MiB),
401/403 Anmeldung bzw. fehlende b-api-Berechtigung, 502/503 `LLM_UNAVAILABLE` (503 mit `Retry-After` bei vorübergehenden Fehlern), 503 `LLM_NOT_CONFIGURED`.
