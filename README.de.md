# topic-tree (Themenbaum-Dienst)

> 🇬🇧 English version: [README.md](README.md) · Übersicht aller Dokumente: [docs/README.md](docs/README.md)

FastAPI-Dienst, der mit einem LLM Sammlungsstrukturen für edu-sharing („Themenbäume“) erzeugt: aus einem Thema, einem Strukturdokument (etwa einem Lehrplan), hochgeladenen Ordnern und Dateien oder aus unstrukturierten Inhalten. Entwürfe lassen sich mit Rückmeldungen schrittweise verfeinern, Inhalte werden den Knoten mit Konfidenzwerten zugeordnet. Ein bestehender Baum, auch einer aus dem Repository, lässt sich nur mit Inhalten füllen (Struktur, Properties und `nodeId` bleiben, wie sie sind), und einzelne Knoten können mit dem ganzen Baum als Kontext eine neue Beschreibung erhalten.

- **`POST /v2/topic-tree`** – aktuelle v2-API; `/docs` erklärt Use Cases, Kombinationen und Optionen und bietet zu jedem ein Beispiel im Auswahlfeld „Examples“ ([API-Leitfaden](docs/de/api.md), [Datenformat](docs/de/datenformat.md), [JSON-Schemas](docs/schemas/), [Beispiel-Anfragen](docs/examples/))
- **`POST /generate-topic-tree`**, **`POST /generate-collection-description`** – formatstabile v1-Endpunkte (nutzen inzwischen dieselbe Anmeldung und Backend-Auswahl für eigenständigen Betrieb und b-api wie v2); neue Aufrufer beschreiben Sammlungen mit der `describe`-Änderung von v2 (siehe Use Case 7)
- **Eingebaute Test-Oberfläche** unter `/ui/` (optional, schaltbar über `UI_ENABLED`)
- **Betrieb & Übergabe**: [Betriebshandbuch mit Runbook](docs/de/betrieb.md) · [Steckbrief](docs/de/steckbrief.md)
- **Messungen & Entwurf**: [Vergleich v1 und v2](docs/measurements/2026-11-25-v1-vs-v2-comparison.md) · [Last- und Token-Messung v2](docs/measurements/2026-11-24-openai-gpt-6-luna.md) · [Entwurfsplan](docs/plans/2026-11-24-topic-tree-v2.md)

## Funktionsweise

```text
request → input & cap checks → resolve refs (allow-listed) → strategy per use case
        → assign contents → optional auto_metadata (label → URI)
        → dedup, short titles, keys, status, shape & quality checks → JSON response
```

- **`topic`**: Erzeugt das vollständige Titel-Grundgerüst über alle angeforderten Ebenen in einem einzigen LLM-Aufruf, entfernt doppelte Titel deterministisch und beschreibt alle Knoten parallel in ausgewogenen Batches mit bis zu 10 Knoten (jeder Batch erhält die ganze Gliederung im Prompt-Cache-Präfix, damit sich die Knoten klar voneinander abgrenzen). Zusätzliche Themen auf Ebene 1 (`extra_topics`: `"general"`, `"methodology"`) zählen zur Spanne `main_topics` auf Ebene 1.
- **`document`**: Liest Markdown-Überschriften und Seitenmarken deterministisch aus, bildet die Gliederung als Baum mit `origin.document` (`section`, `page`) ab und schreibt Knotenbeschreibungen aus Abschnittsauszügen (ist das LLM nicht erreichbar, dienen deterministisch die Überschriften des Dokuments als Rückfall, mit der Warnung `LLM_DEGRADED`).
- **`folders`**: Behält die hochgeladene Ordnerhierarchie bei (`origin.folder`), benennt mit `options.improve=true` optional um, führt zusammen oder verschiebt (jede Änderung steht in `changes[]`) und arbeitet ohne LLM eingeschränkt weiter (`LLM_DEGRADED`).
- **`contents`**: Bildet Themengruppen aus einer geschichteten Stichprobe der Inhalte (`origin.cluster`), entfernt doppelte Gruppentitel und ordnet jeden Inhalt mit Konfidenz zu.
- **`mode: refine`**: Setzt zuerst die gezielten Änderungen aus `feedback.changes` um, dann den Freitext aus `feedback.text`; Äste in `feedback.locked` bleiben geschützt. Mit `options.assign_only=true` werden nur neue Inhalte in den bestehenden Baum einsortiert, und jeder Knoten kommt so zurück, wie er gesendet wurde; die Änderung `describe` schreibt Beschreibungen ausgewählter Knoten mit dem Baum als Kontext neu.
- **Prompt-Caching**: Alle Prompts liegen in `app/prompts/`; `system.md` ist für jeden LLM-Aufruf strikt gleich.

## Was sich von v1 zu v2 geändert hat

Der ursprüngliche v1-Dienst (archiviert im Branch `backup_old`; die Antwortschemas bleiben unter `/generate-topic-tree` und `/generate-collection-description` erhalten) war eng an einen einzigen Betriebsweg und eine feste Generierungskaskade gebunden. Version 2 baut sowohl die Laufzeitarchitektur als auch die Pipeline zur Baumerzeugung neu auf:

