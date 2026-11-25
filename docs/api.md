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

Strukturerzeugung und Inhaltszuordnung sind entkoppelt und lassen sich über das Feld `"use"` je Eintrag in `items` frei kombinieren:

- **`use_case: "topic"` + `items` ohne `use` (oder `"use": ["content"]`)**: Baut den Baum systematisch aus `topic` und sortiert alle `items` anschließend mit Konfidenz ein.
- **`use_case: "topic"` + `items` mit `"use": ["structure", "content"]`**: Übergibt bis zu 50 Materialien (Titel, Schlagworte, Kurzbeschreibung sowie bis zu 5 Volltext-Auszüge; darüber `INPUTS_TRUNCATED`) als ergänzende Anregung an `plan_structure` (zusätzliche Hauptthemen erhalten `status: "suggested"`) und sortiert alle Inhalte in den Baum ein.
- **`use_case: "contents"` + `topic` + `items`**: Bildet Cluster primär aus den Materialien im Rahmen von `topic` (fachfremde Einträge landen mit `off_topic` in `unassigned`; reine `"use": ["content"]`-Einträge werden nur zugeordnet, ohne die Gruppenbildung zu verzerren).
- **`use_case: "document"` + optional `topic` + Strukturdokument (`"structure"`) + Materialien (`"content"`)**: Leitet den Baum aus der Dokumentgliederung ab (`origin.document`) und ordnet die Materialien den Abschnitten zu.
- **`use_case: "folders"` + `folders` + lose Zusatz-`items` (+ optionales Strukturdokument bei `options.improve: true`)**: Übernimmt bestehende Ordnerzuordnungen (`confidence: 1.0`), verbessert auf Wunsch die Ordnerstruktur und sortiert lose Materialien nach.
- **`mode: "refine"` + `feedback` + neue `items`**: Setzt Strukturänderungen unter Schutz von `locked` um, beschreibt neue/umbenannte Knoten und sortiert neue Materialien im selben Aufruf in den aktualisierten Baum ein.

## Automatische Knoten-Metadaten (`options.auto_metadata`)

Ist `options.auto_metadata: true` gesetzt und ein Feld im `frame` leer oder mehrwertig (z. B. fächerübergreifendes
Thema), verengt der Dienst `ccm:taxonid`, `ccm:educationalcontext` und `ccm:educationalintendedenduserrole` je Knoten
zunächst deterministisch aus zugeordneten Inhalten und klassifiziert verbleibende Knoten über exakte deutsche
Vokabular-Bezeichnungen, die deterministisch auf kanonische SkoHub-URIs abgebildet werden.

## Nächster Durchlauf

`collection` als `current_tree.collection`, `metadata.generation` als `current_tree.generation`, `metadata.version`
als `current_tree.version` sowie (optional) `metadata.title`/`metadata.description` als `current_tree.title`/
`current_tree.description` zurückgeben und nur das neue `feedback` ergänzen. Fehlende Vorgaben übernimmt der Dienst
aus `generation`.

## Seitenmarken im Markdown (use_case document)

Erkannt werden `<!-- page: N -->`, `<!-- PageNumber="N" -->` (setzen die Seite) sowie `<!-- page_break -->`,
`<!-- PageBreak -->` und Seitenvorschub (zählen ab Seite 1 hoch). Ohne Marken bleibt `origin.page` leer.

## Antwort lesen

- `warnings[]`: `{code, message, key?, step?}` – was nicht gelungen ist oder auffiel (z. B. `LLM_DEGRADED`,
  `DESCRIBE_FAILED`, `DESCRIBE_UNKNOWN_KEY`, `METADATA_LABEL_UNKNOWN`, `METADATA_FAILED`, `INPUTS_TRUNCATED`,
  `OUTLINE_FALLBACK`, `DEADLINE_EXCEEDED`, `SHAPE_SINGLE_CHILD`, `SHAPE_UNBALANCED`, `DUPLICATE_TITLE`, `GENERIC_TITLE`,
  `FACET_AS_NODE`, `TOPIC_REPEAT`, `CHANGE_REJECTED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`, `REF_*`).
- `questions[]`: Rückfragen zu unklarem Feedback; der Baum bleibt dafür unverändert.
- `metadata.generation.usage`: LLM-Aufrufe, Tokens (davon aus dem Cache), Dauer.

## Fehler

`{"error": {"code", "message", "trace_id", "details"?}}`. 422 ungültige oder unvollständige Anfrage
(`MISSING_INPUT`, `INVALID_INPUT`, `SHAPE_LIMIT_EXCEEDED`, `DUPLICATE_ID`, `UNKNOWN_ITEM`, `ITEMS_TOO_LARGE`,
`REF_NOT_ALLOWED` …),
401/403 Anmeldung bzw. fehlende b-api-Berechtigung, 502/503 `LLM_UNAVAILABLE` (503 mit `Retry-After` bei vorübergehenden Fehlern), 503 `LLM_NOT_CONFIGURED`.
