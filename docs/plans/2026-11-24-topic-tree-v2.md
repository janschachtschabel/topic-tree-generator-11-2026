# Design: Themenbaum-Dienst v2

Stand: 24.11.2026 · Status: **freigegeben (mit Änderungen aus Runde 2)** · Branch: `feature/topic-tree-v2`

## Ziel

Der Dienst erzeugt Sammlungsstrukturen für vier Use Cases (Thema, Strukturdokument, Ordner, unstrukturierte
Inhalte), entwickelt Entwürfe auf Rückmeldung weiter und ordnet Inhalte zu. Er ist schneller und günstiger als
heute, läuft mit und ohne b-api und erfüllt den Leitfaden für die Übergabe an T6. Der alte Endpunkt bleibt
formatgleich.

## Kontext

Heute: FastAPI-Monolith (`main.py`, 458 Zeilen), nur Use Case „Thema“, feste drei Ebenen, 1 + N + N×M
LLM-Aufrufe, verschluckte Fehler, String-Parsing von JSON, Vokabulare beim Import aus dem Netz. Grundlagen
dieses Plans:

- **Spec**: „Themenbaum-Dienst: Use Cases und Datenformat“ (Anfrage, Antwort, Feldwerte, Beispiele) – maßgeblich
  für alle Felder. Dieses Dokument wiederholt das Format nicht, es nennt nur Ergänzungen und Festlegungen.
- **Gestaltungsregeln**: Übersichtsdokument „Themenbäume“ (Form, Benennung, Baum vs. Facette, Ordnungsprinzip
  je Zielgruppe) – Grundlage für Prompts und Strukturprüfung.
- **Leitfaden** „Dienste an T6 übergeben“ (Stand 17.11.2026) – Muss/Soll für API, b-api, Logging, Betrieb, Helm.

## Klärungen (aus dem Chat, 24.11.2026)

| Frage | Antwort |
|---|---|
| Betrieb ohne b-api | Nativer OpenAI-Support (OpenAI-kompatibler Endpunkt per Env); optional setzbare Auth für Aufrufe. Mit b-api läuft das LLM über die b-api. Später nur intern über die b-api erreichbar. Erkennung automatisch, per Env auf feste Werte umschaltbar. |
| Laufzeit > 30 s | Synchron. Mehrere Worker, Timeout konfigurierbar, kein Streaming, Wiederholungen bei abgebrochenen Einzel-Prompts, Logging nach Leitfaden. |
| Umfang | Alle Phasen am Stück. |
| Dienst-ID | `topic-tree` (bestehender b-api-Proxy-Eintrag). |
| Alter Endpunkt | Funktioniert genauso wie bisher; neue Systematik nur im neuen Endpunkt (E7). |
| Seitenmarken | Erläutert; Format wird im Team geklärt. Bis dahin E11 (alle gängigen Formate). |

## Scope

**In scope**
- `POST /v2/topic-tree` mit `mode` create/refine und allen vier Use Cases nach Spec, inkl. Zuordnung,
  `unassigned`, `changes`, `questions`, `warnings`, `metadata.generation`.
- Alte Endpunkte `/generate-topic-tree` und `/generate-collection-description`: Format eingefroren (Vertragstest).
- Modus-Erkennung b-api/eigenständig, optionale Dienst-Auth, LLM über b-api-Router oder OpenAI-kompatibel.
- Geschwindigkeit/Kosten: weniger Aufrufe, Prompt-Caching, Parallelitätsgrenze, mehrere Worker.
- Prompt-Überarbeitung inkl. Erkennung des Ordnungsprinzips, wenn `hints.order` fehlt.
- Leitfaden: zwei Ports, Proben, Metriken, JSON-Logs, B3/`x-client-trace-id`, Fehlerformat, Dockerfile
  (non-root, multi-stage), Helm-Chart, CI, Steckbrief-Vorlage, JSON-Schemata unter `docs/schemas/`.

**Out of scope**
- Zugriff aufs Repository (auch lesend), Kestra-Flows, Job-Endpunkte, Streaming.
- Embedding-Clustering für `contents` (LLM-Gruppierung genügt für den Start; siehe Folgearbeiten).
- OpenTelemetry-Export von Spans (B3 wird selbst gelesen und weitergegeben; OTel ist im Leitfaden „Soll“).
- Gemessene Kosten und Laufzeiten im Steckbrief: Werkzeug und Vorlage kommen mit, messen muss T4 mit echtem
  Schlüssel (diese Umgebung erreicht weder b-api noch OpenAI).
- Facetten-Vokabulare (Kompetenzen, Niveaus), SKOS-Export der Bäume.

## Entscheidungen

### E1 Generierung: Skelett zuerst (gewählt: B)

| Ansatz | Wie | Aufrufe bei 8×5×3 | Bewertung |
|---|---|---|---|
| A Ebene für Ebene (heute) | je Knoten ein Aufruf für seine Kinder | 49 | langsam, teuer, Geschwister sehen sich nicht |
| **B Skelett + Äste** | 1 Planungsaufruf: Ordnungsprinzip + obere Ebenen als Titel; dann 1 Aufruf je Hauptast: Unterbaum mit Beschreibungen, parallel | 9 | wenige Aufrufe, Äste kennen das ganze Skelett (weniger Dubletten), Fehler bleibt auf einen Ast begrenzt |
| C Ein Aufruf für alles | ganzer Baum in einer Antwort | 1 | lange Ausgabe, Timeout-Risiko, ein Fehler kostet alles |

B, weil es Kosten und Laufzeit stark senkt, ohne das Ausfallrisiko von C. Bei GWDG-Routen (10 Anfragen/min
geteilt) ist die Aufrufzahl ohnehin der Engpass.

### E2 Prompt-Caching

1. **System-Nachricht statisch**: `app/prompts/system.md` (Rollen, Format- und Gestaltungsregeln, Ordnungsprinzipien
   je Bildungsbereich, Tabu-Liste Facetten). Byte-gleich in jedem Aufruf, jeder Anfrage; > 1.024 Tokens, damit
   der Präfix-Cache des Anbieters greift.
2. **User-Nachricht vom Allgemeinen zum Besonderen**: zuerst der Anfragekontext (Rahmen mit Labels, Thema,
   Hinweise, Skelett), dann die Schrittanweisung, zuletzt das Ast-Spezifische. Parallele Ast-Aufrufe teilen damit
   alles bis auf den letzten Block.
3. **`prompt_cache_key`** = Hash aus Dienst-ID und Schritt, nur wenn `LLM_SEND_PROMPT_CACHE_KEY=true`
   (Standard: an bei OpenAI nativ, aus bei b-api, bis geprobt ist, dass GWDG-Modelle das Feld tolerieren).
4. Gemessen wird `usage.prompt_tokens_details.cached_tokens` je Aufruf (Log, Metrik, `generation.usage`).
5. Tests sichern die Invarianten: System-Nachricht in allen Aufrufen identisch; Ast-Aufrufe einer Anfrage haben
   identischen Präfix bis zum Ast-Block.

### E3 Modus-Erkennung und Auth