| Bereich | Alt: v1 (`/generate-topic-tree`, `/generate-collection-description`) | Aktuell: v2 (`POST /v2/topic-tree`) |
|---|---|---|
| **Betrieb & LLM-Routing** | Ursprünglich fest auf den Betrieb hinter dem b-api-Router ausgelegt (`/api/v1/llm/router/`, feste Route `topic-tree-generator`), mit verpflichtendem Bearer-Token des Aufrufers. *(Hinweis: Die v1-Endpunkte unterstützen inzwischen auch eigenständig `OPENAI_API_KEY` / `SERVICE_API_KEYS`, damit `/docs` ohne b-api funktioniert; hinter der b-api bleibt die Router-Kompatibilität erhalten.)* | Läuft hinter der b-api (`Bearer bdt_…`), eigenständig gegen OpenAI oder jede OpenAI-kompatible API (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`) oder im Doppelmodus `auto` mit optionalen `SERVICE_API_KEYS`. Hinter der b-api werden **sowohl** Router-Routen (`B_API_ROUTE`) als auch direkte Aufrufe eines einzelnen Modells beim Provider (`B_API_MODEL` + `B_API_MODEL_PROVIDER`) unterstützt, ohne von einer Router-Route abzuhängen. |
| **Use Cases & Abläufe** | Ein einziger starrer Ablauf: Themenkaskade über 3 Ebenen (`main → sub → curriculum`), nur aus einem Thema als Text. Keine schrittweise Bearbeitung, kein Auslesen von Dokumenten, kein Einsortieren von Inhalten. | **4 kombinierbare Use Cases** (`topic`, `document`, `folders`, `contents`) + schrittweises **`mode: refine`** (`feedback.changes`, Freitext `feedback.text`, gesperrte Äste über `feedback.locked`, `options.assign_only`) + Zuordnung von Inhalten (`items` mit durchgereichter `nodeId` und Konfidenzwerten). |
| **Duplikatvermeidung & Tempo** | Hauptthemen, Unterthemen und Lehrplanthemen entstanden in getrennten LLM-Aufrufen je Ast, ohne Blick auf die Geschwister im ganzen Baum. Das führte leicht zu doppelten Titeln über Äste hinweg und zu langsamen mehrstufigen Kaskaden. | **Gerüst zuerst**: plant die vollständige mehrstufige Gliederung in einem LLM-Aufruf, entfernt Duplikate deterministisch (`eliminate_generated_duplicates`) und erzeugt Beschreibungen und Schlagworte in **parallelen, ausgewogenen Batches zu 10 Knoten**, die alle die ganze Gliederung im Prompt-Cache-Präfix erhalten. |
| **Vokabulare & Metadaten** | Übernahm die vom Aufrufer gesendeten `discipline_uri` / `educational_context_uri` unverändert auf alle Knoten; keine Klassifikation je Knoten, feste Rolle Lehrkraft. | Mitgelieferter Offline-**Snapshot der OEH-SkoHub-Vokabulare** (`discipline`, `educationalContext`, `intendedEndUserRole`). Mit `options.auto_metadata=true` werden Knoten über ein striktes JSON-Schema exakten deutschen Labels zugeordnet und diese deterministisch auf URIs abgebildet. |
| **Antwort- & Fehlervertrag** | Eingefrorene v1-Antwort (`metadata` + `collection` mit `cm_title` usw., oder reiner `str`) und FastAPI-Fehler `{"detail": "…"}`, damit bestehende edu-sharing-Anbindungen ohne Anpassung weiterlaufen. | Umfangreiche `TopicTreeResponseV2` (`collection` mit stabilem `key`/`status`/`origin`/`items`, `unassigned`, `changes`, `warnings`, `questions`, `usage`, `metadata.generation`) und einheitliche Fehler `{"error": {"code", "message", "trace_id"}}` ohne rohen Ausnahmetext. |

---

## Installation & Docker

### Variante A: Docker Compose – lokal bauen, direkte Ports (am schnellsten für lokalen Betrieb oder Docker auf einem Host)

Nutzt [`docker-compose.build.yml`](docker-compose.build.yml) (baut das mehrstufige Image auf Basis `python:3.13-slim`, ~193 MB, ohne Root-Rechte mit `uid=10001`, schreibgeschütztes Root-Dateisystem, öffnet `:8000` öffentlich und `:9000` intern).

```shell
git clone https://github.com/janschachtschabel/topic-tree-generator-11-2026.git
cd topic-tree-generator-11-2026
cp .env.example .env
# .env bearbeiten: OPENAI_API_KEY setzen (eigenständig) oder B_API_BASE_URL + B_API_ROUTE (bzw. B_API_MODEL) konfigurieren
docker compose -f docker-compose.build.yml up --build -d
```

Laufenden Container prüfen:

```shell
curl -s http://localhost:8000/health     # {"status":"ok","vocab_snapshot":"..."}
curl -s http://localhost:9000/ready      # 200, wenn LLM-Zugangsdaten oder b-api-Modus bereit sind
curl -s http://localhost:9000/metrics    # Prometheus-Metriken (nur interner Port)
```

Die eingebaute Test-Oberfläche liegt unter `http://localhost:8000/ui/` (die OpenAPI-Doku unter `http://localhost:8000/docs`).

**Andere Ports (mehrere APIs auf einem Host):** Sind `8000`/`9000` schon belegt, andere Ports in `.env` setzen;
beide Compose-Dateien nutzen sie für den Container *und* die Host-Seite, Traefik-Routing und Healthcheck ziehen mit:

```shell
# .env
PUBLIC_PORT=8010
INTERNAL_PORT=9010
```

Dann liegt die Oberfläche unter `http://localhost:8010/ui/` und `/ready` unter `http://localhost:9010/ready`. Die beiden
Ports müssen sich unterscheiden und in `1–65535` liegen; im Container (ohne Root-Rechte) Ports `≥ 1024` wählen.

### Variante B: Docker Compose – fertiges Image hinter Traefik (Compose aus URL / Reverse Proxy)

Nutzt [`docker-compose.yml`](docker-compose.yml) mit Traefik-HTTPS-Labels; beim ersten Start ist keine Umgebungsvariable Pflicht:

1. Repository mit `docker-compose.yml` bereitstellen (startet sauber mit den Standardwerten aus `.env.example`; kein externes Docker-Netz nötig, `TRAEFIK_NETWORK` wird automatisch angelegt bzw. genutzt).
   Ohne Domain ist der Dienst direkt unter `http://<server-ip>:18000/` erreichbar (Oberfläche: `/ui/`). Ist `18000`
   belegt, den Host-Port mit `HOST_PORT` ändern.
2. In `.env` einstellen:
   - LLM-Zugangsdaten: `OPENAI_API_KEY=<your-key>` (eigenständig) **oder** `SERVICE_MODE=bapi` + `B_API_BASE_URL` / `B_API_ROUTE`
   - `SERVICE_API_KEYS=<secret>` **zusammen mit dem LLM-Schlüssel**: Der direkte Port ist öffentlich und unverschlüsselt,
     ohne Dienst-Schlüssel kann jeder, der ihn findet, auf Kosten des LLM-Kontos Bäume erzeugen (die Test-Oberfläche hat
     dafür ein Token-Feld).
   - Optional zur Härtung: `UI_ENABLED=false`
3. Später mit Domain: `DOMAIN=trees.example.org` (nur der Hostname, **ohne** `https://`, Pfad oder Port), den
   DNS-A/AAAA-Eintrag auf den Host zeigen lassen und neu bereitstellen. Traefik terminiert TLS und leitet HTTPS auf
   Container-Port `8000`; Port `9000` bleibt rein intern. Danach `HOST_BIND=127.0.0.1` setzen, um den unverschlüsselten
   direkten Port zu schließen.

Statt `:latest` ein bestimmtes Release-Tag festlegen (für Staging und Produktion empfohlen):

```shell
IMAGE=ghcr.io/janschachtschabel/topic-tree-generator-11-2026:2.2.0 docker compose up -d
```

### Variante C: Kubernetes / Helm-Chart (`deploy/helm/topic-tree`)

Ein produktionsreifes Helm-Chart (`version` = `appVersion` = `2.2.0`, ohne Root-Rechte mit `uid=10001`, `readOnlyRootFilesystem: true`, `Service` mit zwei Ports `:8000` / `:9000`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `HPA`, `PodDisruptionBudget`) liegt unter [`deploy/helm/topic-tree/`](deploy/helm/topic-tree/) und wird zu jedem Release-Tag `vX.Y.Z` als OCI-Artefakt veröffentlicht (Vorlage für die b-api-Route: [`deploy/b-api/route-topic-tree-generator.json`](deploy/b-api/route-topic-tree-generator.json)):

```shell
# Aus dem veröffentlichten OCI-Helm-Chart installieren (Tag v2.2.0)
helm upgrade --install topic-tree \
  oci://ghcr.io/janschachtschabel/topic-tree-generator-11-2026/charts/topic-tree \
  --version 2.2.0 \
  --set image.repository=ghcr.io/janschachtschabel/topic-tree-generator-11-2026 \
  --set image.tag=2.2.0 \
  --set config.bApiBaseUrl=https://b-api.staging.openeduhub.net \
  --set config.bApiRoute=topic-tree-generator

# Oder direkt aus dem lokalen Chart im Repository installieren bzw. rendern
helm upgrade --install topic-tree ./deploy/helm/topic-tree -f values-custom.yaml
```

Hinter der b-api braucht das Chart kein Secret. Was das Plattform-Team einrichten muss (Proxy-Eintrag und Route in der
b-api, NetworkPolicy-Partner und Egress, Monitoring-Labels), die Prüfung nach der Installation, Upgrades, Rollback und
ein Runbook für jeden Alarm stehen im [Betriebshandbuch](docs/de/betrieb.md).

### Variante D: Lokale Python-Entwicklung (ohne Docker)

Benötigt **Python 3.13** und [uv](https://docs.astral.sh/uv/):

```shell
uv sync
cp .env.example .env          # OPENAI_API_KEY oder B_API_DEV_KEY setzen
uv run python -m app          # öffentliche API :8000 (/docs, /ui/), intern :9000 (/health, /ready, /metrics)
```

Produktionsnaher Prozessmanager: `uv run gunicorn -c gunicorn.conf.py app.main:app`.

---

## Konfiguration (Umgebungsvariablen)

Alle Einstellungen werden aus Umgebungsvariablen oder `.env` gelesen und haben Standardwerte (siehe [`.env.example`](.env.example)). Leere Zeichenketten in `.env` gelten als nicht gesetzt.

### Betriebsmodus & Anmeldung

| Variable | Standard | Beschreibung |
|---|---|---|
| `SERVICE_ID` | `topic-tree` | Kennung des Dienstes in Logs, Metriken und Cache-Schlüsseln. |
| `SERVICE_MODE` | `auto` | `auto`: `Authorization: Bearer bdt_…` läuft über die b-api, alles andere eigenständig. `bapi`: nur Delegations-Tokens. `standalone`: ruft die b-api nie auf. |
| `SERVICE_API_KEYS` | *(leer)* | Kommagetrennte Bearer-Schlüssel für die Anmeldung im eigenständigen Betrieb. Leer = offen (eigenständig keine Anmeldung nötig). Im Modus `auto` wird ein `bdt_…`-Token nicht gegen diese Schlüssel geprüft: Die b-api prüft es beim ersten LLM-Aufruf, und Arbeit ohne LLM (gezielte Änderungen, Downloads von `ref` aus der Allowlist) geschieht vorher. Eine öffentliche Instanz, die nur Dienst-Schlüssel annehmen soll, läuft mit `SERVICE_MODE=standalone`. |

### Docker & Reverse Proxy (`docker-compose.yml`)

| Variable | Standard | Beschreibung |
|---|---|---|
| `DOMAIN` | *(leer)* | Öffentlicher Hostname für Traefik (`Host(...)`), z. B. `trees.example.org` (ohne Schema, Port oder Pfad). |
| `IMAGE` | `ghcr.io/...:latest` | Referenz auf das fertige Image für `docker-compose.yml`. |
| `TRAEFIK_NETWORK` | `topic-tree-web` | Name des Docker-Netzes, das Traefik und der Dienst-Container nutzen. |
| `TRAEFIK_ENTRYPOINT` | `websecure` | Name des Traefik-Entrypoints für HTTPS-Routing. |
| `TRAEFIK_CERTRESOLVER` | `letsencrypt` | Name des TLS-Zertifikat-Resolvers in Traefik. |
| `HOST_PORT` | `18000` | Host-Port von `docker-compose.yml` für den direkten Zugriff ohne Domain (`http://<server-ip>:18000/`). |
| `HOST_BIND` | `0.0.0.0` | Host-Schnittstelle für `HOST_PORT`; `127.0.0.1` setzen, sobald `DOMAIN` über Traefik ausgeliefert wird, um den direkten Weg zu schließen. |
| `TRAEFIK_ROUTER` | `topic-tree` | Name von Router und Service in Traefik. Diese Namen gelten in Traefik global: Jede weitere Instanz auf demselben Host braucht einen eigenen Wert (z. B. `topic-tree-staging`), sonst verteilt Traefik Anfragen auf beide Container. |
| `PUBLIC_PORT` | `8000` | Port für öffentliche API und Oberfläche; Docker Compose veröffentlicht denselben Port auf dem Host (anderer Port je Dienst). |
| `INTERNAL_PORT` | `9000` | Interner Port für `/health`, `/ready` und Prometheus-`/metrics` (nicht öffentlich freigeben); muss sich von `PUBLIC_PORT` unterscheiden. |
| `WEB_CONCURRENCY` | `2` | Anzahl der Gunicorn-Worker-Prozesse (~125 MiB RAM im Leerlauf bei 2 Workern). |

### LLM-Backend (b-api-Router & eigenständig mit OpenAI)

| Variable | Standard | Beschreibung |
|---|---|---|
| `B_API_BASE_URL` | `https://b-api.staging.openeduhub.net` | Basis-URL des b-api-Gateways (der Router-Pfad `/api/v1/llm/router/` wird automatisch angehängt). |
| `B_API_ROUTE` | *(leer)* | Variante 1: Routenname beim LLM-Router der b-api (`/api/v1/llm/router/`), z. B. `topic-tree-generator`. **Hat Vorrang, sobald gesetzt** (alter Alias: `LLM_MODEL`). Die eingefrorenen v1-Endpunkte nutzen `topic-tree-generator`, wenn der Wert leer ist. |
| `B_API_MODEL` | *(leer)* | Variante 2: ein einzelnes Modell (z. B. `gpt-6-luna`), nur genutzt, solange `B_API_ROUTE` leer ist. Es geht an den Provider-Endpunkt `/api/v1/llm/<B_API_MODEL_PROVIDER>/`. Alternativ nimmt der Router `provider/model` als Routennamen an (`B_API_ROUTE=openai/gpt-6-luna`). Ohne Route und Modell antworten b-api-Anfragen mit `503 LLM_NOT_CONFIGURED`. |
| `B_API_MODEL_PROVIDER` | `openai` | Provider von `B_API_MODEL` bei der b-api: `openai` oder `academiccloud` (der Alias `B_API_PROVIDER` nimmt auch `router` an). |
| `B_API_DELEGATION_HEADER` | *(leer)* | Eigener Header-Name, falls der b-api-Proxy das Delegations-Token außerhalb von `Authorization` sendet. |
| `B_API_DEV_KEY` | *(leer)* | Lokaler Entwicklerschlüssel für direkte Tests gegen die b-api-Staging-Umgebung, wenn `OPENAI_API_KEY` nicht gesetzt ist. |
| `OPENAI_API_KEY` | *(leer)* | API-Schlüssel für eigenständigen Betrieb mit OpenAI oder OpenAI-kompatiblen Endpunkten. |
| `OPENAI_BASE_URL` | *(leer)* | Optionale eigene Basis-URL für OpenAI-kompatible Anbieter. |
| `OPENAI_MODEL` | `gpt-6-luna` | Modellname im eigenständigen Betrieb. |

### LLM-Parameter, Parallelität & Kostengrenzen

| Variable | Standard | Beschreibung |
|---|---|---|
| `LLM_PARAM_FAMILY` | `common` | `common` (`max_completion_tokens` + `reasoning_effort`), `gpt5` (begrenzt das Reasoning auf `low`) oder `classic` (`max_tokens`). |
| `LLM_REASONING_EFFORT` | `none` | Reasoning-Aufwand: `none`, `minimal` oder `low` (fest auf höchstens `low` begrenzt, wegen Latenz und Kosten). |
| `LLM_OUTPUT_MODE` | `json_schema` | Modus für strukturierte Ausgabe: `json_schema` (strikt), `json_object` oder `prompt`. |
| `LLM_SEND_PROMPT_CACHE_KEY` | `auto` | `prompt_cache_key` senden: `auto` (an für OpenAI, aus für die b-api), `true` oder `false`. |
| `LLM_MAX_CONCURRENCY` | `20` | Höchstzahl paralleler LLM-Aufrufe je Worker-Prozess (**nur per Umgebungsvariable**, nie über API oder Oberfläche einstellbar). |
| `MAX_TREE_DEPTH` | `3` | Feste Obergrenze (`1–4`) für `shape.depth`; höhere Anfragen scheitern mit `422 SHAPE_LIMIT_EXCEEDED`. |
| `MAX_NODES_PER_LEVEL` | `20` | Feste Obergrenze (`2–20`) für `shape.main_topics.max` und `shape.children.max` (`422 SHAPE_LIMIT_EXCEEDED`). |
| `LLM_TIMEOUT_SECONDS` | `120` | Zeitlimit je LLM-Aufruf in Sekunden (begrenzt durch die verbleibende Frist der Anfrage). |
| `LLM_MAX_RETRIES` | `3` | Wiederholungen des SDK bei vorübergehenden Fehlern der Gegenstelle (`429`, `5xx`). |
| `REQUEST_TIMEOUT_SECONDS` | `280` | Gesamtfrist einer synchronen Anfrage (Timeout von Reverse Proxy bzw. b-api auf ≥ `310s` setzen). |
| `LEGACY_MAX_RETRIES` | `4` | Anzahl der Wiederholungen für die eingefrorenen v1-Endpunkte (alter Alias: `MAX_RETRIES`). |

### Externe Referenzen (`items_ref`, `fulltext.ref`), Logging & Oberfläche

| Variable | Standard | Beschreibung |
|---|---|---|
| `REF_ALLOWED_HOSTS` | *(leer)* | Kommagetrennte Allowlist von HTTPS-Hosts für `ref`-URLs (`.example.org` erlaubt Subdomains). Leer = alle `ref`-URLs abgelehnt (Schutz vor SSRF). |
| `REF_MAX_BYTES` | `10485760` | Höchstgröße je referenzierter Ressource (10 MiB). |
| `REF_TIMEOUT_SECONDS` | `20` | Zeitlimit für den Download je `ref`-URL. |
| `ITEMS_INLINE_MAX` | `500` | Höchstzahl direkt mitgesendeter Inhalte je Anfrage (größere Mengen über `items_ref`, bis 5.000 Inhalte). |
| `MAX_REQUEST_BYTES` | `33554432` | Höchstgröße des Request-Bodys in Bytes (32 MiB); größere erhalten `413 REQUEST_TOO_LARGE`. |
| `LOG_LEVEL` | `INFO` | Log-Stufe (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `LOG_FORMAT` | `json` | `json` für Container- und Produktions-Logs, `text` für gut lesbare lokale Logs. |
| `UI_ENABLED` | `true` | Schaltet die eingebaute Test-Oberfläche unter `/ui/` ein (`true`) oder vollständig ab (`false`). |

---

## Eingebaute Test-Oberfläche (`/ui/`)

Der Dienst bringt eine selbst gehostete interaktive Test-Oberfläche mit (keine externen Skripte, keine Schriften oder CDNs von Dritten, keine Speicherung von Tokens, Oberfläche umschaltbar zwischen **DE / EN**, Deutsch als Standard).

- **Einschalten** (Standard in lokaler Entwicklung und Docker Compose): `UI_ENABLED=true` → erreichbar unter `http://localhost:8000/ui/` (`/ui` leitet auf `/ui/` weiter).
- **Abschalten** (für Produktion empfohlen; Standard im Helm-Chart): `UI_ENABLED=false` in `.env` oder der Container-Umgebung setzen. Alle Routen der Oberfläche (`/ui`, `/ui/`, `/ui/presets`, `/ui/assets/*`) antworten dann sofort mit **`404 Not Found`**. In `/openapi.json` erscheinen sie nie.
- **Funktionen**:
  - Navigation links nach Aufgabe (Thema, Dokument, Ordner, Inhalte gruppieren, Inhalte einsortieren, Baum ändern); jede
    Aufgabe zeigt nur ihre Felder und eine Gruppe „Zusätzlich einbeziehen“ für Kombinationen (Materialien, die die
    Struktur prägen, Materialien, die nur einsortiert werden, ein Strukturdokument als Anregung oder Vorgabe). 28 Beispiele,
    gefiltert je Aufgabe und aufgeteilt in Grundbeispiele und Kombinationen (z. B. Thema + Materialien nur einsortieren),
    füllen das Formular, ohne zu starten.
  - „Inhalte einsortieren“: ein Ausgangsbaum (Beispiel, letztes Ergebnis oder eingefügtes JSON, auch ein Baum aus dem
    Repository mit `nodeId` und ohne Schlüssel) plus Materialien; der Baum wird schreibgeschützt angezeigt und als
    `refine` + `assign_only` gesendet.
  - Zeileneditoren statt JSON: Materialien als `Titel | Schlagworte | Beschreibung`, Ordner als eingerückte Gliederung.
    Ein Strukturdokument lässt sich auch als Inhalt einsortieren.
  - „Baum ändern“: gezielte Änderungen (`feedback.changes`, alle acht Operationen einschließlich `describe`) in einem
    Zeileneditor mit Knotenauswahl; „Sperren“ und „Ändern …“ direkt am Ausgangs- oder Ergebnisbaum; „Als Ausgangsbaum für
    Änderungen nutzen“ übernimmt ein Ergebnis.
  - Die Anfrage ist immer als JSON sichtbar und lässt sich bearbeiten und unverändert senden, so bleibt jede Option
    (z. B. `nodeId`) erreichbar. Ergebniskarte mit Kennzahlen zu Qualität, Kosten und Dauer, einklappbare Warnungen,
    Rückfragen, Änderungen und nicht zugeordnete Inhalte, Baumansicht mit hervorgehobenen Duplikaten, JSON kopieren oder
    speichern.
---

## Aufbau von Anfrage und Antwort (`POST /v2/topic-tree`)

Jedes Feld von Anfrage und Antwort mit Typ, Standard und Bedeutung steht in
[`docs/de/datenformat.md`](docs/de/datenformat.md) (aus den Modellen erzeugt). Maschinenlesbar:
[`docs/schemas/`](docs/schemas/); Aufrufmuster, Rollen und die Entscheidungstabelle für Aufrufer:
[`docs/de/api.md`](docs/de/api.md).

| Feld der Anfrage | Pflicht | Zweck |
|---|---|---|
| `mode` | ja | `create` (neuer Baum) oder `refine` (`current_tree` ändern) |
| `use_case` | ja | Gerüst des Baums: `topic`, `document`, `folders` oder `contents` |
| `frame` | ja | Fach, Bildungsstufe und Zielgruppe als SkoHub-URIs (Listen dürfen leer sein) |
| `topic` | bei `topic` | Thema als Text; sonst grenzt es den Umfang ein und benennt den Baum |
| `items` / `items_ref` | je nach Fall | Materialien und Dokumente; jeweils mit einer Rolle in `use` (`structure`, `content`, beides, keine), optional `fulltext` (Text oder `ref`) und `path` |
| `folders`, `folders_use` | bei `folders` | Bestehender Ordnerbaum (`title`, `items`, `subcollections`); `folders_use` ist seine Rolle in anderen Use Cases |
| `shape` | nein | `depth`, Spannen `main_topics`/`children`, `extra_topics` |
| `hints` | nein | `context`, `include`, `exclude`, `order`, `description_length`, `language` |
| `options` | nein | `assign_contents`, `multi_assign`, `min_confidence`, `improve`, `assign_only`, `auto_metadata` |
| `current_tree`, `feedback` | bei `refine` | Das vorige Ergebnis oder ein beliebiger bestehender Baum (Knoten brauchen nur `title`; `key` und `nodeId` sind optional) und der Änderungswunsch (`text`, `changes`, `locked`) |

| Feld der Antwort | Inhalt |
|---|---|
| `metadata` | Titel, Beschreibung, `version`, Vokabular-Labels und `generation` (alle Einstellungen des Laufs; für den nächsten Lauf zurückschicken) |
| `collection[]` | Der Baum: je Knoten `key` (stabil über Läufe hinweg), `nodeId` (falls in `current_tree` gesendet), `title`, `shorttitle`, `status`, `origin`, edu-sharing-`properties`, `contents[]` (`id`, `nodeId`, `confidence`), `subcollections[]` |
| `unassigned[]` | Nicht einsortierte Inhalte mit `reason` (`off_topic`, `low_confidence`, `no_matching_node`, `excluded`) |
| `changes[]` | Umgesetzte Änderungen (bei `refine`, oder bei `folders` + `improve`, dann `source: service`) |
| `questions[]` | Rückfragen zu unklarer Rückmeldung; der unklare Teil wird nicht umgesetzt |
| `warnings[]` | Alles, was fehlschlug oder auffiel, mit festem `code` (nie eine stille Lücke) |

Ein vollständiges Paar aus Anfrage und Antwort: [`docs/examples/topic_with_items.json`](docs/examples/topic_with_items.json) →
[`docs/examples/responses/topic_with_items.json`](docs/examples/responses/topic_with_items.json). Fehler haben die Form
`{"error": {"code", "message", "trace_id"}}`; alle Codes stehen in [`docs/de/api.md`](docs/de/api.md#fehler).

## Use Cases & Beispiele (`POST /v2/topic-tree`)

Alle Beispiele unten funktionieren direkt gegen `http://localhost:8000/v2/topic-tree` (sie liegen auch unter [`docs/examples/`](docs/examples/)). Ist im eigenständigen Betrieb `SERVICE_API_KEYS` gesetzt, `-H "Authorization: Bearer <key>"` ergänzen.

**Automatische Standardwerte für `shape`, wenn es fehlt:**
- **Reine Themenvorgabe `topic` (ohne Struktur-Items)**: Empfehlungsrahmen je Zielgruppe (`5–15` Hauptthemen und `3` Ebenen für Schule, Berufsbildung und Hochschule; `5–10` und `2` Ebenen für den Elementarbereich; `5–12` und `2` Ebenen für Fortbildung und Organisationen). Angeforderte `extra_topics` (`"general"`, `"methodology"`) zählen zur Gesamtzahl `main_topics` auf Ebene 1.
- **Eingabegetriebene Anfragen (`document`, `contents`, `folders` oder `topic` mit `"structure"`-Items)**: Die Breite folgt der Eingabe bis `MAX_NODES_PER_LEVEL` (`20`, z. B. ein ganzer Lehrplan mit 20 Themenfeldern), die Tiefe bleibt auf `MAX_TREE_DEPTH` (`3`) begrenzt.

### 1. `topic` – Baum aus einem Thema erzeugen

Erzeugt aus einem Thema als Text und dem OEH-Vokabularrahmen einen ausgewogenen Themenbaum. Bei fachübergreifenden Themen mit `"options": {"auto_metadata": true}` ordnet der Dienst jeden Knoten exakten deutschen Vokabular-Labels zu und bildet sie deterministisch auf SkoHub-URIs ab.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "create",
    "use_case": "topic",
    "topic": "Optik für die Sekundarstufe I, alltagsnah, mit Experimenten",
    "frame": {
      "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
      "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"],
      "intended_end_user_role_uri": ["http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"]
    },
    "shape": {
      "depth": 3,
      "main_topics": {"min": 6, "max": 10},
      "children": {"min": 3, "max": 6},
      "extra_topics": ["general"]
    },
    "hints": {
      "context": "Unterricht Klasse 7 bis 9, viele Schülerexperimente",
      "include": ["Farben"],
      "exclude": ["Wellenoptik"]
    }
  }'
```

*(Kürzester Aufruf: `curl -s http://localhost:8000/v2/topic-tree -H 'Content-Type: application/json' -d @docs/examples/topic_minimal.json`)*

### 2. `document` – Baum aus einem Strukturdokument ableiten (Lehrplan / Inhaltsverzeichnis eines Lehrbuchs)

Ein oder mehrere Markdown-Dokumente mit `"use": ["structure"]` senden (optional mit Seitenmarken wie `<!-- page: 12 -->`). Weitere Items mit `"use": ["content"]` werden automatisch in den entstehenden Baum einsortiert.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "create",
    "use_case": "document",
    "items": [
      {
        "id": "d1",
        "use": ["structure"],
        "properties": {"cm:title": ["Lehrplan Physik, Klassen 7 bis 10"]},
        "fulltext": {
          "format": "markdown",
          "text": "<!-- page: 12 -->\n## Themenfeld 1: Lichtausbreitung\nSchatten, Lochkamera.\n<!-- page: 14 -->\n## Themenfeld 2: Reflexion und Brechung\nSpiegel und Linsen."
        }
      },
      {
        "id": "c1",
        "nodeId": "5c0e1f2a-1111-4000-8000-000000000001",
        "use": ["content"],
        "properties": {"cm:title": ["Arbeitsblatt Schattenwurf"]}
      }
    ],
    "frame": {
      "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
      "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"]
    },
    "hints": {"exclude": ["Wahlpflicht"], "order": "Themenfelder"}
  }'
