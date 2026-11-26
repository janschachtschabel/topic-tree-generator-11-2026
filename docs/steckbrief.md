# Technischer Service-Steckbrief: `topic-tree` (Themenbaum-Dienst)

Stand: **26.11.2026** · Version: **`2.1.0`** · Kompakter Änderungsüberblick gegenüber `v0.4.0`: [`docs/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/aenderungen-v0.4-zu-v2.0.md)  
Aufbau nach **Team-6-Vorlage („Technischer Service-Steckbrief“)** ergänzt um alle Pflichtzeilen, die **Kompatibilitätsmatrix** und den **Leitfaden-Abgleich** aus dem *Leitfaden Dienste* (Kap. 1–8, Stand 17.11.2026).

Legende Status: `geprüft` / `vorhanden` (✅ im Code & durch Tests/Messung belegt) · `In Klärung` / `In Nacharbeit` (⏳ vor Übergabe an T6 / b-api-Admin abzuschließen) · `entfällt` (➖)

---

## 1. Stammdaten

| Feld | Status & Ist-Stand (`2.1.0`) |
|---|---|
| **Service / Dienst-ID** | **`topic-tree`** (einheitlich in `SERVICE_ID`, JSON-Logs `service`, Prometheus-Präfix `topic_tree_*`, Helm-Chart [`deploy/helm/topic-tree`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/deploy/helm/topic-tree), b-api-Proxy `/api/v1/proxy/topic-tree`) |
| **Funktionalität / Kurzbeschreibung** | Erzeugt Themenbäume (Sammlungsstrukturen) für Bildungsinhalte: aus einem Thema, einem Strukturdokument wie einem Lehrplan, aus Ordnern und Dateien oder aus unstrukturierten Inhalten. Entwürfe lassen sich mit Rückmeldungen weiterentwickeln, Inhalte werden den Knoten zugeordnet. |
| **Use Cases** | `topic`, `document`, `folders`, `contents`, dazu `mode: refine` (Rückmeldung als Text oder gezielte Änderungen) und die Zuordnung von Inhalten mit Konfidenz. Die Kurzbeschreibung oben ist wortgleich mit `info.description` (per Test abgesichert). |
| **Stabile Version** | `geprüft` **`2.1.0`** (Release-Tag `v2.1.0` vom 26.11.2026 im Entwicklungs-Repo auf GitHub; die CI veröffentlicht dazu Image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026:2.1.0` und das OCI-Chart `topic-tree` `2.1.0`. Der ältere Tag `v2.0.0` vom 25.11. bleibt bestehen, für ihn wurde nie ein Image oder Chart gebaut. Im Übergabe-Repo steht der Stand in Branch [`v2`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2) noch auf dem Abgleich, siehe *Repository*; [`pyproject.toml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/pyproject.toml) & [`Chart.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/Chart.yaml) per CI-Test synchron; bisheriger Stand [`0.4.0`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/0.4.0) · Änderungsübersicht: [`docs/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/aenderungen-v0.4-zu-v2.0.md)) |
| **Technischer Owner / Ansprechperson** | Jan Schachtschabel · **Vertretung:** `In Klärung` *(vor T6-Übergabe benennen, z. B. Tobias Müller)* |
| **Jira** | `WLO-87: Themenbaum-Generator` |
| **Deployment Status** | `extern` (Docker/Compose Testinstanz) · `staging` (`0.4.0` aktiv hinter b-api; Upgrade auf `2.1.0` vorbereitet) · `prod` (ausstehend nach T6-Abnahme) |
| **Qualitätseinschätzung** | `geprüft` **631 automatisierte Tests** (`pytest`, inkl. Schema-, Vertrags-, Auth-, Helm- & Gunicorn-E2E-Tests; 5 Helm-Tests laufen nur mit `helm`, also in der CI) und 33 Node-Tests der Test-UI, drei vollständige Audits (25./26.11.2026 und Gesamtaudit 26.11.2026 [`docs/audits/2026-11-26-gesamtaudit.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-gesamtaudit.md), alle Befunde behoben oder begründet offen), **Live-Test** vom 26.11.2026 über alle 18 UI-Beispiele und eine refine-Kette ([`docs/audits/2026-11-26-live-test.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-live-test.md)), **Lastmessungen** vom 24./25.11.2026 über alle v2-Use-Cases, Kombinationen und beide v1-Legacy-Endpunkte (Skeleton-first mit deterministischer Duplikat-Eliminierung: **0 Duplikate** auf 100–140 Knoten; SkoHub-Label→URI-Mapping ohne erfundene URIs) |
| **Repository** | `In Klärung` **Übergabe-Repo für T6:** [`https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator) (Stand `2.0.0` in Branch [`v2`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2), Abgleich auf `2.1.0` offen, Altstand `0.4.0` in [`main`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/main) / Tag [`0.4.0`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/0.4.0)). **Entwicklung:** [`https://github.com/janschachtschabel/topic-tree-generator-11-2026`](https://github.com/janschachtschabel/topic-tree-generator-11-2026) (`main`, GitHub Actions, Image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026` ohne Login abrufbar). Vor der Übergabe den GitLab-Stand mit `main` auf GitHub abgleichen. |
| **OpenAPI Spec** | `geprüft` Aus FastAPI-Code generiert unter `GET /openapi.json` (`/docs`, `/redoc`), mit Endnutzer-Beschreibung (`info.title`, `info.description`) und Request-Beispielen vom Minimal- bis zum Vollaufruf ([`app/api/examples.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/api/examples.py)). Exportierte JSON-Schemata zusätzlich unter [`docs/schemas/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/docs/schemas), API-Referenz unter [`docs/api.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/api.md). Interne Pfade (`/health`, `/_ping`, `/ready`, `/metrics`, `/ui/*`) erscheinen **nicht** in `/openapi.json` (per Test abgesichert). |
| **Pipeline und Git-Tags** | `geprüft` GitLab CI ([`.gitlab-ci.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.gitlab-ci.yml)): prüft `ruff check`, `ruff format --check`, `pytest`, `helm lint --strict` + `kubeconform`, validiert Tag-Konsistenz (`vX.Y.Z` == `pyproject.toml` == `Chart.yaml`) und baut/veröffentlicht bei `vX.Y.Z`-Tags Container-Images sowie das versionierte **Helm-Chart als OCI-Artefakt** (ergänzend `docker compose config` und `promtool check rules` in [`.github/workflows/ci.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.github/workflows/ci.yml)). Aktiv läuft heute die GitHub-CI (Prüf-Job nur lesend, erst der Veröffentlichungs-Job hat `packages: write`; Tag muss gleich der Version sein und auf `main` liegen). Seit `2.1.0` in der GitHub-CI: Sperre gegen das erneute Veröffentlichen einer Version (Image und Chart werden vorher geprüft), `latest` kommt nur von `main` (ein Release-Tag verschiebt es nicht), manuelles Nachveröffentlichen eines Tags per `workflow_dispatch`, `uv lock --check` und ein Prüf-Job `pip-audit` auf bekannte Lücken der Laufzeit-Abhängigkeiten (meldet, blockiert die Veröffentlichung nicht). **Noch nicht in der CI (Soll):** Typprüfung, `promtool test rules`. |
| **Endpunkte** | `geprüft` **Öffentlich (Port `8000`):**<br>• `POST /v2/topic-tree` *(v2 Hauptendpunkt: alle 4 Use Cases + `refine` + Inhaltszuordnung)*<br>• `POST /generate-topic-tree` *(v1 Legacy, formatkompatibel eingefroren)*<br>• `POST /generate-collection-description` *(v1 Legacy, formatkompatibel eingefroren)*<br>• `GET /` *(Kurzinfo zum Dienst, nicht in OpenAPI)*<br>• `GET /_ping`, `GET /health` *(Liveness/Readiness für K8s-Probe, nicht in OpenAPI)*<br>• Optional `GET /ui/*` *(eingebaute Test-UI, in Produktion per `UI_ENABLED=false` komplett abgeschaltet → `404`)*<br>**Intern (Port `9000`, nur Cluster/Monitoring):**<br>• `GET /health`, `GET /ready`, `GET /metrics` |
| **Endpunkte auf zwei Ports** | `geprüft` **Ja:** Öffentlicher API-Port `PUBLIC_PORT=8000` (FastAPI/Uvicorn-Worker) und getrennter interner Port `INTERNAL_PORT=9000` (einmalig im Gunicorn-Master gebunden für `/health`, `/ready`, `/metrics`) |
| **Header / Content-Types** | `geprüft` **Content-Type:** ausschließlich `application/json` (kein SSE/Streaming, keine Datei-Uploads).<br>**Eingehende Header:** `Authorization: Bearer bdt_…` (Delegations-Token der b-api, alternativ konfigurierbarer `B_API_DELEGATION_HEADER`; im Standalone-Betrieb optional `SERVICE_API_KEYS`), optional `X-B3-*` / `b3` und `x-client-trace-id`. Keine eigenen Personen- oder Repository-Header (`X-Edu-*`, `X-API-KEY` werden nie gesendet).<br>**Ausgehende Header an den Aufrufer:** `Retry-After` (bei `503 LLM_UNAVAILABLE`) und `WWW-Authenticate` (bei `401`).<br>**Freigaben im Proxy-Eintrag:** `allowedResponseHeaders: [Retry-After, WWW-Authenticate]`; `allowedRequestHeaders: [b3, X-B3-TraceId, X-B3-SpanId, X-B3-ParentSpanId, X-B3-Sampled, X-B3-Flags, x-client-trace-id]`, sofern die b-api diese nicht ohnehin durchreicht (mit b-api-Admin klären). |
| **Asynchrone Job-Endpunkte** | `geprüft` **Keine (synchroner Dienst)** — bewusste Architekturentscheidung, da das b-api-Delegations-Token (`bdt_…`) mit Beendigung des HTTP-Aufrufs erlischt und Hintergrundjobs im Dienst die b-api nicht mehr im Personenkontext zurückrufen dürfen (Leitfaden Kap. 1 & 2.2). Für mehrstufige Repository-Abläufe wird der Dienst aus einem **Kestra-Flow** über `/api/v1/proxy/topic-tree` aufgerufen. |
| **Timeout für Requests** | `geprüft` Dienst-Deadline **`REQUEST_TIMEOUT_SECONDS=280`** (280 s), Gunicorn-Worker-Timeout `310 s`, Graceful-Shutdown `graceful_timeout=290 s` / `terminationGracePeriodSeconds=300 s`, Einzel-LLM-Call `LLM_TIMEOUT_SECONDS=120`. **Erforderliches Proxy-/Ingress-Timeout (`responseTimeout` in der b-api): mindestens `310 000 ms` (310 s).** |
| **Readiness Status** | `geprüft` Kubernetes `livenessProbe` prüft `GET :9000/health`, `readinessProbe` prüft `GET :8000/health` **komplett ohne externe Abhängigkeiten** (nimmt Pods bei b-api-Störung nicht aus dem Netz, Leitfaden Kap. 3). `GET :9000/ready` prüft getrennt die lokale Konfiguration (`LLM_NOT_CONFIGURED`). |

---

## 2. Architektur & b-api-Integration

### Kurze Architekturübersicht (Leitfaden Kap. 3)

```text
Aufrufer / edu-sharing (/bapi/**) / Kestra-Flow
        │  POST /v2/topic-tree (JSON, Authorization: Bearer bdt_… + B3 / x-client-trace-id)
        ▼
[ topic-tree :8000 ]  FastAPI (Gunicorn + Uvicorn-Worker, zustandslos)
   ├── Eingabe- & Größenprüfung (MAX_TREE_DEPTH=3, MAX_NODES_PER_LEVEL=20)
   ├── Optionales Nachladen von items_ref / fulltext.ref (nur HTTPS + REF_ALLOWED_HOSTS, SSRF-geschützt)
   ├── Strategie je Use Case (topic | document | folders | contents | refine)
   │     └── LLMClient (kein Streaming, Semaphor LLM_MAX_CONCURRENCY=20, JSON-Schema + 1 Repair,
   │                    statischer system.md-Präfix für Prompt-Caching, B3/Trace-Weitergabe)
   ├── Optionale Inhaltszuordnung (assign_contents, 40er-Batches) & Vokabular-Klassifikation (Label → SkoHub-URI)
   └── Deterministische Nachbereitung (Duplikat-Eliminierung, Kurztitel ≤ 20 Z., Keys, Diff-Status, Qualitäts-Checks)
        │
        ├──► [ b-api :443 ] POST /api/v1/llm/router/chat/completions (mit unverändertem Bearer bdt_…)
        │                   (im Standalone-Ausnahmebetrieb: OpenAI-kompatibler Endpunkt per OPENAI_API_KEY)
        └──► [ Intern :9000 ] GET /health, /ready, /metrics (Prometheus Multiprozess im Gunicorn-Master)
```

| Feld | Status & Ist-Stand (`2.1.0`) |
|---|---|
| **Überblick** | Python 3.13, FastAPI, Pydantic v2, `openai` AsyncClient (über geteilten `httpx.AsyncClient`), `gunicorn` + `uvicorn-worker`, `loguru`, `prometheus-client`; gebündelter Offline-SkoHub-Vokabular-Snapshot (`discipline`, `educationalContext`, `intendedEndUserRole` unter [`app/vocab/data/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/app/vocab/data)) |
| **Horizontale Skalierbarkeit / Clusterfähigkeit** | `geprüft` **Vollständig zustandslos (`stateless`)** — keine Sessions, keine In-Memory-Jobs, keine SQLite/Datenbank, kein geteiltes Volume. Beliebig viele Pods parallel hinter einem Service (`RollingUpdate`, Standard im Chart `replicaCount: 2`, optionaler HPA `2–6` Pods). Skalierungsgrenzen liegen ausschließlich in den Rate-Limits/Kontingenten der upstream LLM-Route (insb. GWDG-Kontingent ~10 Req/min; ein 3-Ebenen-Baum benötigt ~9–14 LLM-Calls und sollte daher auf OpenAI/Azure-Routen statt GWDG laufen). |
| **Integriert in B-API (`b-api`)** | `In Klärung` *(Code & Referenz-Route fertig; Proxy-Update auf Staging/Prod mit b-api-Admin vorzunehmen)*:<br>• Proxy-Eintrag: **`topic-tree`** (`/api/v1/proxy/topic-tree`)<br>• `forwardDelegation: true`, `delegationScopes: ["llm"]` (`forwardApiKey` entfällt)<br>• `responseTimeout: 310000` (310 s), `delegationLifetimeSeconds` ≥ `310`<br>• Benötigte Rechte am Schlüssel: Dienst-Recht `topic-tree` + LLM-Recht<br>• `openApiPath: /openapi.json`; `pathToIgnore`: `/`, `/_ping`, `/health`, `/ui/**`, `/docs`, `/redoc` (nicht in der Spec, aber am öffentlichen Port erreichbar)<br>• Header-Freigaben siehe *Header / Content-Types*<br>• **Cache der b-api:** Der Dienst schickt kein `temperature`; wortgleiche Anfragen kann die b-api daher aus ihrem Cache beantworten (gleicher Baum, keine Kosten). Ob „neu erzeugen“ den Cache per `?ignore-caching=true` umgehen soll, ist offen.<br>• **Empfohlene LLM-Route `topic-tree-generator`** (Referenzvorlage [`deploy/b-api/route-topic-tree-generator.json`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/b-api/route-topic-tree-generator.json)):<br>  – **Stufe 0 (Primär):** **`gpt-6-luna`** (OpenAI, `oa-gpt6-luna`, Gewicht `1`)<br>  – **Stufe 1 (Sekundär / Reserve):** **`gpt-5.6-luna`** (OpenAI, `oa-gpt56-luna`, Gewicht `1`)<br>  – `maxAttempts: 3`, `clearCache: true` beim Speichern; beide Modelle nutzen identisch den `common`-Body (`max_completion_tokens` + `reasoning_effort: "none"`, `json_schema` `strict: true`, kein Streaming). Keine GWDG-Reserve hinterlegen (~8–14 parallele Calls/Baum überschreiten das GWDG-Limit von ~10 Req/min). |
| **Ruft selbst die b-api?** | `geprüft` **Ja**, ausschließlich `POST /api/v1/llm/router/chat/completions` (bzw. bei gesetztem `B_API_MODEL` `/api/v1/llm/{provider}/chat/completions`) mit dem unveränderten `Authorization: Bearer bdt_…`-Header. **Keine** Aufrufe an `/api/v1/edu-sharing/**`, **keine verifizierte Person erforderlich**. Ob Gast-Aufrufe ohne Person per Delegation LLM-Aufrufe machen dürfen, klärt das b-api-Team noch (Leitfaden Kap. 8). |
| **Schreibt Suggestions** | `geprüft` **Nein** (reiner Berechnungsdienst, gibt JSON an den Aufrufer zurück) |
| **Nutzt Routing** | `geprüft` **Ja** (`B_API_ROUTE`, Standard im Chart `topic-tree-generator`, versteht auch `provider/modell`; Parameterfamilie `LLM_PARAM_FAMILY=common` sendet `max_completion_tokens` + `reasoning_effort: "none"`, kompatibel mit GPT-5/GPT-6 sowie Qwen/Gemma/DeepSeek) |
| **Nutzt API Keys** | `geprüft` **Hinter der b-api: Nein** (reicht ausschließlich das empfangene Delegations-Token `bdt_…` durch; kein Dienstschlüssel, kein `X-API-KEY`).<br>**Ausnahmebetrieb ohne b-api (`SERVICE_MODE=standalone` / `auto`):** unterstützt `OPENAI_API_KEY` + eigene Bearer-Prüfung über `SERVICE_API_KEYS` (konstante Zeit per `hmac.compare_digest`); lokal zum Testen optional `B_API_DEV_KEY`. |
| **Repo über B-API / Repository-Unabhängigkeit** | `geprüft` **Kein Repository-Zugriff** (weder direkt noch über die b-api). Alle Funktionen arbeiten vollständig mit übergebenem Text und Metadaten; optionale `nodeId`-Werte werden unverändert durchgereicht (Leitfaden Kap. 1 „Unabhängig vom Repository“). |
| **Benötigte Dienste / Abhängigkeiten** | `geprüft` **Laufzeit:** nur b-api LLM-Router (bzw. im Standalone-Modus ein OpenAI-kompatibler LLM-Endpunkt). Optional HTTPS-Download von `items_ref` / `fulltext.ref` nur von explizit in `REF_ALLOWED_HOSTS` freigegebenen Hosts (Default leer = gesperrt). Keine weiteren Dienste nötig. |

### Zeile für die Kompatibilitätsmatrix (Leitfaden Kap. 6)

| Dienst-ID | braucht Dienste | Rechte am Schlüssel | Delegations-Scopes | LLM-Route | Repository-Bezug | nur gemeinsam mit |
|---|---|---|---|---|---|---|
| `topic-tree` | keine (nur b-api LLM; im Flow optional `text-extraction` / Repo-Volltext davor) | Proxy-Recht `topic-tree` + LLM | `llm` | `topic-tree-generator` *(Primär: `gpt-6-luna`, Sekundär: `gpt-5.6-luna`; `common`-Body)* | keiner (`nodeId` wird nur durchgereicht; Volltexte/Metadaten kommen als Eingabe) | — (eigenständig nutzbar) |

---

## 3. Deployment, Infrastruktur, Security & Monitoring

| Bereich / Feld | Status & Ist-Stand (`2.1.0`) |
|---|---|
| **HELM** | `geprüft` Versioniertes Chart im Repo unter [`deploy/helm/topic-tree`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/deploy/helm/topic-tree) (`version: 2.1.0`, `appVersion: "2.1.0"`, Default `config.serviceMode: bapi`), inkl. `Deployment`, `Service` (Port `8000` + `9000`), `Ingress`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `HorizontalPodAutoscaler` und vollständig dokumentierter [`values.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/values.yaml) (`## @param`). Proben (`probes.liveness`, `probes.readiness`) per `values.yaml` einstellbar. Validiert in CI mit `helm lint --strict`, `kubeconform` und `promtool check rules` (noch ohne `promtool test rules`); bei Release-Tags automatisch als OCI-Chart paketiert. |
| **Docker-Files & Image-Größe** | `geprüft` Multi-Stage [`Dockerfile`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/Dockerfile) auf `python:3.13-slim-bookworm` (Basis-Images mit `@sha256`-Digest gepinnt; [`.github/dependabot.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.github/dependabot.yml) ist eingerichtet, Versions-PRs sind aber pausiert (`open-pull-requests-limit: 0`), Digests werden bis zur Freigabe von Hand aktualisiert), [`.dockerignore`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.dockerignore) vorhanden, läuft als Non-Root (`uid=10001`), Pod-Security **`restricted`** (`readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault`; nur `/tmp` als `emptyDir`).<br>**Image-Größe:** **70 MB** komprimiert (Summe der Schichten in GHCR, `latest` am 26.11.2026 gemessen, ohne Login abrufbar), **193 MB** entpackt (Messung 24.11.2026), **0 MB Modelle/Korpora** im Image (gebündelter SkoHub-Vokabular-Snapshot ist reines JSON < 200 KB).<br>Referenz-Compose-Dateien: [`docker-compose.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docker-compose.yml) und [`docker-compose.build.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docker-compose.build.yml). |
| **Abschaltbare Komponenten** | `geprüft` Test-UI abschaltbar per `UI_ENABLED=false` (im Helm-Chart standardmäßig `false`); `Ingress`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `Autoscaling` im Chart einzeln per `.enabled` schaltbar. |
| **Datenbank** | `geprüft` **Nein** (keine Datenbank, kein Redis, kein SQLite). |
| **Große Daten & Updates / CronJobs** | `geprüft` **Nein** (keine großen Modelle, Indizes oder Volumes/PVCs; keine CronJobs nötig). Das kompakte OEH-SkoHub-Vokabular ([`app/vocab/data/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/app/vocab/data)) wird bei Bedarf vor einem Release per [`scripts/build_vocab_snapshot.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/build_vocab_snapshot.py) aktualisiert; das Snapshot-Datum steht in `GET /health` (`vocab_snapshot`). |
| **Authentifizierung** | `geprüft` Hinter der b-api über durchgereichtes Delegations-Token (`Authorization: Bearer bdt_…` oder `B_API_DELEGATION_HEADER`). Im Standalone-Betrieb optional über `SERVICE_API_KEYS`. Niemals Speicherung oder Logging von Schlüsseln/Tokens. |
| **Network Policy** | `vorhanden` Template [`deploy/helm/topic-tree/templates/networkpolicy.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/templates/networkpolicy.yaml) begrenzt Ingress auf `publicFrom` (`:8000`) und `internalFrom` (`:9000`) sowie Egress auf DNS (`53/UDP+TCP`) plus konfigurierbare `egress`-Ziele. Im Chart standardmäßig `networkPolicy.enabled: false`, bis T6 die Namespaces von b-api/Ingress und Monitoring benennt. |
| **ENV Variablen** | `geprüft` Vollständig über Umgebungsvariablen mit sinnvollen Defaults konfigurierbar ([`app/settings.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/settings.py), dokumentiert in [`.env.example`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.env.example), [`README.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/README.md) und [`values.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/values.yaml)). |
| **Benötigte Secrets** | `geprüft` **Hinter der b-api: keine Secrets nötig** (`secrets.existingSecret: ""`).<br>**Nur bei Betrieb ohne b-api (`standalone`):** `OPENAI_API_KEY` und `SERVICE_API_KEYS` (im Chart getrennt über `secrets.existingSecret` per `secretRef` eingebunden). |
| **Prometheus** | `geprüft` `GET :9000/metrics` (nur am internen Port, Multiprozess-fähig über `PROMETHEUS_MULTIPROC_DIR`). Metrik-Labels stammen ausschließlich aus festen Code-Konstanten (`route`, `step`, `outcome`, `kind`, `code` — keine unbegrenzten Pfad-Labels):<br>• `topic_tree_requests_total{route, status}` & `topic_tree_request_seconds{route}`<br>• `topic_tree_llm_calls_total{step, outcome}` & `topic_tree_llm_seconds{step}`<br>• `topic_tree_llm_tokens_total{kind="prompt"|"cached"|"completion"}`<br>• `topic_tree_warnings_total{code}` |
| **Alarmregeln** | `vorhanden` [`deploy/helm/topic-tree/templates/prometheusrule.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/templates/prometheusrule.yaml) mit 3 applikationsspezifischen Alarmen:<br>1. `TopicTreeLLMErrors` (Fehlerrate der LLM-Aufrufe > 20 % über 10 min)<br>2. `TopicTreeSlowRequests` (P90-Antwortzeit `v2.topic_tree` > 240 s über 15 min)<br>3. `TopicTreeDescribeFailures` (> 20 fehlgeschlagene Beschreibungs-Batches `DESCRIBE_FAILED` pro Stunde) |
| **B3-Tracing & Logging** | `geprüft` Strukturierte JSON-Logs nach `stdout` mit `timestamp`, `level`, `service` (`topic-tree`), `trace_id`, `span_id`, `message` (lokal per `LOG_FORMAT=text` umschaltbar; Server-Access-Logs abgeschaltet, eigene Request-Logzeile ohne Header/Rohpfade; `httpx`/`httpcore` auf `WARNING`).<br>Liest und validiert `b3` sowie `X-B3-TraceId` / `X-B3-SpanId` / `X-B3-Sampled` (Regex-geprüft gegen Log-Injection in [`app/context/tracing.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/context/tracing.py)) und reicht sie samt `x-client-trace-id` an die b-api weiter (`x-client-trace-id` wird nie selbst erfunden und steht als `client_trace_id` in jeder Logzeile der Anfrage). Dritte erhalten keine Trace-Header: weder die Hosts der Verweise (`refs.py`) noch ein direkt angesprochener Anbieter im Standalone-Betrieb. |

---

## 4. Ressourcen, Laufzeiten & Kosten (Ist-Messung)

- **Kompakter Änderungsüberblick (`v0.4.0` → `v2.0.0`):** [`docs/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/aenderungen-v0.4-zu-v2.0.md)
- **Vollständige Einzel- und Lastmessung inkl. Token-Aufschlüsselung & Kostenformel:** [`docs/measurements/2026-11-24-openai-gpt-6-luna.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-24-openai-gpt-6-luna.md)
- **Direktvergleich v1 vs. v2 über 3 Themen (25.11.2026):** [`docs/measurements/2026-11-25-v1-vs-v2-comparison.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-25-v1-vs-v2-comparison.md)

### CPU, RAM und Storage (`geprüft`)

- **Speicherverhalten:** Weitgehend **fest / flach** (keine lokalen ML-Modelle, keine Indizes).
- **Gemessene Werte:**
  - Linux-Container (`docker stats` / cgroup, Gunicorn-Master + `WEB_CONCURRENCY=2` Worker): **125,7 MiB** im Leerlauf.
  - Einzelner Worker-Prozess unter paralleler Last (`c=3`): **71,5 MiB** Leerlauf → **95,0 MiB** warm → **97,0 MiB** Spitze (entspricht **~235 MiB** Spitze für Master + 2 Worker).
- **Empfehlung für Kubernetes (`values.yaml`):**
  - `requests`: **`100m` CPU / `256Mi` RAM**
  - `limits`: **`512Mi` RAM** *(kein hartes CPU-Limit empfohlen, da der Dienst überwiegend auf Netzwerk-I/O zum LLM wartet; der RAM-Puffer über +30 % deckt bis zu `5.000` Items / `10 MiB` große `items_ref`- und `fulltext.ref`-Payloads im Speicher ab)*.
- **Interne Obergrenzen passend zum Limit:** `WEB_CONCURRENCY=2`, `LLM_MAX_CONCURRENCY=20` je Worker, `httpx`-Pool `max_connections=50`, `REF_MAX_BYTES=10 MiB`, `MAX_TREE_DEPTH=3`, `MAX_NODES_PER_LEVEL=20`. Kein `numpy`/BLAS im Einsatz.

### Laufzeit & Token-Bedarf je Funktion / Endpunkt (`gpt-6-luna`)

Einzelläufe aus dem Live-Test vom 26.11.2026 (Standalone gegen OpenAI, alle 18 UI-Beispiele, Abschlusslauf,
[`docs/audits/2026-11-26-live-test.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-live-test.md)); Tokens = Eingabe + Ausgabe; 40–85 % der Eingabe-Tokens kamen aus dem Prompt-Cache. Last und v1 aus den Messungen vom 24./25.11.2026.

| Endpunkt / Szenario | Laufzeit (Einzellauf) | LLM-Calls | Tokens gesamt | Unter Last |
|---|---:|---:|---:|---|
| `POST /v2/topic-tree` — `topic`, 2 Ebenen (24–52 Knoten, auch mit Inhalten, Dokument oder `auto_metadata`) | **13,5 – 19,8 s** | 4 – 7 | **14.700 – 28.000** | — |
| `POST /v2/topic-tree` — `topic`, 3 Ebenen (83 Knoten) | **20,4 s** | 10 | **43.100** | 3 Ebenen, ~100–150 Knoten, Concurrency 8: **P50 63,5 s / P90 112,1 s** (24.11.) |
| `POST /v2/topic-tree` — `document` (Lehrplan-Auszug, auch mit `topic`) | **7,5 – 11,7 s** | 3 | 8.600 – 9.600 | — |
| `POST /v2/topic-tree` — `folders` (mit `improve`, lose Dateien) | **4,6 – 5,4 s** | 2 | 5.300 – 5.400 | — |
| `POST /v2/topic-tree` — `contents` (12 Materialien) | **12,2 – 12,8 s** | 2 | 7.200 – 7.300 | — |
| `POST /v2/topic-tree` — `refine` mit Text-Rückmeldung, neuen Inhalten oder `add`/`split` | **1,8 – 12,0 s** | 1 – 5 | 2.600 – 18.900 | — |
| `POST /v2/topic-tree` — `refine` nur mit `feedback.changes` (`remove`/`move`/`edit` …) | **< 0,05 s** | **0** | 0 | — |
| `POST /generate-topic-tree` *(v1 Legacy, 65–78 Knoten, 25.11.)* | **40,2 – 41,9 s** | 21 – 25 | 53.600 – 59.500 (0 % gecacht) | — |
| `POST /generate-collection-description` *(v1 Legacy, 70 Wörter, 25.11.)* | **10,4 – 12,7 s** | 1 | ~710 | — |

Die Knotenzahl eines Themas schwankt zwischen Läufen (z. B. 72–100 Knoten bei `topic_sek1`), die Laufzeit mit ihr.
P50/P90 je Endpunkt über b-api-Staging stehen noch aus (siehe Abschnitt 6).

- **Kostenschätzung:** Vollständiges Token-Rechenmodell je 1.000 Aufrufe in [`docs/measurements/2026-11-24-openai-gpt-6-luna.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-24-openai-gpt-6-luna.md#6-rechenmodell-fur-spatere-kostenbewertungen). `In Klärung`: Der Leitfaden verlangt gemessene Kosten je Funktion aus den Nutzungsdaten der b-api. Sie werden beim Staging-Abnahmelauf aus den Buchungen des Testschlüssels übernommen; bis dahin gelten die Token-Zahlen oben.

---

## 5. Bewusste Abweichungen vom Diensteleitfaden (mit Begründung)

1. **Synchrone Antwortzeit > 30 s bei großen 3-Ebenen-Bäumen (Kap. 1 Soll):**  
   Ein vollständiger Baum mit 80–150 beschriebenen Knoten dauert im Einzellauf rund 20–45 s, unter Last bis 112 s (P90). Ein eigener Hintergrund-Job im Dienst darf nach Ende des HTTP-Requests mit dem Delegations-Token (`bdt_…`) die b-api nicht mehr aufrufen (Kap. 2.2). Daher antwortet der Endpunkt synchron innerhalb von `REQUEST_TIMEOUT_SECONDS=280` (erforderliches Proxy-Timeout ≥ `310 s`); für asynchrone Hintergrundläufe ruft ein Kestra-Flow den Dienst über `proxy:topic-tree` auf (Kap. 5).
2. **Leichtgewichtige B3-/Trace-Weitergabe ohne OpenTelemetry-Span-Exporter (Kap. 2.3 Soll):**  
   B3-Header (`b3`, `X-B3-*`) und `x-client-trace-id` werden vollständig validiert, in jede JSON-Logzeile geschrieben und an ausgehende b-api-Aufrufe propagiert. Auf das zusätzliche `opentelemetry-sdk` (OTLP-Span-Export) wurde zugunsten minimaler Abhängigkeiten und eines schlanken Images (70 MB komprimiert) verzichtet.
3. **Optionaler Standalone-Modus für Entwicklung & Einzelbetrieb (Kap. 2.2 „Ausnahme: Betrieb ohne b-api“):**  
   Hinter der b-api (`SERVICE_MODE=bapi`) akzeptiert der Dienst ausschließlich Delegations-Tokens (`bdt_…`) ohne eigene Anbieter-Schlüssel. Für lokale Entwicklung und eigenständige Docker-Testinstanzen unterstützt er per Env (`SERVICE_MODE=standalone` / `auto`) zusätzlich `OPENAI_API_KEY` + `SERVICE_API_KEYS`.
4. **`401` statt anonymer Antwort ohne Token (Kap. 1 Soll):**  
   Jede Funktion außer gezielten Änderungen braucht das Sprachmodell, und das erreicht der Dienst hinter der b-api nur mit dem durchgereichten Token. Ohne Token antwortet er deshalb `401 UNAUTHORIZED` („Aufruf nur über die b-api“). Ein Aufruf über die b-api trägt immer ein Token, auch für Gäste.
5. **Fehlerformat der v1-Endpunkte (Kap. 1 Soll):**  
   `/generate-topic-tree` und `/generate-collection-description` antworten weiter mit `{"detail": …}` ohne `trace_id`, damit bestehende Aufrufer unverändert funktionieren. `/v2/topic-tree` nutzt das Format `{"error": {"code", "message", "trace_id"}}`.
6. **`/ready` prüft nur die Konfiguration (Kap. 3):**  
   Die Readiness-Probe (`:8000/health`) prüft wie verlangt keine Abhängigkeiten. `:9000/ready` meldet, ob eine LLM-Route oder ein Modell konfiguriert ist, ruft die b-api aber nicht auf; die Erreichbarkeit der b-api zeigen die LLM-Metriken und der Alarm `TopicTreeLLMErrors`.

---

## 6. Verbleibende organisatorische Punkte vor Übergabe an Team 6 / b-api-Admin

Alle technischen Leitfaden-Anpassungen im Code, Helm-Chart, Dockerfile und CI-Workflow (siehe auch [`docs/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/aenderungen-v0.4-zu-v2.0.md)) sind **umgesetzt und getestet**.

Vor der finalen Produktiv-Übergabe sind nur noch folgende **organisatorische / plattformseitige Abstimmungen** offen:

1. **b-api-Proxy-Eintrag `topic-tree` & Route `topic-tree-generator` einrichten (b-api-Admin):**
   - Proxy: `forwardDelegation: true` und `delegationScopes: ["llm"]` aktivieren (`forwardApiKey` entfernen), `responseTimeout` ≥ `310000` ms setzen, Pfad `/v2/topic-tree` prüfen.
   - LLM-Route `topic-tree-generator` gemäß [`deploy/b-api/route-topic-tree-generator.json`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/b-api/route-topic-tree-generator.json) anlegen (**Stufe 0: `gpt-6-luna`**, **Stufe 1: `gpt-5.6-luna`**, `maxAttempts: 3`, `clearCache: true`).
2. **Stufe-2/3-Messung über b-api-Staging:**
   - [`scripts/probe_llm.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/probe_llm.py) und [`scripts/loadtest.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/loadtest.py) über die echte Staging-b-api ausführen und die gebuchten EUR/USD-Kosten je Use Case aus den b-api-Nutzungsdaten oben in Abschnitt 4 eintragen.
3. **Plattform-Angaben, Namenskonvention & Vertretung mit Team 6 klären:**
   - Namespaces für Ingress/b-api (`networkPolicy.publicFrom`) und Monitoring (`networkPolicy.internalFrom`) sowie Egress-Ziele für die Aktivierung der `NetworkPolicy` erfragen.
   - Stellvertretende Ansprechperson unter *Technischer Owner* eintragen.
4. **Release und Repository:**
   - Erledigt am 26.11.2026: Tag `v2.1.0` gesetzt, Image und Chart `2.1.0` auf GHCR veröffentlicht (ohne Login abrufbar, siehe *Stabile Version*).
   - Klären, aus welchem Repository T6 baut (GitLab `scm.edu-sharing.com` oder GitHub), und den GitLab-Stand mit `main` abgleichen.
   - Optional bei Übergabe abstimmen, ob Repository-/Image-Name in GitLab von `topic-tree-generator` (und auf GHCR von `topic-tree-generator-11-2026`) auf die Dienst-ID `topic-tree` vereinheitlicht werden soll (`OPENAI_MODEL`-Default `gpt-6-luna` im Standalone-Modus wurde bewusst aus Rückwärtskompatibilität für bestehende `.env`-Setups beibehalten).