`SERVICE_MODE` = `auto` (Standard) | `bapi` | `standalone`.

| Eingehend | `auto` | `bapi` | `standalone` |
|---|---|---|---|
| `Authorization: Bearer bdt_…` (bzw. `B_API_DELEGATION_HEADER`) | b-api-Modus | b-api-Modus | als Dienst-Schlüssel geprüft |
| anderer Bearer | eigenständig, als Dienst-Schlüssel geprüft | 401 | als Dienst-Schlüssel geprüft |
| keiner | eigenständig | 401 | eigenständig |

- **b-api-Modus**: LLM über `B_API_BASE_URL` + `/api/v1/llm/router/`, Routenname `B_API_ROUTE`
  (Standard `topic-tree-generator`, liest `LLM_MODEL` als Altname), Token unverändert als `Authorization`.
- **Eigenständig**: Dienst-Auth nur, wenn `SERVICE_API_KEYS` gesetzt ist (Vergleich in konstanter Zeit, 401 sonst;
  ohne Liste offen – Leitfaden: „fehlt eine Anmeldung, antwortet der Dienst anonym“). LLM über
  `OPENAI_BASE_URL` (optional, OpenAI-kompatibel) + `OPENAI_API_KEY` + `OPENAI_MODEL`. Fehlt der Schlüssel: 503
  `LLM_NOT_CONFIGURED`.
- **Lokaler Dev-Modus** (Leitfaden Stufe 2): `B_API_DEV_KEY` gesetzt → eigenständige Anfragen nutzen den
  b-api-Router mit diesem Schlüssel. Nur per Env, nicht im Chart-Standard.
- **Verhaltensänderung alt**: Bisher wurde jeder Bearer als b-api-Schlüssel weitergereicht. Hinter dem b-api-Proxy
  kommt seit 10.11.2026 ohnehin das Delegations-Token an; direkte Aufrufer mit eigenem b-api-Schlüssel nutzen
  künftig `B_API_DEV_KEY` oder den Proxy. Steht im Changelog.

### E4 Laufzeit, Worker, Wiederholungen

- gunicorn mit `uvicorn_worker.UvicornWorker`, `WEB_CONCURRENCY` Worker (Standard 2). Interner Port (`/health`,
  `/ready`, `/metrics`) einmal im gunicorn-Master (`when_ready`-Hook, stdlib-HTTP-Server in einem Thread,
  Prometheus-Multiprozess über `PROMETHEUS_MULTIPROC_DIR`, `child_exit` → `mark_process_dead`).
- `REQUEST_TIMEOUT_SECONDS` (Standard 280) als Frist je Anfrage; gunicorn-`timeout` = Frist + 30 s,
  `graceful_timeout` 70 s. Läuft die Frist ab, endet die Anfrage mit dem Fertigen plus `warnings`
  (`DEADLINE_EXCEEDED`), nicht mit einem Abbruch.
- Je LLM-Aufruf: `LLM_TIMEOUT_SECONDS` (120), Transport-Wiederholungen `LLM_MAX_RETRIES` (3, über das SDK, mit
  Backoff und Retry-After), dazu **genau ein** Reparaturversuch bei ungültigem JSON oder Schemafehler.
  Scheitert ein Ast danach, bleibt der Rest gültig und `warnings` nennt ihn.
- Parallelität je Prozess: `LLM_MAX_CONCURRENCY` (8) über ein Semaphor.

### E5 Strukturierte Ausgabe

`LLM_OUTPUT_MODE` = `json_schema` (Standard; `response_format` mit `strict`) | `json_object` | `prompt`
(Schema nur im Prompt). Jede Antwort wird gegen das Pydantic-Modell validiert, egal welcher Modus.
Parameterfamilie `LLM_PARAM_FAMILY` = `common` (Standard: `max_completion_tokens` + `reasoning_effort: "none"`,
laut Leitfaden für gpt-6-luna und die GWDG-Modelle) | `gpt5` | `classic` (`max_tokens`). Kein Modellname im Code.

### E6 Repository-Unabhängigkeit und Referenzen

Kein Repository-Zugriff. `nodeId` wird durchgereicht. `fulltext.ref` und `items_ref` werden nur von Hosts aus
`REF_ALLOWED_HOSTS` geladen (Standard leer = abgelehnt mit 422 `REF_NOT_ALLOWED`), nur HTTPS, Grenzen
`REF_MAX_BYTES` (10 MB) und `REF_TIMEOUT_SECONDS` (20). Schützt vor SSRF.

### E7 Alte Endpunkte (entschieden: Verhalten eingefroren)

`/generate-topic-tree` und `/generate-collection-description` behalten Anfrage, Antwort, Prompts und Ablauf
(Ebene für Ebene, Bearer wird als Schlüssel an die b-api gereicht). Der Code zieht nach `app/legacy/` um, ohne
Logikänderung. Gemeinsam mit v2 nutzen sie nur die Querschnitte: Tracing-Middleware, Zugriffszeile, Logformat,
`/health`. Einzige Abweichung: Fach- und Stufenlabels kommen aus dem Vokabular-Snapshot statt aus einem
Netzabruf beim Start (sonst startet der Dienst ohne Netz nicht); dabei werden zuverlässig die deutschen Labels
genommen, bisher zufällig deutsch oder englisch. Vertragstests frieren Format und Auth-Verhalten ein.

### E8 Ordnungsprinzip erkennen

Fehlt `hints.order`, wählt der Planungsschritt das Prinzip der obersten Ebenen anhand von Bildungsstufe, Fach,
Zweck und (bei `document`/`folders`/`contents`) der Eingaben: Themenfelder/Themen (Schule), Lernfelder bzw.
berufliche Handlungen (Berufsbildung), Entwicklungsbereiche (Elementarbereich), Fächersystematik/Module
(Hochschule), Prozesse/Aufgaben (Organisationen). Facetten (Stufe, Format, Kompetenz, Zielgruppe) werden nie
Knoten. Ergebnis steht in `metadata.generation.structure`.

### E9 Längen

`hints.description_length` wird als **Wörter** gelesen (Spec schreibt „Zeichen“, 60 Zeichen wäre kaum ein Satz;
der alte Dienst nutzt Wörter). Prompt fordert „etwa N Wörter, höchstens N + 20 %“; die Prüfung kürzt nicht,
sie meldet starke Abweichungen in `warnings` (Code `DESCRIPTION_LENGTH`).

### E10 Ergänzungen zum Spec-Format

Alles zusätzlich, nichts ersetzt:

- `metadata.generation.structure`: `{ "order": "...", "levels": ["Themenfeld", "Thema", ...], "source": "hint" | "detected" }`
- `metadata.generation.usage`: `{ "llm_calls", "prompt_tokens", "cached_tokens", "completion_tokens", "duration_ms" }`
- `warnings[]`: `{ "code", "message", "key"?, "step"? }` – Codes: `BRANCH_FAILED`, `DEADLINE_EXCEEDED`,
  `SHAPE_SINGLE_CHILD`, `SHAPE_DEPTH`, `SHAPE_WIDTH`, `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH`,
  `CHANGE_REJECTED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`.