```

### 3. `folders` – Hochgeladene Ordnerhierarchie behalten und optional verbessern

Behält den Ordnerbaum des Aufrufers bei (`origin.type="folder"`), schreibt Beschreibungen und Schlagworte für jeden Ordner und behält zugeordnete Inhalte mit Konfidenz `1.0`. Mit `"options": {"improve": true}` benennt der Dienst nichtssagende Ordner (wie `Neuer Ordner (2)`) um oder korrigiert die Struktur; jede umgesetzte Änderung steht in `changes[]`.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "create",
    "use_case": "folders",
    "folders": [
      {"title": "Optik", "items": ["c1"], "subcollections": []},
      {"title": "Neuer Ordner (2)", "items": ["c2"], "subcollections": []}
    ],
    "items": [
      {"id": "c1", "nodeId": "5c0e1f2a-1111-4000-8000-000000000001", "properties": {"cm:title": ["Licht und Schatten"]}},
      {"id": "c2", "nodeId": "71bd09e4-2222-4000-8000-000000000002", "properties": {"cm:title": ["Spiegelbilder am Hohlspiegel"]}}
    ],
    "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]},
    "options": {"improve": true}
  }'
```

### 4. `contents` – Unstrukturierte Inhalte zu einem neuen Baum gruppieren

