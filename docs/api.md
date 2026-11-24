# Aufrufe von POST /v2/topic-tree

Vollständige Beispiele liegen unter `docs/examples/`, das Format unter `docs/schemas/`, die Feldbedeutungen in der
Spec „Themenbaum-Dienst: Use Cases und Datenformat“. Laufzeit synchron, typisch 10 bis 120 Sekunden.

## Anmeldung

- Über die b-api: Der Proxy reicht das Delegations-Token (`Authorization: Bearer bdt_…`) durch; nichts weiter zu tun.
- Eigenständig: ohne Anmeldung, oder mit `Authorization: Bearer <Dienst-Schlüssel>`, wenn `SERVICE_API_KEYS` gesetzt ist.

## Kürzester Aufruf

```json
{"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}}
```

## Je Use Case

| Datei | Use Case | Was passiert |
|---|---|---|
| `topic_minimal.json`, `topic_full.json` | topic | Skelett, dann ein Aufruf je Hauptthema |
| `document.json` | document | Gliederung aus den Überschriften, Abschnitt und Seite je Knoten |
| `folders.json` | folders | Ordner bleiben; mit `options.improve` Vorschläge, die als `changes` zurückkommen |
| `contents.json` | contents | Gruppen aus den Inhalten, Zuordnung mit Konfidenz |
| `refine_feedback.json` | refine | Rückmeldung als Text; `locked` schützt Äste |
| `assign_only.json` | refine | Nur neue Inhalte einsortieren, Struktur bleibt |

## Nächster Durchlauf

`collection` als `current_tree.collection`, `metadata.generation` als `current_tree.generation`, `metadata.version`
als `current_tree.version` zurückgeben und nur das neue `feedback` ergänzen. Fehlende Vorgaben übernimmt der Dienst
aus `generation`.

## Seitenmarken im Markdown (use_case document)

Erkannt werden `<!-- page: N -->`, `<!-- PageNumber="N" -->` (setzen die Seite) sowie `<!-- page_break -->`,
`<!-- PageBreak -->` und Seitenvorschub (zählen ab Seite 1 hoch). Ohne Marken bleibt `origin.page` leer.

## Antwort lesen

- `warnings[]`: `{code, message, key?, step?}` – was nicht gelungen ist oder auffiel (z. B. `BRANCH_FAILED`,
  `DEADLINE_EXCEEDED`, `SHAPE_SINGLE_CHILD`, `DUPLICATE_TITLE`, `GENERIC_TITLE`, `FACET_AS_NODE`, `TOPIC_REPEAT`,
  `CHANGE_REJECTED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`, `REF_*`).
- `questions[]`: Rückfragen zu unklarem Feedback; der Baum bleibt dafür unverändert.
- `metadata.generation.usage`: LLM-Aufrufe, Tokens (davon aus dem Cache), Dauer.

## Fehler

`{"error": {"code", "message", "trace_id", "details"?}}`. 422 ungültige oder unvollständige Anfrage
(`MISSING_INPUT`, `INVALID_INPUT`, `DUPLICATE_ID`, `UNKNOWN_ITEM`, `ITEMS_TOO_LARGE`, `REF_NOT_ALLOWED` …),
401/403 Anmeldung bzw. fehlende b-api-Berechtigung, 502/503 `LLM_UNAVAILABLE` (503 mit `Retry-After` bei vorübergehenden Fehlern), 503 `LLM_NOT_CONFIGURED`.