- `questions[]`: `{ "text", "key"?, "options"? }`
- Fehlerantwort: `{ "error": { "code", "message", "trace_id", "details"? } }`, 422 für ungültige Anfragen,
  401/403 Auth, 503 `LLM_NOT_CONFIGURED` bzw. Abhängigkeit vorübergehend (mit `Retry-After`).
- Grenzen (offener Spec-Punkt): `items` inline bis `ITEMS_INLINE_MAX` (500), darüber `items_ref`.

### E11 Seitenmarken im Markdown

Unterstützt werden `<!-- page: N -->`, `<!-- PageNumber="N" -->`, `<!-- page_break -->` (zählt hoch) und
Formfeed `\f` (zählt hoch). Ohne Marken bleibt `origin.page` leer. **Zur Bestätigung**: Welches Format liefert
die Konvertierung tatsächlich?

## Globale Vorgaben

Aus `AGENTS.md` (verbindlich): Python 3.13, uv, ruff 120, TDD, Conventional Commits, Englisch im Code, Deutsch in
Prompts/Plänen, Dateien ≤ ~300 Zeilen, Abhängigkeiten nach innen, kein Repository-Zugriff, Token nie loggen,
keine stillen Lücken, kein Streaming.

Neue Abhängigkeiten (je eine Zeile Begründung):
- `gunicorn` – mehrere Worker mit Master-Hook für den internen Port (Leitfaden: interner Port nur einmal binden).
- `uvicorn-worker` – offizieller Nachfolger von `uvicorn.workers` für gunicorn.
- `prometheus-client` – Leitfaden-Muss `/metrics`, inkl. Multiprozess-Modus.
- `httpx` – bereits transitiv über `openai`; wird direkt genutzt für `ref`-Abrufe und den Test-Stub. Explizit deklariert.
- Entfernt: `ruff` aus den Laufzeit-Abhängigkeiten (nur dev). `rdflib` bleibt für den Vokabular-Snapshot-Build, nicht zur Laufzeit.

## Architektur

### Dateien

```
app/
  __init__.py
  __main__.py              dev: public :8000 + internal :9000 in einem Prozess
  main.py                  create_app(): FastAPI, Router, Middleware, Exception-Handler
  settings.py              Settings (pydantic-settings), alle Env mit Vorgaben
  internal_server.py       /health /ready /metrics (stdlib http.server), auch im gunicorn-Master
  api/
    deps.py                Dependency: CallerContext + LLMClient je Anfrage
    errors.py              ApiError, Fehlerformat, Handler
    legacy.py              Router für die alten Endpunkte (ruft app/legacy/)
    v2.py                  POST /v2/topic-tree
    health.py              /health, /_ping auf dem öffentlichen Port (nicht in OpenAPI)
  context/
    tracing.py             B3 lesen/prüfen/erzeugen, x-client-trace-id, contextvars, Header für ausgehend
    caller.py              Modus-Erkennung, Dienst-Auth → CallerContext
  llm/
    backend.py             LLMBackend aus CallerContext + Settings (bapi | openai | dev)
    client.py              LLMClient.complete_json / complete_text, Familien, Ausgabemodi, Reparatur, Semaphor
    usage.py               UsageTracker je Anfrage
  prompts/
    __init__.py            load(name), render(name, **fields)
    system.md              statisch (Cache-Präfix)
    plan_structure.md  expand_branch.md  describe_nodes.md  assign_contents.md
    interpret_feedback.md  improve_folders.md  map_outline.md  group_contents.md
    collection_description.md   (alter Endpunkt)
  schemas/
    common.py              Enums: Mode, UseCase, ItemUse, NodeStatus, OriginType, ChangeOp, ChangeSource, UnassignedReason
    properties.py          Properties: nimmt cm:title und cm_title an; gibt Doppelpunkt (v2) oder Unterstrich (alt) aus
    request_v2.py          TopicTreeRequestV2, Frame, Shape, Range, Hints, Options, Item, Fulltext, FolderNode, CurrentTree, Feedback, Change
    response_v2.py         TopicTreeResponseV2, NodeOut, ContentRef, Unassigned, ChangeRecord, Question, Warning, Metadata, Generation
  domain/
    tree.py                Node (key, title, shorttitle, description, keywords, status, origin, confidence, contents, children, locked); walk/find/path/parent
    keys.py                make_key(title, taken) → "k-<slug>[-n]"
    shape_rules.py         check_shape(tree, shape) → warnings; normalize_shorttitle; dedup_siblings
    ops.py                 apply_changes(tree, changes, locked) → (applied, rejected)
    diff.py                mark_status(new, old) ; status gegen Ordner
  pipeline/
    orchestrator.py        run(request, ctx) → Response: Prüfen, Strategie, refine, assign, finalize
    run_context.py         RunContext: LLMClient, Frist, Warnungen, Vokabular-Labels, Usage
    steps/
      plan_structure.py    Ordnungsprinzip + Skelett
      expand_branch.py     Unterbaum + Beschreibungen je Hauptast
      describe_nodes.py    Beschreibungen/Keywords für Knoten ohne (Batch)
      assign_contents.py   Zuordnung in Batches mit Konfidenz
      interpret_feedback.py Text → Änderungen oder Rückfragen
      improve_folders.py   Ordner verbessern (options.improve)
      map_outline.py       Gliederung → Baum (Auswahl, Normalisierung)
      group_contents.py    Gruppen aus Inhalten bilden
    strategies/
      topic.py  document.py  folders.py  contents.py
    inputs/
      outline.py           Markdown → Abschnitte mit id, Ebene, Seite, Textauszug
      refs.py              ref-Laden mit Allowlist, Größen- und Zeitgrenze
    finalize.py            Properties aus frame, Metadaten, generation, Ausgabe
  legacy/                  alter Ablauf, Logik unverändert: service.py, prompts.py, structured_text.py, dtos.py
  vocab/
    labels.py              label(uri) → deutsches prefLabel; Snapshot, kein Netz zur Laufzeit
    data/discipline.json  data/educationalContext.json  data/intendedEndUserRole.json
  observability/
    logging.py             loguru: JSON nach stdout (service, trace_id, span_id), Klartext per Env
    metrics.py             Prometheus-Metriken
    access_log.py          eine Zeile je Anfrage (Routenklasse, Status, Dauer, trace_id)
scripts/
  build_vocab_snapshot.py  Turtle von GitHub → data/*.json (rdflib, nur dev)
  export_schemas.py        Pydantic → docs/schemas/*.json
  loadtest.py              parallele Anfragen gegen eine Instanz, P50/P90, Fehlerquote
deploy/helm/topic-tree/    Chart (Name = Dienst-ID, siehe offene Punkte)
docs/
  schemas/request-v2.schema.json, response-v2.schema.json
  api.md                   Aufrufe vom kürzesten bis vollständigen, je Use Case
  steckbrief.md            Vorlage nach Leitfaden, mit Messanleitung
gunicorn.conf.py  Dockerfile  compose.yml  main.py (Shim: from app.main import app)
tests/                     spiegelt app/; tests/fakes/llm.py (skriptbarer LLM), tests/stub_openai.py (HTTP-Stub)
```