Bildet Themengruppen direkt aus den gesendeten Inhalten (`origin.type="cluster"`) und ordnet jeden Inhalt mit Konfidenzwerten zu; themenfremde Inhalte stehen in `unassigned[]`.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "create",
    "use_case": "contents",
    "topic": "Optik",
    "items": [
      {"id": "c1", "properties": {"cm:title": ["Licht und Schatten"]}},
      {"id": "c2", "properties": {"cm:title": ["Lochkamera basteln"]}},
      {"id": "c3", "properties": {"cm:title": ["Sammellinsen im Alltag"]}},
      {"id": "c4", "properties": {"cm:title": ["Hohlspiegel und Brennpunkt"]}}
    ],
    "frame": {
      "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
      "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"]
    }
  }'
```

### 5. `refine` – Bestehenden Baum mit Rückmeldung und gesperrten Ästen weiterentwickeln

In `current_tree` die `collection`, `metadata.version` und `metadata.generation` der vorigen Antwort senden (optional auch `metadata.title` und `metadata.description` als `title`/`description`, damit der verfeinerte Baum sie behält), dazu `feedback.text`, gezielte `feedback.changes` und in `feedback.locked` die Schlüssel fertiger Äste, die geschützt bleiben sollen.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "refine",
    "use_case": "topic",
    "current_tree": {
      "version": "v1",
      "collection": [
        {"key": "k-optik", "title": "Optik", "subcollections": []},
        {"key": "k-akustik", "title": "Akustik", "subcollections": []}
      ]
    },
    "feedback": {
      "text": "Farben als eigenes Hauptthema ergänzen",
      "locked": ["k-optik"]
    },
    "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}
  }'
```

