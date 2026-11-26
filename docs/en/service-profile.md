# Technical service profile: `topic-tree` (Themenbaum-Dienst)

> 🇩🇪 Deutsche Fassung: [`../de/steckbrief.md`](../de/steckbrief.md) · Operations and handover: [`operations.md`](operations.md)

The German Steckbrief is the authoritative version for the handover to Team 6; this is a translation.

As of: **26.11.2026** · Version: **`2.2.0`** · Compact overview of changes since `v0.4.0`: [`docs/de/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/aenderungen-v0.4-zu-v2.0.md) (English: [`changes-v0.4-to-v2.0.md`](changes-v0.4-to-v2.0.md))  
Structured after the **Team 6 template ("Technischer Service-Steckbrief")**, extended by all mandatory rows, the **compatibility matrix** and the **guideline check** from the *Leitfaden Dienste* (service guideline, chapters 1–8, as of 17.11.2026).

Status legend: `verified` / `present` (✅ in the code and backed by tests/measurements; German `geprüft` / `vorhanden`) · `being clarified` / `follow-up` (⏳ to be completed before handover to T6 / the b-api admin; German `In Klärung` / `In Nacharbeit`) · `n/a` (➖; German `entfällt`)

---

## 1. Master data

| Field | Status & current state (`2.2.0`) |
|---|---|
| **Service / service ID** | **`topic-tree`** (consistent in `SERVICE_ID`, JSON logs `service`, Prometheus prefix `topic_tree_*`, Helm chart [`deploy/helm/topic-tree`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/deploy/helm/topic-tree), b-api proxy `/api/v1/proxy/topic-tree`) |
| **Functionality / short description** | Erzeugt Themenbäume (Sammlungsstrukturen) für Bildungsinhalte: aus einem Thema, einem Strukturdokument wie einem Lehrplan, aus Ordnern und Dateien oder aus unstrukturierten Inhalten. Entwürfe lassen sich mit Rückmeldungen weiterentwickeln, Inhalte werden den Knoten zugeordnet. (German, identical to `info.description`) |
| **Use cases** | `topic`, `document`, `folders`, `contents`, plus `mode: refine` (feedback as text or targeted changes, including `describe` for new descriptions of single nodes with the whole tree as context), sorting contents into an existing tree without changing the nodes (`options.assign_only`, also for collection trees from the repository with `nodeId`) and assigning contents with confidence. The short description above is word-for-word identical to `info.description` (ensured by a test). |
| **Stable version** | `follow-up` **`2.2.0`** prepared in the code (version in `pyproject.toml` and `Chart.yaml`, CHANGELOG); the release tag `v2.2.0` is set after the merge, then the CI publishes the image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026:2.2.0` and the OCI chart `topic-tree` `2.2.0`. Until then **`2.1.0`** (tag `v2.1.0` of 26.11.2026, image and chart `2.1.0` on GHCR) is the latest published version. The older tag `v2.0.0` of 25.11. remains; no image or chart was ever built for it. In the handover repo, the state in branch [`v2`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2) is still awaiting the sync, see *Repository*; [`pyproject.toml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/pyproject.toml) & [`Chart.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/Chart.yaml) kept in sync by a CI test; previous state [`0.4.0`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/0.4.0) · overview of changes: [`docs/de/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/aenderungen-v0.4-zu-v2.0.md)) |
| **Technical owner / contact person** | Jan Schachtschabel · **Deputy:** `being clarified` *(to be named before the T6 handover, e.g. Tobias Müller)* |
| **Jira** | `WLO-87: Themenbaum-Generator` |
| **Deployment status** | `extern` (Docker/Compose test instance) · `staging` (`0.4.0` active behind the b-api; upgrade to `2.2.0` prepared) · `prod` (pending after T6 acceptance) |
| **Quality assessment** | `verified` **718 automated tests** (`pytest`, incl. schema, contract, auth, Helm & Gunicorn E2E tests; 6 Helm tests run only with `helm`, i.e. in the CI), 44 Node tests of the test UI and 8 `promtool` tests of the alert rules, four complete audits (25./26.11.2026, overall audit 26.11.2026 [`docs/audits/2026-11-26-gesamtaudit.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-gesamtaudit.md) and final audit 26.11.2026 [`docs/audits/2026-11-26-abschlussaudit.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-abschlussaudit.md) (German), all findings fixed or left open with a reason), **live test** of 26.11.2026 across all 18 UI examples and a refine chain ([`docs/audits/2026-11-26-live-test.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-live-test.md)), **load measurements** of 24./25.11.2026 across all v2 use cases, combinations and both v1 legacy endpoints (skeleton first with deterministic duplicate elimination: **0 duplicates** on 100–140 nodes; SkoHub label→URI mapping without invented URIs) |
| **Repository** | `being clarified` **Handover repo for T6:** [`https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator) (state `2.0.0` in branch [`v2`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2), sync to `2.2.0` pending, old state `0.4.0` in [`main`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/main) / tag [`0.4.0`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/0.4.0)). **Development:** [`https://github.com/janschachtschabel/topic-tree-generator-11-2026`](https://github.com/janschachtschabel/topic-tree-generator-11-2026) (`main`, GitHub Actions, image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026` available without login). Before the handover, sync the GitLab state with `main` on GitHub. |
| **OpenAPI spec** | `verified` Generated from the FastAPI code at `GET /openapi.json` (`/docs`, `/redoc`), with an end-user description (`info.title`, `info.description`) and request examples from the minimal to the full call ([`app/api/examples.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/api/examples.py)). Exported JSON schemas additionally under [`docs/schemas/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/docs/schemas), API reference under [`docs/de/api.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/api.md), operations manual with runbook under [`docs/de/betrieb.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/betrieb.md). Internal paths (`/health`, `/_ping`, `/ready`, `/metrics`, `/ui/*`) do **not** appear in `/openapi.json` (ensured by a test). |
| **Pipeline and Git tags** | `verified` GitLab CI ([`.gitlab-ci.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.gitlab-ci.yml)): runs `ruff check`, `ruff format --check`, `pytest`, `helm lint --strict` + `kubeconform`, validates tag consistency (`vX.Y.Z` == `pyproject.toml` == `Chart.yaml`) and on `vX.Y.Z` tags builds/publishes container images and the versioned **Helm chart as an OCI artifact** (additionally `docker compose config`, `promtool check rules` and `promtool test rules` in [`.github/workflows/ci.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.github/workflows/ci.yml)). The GitHub CI is the one active today (check job read-only, only the publish job has `packages: write`; the tag must equal the version and be on `main`). Since `2.1.0` in the GitHub CI: a lock against republishing a version (image and chart are checked first), `latest` only comes from `main` (a release tag does not move it), manual republishing of a tag via `workflow_dispatch`, `uv lock --check` and a check job `pip-audit` for known vulnerabilities in the runtime dependencies (reports, does not block publishing). Since `2.2.0`: unit tests of the alert rules with `promtool test rules` ([`tests/alerts/topic-tree.test.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/tests/alerts/topic-tree.test.yml)). **Not yet in the CI (target):** type checking; actions are pinned to version tags instead of commit SHAs. |
| **Endpoints** | `verified` **Public (port `8000`):**<br>• `POST /v2/topic-tree` *(v2 main endpoint: all 4 use cases + `refine` (incl. `describe` and `assign_only`) + content assignment)*<br>• `POST /generate-topic-tree` *(v1 legacy, frozen format-compatible)*<br>• `POST /generate-collection-description` *(v1 legacy, frozen format-compatible; successor is the change `describe`)*<br>• `GET /` *(short service info, not in OpenAPI)*<br>• `GET /_ping`, `GET /health` *(liveness/readiness for the K8s probe, not in OpenAPI)*<br>• Optional `GET /ui/*` *(built-in test UI, switched off completely in production via `UI_ENABLED=false` → `404`)*<br>**Internal (port `9000`, cluster/monitoring only):**<br>• `GET /health`, `GET /ready`, `GET /metrics` (other methods: `405` as JSON) |
| **Endpoints on two ports** | `verified` **Yes:** public API port `PUBLIC_PORT=8000` (FastAPI/Uvicorn worker) and a separate internal port `INTERNAL_PORT=9000` (bound once in the Gunicorn master for `/health`, `/ready`, `/metrics`) |
| **Headers / content types** | `verified` **Content-Type:** `application/json` only (no SSE/streaming, no file uploads).<br>**Incoming headers:** `Authorization: Bearer bdt_…` (b-api delegation token, alternatively the configurable `B_API_DELEGATION_HEADER`; in standalone operation optionally `SERVICE_API_KEYS`), optionally `X-B3-*` / `b3` and `x-client-trace-id`. No own person or repository headers (`X-Edu-*`, `X-API-KEY` are never sent).<br>**Outgoing headers to the caller:** `Retry-After` (on `503 LLM_UNAVAILABLE`) and `WWW-Authenticate` (on `401`).<br>**Allowances in the proxy entry:** `allowedResponseHeaders: [Retry-After, WWW-Authenticate]`; `allowedRequestHeaders: [b3, X-B3-TraceId, X-B3-SpanId, X-B3-ParentSpanId, X-B3-Sampled, X-B3-Flags, x-client-trace-id]`, unless the b-api forwards them anyway (to be clarified with the b-api admin). |
| **Asynchronous job endpoints** | `verified` **None (synchronous service)**: a deliberate architecture decision, because the b-api delegation token (`bdt_…`) expires when the HTTP call ends, and background jobs in the service may no longer call back the b-api in the person's context (guideline ch. 1 & 2.2). For multi-step repository workflows, the service is called from a **Kestra flow** via `/api/v1/proxy/topic-tree`. |
| **Request timeout** | `verified` Service deadline **`REQUEST_TIMEOUT_SECONDS=280`** (280 s), Gunicorn worker timeout `310 s`, graceful shutdown `graceful_timeout=290 s` / `terminationGracePeriodSeconds=300 s`, single LLM call `LLM_TIMEOUT_SECONDS=120`. **Required proxy/ingress timeout (`responseTimeout` in the b-api): at least `310 000 ms` (310 s).** |
| **Readiness status** | `verified` Kubernetes `livenessProbe` checks `GET :9000/health`, `readinessProbe` checks `GET :8000/health` **entirely without external dependencies** (does not take pods out of rotation during a b-api outage, guideline ch. 3). `GET :9000/ready` separately checks the local configuration (`LLM_NOT_CONFIGURED`). |

---

## 2. Architecture & b-api integration

### Short architecture overview (guideline ch. 3)

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

In English: caller / edu-sharing / Kestra flow → `topic-tree :8000` (stateless FastAPI) with input and size checks,
optional loading of `items_ref` / `fulltext.ref` (HTTPS and `REF_ALLOWED_HOSTS` only, SSRF-protected), a strategy per
use case, the `LLMClient` (no streaming, semaphore, JSON schema + 1 repair, static `system.md` prefix for prompt
caching, B3/trace forwarding), optional content assignment (batches of 40) and vocabulary classification
(label → SkoHub URI), and deterministic post-processing (duplicate elimination, short titles ≤ 20 characters, keys,
diff status, quality checks). Outbound only to the b-api LLM router (in the standalone exception: an
OpenAI-compatible endpoint via `OPENAI_API_KEY`); internal port `:9000` for `/health`, `/ready`, `/metrics`.

| Field | Status & current state (`2.2.0`) |
|---|---|
| **Overview** | Python 3.13, FastAPI, Pydantic v2, `openai` AsyncClient (via a shared `httpx.AsyncClient`), `gunicorn` + `uvicorn-worker`, `loguru`, `prometheus-client`; bundled offline SkoHub vocabulary snapshot (`discipline`, `educationalContext`, `intendedEndUserRole` under [`app/vocab/data/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/app/vocab/data)) |
| **Horizontal scalability / cluster capability** | `verified` **Fully stateless (`stateless`)**: no sessions, no in-memory jobs, no SQLite/database, no shared volume. Any number of pods in parallel behind one service (`RollingUpdate`, chart default `replicaCount: 2`, optional HPA `2–6` pods). Scaling limits lie solely in the rate limits/quotas of the upstream LLM route (especially the GWDG quota of ~10 req/min; a 3-level tree needs ~9–14 LLM calls and should therefore run on OpenAI/Azure routes instead of GWDG). |
| **Integrated in the B-API (`b-api`)** | `being clarified` *(code & reference route done; proxy update on staging/prod to be done with the b-api admin)*:<br>• Proxy entry: **`topic-tree`** (`/api/v1/proxy/topic-tree`)<br>• `forwardDelegation: true`, `delegationScopes: ["llm"]` (`forwardApiKey` not needed)<br>• `responseTimeout: 310000` (310 s), `delegationLifetimeSeconds` ≥ `310`<br>• Required permissions on the key: service permission `topic-tree` + LLM permission<br>• `openApiPath: /openapi.json`; `pathToIgnore`: `/`, `/_ping`, `/health`, `/ui/**`, `/docs`, `/redoc` (not in the spec, but reachable on the public port)<br>• Header allowances see *Headers / content types*<br>• **b-api cache:** the service sends no `temperature`; the b-api can therefore answer identical requests from its cache (same tree, no cost). Whether "regenerate" should bypass the cache via `?ignore-caching=true` is open.<br>• **Recommended LLM route `topic-tree-generator`** (reference template [`deploy/b-api/route-topic-tree-generator.json`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/b-api/route-topic-tree-generator.json)):<br>  – **Level 0 (primary):** **`gpt-6-luna`** (OpenAI, `oa-gpt6-luna`, weight `1`)<br>  – **Level 1 (secondary / fallback):** **`gpt-5.6-luna`** (OpenAI, `oa-gpt56-luna`, weight `1`)<br>  – `maxAttempts: 3`, `clearCache: true` on save; both models use the same `common` body (`max_completion_tokens` + `reasoning_effort: "none"`, `json_schema` `strict: true`, no streaming). Do not configure a GWDG fallback (~8–14 parallel calls per tree exceed the GWDG limit of ~10 req/min). |
| **Calls the b-api itself?** | `verified` **Yes**, only `POST /api/v1/llm/router/chat/completions` (or, with `B_API_MODEL` set, `/api/v1/llm/{provider}/chat/completions`) with the unchanged `Authorization: Bearer bdt_…` header. **No** calls to `/api/v1/edu-sharing/**`, **no verified person required**. Whether guest calls without a person may make LLM calls via delegation is still being clarified by the b-api team (guideline ch. 8). |
| **Writes suggestions** | `verified` **No** (pure computation service, returns JSON to the caller) |
| **Uses routing** | `verified` **Yes** (`B_API_ROUTE`, chart default `topic-tree-generator`, also understands `provider/model`; parameter family `LLM_PARAM_FAMILY=common` sends `max_completion_tokens` + `reasoning_effort: "none"`, compatible with GPT-5/GPT-6 as well as Qwen/Gemma/DeepSeek) |
| **Uses API keys** | `verified` **Behind the b-api: no** (only forwards the received delegation token `bdt_…`; no service key, no `X-API-KEY`).<br>**Exception mode without b-api (`SERVICE_MODE=standalone` / `auto`):** supports `OPENAI_API_KEY` + its own bearer check via `SERVICE_API_KEYS` (constant time via `hmac.compare_digest`); locally for testing optionally `B_API_DEV_KEY`. |
| **Repo via B-API / repository independence** | `verified` **No repository access** (neither directly nor via the b-api). All functions work entirely with the text and metadata passed in; optional `nodeId` values are passed through unchanged (guideline ch. 1 "independent of the repository"). |
| **Required services / dependencies** | `verified` **Runtime:** only the b-api LLM router (or, in standalone mode, an OpenAI-compatible LLM endpoint). Optional HTTPS download of `items_ref` / `fulltext.ref` only from hosts explicitly allowed in `REF_ALLOWED_HOSTS` (default empty = blocked). No other services needed. |

### Row for the compatibility matrix (guideline ch. 6)

| Service ID | needs services | permissions on the key | delegation scopes | LLM route | repository relation | only together with |
|---|---|---|---|---|---|---|
| `topic-tree` | none (only b-api LLM; in a flow optionally `text-extraction` / repo full text before it) | proxy permission `topic-tree` + LLM | `llm` | `topic-tree-generator` *(primary: `gpt-6-luna`, secondary: `gpt-5.6-luna`; `common` body)* | none (`nodeId` is only passed through; full texts/metadata come as input) | — (usable on its own) |

---

## 3. Deployment, infrastructure, security & monitoring

| Area / field | Status & current state (`2.2.0`) |
|---|---|
| **HELM** | `verified` Versioned chart in the repo under [`deploy/helm/topic-tree`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/deploy/helm/topic-tree) (`version: 2.2.0`, `appVersion: "2.2.0"`, default `config.serviceMode: bapi`), incl. `Deployment`, `Service` (port `8000` + `9000`), `PodDisruptionBudget` (on by default, `maxUnavailable: 1`), `Ingress`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `HorizontalPodAutoscaler` and a fully documented [`values.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/values.yaml) (`## @param`). Probes (`probes.liveness`, `probes.readiness`) configurable via `values.yaml`. The pod gets no service account token (`automountServiceAccountToken: false`); the probes have `timeoutSeconds: 3`. Validated in CI with `helm lint --strict`, `kubeconform`, `promtool check rules` and `promtool test rules`; packaged automatically as an OCI chart on release tags. |
| **Docker files & image size** | `verified` Multi-stage [`Dockerfile`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/Dockerfile) on `python:3.13-slim-bookworm` (base images pinned with an `@sha256` digest; [`.github/dependabot.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.github/dependabot.yml) is set up, but version PRs are paused (`open-pull-requests-limit: 0`), digests are updated by hand until approval), [`.dockerignore`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.dockerignore) present, runs as non-root (`uid=10001`), pod security **`restricted`** (`readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault`; only `/tmp` as `emptyDir`).<br>**Image size:** **70 MB** compressed (sum of layers in GHCR, `latest` measured on 26.11.2026, available without login), **193 MB** unpacked (measured 24.11.2026), **0 MB models/corpora** in the image (the bundled SkoHub vocabulary snapshot is plain JSON < 200 KB).<br>Reference compose files: [`docker-compose.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docker-compose.yml) and [`docker-compose.build.yml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docker-compose.build.yml). |
| **Components that can be switched off** | `verified` Test UI can be switched off via `UI_ENABLED=false` (`false` by default in the Helm chart); `Ingress`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `Autoscaling` individually switchable in the chart via `.enabled`. |
| **Database** | `verified` **No** (no database, no Redis, no SQLite). |
| **Large data & updates / CronJobs** | `verified` **No** (no large models, indexes or volumes/PVCs; no CronJobs needed). The compact OEH SkoHub vocabulary ([`app/vocab/data/`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/tree/v2/app/vocab/data)) is updated when needed before a release via [`scripts/build_vocab_snapshot.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/build_vocab_snapshot.py); the snapshot date is shown in `GET /health` (`vocab_snapshot`). |
| **Authentication** | `verified` Behind the b-api via the forwarded delegation token (`Authorization: Bearer bdt_…` or `B_API_DELEGATION_HEADER`). In standalone operation optionally via `SERVICE_API_KEYS`. Keys/tokens are never stored or logged. |
| **Network policy** | `present` Template [`deploy/helm/topic-tree/templates/networkpolicy.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/templates/networkpolicy.yaml) limits ingress to `publicFrom` (`:8000`) and `internalFrom` (`:9000`) and egress to DNS (`53/UDP+TCP`) plus configurable `egress` targets. In the chart `networkPolicy.enabled: false` by default until T6 names the namespaces of b-api/ingress and monitoring. |
| **ENV variables** | `verified` Fully configurable via environment variables with sensible defaults ([`app/settings.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/settings.py), documented in [`.env.example`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/.env.example), [`README.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/README.md) and [`values.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/values.yaml)). |
| **Required secrets** | `verified` **Behind the b-api: no secrets needed** (`secrets.existingSecret: ""`).<br>**Only when operating without the b-api (`standalone`):** `OPENAI_API_KEY` and `SERVICE_API_KEYS` (mounted separately in the chart via `secrets.existingSecret` per `secretRef`). |
| **Prometheus** | `verified` `GET :9000/metrics` (internal port only, multiprocess-capable via `PROMETHEUS_MULTIPROC_DIR`). Metric labels come exclusively from fixed code constants (`route`, `step`, `outcome`, `kind`, `code`; no unbounded path labels):<br>• `topic_tree_requests_total{route, status}` & `topic_tree_request_seconds{route}`<br>• `topic_tree_llm_calls_total{step, outcome}` & `topic_tree_llm_seconds{step}`<br>• `topic_tree_llm_tokens_total{kind="prompt"|"cached"|"completion"}`<br>• `topic_tree_warnings_total{code}` |
| **Alert rules** | `present` [`deploy/helm/topic-tree/templates/prometheusrule.yaml`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/helm/topic-tree/templates/prometheusrule.yaml) with 5 alerts, each with `description` and `runbook_url` (section *Runbook* in [`docs/de/betrieb.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/betrieb.md), base URL via `prometheusRule.runbookUrl`), tested with `promtool test rules`:<br>1. `TopicTreeDown` (no pod scrapable for 5 min, `critical`)<br>2. `TopicTreeServerErrors` (> 5 % of requests with 5xx over 10 min, from 10 requests)<br>3. `TopicTreeLLMErrors` (> 20 % failed LLM calls over 10 min, from 10 calls; 401/403 due to missing caller permissions do not count)<br>4. `TopicTreeSlowRequests` (P90 response time `v2.topic_tree` > 240 s over 15 min)<br>5. `TopicTreeDescribeFailures` (> 20 failed description batches `DESCRIBE_FAILED` per hour, `info`)<br>For the Prometheus Operator, labels can be set (`serviceMonitor.labels`, `prometheusRule.labels`, e.g. `release`). |
| **B3 tracing & logging** | `verified` Structured JSON logs to `stdout` with `timestamp`, `level`, `service` (`topic-tree`), `trace_id`, `span_id`, `message` (switchable locally via `LOG_FORMAT=text`; server access logs disabled, own request log line without headers/raw paths; `httpx`/`httpcore` at `WARNING`).<br>Reads and validates `b3` as well as `X-B3-TraceId` / `X-B3-SpanId` / `X-B3-Sampled` (regex-checked against log injection in [`app/context/tracing.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/app/context/tracing.py)) and forwards them together with `x-client-trace-id` to the b-api (`x-client-trace-id` is never invented and appears as `client_trace_id` in every log line of the request). Third parties receive no trace headers: neither the hosts of references (`refs.py`) nor a provider addressed directly in standalone operation. |

---

## 4. Resources, runtimes & costs (measured)

- **Compact overview of changes (`v0.4.0` → `v2.0.0`):** [`docs/de/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/aenderungen-v0.4-zu-v2.0.md) (English: [`changes-v0.4-to-v2.0.md`](changes-v0.4-to-v2.0.md))
- **Complete single and load measurement incl. token breakdown & cost formula:** [`docs/measurements/2026-11-24-openai-gpt-6-luna.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-24-openai-gpt-6-luna.md)
- **Direct comparison v1 vs. v2 across 3 topics (25.11.2026):** [`docs/measurements/2026-11-25-v1-vs-v2-comparison.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-25-v1-vs-v2-comparison.md)

### CPU, RAM and storage (`verified`)

- **Memory behaviour:** largely **fixed / flat** (no local ML models, no indexes).
- **Measured values:**
  - Linux container (`docker stats` / cgroup, Gunicorn master + `WEB_CONCURRENCY=2` workers): **125.7 MiB** idle.
  - Single worker process under parallel load (`c=3`): **71.5 MiB** idle → **95.0 MiB** warm → **97.0 MiB** peak (equivalent to a **~235 MiB** peak for master + 2 workers).
- **Recommendation for Kubernetes (`values.yaml`):**
  - `requests`: **`100m` CPU / `256Mi` RAM**
  - `limits`: **`512Mi` RAM** *(no hard CPU limit recommended, as the service mostly waits on network I/O to the LLM; the RAM buffer of more than +30 % covers up to `5.000` items / `10 MiB` `items_ref` and `fulltext.ref` payloads in memory)*.
- **Internal limits matching the limit:** `WEB_CONCURRENCY=2`, `LLM_MAX_CONCURRENCY=20` per worker, `httpx` pool `max_connections=50`, `REF_MAX_BYTES=10 MiB`, `MAX_TREE_DEPTH=3`, `MAX_NODES_PER_LEVEL=20`. No `numpy`/BLAS in use.

### Runtime & token demand per function / endpoint (`gpt-6-luna`)

Single runs from the live test of 26.11.2026 (standalone against OpenAI, all 18 UI examples, final run,
[`docs/audits/2026-11-26-live-test.md`](https://github.com/janschachtschabel/topic-tree-generator-11-2026/blob/main/docs/audits/2026-11-26-live-test.md)); tokens = input + output; 40–85 % of the input tokens came from the prompt cache. Load and v1 from the measurements of 24./25.11.2026.

| Endpoint / scenario | Runtime (single run) | LLM calls | Total tokens | Under load |
|---|---:|---:|---:|---|
| `POST /v2/topic-tree` — `topic`, 2 levels (24–52 nodes, also with contents, document or `auto_metadata`) | **13.5 – 19.8 s** | 4 – 7 | **14,700 – 28,000** | — |
| `POST /v2/topic-tree` — `topic`, 3 levels (83 nodes) | **20.4 s** | 10 | **43,100** | 3 levels, ~100–150 nodes, concurrency 8: **P50 63.5 s / P90 112.1 s** (24.11.) |
| `POST /v2/topic-tree` — `document` (curriculum excerpt, also with `topic`) | **7.5 – 11.7 s** | 3 | 8,600 – 9,600 | — |
| `POST /v2/topic-tree` — `folders` (with `improve`, loose files) | **4.6 – 5.4 s** | 2 | 5,300 – 5,400 | — |
| `POST /v2/topic-tree` — `contents` (12 materials) | **12.2 – 12.8 s** | 2 | 7,200 – 7,300 | — |
| `POST /v2/topic-tree` — `refine` with text feedback, new contents or `add`/`split` | **1.8 – 12.0 s** | 1 – 5 | 2,600 – 18,900 | — |
| `POST /v2/topic-tree` — `refine` with `feedback.changes` only (`remove`/`move`/`edit` …) | **< 0.05 s** | **0** | 0 | — |
| `POST /generate-topic-tree` *(v1 legacy, 65–78 nodes, 25.11.)* | **40.2 – 41.9 s** | 21 – 25 | 53,600 – 59,500 (0 % cached) | — |
| `POST /generate-collection-description` *(v1 legacy, 70 words, 25.11.)* | **10.4 – 12.7 s** | 1 | ~710 | — |

The number of nodes for a topic varies between runs (e.g. 72–100 nodes for `topic_sek1`), and the runtime with it.
P50/P90 per endpoint via b-api staging are still pending (see section 6).

- **Cost estimate:** complete token calculation model per 1,000 calls in [`docs/measurements/2026-11-24-openai-gpt-6-luna.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/measurements/2026-11-24-openai-gpt-6-luna.md#6-rechenmodell-fur-spatere-kostenbewertungen). `being clarified`: the guideline requires measured costs per function from the b-api usage data. They will be taken from the bookings of the test key during the staging acceptance run; until then the token figures above apply.

---

## 5. Deliberate deviations from the service guideline (with reasons)

1. **Synchronous response time > 30 s for large 3-level trees (ch. 1 target):**  
   A complete tree with 80–150 described nodes takes around 20–45 s in a single run, under load up to 112 s (P90). A background job in the service may no longer call the b-api with the delegation token (`bdt_…`) after the HTTP request has ended (ch. 2.2). The endpoint therefore responds synchronously within `REQUEST_TIMEOUT_SECONDS=280` (required proxy timeout ≥ `310 s`); for asynchronous background runs, a Kestra flow calls the service via `proxy:topic-tree` (ch. 5).
2. **Lightweight B3/trace forwarding without an OpenTelemetry span exporter (ch. 2.3 target):**  
   B3 headers (`b3`, `X-B3-*`) and `x-client-trace-id` are fully validated, written into every JSON log line and propagated to outgoing b-api calls. The additional `opentelemetry-sdk` (OTLP span export) was left out in favour of minimal dependencies and a slim image (70 MB compressed).
3. **Optional standalone mode for development & single-instance operation (ch. 2.2 "exception: operation without b-api"):**  
   Behind the b-api (`SERVICE_MODE=bapi`), the service accepts only delegation tokens (`bdt_…`) without its own provider keys. For local development and standalone Docker test instances, it additionally supports `OPENAI_API_KEY` + `SERVICE_API_KEYS` via env (`SERVICE_MODE=standalone` / `auto`).
4. **`401` instead of an anonymous response without a token (ch. 1 target):**  
   Every function except targeted changes needs the language model, and behind the b-api the service reaches it only with the forwarded token. Without a token it therefore responds `401 UNAUTHORIZED` ("Aufruf nur über die b-api", calls only via the b-api). A call via the b-api always carries a token, also for guests.
5. **Error format of the v1 endpoints (ch. 1 target):**  
   `/generate-topic-tree` and `/generate-collection-description` keep responding with `{"detail": …}` without `trace_id`, so that existing callers keep working unchanged. `/v2/topic-tree` uses the format `{"error": {"code", "message", "trace_id"}}`.
6. **`/ready` checks only the configuration (ch. 3):**  
   The readiness probe (`:8000/health`) checks no dependencies, as required. `:9000/ready` reports whether an LLM route or model is configured, but does not call the b-api; the reachability of the b-api is shown by the LLM metrics and the alert `TopicTreeLLMErrors`.

---

## 6. Remaining organisational items before handover to Team 6 / b-api admin

All technical guideline adjustments in the code, Helm chart, Dockerfile and CI workflow (steps for T6 in the [operations manual](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/betrieb.md), see also [`docs/de/aenderungen-v0.4-zu-v2.0.md`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/docs/de/aenderungen-v0.4-zu-v2.0.md)) are **implemented and tested**.

Before the final production handover, only the following **organisational / platform coordination items** are open:

1. **Set up the b-api proxy entry `topic-tree` & route `topic-tree-generator` (b-api admin):**
   - Proxy: enable `forwardDelegation: true` and `delegationScopes: ["llm"]` (remove `forwardApiKey`), set `responseTimeout` ≥ `310000` ms, check the path `/v2/topic-tree`.
   - Create the LLM route `topic-tree-generator` according to [`deploy/b-api/route-topic-tree-generator.json`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/deploy/b-api/route-topic-tree-generator.json) (**level 0: `gpt-6-luna`**, **level 1: `gpt-5.6-luna`**, `maxAttempts: 3`, `clearCache: true`).
2. **Level 2/3 measurement via b-api staging:**
   - Run [`scripts/probe_llm.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/probe_llm.py) and [`scripts/loadtest.py`](https://scm.edu-sharing.com/edu-sharing/projects/wlo/topic-tree-generator/-/blob/v2/scripts/loadtest.py) against the real staging b-api and enter the booked EUR/USD costs per use case from the b-api usage data in section 4 above.
3. **Clarify platform details, naming convention & deputy with Team 6:**
   - Ask for the namespaces for ingress/b-api (`networkPolicy.publicFrom`) and monitoring (`networkPolicy.internalFrom`) as well as egress targets for enabling the `NetworkPolicy`.
   - Enter the deputy contact person under *Technical owner*.
4. **Release and repository:**
   - Done on 26.11.2026: tag `v2.1.0` set, image and chart `2.1.0` published on GHCR (available without login, see *Stable version*).
   - Open: set tag `v2.2.0` after merging the final audit (version prepared in the code).
   - Clarify which repository T6 builds from (GitLab `scm.edu-sharing.com` or GitHub), and sync the GitLab state with `main`.
   - Optionally agree at handover whether the repository/image name in GitLab should be unified from `topic-tree-generator` (and on GHCR from `topic-tree-generator-11-2026`) to the service ID `topic-tree` (the `OPENAI_MODEL` default `gpt-6-luna` in standalone mode was deliberately kept for backward compatibility with existing `.env` setups).