Entfällt: `src/` (Inhalt wandert nach `app/`), `.idea/` (aus dem Repo, in `.gitignore`).

### Datenfluss (create)

```
HTTP → tracing-Middleware → api/v2 → deps: CallerContext (Modus, Auth) + LLMClient(Backend)
     → orchestrator.run
         1 Anfrage prüfen (Pflichtfelder je use_case, Grenzen, refs laden)
         2 RunContext anlegen (Frist, Labels aus vocab, Warnungen, Usage)
         3 Strategie: topic | document | folders | contents  → domain.Node-Baum
         4 Zuordnung, wenn Inhalte da und assign_contents
         5 shape_rules: prüfen, Kurztitel/Dubletten normalisieren → warnings
         6 keys vergeben, status setzen
         7 finalize: Properties aus frame, metadata.generation, Ausgabeformat
     → JSON-Antwort
```

**refine**: 1 → `current_tree` in `domain.Node` (fehlende keys vergeben, `generation` als Vorgaben-Rückfall) →
strukturierte `changes` anwenden (Vorrang) → Feedback-Text interpretieren (Änderungen oder `questions`) →
anwenden (locked geschützt) → neue/geänderte Knoten beschreiben → bei `assign_only` nur Zuordnung → 4–7 mit
`based_on`, Version +1, Feedback-Verlauf ergänzt.

### Strategien

| Use Case | Struktur entsteht durch | LLM-Schritte |
|---|---|---|
| `topic` | plan_structure (Skelett) → expand_branch je Hauptast | 1 + N |
| `document` | outline (deterministisch) → map_outline (Auswahl/Normalisierung nach hints) → describe_nodes mit Abschnittstext | 1 + ⌈Knoten/30⌉ |
| `folders` | Ordner 1:1 übernehmen; `improve` → improve_folders (Änderungen als ops); describe_nodes aus Inhalts-Metadaten; Zuordnung aus Ordnern (Konfidenz 1.0) | 0–1 + ⌈Knoten/30⌉ |
| `contents` | group_contents (Schema aus allen Titeln/Keywords, bei > 300 Einträgen aus einer Stichprobe plus Titelliste) → assign_contents in Batches à 40 | 1 + ⌈Items/40⌉ |

Ergänzende Eingaben (Spec „Kombinationen“): `structure`-Items bei `topic`/`folders` gehen kompakt in den
Planungs- bzw. Verbesserungsschritt; daraus entstehende Knoten bekommen `status: "suggested"`.

### Schnittstellen (Kern)

```python
# llm/client.py
class LLMClient:
    async def complete_json(self, step: str, user: str, model: type[T], *, max_tokens: int) -> T: ...
    async def complete_text(self, step: str, system: str, user: str, *, max_tokens: int) -> str: ...

# pipeline/run_context.py
@dataclass
class RunContext:
    llm: LLMClient
    deadline: float                 # monotonic
    labels: VocabLabels
    warnings: list[Warning]
    usage: UsageTracker
    def remaining(self) -> float: ...

# pipeline/strategies/*.py
async def build(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult   # (roots: list[Node], structure: StructureInfo)

# domain/ops.py
def apply_changes(roots: list[Node], changes: list[Change], locked: set[str], source: ChangeSource) -> ApplyResult

# context/caller.py
@dataclass(frozen=True)
class CallerContext:
    mode: Literal["bapi", "standalone"]
    delegation_token: str | None    # nur im Speicher dieser Anfrage
    trace: TraceContext
```

### Konfiguration (Env, alle mit Vorgabe)

| Variable | Vorgabe | Zweck |
|---|---|---|
| `SERVICE_ID` | `topic-tree` | Dienst-ID in Logs/Metriken |
| `SERVICE_MODE` | `auto` | E3 |
| `SERVICE_API_KEYS` | leer | optionale Dienst-Auth (kommagetrennt) |
| `B_API_BASE_URL` | `https://b-api.staging.openeduhub.net` | b-api |
| `B_API_ROUTE` (`LLM_MODEL` als Altname) | `topic-tree-generator` | Routenname |
| `B_API_DELEGATION_HEADER` | leer | falls der Admin einen eigenen Header setzt |
| `B_API_DEV_KEY` | leer | lokaler Dev-Modus |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` | leer / leer / `gpt-6-luna` | eigenständig |
| `LLM_PARAM_FAMILY` | `common` | E5 |
| `LLM_OUTPUT_MODE` | `json_schema` | E5 |
| `LLM_SEND_PROMPT_CACHE_KEY` | `auto` (an bei openai, aus bei bapi) | E2 |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` / `LLM_MAX_CONCURRENCY` | 120 / 3 / 8 | E4 |
| `REQUEST_TIMEOUT_SECONDS` | 280 | E4 |
| `WEB_CONCURRENCY` | 2 | gunicorn-Worker |
| `PUBLIC_PORT` / `INTERNAL_PORT` | 8000 / 9000 | Leitfaden Kap. 3 |
| `REF_ALLOWED_HOSTS` / `REF_MAX_BYTES` / `REF_TIMEOUT_SECONDS` | leer / 10485760 / 20 | E6 |
| `ITEMS_INLINE_MAX` | 500 | E10 |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Logging (`text` für lokal) |
| `PROMETHEUS_MULTIPROC_DIR` | `/tmp/prometheus` | Multiprozess-Metriken |

## Nicht-funktional

- **Leistung**: Thema 8×5×3 mit ≤ 10 LLM-Aufrufen; Parallelität begrenzt; Ziel P50 < 60 s auf `gpt-6-luna`
  (Messung durch T4). Kein Streaming.
- **Sicherheit**: Token nur im Speicher der Anfrage, nie geloggt; Dienst-Schlüssel in konstanter Zeit
  verglichen; SSRF-Schutz für `ref`; Trace-Header nach Länge/Zeichensatz geprüft; Fehler ohne interne Details;
  Container non-root, Dateisystem nur lesend außer `/tmp`; Eingabegrößen begrenzt.
- **Observability**: JSON-Logs mit `service`, `trace_id`, `span_id`; eine Zeile je Anfrage; je LLM-Aufruf eine
  Debug-Zeile mit Schritt, Dauer, Tokens, Cache-Tokens (nie Prompt-Inhalt auf INFO). Metriken:
  `topic_tree_requests_total{route,status}`, `topic_tree_request_seconds{route}`,
  `topic_tree_llm_calls_total{step,outcome}`, `topic_tree_llm_seconds{step}`,
  `topic_tree_llm_tokens_total{kind}` (prompt|cached|completion), `topic_tree_warnings_total{code}`.