**Gezielte Änderungen (`feedback.changes`)** werden ohne LLM umgesetzt (außer `split`), zusammen mit `feedback.text` oder an seiner Stelle:

| `op` | Pflichtfelder | Wirkung |
|---|---|---|
| `add` | `title` (+ optional `parent`, Schlüssel oder Titel) | Neuer Knoten; ohne `parent` auf der Hauptebene |
| `remove` | `key` | Entfernt den Ast; seine Inhalte wandern nach `unassigned` |
| `rename` | `key`, `title` | Neuer Titel; Kurztitel und Beschreibung werden neu geschrieben |
| `edit` | `key`, `properties` | Setzt Properties wie `cclom:general_keyword` |
| `move` | `key` (+ `to`) | Verschiebt unter `to`; ohne `to` (oder mit `null`) auf die Hauptebene |
| `merge` | `keys` (≥ 2), `title` | Führt Knoten im ersten Schlüssel zusammen |
| `split` | `key`, `hint` | Teilt einen Knoten wie beschrieben auf (LLM) |
| `describe` | `key` (+ optional `hint`) | Schreibt Beschreibung und Schlagworte mit dem Baum als Kontext neu, nach `hint` (LLM); siehe Use Case 7 |

Sieben davon in einer Anfrage: `curl -s http://localhost:8000/v2/topic-tree -H 'Content-Type: application/json' -d @docs/examples/refine_changes.json`.
Gesperrte Schlüssel (`feedback.locked`) und ihre Äste ändern sich nie; eine Änderung, die sie berühren würde, wird mit
`CHANGE_REJECTED` abgelehnt. Die Antwort kennzeichnet den `status` jedes Knotens (`new`, `changed`, `moved`, `unchanged`),
listet die umgesetzten `changes` und zählt die Version hoch (`v1` → `v2`). Für den nächsten Lauf `collection`,
`metadata.version`, `metadata.generation` und (um sie zu behalten) `metadata.title`/`metadata.description` als
`current_tree` zurückschicken (siehe [`docs/de/api.md`](docs/de/api.md), „Änderungen an einem Baum einreichen“).

### 6. Inhalte in einen bestehenden Baum einsortieren (`refine` + `assign_only`)

Füllt einen bereits bestehenden Baum, etwa einen Sammlungsbaum aus edu-sharing, mit Inhalten und ändert sonst nichts:
kein Umbau, keine neuen Beschreibungen, keine Formprüfungen, und die `properties` jedes Knotens kommen genau so zurück,
wie sie gesendet wurden (der `frame` hilft nur bei der Zuordnung). Knoten brauchen nur einen `title`; fehlende `key`s
vergibt der Dienst, eine `nodeId` je Knoten wird durchgereicht, so lässt sich jede Zuordnung ihrer Sammlung zuordnen.
`use_case` spielt hier keine Rolle (`topic` genügt), eine `generation` ist optional; `metadata.generation.frame` behält
den Rahmen, mit dem der Baum entstand. Themenfremde oder nicht passende Inhalte landen in `unassigned`;
`options.auto_metadata` und `feedback` werden mit einer Warnung ignoriert. In der Test-Oberfläche ist das die Aufgabe
„Inhalte einsortieren“.

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "refine",
    "use_case": "topic",
    "current_tree": {
      "collection": [
        {"nodeId": "n-optik", "title": "Optik", "subcollections": [{"nodeId": "n-linsen", "title": "Linsen"}]},
        {"nodeId": "n-schall", "title": "Schall"}
      ]
    },
    "items": [
      {"id": "c9", "nodeId": "n-c9", "use": ["content"], "properties": {"cm:title": ["Brennweite einer Lupe bestimmen"]}}
    ],
    "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]},
    "options": {"assign_only": true}
  }'