- **Datenschutz**: Inhalte von Items nur an das LLM, nicht in Logs (nur Anzahl und ids auf DEBUG).

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| GWDG-Modelle verstehen `response_format: json_schema` oder `prompt_cache_key` nicht | Ausgabemodus und Cache-Key per Env; Validierung + Reparatur unabhängig vom Modus; Probe-Skript `scripts/probe_llm.py` für T4 |
| Große Bäume überschreiten die Frist | Frist mit Teilergebnis + Warnung; Grenzen in `shape` (max. Tiefe 4, Hauptebene ≤ 20) |
| Abnehmer des alten Formats brechen | alter Ablauf unverändert, Vertragstests für Format und Auth |
| LLM erfindet keys oder ids bei Zuordnung/Feedback | Ausgaben gegen vorhandene keys/ids geprüft; Unbekanntes → `CHANGE_REJECTED`/`ASSIGN_FAILED` |
| Vokabular-Snapshot veraltet | Skript zum Neubau, Datum im Snapshot, unbekannte URIs → Warnung, nicht Fehler |
| Zwei Ports mit mehreren Workern | Master-Hook-Muster aus der prometheus-client-Doku; Test startet gunicorn real im Smoke-Test |

## Offene Punkte

1. Format der Seitenmarken aus der Konvertierung (betrifft nur T4.1; bis dahin E11).

Annahmen ohne Rückfrage (bei Widerspruch bitte melden): E9 Wörter; GitLab-CI bleibt der Deploy-Weg,
GitHub Actions nur Lint/Test/Helm-Lint; Chart im Repo unter `deploy/helm/<dienst-id>`.

---

# Aufgaben

Jede Phase beginnt mit **Schritt 0: `/better-coding-workflow` neu laden**. Jede Aufgabe: Test zuerst (rot),
minimale Umsetzung (grün), Refactor, `uv run pytest -q && uv run ruff check && uv run ruff format --check`,
Commit. Aufgaben mit [P] sind innerhalb ihrer Phase unabhängig. Testfälle sind verbindlich; Code entsteht in
der Umsetzung (bei dieser Größe ersetzt die genaue Schnittstellen- und Testangabe den Volltext-Code im Plan).

## Phase 1 – Fundament

Schritt 0: `/better-coding-workflow` laden.

- [x] **T1.1 Paketgerüst und Settings**
  Dateien: `app/__init__.py`, `app/settings.py`, `tests/test_settings.py`; `pyproject.toml` (Abhängigkeiten, ruff nach dev).
  Tests: Vorgaben aus der Tabelle; `LLM_MODEL=x` ohne `B_API_ROUTE` → `b_api_route == "x"`; `SERVICE_API_KEYS="a, b"` → `["a","b"]`;
  `REF_ALLOWED_HOSTS` als Liste; ungültiger `SERVICE_MODE` → ValidationError.
  Verifikation: `uv run pytest tests/test_settings.py -q`.

- [x] **T1.2 Tracing** [P]
  Dateien: `app/context/tracing.py`, `tests/context/test_tracing.py`.
  Schnittstelle: `TraceContext(trace_id, span_id, parent_span_id, sampled, client_trace_id)`; `from_headers(h) -> TraceContext`;
  `outgoing_headers(tc) -> dict`; contextvar `current_trace`.
  Tests: gültige `X-B3-TraceId` (16/32 hex) übernommen; ungültige (Länge, Zeichen) → neue ID; `b3`-Einzelheader;
  `x-client-trace-id` durchgereicht, aber nie erzeugt; ausgehend neue `span_id`, gleiche `trace_id`.

- [x] **T1.3 Logging und Zugriffszeile** [P]
  Dateien: `app/observability/logging.py`, `app/observability/access_log.py`, Tests.
  Tests: JSON-Zeile hat `timestamp, level, service, trace_id, span_id, message`; `LOG_FORMAT=text` → Klartext;
  Zugriffszeile nutzt Routenklasse (`v2.topic_tree`), nicht den Pfad; Header-Werte tauchen nie auf (Test mit Token im Header).

- [x] **T1.4 Fehlerformat**
  Dateien: `app/api/errors.py`, Tests.
  Tests: `ApiError(422,"INVALID_INPUT",...)` → `{"error":{code,message,trace_id}}`; RequestValidationError → 422 mit `details`
  (Feldpfade, ohne Eingabewerte); unbehandelte Exception → 500 `INTERNAL`, Meldung ohne Exception-Text.

- [x] **T1.5 Modus-Erkennung und Dienst-Auth**
  Dateien: `app/context/caller.py`, `tests/context/test_caller.py`.
  Tests: gesamte Tabelle aus E3 (9 Fälle); `B_API_DELEGATION_HEADER` gesetzt → Token von dort; `bearer` klein → als fehlend
  behandelt; falscher Dienst-Schlüssel → 401 mit `WWW-Authenticate: Bearer`; Vergleich über `hmac.compare_digest`.

- [x] **T1.6 LLM-Backend**
  Dateien: `app/llm/backend.py`, Tests.
  Schnittstelle: `resolve_backend(ctx, settings) -> LLMBackend(base_url, api_key, model, kind, send_cache_key)`.
  Tests: bapi → `base_url` endet auf `/api/v1/llm/router/`, `api_key` = Token, `model` = Route; standalone mit OpenAI-Key →
  `kind="openai"`; standalone ohne Key, mit `B_API_DEV_KEY` → `kind="dev"`; ohne beides → `ApiError(503,"LLM_NOT_CONFIGURED")`;
  `send_cache_key` gemäß `auto`.

- [x] **T1.7 LLM-Client**
  Dateien: `app/llm/client.py`, `app/llm/usage.py`, `tests/fakes/llm.py`, `tests/llm/test_client.py`.
  Tests (mit gefälschtem `AsyncOpenAI`): Familie `common` sendet `max_completion_tokens` + `reasoning_effort:"none"`, kein
  `temperature`; `classic` sendet `max_tokens`; `json_schema`-Modus setzt `response_format` mit Schema aus dem Modell;
  ungültiges JSON → genau ein Reparaturaufruf mit Fehlerhinweis, danach `LLMStepError`; Schemafehler ebenso; kein
  `stream`; nie `X-API-KEY`-Header (`default_headers` geprüft); Semaphor begrenzt gleichzeitige Aufrufe (Test mit 20
  Tasks, max. beobachtet = Limit); Usage summiert `prompt/cached/completion`; Timeout aus der Frist (`min(LLM_TIMEOUT, remaining)`).

- [x] **T1.8 Prompt-Lader und System-Prompt**
  Dateien: `app/prompts/__init__.py`, `app/prompts/system.md`, `tests/prompts/test_prompts.py`.
  Tests: `render` ersetzt nur `{{name}}`-Platzhalter (keine `str.format`-Kollision mit JSON-Klammern); fehlender
  Platzhalter → `KeyError`; `system.md` enthält keine Platzhalter; Länge ≥ 4.500 Zeichen (≈ 1.024 Tokens, Cache-Schwelle).

- [x] **T1.9 Vokabular-Labels**
  Dateien: `scripts/build_vocab_snapshot.py`, `app/vocab/labels.py`, `app/vocab/data/*.json`, Tests.
  Tests: `label(".../discipline/460") == "Physik"`; `label(".../educationalContext/sekundarstufe_1")` deutsch; unbekannte URI → `None`;
  kein Netzwerkzugriff beim Import (Test patcht Socket); Snapshot enthält `generated_at`.