```

Antwort (gekürzt): Der Knoten `Linsen` behält `"nodeId": "n-linsen"` und erhält
`"contents": [{"id": "c9", "nodeId": "n-c9", "confidence": 0.9}]`; jeder Knoten hat `status: "unchanged"`.

### 7. Knoten beschreiben (Änderung `describe`, Nachfolger von `/generate-collection-description`)

`{"op": "describe", "key": …, "hint": …}` in `feedback.changes` schreibt eine neue Beschreibung und Schlagworte für den
Knoten. Dabei sind Pfad, Geschwister und der ganze Baum bekannt, sodass sich der Text von den Nachbarknoten abgrenzt.
Das optionale `hint` (bis 1.000 Zeichen) ist Grundlage oder Wunsch für den Text, z. B. der Freitext, den der alte
Endpunkt erhielt. Die Struktur bleibt; gesperrte Knoten werden mit `CHANGE_REJECTED` abgelehnt, ebenso ein Knoten, den
eine spätere Änderung derselben Anfrage entfernt, einschmilzt oder aufteilt; lässt das Modell einen Knoten aus, kommt
`DESCRIBE_FAILED`. Wie bei jedem `refine` mit Rückmeldung werden Knoten ganz ohne Beschreibung im selben Lauf
mitbeschrieben (bei einem großen Baum aus dem Repository ohne Beschreibungen heißt das ein Aufruf je 10 Knoten), der
`frame` wird an Knoten gesetzt, denen er fehlt, und Schlagworte werden bereinigt. Für eine einzelne Sammlung einen Baum
mit einem Knoten senden.
Beispiel: [`docs/examples/describe.json`](docs/examples/describe.json).

### 8. Use Cases kombinieren (z. B. Thema + Inhalte)

`use_case` wählt die Quelle, die das Gerüst bildet; die Rollen entscheiden, wie jede weitere Eingabe einfließt. Baumerzeugung und Zuordnung von Inhalten sind entkoppelt und werden je Item über `"use"` (`"content"`, `"structure"`, beides oder keins) gesteuert, für die Ordnerstruktur über `folders_use`:

| Ziel der Kombination | Aufbau der Anfrage | Verhalten |
|---|---|---|
| **Thema + Inhalte einsortieren** *(von oben nach unten)* | `use_case: "topic"` + `topic` + `items` *(ohne `use` oder `["content"]`)* | Plant den Baum systematisch aus `topic` und ordnet dann die `items` mit Konfidenz zu. |
| **Thema + Inhalte regen auch Äste an** *(hybrid)* | `use_case: "topic"` + `topic` + `items` mit `"use": ["structure", "content"]` | Gibt bis zu 50 Items (Titel, Schlagworte, Beschreibungen + bis zu 5 Volltextauszüge) als ergänzende Eingabe an `plan_structure` (zusätzliche, aus der Eingabe entstandene Hauptthemen erhalten `status: "suggested"`) und ordnet danach alle Inhalte zu. |
| **Inhalte innerhalb eines Themas gruppieren** *(von unten nach oben)* | `use_case: "contents"` + `topic` + `items` | Bildet Gruppen aus den `items`, eingegrenzt auf `topic`; themenfremde Inhalte landen in `unassigned` (`off_topic`). Items, die nur mit `"use": ["content"]` markiert sind, werden einsortiert, ohne die Gruppen zu verzerren. |
| **Lehrplan-Dokument + Thema + Inhalte** | `use_case: "document"` + optional `topic` + Markdown-Item(s) mit `"structure"` + Items mit `"content"` | Leitet den Baum aus den Überschriften des Lehrplans ab (`origin.document`), nutzt `topic` als Schwerpunkt und Titel und ordnet die Inhalte zu. |
| **Ordner + Thema + lose Inhalte + Lehrplan** | `use_case: "folders"` + `folders` + `items` (Ordner-Inhalte + lose `"content"`-Items + optional ein `"structure"`-Dokument) + `options.improve: true` | Behält die Zuordnungen der Ordner (`confidence: 1.0`), verbessert die Ordnerstruktur anhand von `topic` und ergänzenden Dokumenten und sortiert die übrigen losen Inhalte in passende Ordner ein. |
| **Thema, Lehrplan oder Inhalte + Ordner** | `use_case: "topic"`, `"document"` oder `"contents"` + `folders` + optional `folders_use` | Die Ordnerstruktur als Ganzes erhält eine Rolle wie `use` (Standard `["structure", "content"]`): Ihr Baum regt die Planung an, und der Ordnerpfad jeder Datei ist ein Hinweis für die Zuordnung. `[]` nimmt sie ungenutzt an (`INPUT_IGNORED`). Die Entscheidungstabelle für Aufrufer steht in [`docs/de/api.md`](docs/de/api.md). |
| **Refine + Rückmeldung + neue Inhalte** | `mode: "refine"` + `current_tree` + `feedback` + neue `items` | Setzt Strukturänderungen um (unter Beachtung von `locked`), beschreibt neue und umbenannte Knoten und ordnet die neuen `items` im selben Aufruf dem aktualisierten Baum zu. |

Weitere kombinierte Anfragen in [`docs/examples/`](docs/examples/): `combo_topic_folders.json` (Thema + Ordnerstruktur
mit `folders_use` + ein Item mit `path`), `combo_document_topic_contents.json` (Lehrplan + Thema + Themenliste +
Inhalte) und `contents_with_curriculum.json` (Inhalte gruppiert mit einem Lehrplan-Volltext).

Beispiel für hybrides `topic` + `items`:

```shell
curl -s http://localhost:8000/v2/topic-tree \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "create",
    "use_case": "topic",
    "topic": "Optik in der Sekundarstufe I",
    "items": [
      {
        "id": "m1",
        "nodeId": "n-m1",
        "use": ["structure", "content"],
        "properties": {
          "cm:title": ["Schülerexperiment: Lochkamera bauen"],
          "cclom:general_keyword": ["Lochkamera", "Lichtausbreitung"]
        }
      },
      {
        "id": "m2",
        "nodeId": "n-m2",
        "use": ["content"],
        "properties": {"cm:title": ["Arbeitsblatt Reflexionsgesetz"]}
      }
    ],
    "frame": {
      "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
      "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"]
    }
  }'
```

---

## Tests und Prüfungen

```shell
uv run pytest -q                                # ganze Suite inkl. E2E-Server und Gunicorn-Smoke-Test; die Node-Tests
                                                # der Oberfläche laufen, wenn `node` installiert ist, die Chart-Tests,
                                                # wenn `helm` installiert ist (CI hat beides)
node --test tests/ui_js/*.test.cjs              # nur die JavaScript-Unit-Tests der Test-Oberfläche
uv run ruff check && uv run ruff format --check # Lint & Formatierung (Zeilenlänge 120)
helm lint --strict deploy/helm/topic-tree       # Prüfung des Helm-Charts (CI führt zusätzlich kubeconform und promtool aus)
uv run python -m scripts.export_schemas         # docs/schemas und beide Feldreferenzen nach Modelländerungen neu erzeugen
uv run python -m scripts.build_vocab_snapshot   # mitgelieferte OEH-Vokabular-Labels aktualisieren
uv run python -m scripts.probe_llm --model <route> --base-url <router-url>
uv run python -m scripts.loadtest --url http://localhost:8000/v2/topic-tree --payload docs/examples/topic_full.json
```

## Aufbau des Repositorys

```text
app/api        HTTP layer (v2 endpoint, errors, deps, OpenAPI examples)
app/pipeline   orchestrator, strategies per use case, LLM steps, input loading, finalize
app/domain     tree, keys, shape rules, quality guards, change ops, status (pure, no I/O)
app/schemas    Pydantic v2 request/response models
app/llm        backend selection and structured JSON client (no streaming, concurrency cap)
app/context    tracing and caller/mode detection
app/vocab      bundled SkoHub vocabulary snapshot (no runtime network)
app/ui         optional self-hosted test UI (/ui/, toggled via UI_ENABLED)
app/legacy     frozen v1 endpoints
deploy/helm    Helm chart template (published to GHCR OCI on vX.Y.Z tags)
deploy/b-api   Reference LLM route definition (gpt-6-luna primary, gpt-5.6-luna fallback)
docs/en, docs/de  guides in English and German (API, data format, operations, service profile)
docs/          JSON schemas, request examples, audits, benchmarks, design plans (index: docs/README.md)
```