- [x] **T1.10 Metriken und interner Server**
  Dateien: `app/observability/metrics.py`, `app/internal_server.py`, `gunicorn.conf.py`, `app/__main__.py`, Tests.
  Tests: `GET /health` 200 `{"status":"ok","vocab_snapshot": "<datum>"}`; `/ready` 200 bei gültiger Konfiguration, 503 bei
  fehlendem LLM in jedem Modus; `/metrics` liefert Prometheus-Text; Smoke-Test startet `gunicorn -c gunicorn.conf.py` mit
  2 Workern und prüft beide Ports (markiert `@pytest.mark.slow`).

- [x] **T1.11 App-Fabrik und alte Endpunkte umgezogen**
  Dateien: `app/main.py`, `app/api/deps.py`, `app/api/health.py`, `app/api/legacy.py`, `app/legacy/*` (Logik aus `main.py`/`src/`
  unverändert), `main.py` (Shim), Tests; `src/` löschen, `.idea/` aus dem Repo.
  Tests: `/openapi.json` enthält nur `/generate-topic-tree`, `/generate-collection-description`, `/v2/topic-tree` (Letzteres ab
  T2.9); `/health` und `/_ping` 200, nicht in OpenAPI; alte Endpunkte reichen den Bearer weiter wie bisher.
  **Vertragstest** `tests/api/test_legacy_contract.py`: Antwortstruktur des alten Endpunkts mit Fake-LLM eingefroren
  (Schlüssel `metadata{title,description,target_audience,created_at,version,author}`, `collection[].{title,shorttitle,properties{cm_title,...},subcollections?}`).
  Alte Tests unter `tests/` an neue Pfade angepasst und grün.

**Abweichungen in Phase 1** (bewusst, YAGNI bzw. Schichtung):
- `ApiError` liegt in `app/errors.py` (nicht in `api/`), damit `context/` nicht aus `api/` importiert.
- `LLMClient.complete_text` entfällt: kein Abnehmer, die alten Endpunkte behalten ihren eigenen Aufruf.
- Alter Router liegt in `app/legacy/router.py` (statt `app/api/legacy.py`), Logik eingefroren; ruff-Ausnahmen nur für `app/legacy/**`.
- `app/api/deps.py` kommt mit T2.9 (erster Abnehmer). `.idea/` bleibt im Repo (PyCharm-Startkonfiguration zeigt weiter auf `main.py`).
- Neu: `app/version.py`, `app/llm/json_schema.py` (strict-Schema), Dev-Abhängigkeit `pytest-asyncio`.
- Fund beim Testen: `httpx` loggte ausgehende URLs auf INFO; jetzt auf WARNING gedeckelt.

## Phase 2 – v2-Vertrag und Domäne

Schritt 0: `/better-coding-workflow` laden.

- [x] **T2.1 Enums und Properties** [P]
  Dateien: `app/schemas/common.py`, `app/schemas/properties.py`, Tests.
  Tests: `Properties` nimmt `cm:title` und `cm_title` an; `dump_v2()` → Doppelpunkt, `dump_legacy()` → Unterstrich; zusätzliche
  Properties bleiben erhalten (`extra="allow"`); alle Werte Listen von Strings.

- [x] **T2.2 Anfrage v2**
  Dateien: `app/schemas/request_v2.py`, `tests/schemas/test_request_v2.py`, `tests/fixtures/spec_examples/*.json` (alle Anfrage-Beispiele aus der Spec).
  Tests: jedes Spec-Beispiel validiert (Platzhalter `…` durch Minimalwerte ersetzt); `refine` ohne `current_tree` → 422;
  Pflichteingabe je `use_case` fehlt → 422 mit Code `MISSING_INPUT`; `use`-Standard (contents → beides, sonst content);
  `shape.depth` 1–4, `main_topics.max` ≤ 20, `min ≤ max`; `items` > `ITEMS_INLINE_MAX` → 422; Item-ids eindeutig; Ordner-
  Verweise auf unbekannte ids → 422.

- [x] **T2.3 Antwort v2** [P]
  Dateien: `app/schemas/response_v2.py`, Tests.
  Tests: Spec-Antwortbeispiel validiert; `subcollections` immer vorhanden; Serialisierung mit Doppelpunkt-Schlüsseln;
  `generation` ohne große Daten (nur Zählungen).

- [x] **T2.4 Baum und Keys** [P]
  Dateien: `app/domain/tree.py`, `app/domain/keys.py`, Tests.
  Tests: `make_key("Optik", taken)` → `k-optik`; Umlaute → `k-waerme`; Kollision → `k-optik-2`; `walk`, `find(key)`,
  `path(key)`, `parent(key)`; Baum aus `current_tree` → keys bleiben, fehlende werden vergeben.

- [x] **T2.5 Formregeln**
  Dateien: `app/domain/shape_rules.py`, Tests.
  Tests: Einzelkind → `SHAPE_SINGLE_CHILD`; Tiefe > `shape.depth` → `SHAPE_DEPTH`; Hauptebene außerhalb der Spanne → `SHAPE_WIDTH`;
  doppelte Geschwistertitel → `DUPLICATE_TITLE` und Zusammenlegen nur, wenn beide aus dem LLM stammen; Kurztitel > 20
  Zeichen → an Wortgrenze gekürzt, nur Buchstaben/Ziffern/Leerzeichen, eindeutig unter Geschwistern.

- [x] **T2.6 Änderungsoperationen**
  Dateien: `app/domain/ops.py`, Tests.
  Tests je `op`: add (Wurzel und Kind), remove (Inhalte → `unassigned` mit `no_matching_node`), rename, edit, move (Zyklus →
  abgelehnt), merge (Inhalte vereint, key des ersten bleibt), split (markiert für Schritt, keine Logik hier); unbekannter key →
  abgelehnt; locked oder Nachfahre eines locked → abgelehnt; Ergebnis listet `applied` mit `from`.

- [x] **T2.7 Status gegen Vorversion** [P]
  Dateien: `app/domain/diff.py`, Tests.
  Tests: neuer key → `new`; gleiche Felder → `unchanged`; Titel/Beschreibung geändert → `changed`; anderer Elternknoten → `moved`;
  gegen Ordner: Ordnerpfad gleich → `unchanged`, umbenannt → `changed`, verschoben → `moved`.

- [x] **T2.8 Abschluss und Metadaten**
  Dateien: `app/pipeline/finalize.py`, Tests.
  Tests: `frame` landet in jedem Knoten (`ccm:taxonid`, `ccm:educationalcontext`, `ccm:educationalintendedenduserrole`),
  außer der Knoten ist enger gefasst; `version` v1 bzw. `based_on`+1; Feedback-Verlauf angehängt; `generator_version` aus
  `pyproject.toml`; `model` aus dem Backend; `inputs`-Zählungen.

- [x] **T2.9 Endpunkt, Orchestrator-Gerüst, Schemata**
  Dateien: `app/api/v2.py`, `app/pipeline/orchestrator.py`, `app/pipeline/run_context.py`, `scripts/export_schemas.py`,
  `docs/schemas/*.json`, Tests.
  Tests: Endpunkt mit Fake-Strategie liefert gültige Antwort; Frist abgelaufen → Teilergebnis + `DEADLINE_EXCEEDED`;
  Test prüft, dass `docs/schemas/*.json` aktuell sind (Export im Test vergleichen); OpenAPI-Beispiele je Use Case vom kürzesten bis vollständigen.

**Abweichungen in Phase 2:**
- Zusätzlicher Warncode `DESCRIPTION_MISSING` (Knoten ohne Beschreibung), getrennt von `DESCRIPTION_LENGTH`.
- `ChildRange.min` ≥ 2 (nie genau ein Kind); `MainRange.min` ≥ 1.
- Eingabeprüfungen liegen in `app/pipeline/input_checks.py` (brauchen Settings), nicht im Schema.
- Strategien registrieren sich in `orchestrator.STRATEGIES`; fehlende Use Cases antworten bis Phase 4 mit 501.
- `inputs.folders` zählt Ordner der obersten Ebene (wie im Spec-Beispiel).
- Fund: Statusvergleich gegen Ordner hätte nach Umbenennen eines Ordners alle Unterordner als `moved` markiert;
  Regressionstest und Korrektur (Vergleich mit dem Herkunftspfad des Elternknotens).
- Schema-Export: `uv run python -m scripts.export_schemas`.

## Phase 3 – topic, folders, refine, Zuordnung

Schritt 0: `/better-coding-workflow` laden.

- [x] **T3.1 Schritt plan_structure**
  Dateien: `app/pipeline/steps/plan_structure.py`, `app/prompts/plan_structure.md`, Tests.
  Ausgabe-Modell: `{order, levels[], rationale, main_topics:[{title, shorttitle, children:[{title, shorttitle}]}]}`.
  Tests (Fake-LLM): Prompt enthält Labels aus `frame`, `hints.include/exclude/context`, `extra_topics`; mit `hints.order` →
  `source:"hint"` und Prompt nennt es als Vorgabe; Spanne aus `shape` im Prompt; Ergebnis mit zu vielen Hauptthemen → auf
  `max` gekürzt + Warnung.

- [x] **T3.2 Schritt expand_branch**
  Dateien: `app/pipeline/steps/expand_branch.py`, `app/prompts/expand_branch.md`, Tests.
  Tests: ein Aufruf je Hauptast, parallel; **Cache-Invariante**: alle Ast-Prompts identisch bis zum Ast-Block, System-Nachricht
  identisch; fehlschlagender Ast → Knoten bleibt ohne Kinder/Beschreibung, `BRANCH_FAILED` mit key; Tiefe 1 → kein Ast-Aufruf,
  stattdessen describe_nodes.

- [x] **T3.3 Strategie topic**
  Dateien: `app/pipeline/strategies/topic.py`, Tests.
  Tests: `extra_topics: general` vorn, `methodology` hinten (deterministisch eingefügt, Beschreibung per Ast-Aufruf);
  `structure`-Items → Kontextblock, daraus entstandene Knoten `suggested` (Fake-LLM markiert Quelle); Ende-zu-Ende mit
  Fake-LLM: 8×5×3 erzeugt ≤ 10 Aufrufe (gezählt).

- [x] **T3.4 entfällt** (E7: alter Endpunkt bleibt beim alten Ablauf).

- [x] **T3.5 Schritt describe_nodes** [P]
  Dateien: `app/pipeline/steps/describe_nodes.py`, `app/prompts/describe_nodes.md`, Tests.
  Tests: Batches à 30 Knoten; Eingabe je Knoten: Pfad, Titel, optional Inhaltstitel/-keywords bzw. Abschnittsauszug (gekürzt
  auf 1.500 Zeichen); Antwort mit unbekanntem key ignoriert + Warnung; fehlende Beschreibung → Warnung statt Platzhaltertext.

- [x] **T3.6 Strategie folders**
  Dateien: `app/pipeline/strategies/folders.py`, `app/pipeline/steps/improve_folders.py`, `app/prompts/improve_folders.md`, Tests.
  Tests: ohne `improve` 0 Strukturaufrufe, Baum gleich Ordnern, `origin.folder.path`, Inhalte aus Ordnern mit Konfidenz 1.0;
  Ordner „Neuer Ordner (2)“ mit `improve` → Fake-LLM liefert rename/move → als `changes` mit `from:"service"`; ohne `improve`
  bleiben Namen unverändert, auch generische.

- [x] **T3.7 Schritt assign_contents**
  Dateien: `app/pipeline/steps/assign_contents.py`, `app/prompts/assign_contents.md`, Tests.
  Tests: Batches à 40; Baum kompakt als `key: Pfad`; `min_confidence` → darunter `unassigned/low_confidence`; `multi_assign=false`
  → nur bester Knoten; `hints.exclude`-Treffer → `excluded`; unbekannter key → verworfen + `ASSIGN_FAILED`; Batch-Fehler →
  betroffene Items `unassigned/no_matching_node` + Warnung; `nodeId` unverändert durchgereicht.

- [x] **T3.8 refine**
  Dateien: `app/pipeline/steps/interpret_feedback.py`, `app/prompts/interpret_feedback.md`, Ergänzung `orchestrator.py`, Tests.
  Tests: nur `changes` → 0 Interpretationsaufrufe; Text → Fake-LLM liefert ops → angewendet, `changes[].from:"feedback_text"`;
  Text und changes → changes zuerst, widersprechende Text-ops abgelehnt; unklarer Text → `questions`, Baum unverändert;
  locked-Knoten unverändert inkl. Kinder; unveränderte Knoten behalten keys und `status:"unchanged"`; `assign_only` → keine
  Strukturänderung, nur neue Zuordnungen; fehlende Vorgaben aus `current_tree.generation`; Version `v1` → `v2`, `based_on: v1`.

**Abweichungen in Phase 3:**
- Neu `app/pipeline/context_block.py`: Anfragekontext einmal je Anfrage im Orchestrator gebaut (`RunContext.context`),
  unbekannte Vokabular-URIs → `VOCAB_UNKNOWN`.
- `StrategyResult` in `app/pipeline/result.py`; refine ist eine eigene Strategie (`strategies/refine.py`), unabhängig vom Use Case.
- Zuordnung läuft im Orchestrator nach jeder Strategie für noch nicht platzierte Inhalte.
- Neue Warncodes: `DESCRIBE_FAILED`; Kürzungen der Äste getrennt als `SHAPE_DEPTH`/`SHAPE_WIDTH`.
- `split` mit eigenem Schritt `steps/split_node.py` (2–4 Teile, Kinder und Inhalte deterministisch verteilt).
- Neu `app/pipeline/effective.py`: nicht gesendete Vorgaben aus `current_tree.generation`.

## Phase 4 – document, contents, Referenzen

Schritt 0: `/better-coding-workflow` laden.

- [x] **T4.1 Gliederung aus Markdown** [P]
  Dateien: `app/pipeline/inputs/outline.py`, Tests mit Fixture `tests/fixtures/lehrplan_physik_auszug.md`.
  Tests: `#`–`######` → Abschnitte mit id `s<n>`, Ebene, Titel, Seite; alle vier Seitenmarkenformate aus E11; Text unter
  Überschrift als Auszug; Dokument ohne Überschriften → ein Abschnitt; Code-Blöcke ignoriert.

- [x] **T4.2 Referenzen laden** [P]
  Dateien: `app/pipeline/inputs/refs.py`, Tests (httpx MockTransport).
  Tests: Host nicht in Allowlist → `REF_NOT_ALLOWED`; `http://` → abgelehnt; > `REF_MAX_BYTES` → abgebrochen; Timeout →
  `REF_FAILED`; Weiterleitung auf fremden Host → abgelehnt; `items_ref` liefert Liste von Items.

- [x] **T4.3 Strategie document**
  Dateien: `app/pipeline/strategies/document.py`, `app/pipeline/steps/map_outline.py`, `app/prompts/map_outline.md`, Tests.
  Tests: Gliederung geht kompakt (id, Ebene, Titel, Seite) ins LLM, nicht der Volltext; Ausgabe verweist nur auf vorhandene
  Abschnitts-ids (unbekannte verworfen + Warnung); `origin: {type: document, id, section, page}`; `hints.exclude:["Wahlpflicht"]`
  im Prompt; Beschreibungen mit Abschnittsauszug; Strukturdokument ohne `content` wird nicht zugeordnet, mit `content` schon;
  mehrere Strukturdokumente → zusammengeführte Gliederung mit Dokument-id je Abschnitt.

- [x] **T4.4 Strategie contents**
  Dateien: `app/pipeline/strategies/contents.py`, `app/pipeline/steps/group_contents.py`, `app/prompts/group_contents.md`, Tests.
  Tests: nur `structure`-Items bilden Gruppen, `content`-only (Sammelmappe) wird nur zugeordnet; `topic` als Eingrenzung im Prompt;
  > 300 Items → Stichprobe 300 mit vollständigen Metadaten + Titelliste aller; Gruppen → Knoten mit `origin: cluster`;
  Zuordnung mit Konfidenz über T3.7; fachfremde Items → `off_topic`.

**Abweichungen in Phase 4:**
- Seitenmarken: zusätzlich `<!-- PageBreak -->` (Azure); Format bleibt im Team zu klären.
- Allowlist-Regeln: exakter Host oder `.domain` für Subdomains; Weiterleitungen werden nie verfolgt.
- Neue Codes: `REF_TOO_LARGE`, `REF_INVALID`, `SECTION_UNKNOWN`, `OUTLINE_TRUNCATED`, `ITEMS_SAMPLED`.
- `items_ref` bis 5.000 Einträge; nach dem Laden erneute Prüfung ohne Inline-Grenze.
- Gruppen in `contents` liefern Beschreibungen gleich mit (kein extra describe-Aufruf); Knotenumwandlung mit `expand_branch` geteilt.

## Phase 5 – Betrieb und Übergabe

Schritt 0: `/better-coding-workflow` laden.

- [ ] **T5.1 Dockerfile und Compose**
  Multi-Stage (uv-Build → `python:3.13-slim`), Nutzer `app` (uid 10001), nur `/tmp` beschreibbar, `CMD gunicorn -c gunicorn.conf.py app.main:app`,
  `EXPOSE 8000 9000`. Compose mit beiden Ports und `.env`.
  Verifikation: falls Docker verfügbar `docker build` + `docker run` + `curl :8000/health :9000/metrics`; sonst Hinweis im Bericht.

- [ ] **T5.2 Helm-Chart**
  `deploy/helm/<dienst-id>`: Deployment (zwei Ports, Liveness intern `/health`, Readiness öffentlich `/health`), Service,
  optional Ingress, NetworkPolicy (Standard aus), ServiceMonitor, PrometheusRule (Fehlerrate LLM, P90 > Frist, Warnungsrate),
  HPA optional, Pod Security restricted, `values.yaml` mit `## @param` je Wert, Secrets nur als Namen.
  Tests: `tests/test_chart_version.py` (`Chart.version == appVersion == pyproject version`); `helm lint --strict`, `helm template`.

- [ ] **T5.3 CI**
  `.gitlab-ci.yml`: ruff, pytest, Build mit Tag `X.Y.Z` und Branch-Slug, Chart-Lint; GitHub Actions `ci.yml`: ruff, pytest, helm lint.

- [ ] **T5.4 Doku und Übergabe**
  `README.md` (Zweck, Start, Env, Modi, Tests), `docs/api.md` (Aufrufe je Use Case), `docs/steckbrief.md` (Vorlage nach Leitfaden, Ressourcen-Messanleitung),
  `scripts/loadtest.py`, `scripts/probe_llm.py` (prüft `response_format`, `reasoning_effort`, `prompt_cache_key` gegen eine Route),
  `CHANGELOG.md` mit Verhaltensänderung aus E3, Version `2.0.0` in `pyproject.toml`.

## Phase 6 – Prüfen

- [ ] **T6.1 Review** (`/better-coding-review`): Stufe 1 gegen dieses Dokument und die Spec, Stufe 2 Codequalität.
- [ ] **T6.2 Audit** (`/better-coding-audit`): Auth/Token-Fluss, SSRF, Logging von Geheimnissen, Eingabegrenzen.
- [ ] **T6.3 Verify** (`/better-coding-verify`): volle Suite, Ende-zu-Ende gegen `tests/stub_openai.py` mit gunicorn, Anforderungs-Checkliste
  Zeile für Zeile, Bericht.

# Verifikationsplan

| Anforderung | Nachweis |
|---|---|
| Altes Format unverändert | `tests/api/test_legacy_contract.py` |
| Vier Use Cases + refine nach Spec | Spec-Beispiele als Fixtures, je Use Case Ende-zu-Ende-Test mit Fake-LLM |
| Keine stillen Lücken | Tests mit fehlschlagendem Ast/Batch/Frist → `warnings` |
| Weniger Aufrufe | Aufrufzähler im Test 8×5×3 ≤ 10 |
| Prompt-Caching | Invarianten-Tests System-Nachricht und Ast-Präfix; Usage-Feld `cached_tokens` |
| Modus-Erkennung, Auth | Tabellentest E3 |
| Token nie geloggt | Test fängt Logs ab und sucht nach `bdt_` |
| Leitfaden Ports/Proben/Metriken | Internal-Server-Tests, gunicorn-Smoke-Test |
| SSRF-Schutz | `refs`-Tests |
| Helm | `helm lint --strict`, `helm template`, Versionstest |
| Regression | gesamte Suite grün, ruff sauber |

# Folgearbeiten (nicht Teil dieses Plans)

- Embedding-Clustering für große `contents`-Mengen über die b-api (`embeddings`).
- OTel-Spans exportieren.
- Kestra-Flow für Läufe, die das Delegations-Token überdauern.
- Spannen in `shape` je Sammlungsart vorbelegen (offener Spec-Punkt).
- MEM-Kennungen in `origin` bei Lehrplänen (offener Spec-Punkt).
