# topic-tree (Themenbaum-Dienst)

FastAPI service that generates edu-sharing collection structures ("Themenbäume") with an LLM: from a topic, a structure document (such as a curriculum), uploaded folders and files, or unstructured contents. Drafts can be refined iteratively with feedback, and content items are assigned to nodes with confidence scores. An existing tree, also one taken from the repository, can be filled with contents only (structure, properties and `nodeId` stay as they are), and single nodes can get a fresh description with the whole tree as context.

- **`POST /v2/topic-tree`** – current v2 API; `/docs` explains use cases, combinations and options and offers an example for each in the "Examples" drop-down ([API reference](docs/api.md), [JSON schemas](docs/schemas/), [example payloads](docs/examples/))
- **`POST /generate-topic-tree`**, **`POST /generate-collection-description`** – format-frozen legacy v1 endpoints (now sharing standalone & b-api auth/backend resolution with v2); new callers describe collections with the `describe` change of v2 (see use case 7)
- **Built-in Test UI** at `/ui/` (optional, toggleable via `UI_ENABLED`)
- **Operations & benchmarks**: [docs/steckbrief.md](docs/steckbrief.md) · [v1 vs. v2 comparison](docs/measurements/2026-11-25-v1-vs-v2-comparison.md) · [v2 load & token benchmark](docs/measurements/2026-11-24-openai-gpt-6-luna.md) · [Design plan](docs/plans/2026-11-24-topic-tree-v2.md)

## How it works

```text
request → input & cap checks → resolve refs (allow-listed) → strategy per use case
        → assign contents → optional auto_metadata (label → URI)
        → dedup, short titles, keys, status, shape & quality checks → JSON response
```

- **`topic`**: Generates the complete title-only skeleton across all requested levels in a single LLM call, eliminates any duplicate titles deterministically, and describes all nodes in parallel balanced batches of up to 10 nodes (each sharing the full tree outline in the prompt-cache prefix for crisp demarcation). Extra Level-1 topics (`extra_topics`: `"general"`, `"methodology"`) count toward the total Level-1 `main_topics` range.
- **`document`**: Parses Markdown headings and page markers deterministically, maps the outline into a tree with `origin.document` (`section`, `page`), and writes node descriptions from section excerpts (falling back deterministically to the document's headings with an `LLM_DEGRADED` warning if the LLM is unavailable).
- **`folders`**: Preserves the uploaded folder hierarchy (`origin.folder`), optionally applies renames/merges/moves when `options.improve=true` (each reported in `changes[]`), and degrades gracefully (`LLM_DEGRADED`) if the LLM is unavailable.
- **`contents`**: Induces topic groups from a stratified sample of items (`origin.cluster`), eliminates duplicate group titles, and assigns every item with confidence.
- **`mode: refine`**: Applies structured `feedback.changes` first, then interprets free-text `feedback.text` while protecting `feedback.locked` subtrees. With `options.assign_only=true`, only new items are sorted into the existing tree and every node comes back as sent; the `describe` change rewrites descriptions of chosen nodes with the tree as context.
- **Prompt caching**: All prompts live in `app/prompts/`; `system.md` is strictly static across every LLM call.

## What changed from v1 to v2

The original v1 service (archived on branch `backup_old`; response schemas preserved on `/generate-topic-tree` and `/generate-collection-description`) was tightly coupled to a single deployment path and generation cascade. Version 2 redesigns both the runtime architecture and the tree generation pipeline:

| Dimension | Legacy v1 (`/generate-topic-tree`, `/generate-collection-description`) | Current v2 (`POST /v2/topic-tree`) |
|---|---|---|
| **Deployment & LLM routing** | Originally hardcoded to run strictly behind the b-api router (`/api/v1/llm/router/`, fixed route `topic-tree-generator`) with mandatory caller Bearer tokens. *(Note: v1 endpoints now also support standalone `OPENAI_API_KEY` / `SERVICE_API_KEYS` so `/docs` works without b-api, while keeping router compatibility behind the b-api.)* | Runs behind the b-api (`Bearer bdt_…`), standalone against OpenAI or any OpenAI-compatible API (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`), or in `auto` dual mode with optional `SERVICE_API_KEYS`. Behind the b-api, supports **both** router routes (`B_API_ROUTE`) and direct single-model provider calls (`B_API_MODEL` + `B_API_MODEL_PROVIDER`) without depending on a router route. |
| **Use cases & workflows** | Single rigid workflow: 3-level topic cascade (`main → sub → curriculum`) from a theme string only. No iterative editing, no document parsing, no content sorting. | **4 combinable use cases** (`topic`, `document`, `folders`, `contents`) + iterative **`mode: refine`** (`feedback.changes`, free-text `feedback.text`, `feedback.locked` subtrees, `options.assign_only`) + content assignment (`items` with `nodeId` passthrough and confidence scores). |
| **Duplicate prevention & speed** | Generated main topics, subtopics, and curriculum topics in isolated per-branch LLM calls without global sibling visibility—prone to duplicate titles across branches and slow multi-hop cascades. | **Skeleton-first**: plans the complete multi-level outline in one LLM call, runs deterministic duplicate elimination (`eliminate_generated_duplicates`), and generates descriptions/keywords in **parallel balanced 10-node batches** that all receive the full tree outline in the prompt-cache prefix. |
| **Vocabulary & metadata** | Copied caller-supplied `discipline_uri` / `educational_context_uri` onto all nodes verbatim; no node-level classification, fixed teacher role. | Bundled offline **OEH SkoHub vocabulary snapshot** (`discipline`, `educationalContext`, `intendedEndUserRole`). With `options.auto_metadata=true`, classifies nodes onto exact German labels via strict JSON schema and maps them deterministically to URIs. |
| **Response & error contract** | Frozen v1 response (`metadata` + `collection` with `cm_title` etc., or raw `str`) and FastAPI `{"detail": "…"}` errors so existing edu-sharing integrations stay drop-in compatible. | Rich `TopicTreeResponseV2` (`collection` with stable `key`/`status`/`origin`/`items`, `unassigned`, `changes`, `warnings`, `questions`, `usage`, `metadata.generation`) and uniform `{"error": {"code", "message", "trace_id"}}` error payloads without raw exception text. |

---

## Installation & Docker Setup

### Option A: Docker Compose – local build & direct ports (quickest for local or single-host Docker)

Uses [`docker-compose.build.yml`](docker-compose.build.yml) (builds the multi-stage `python:3.13-slim` image, ~193 MB, non-root `uid=10001`, read-only root filesystem, exposes `:8000` public and `:9000` internal).

```shell
git clone https://github.com/janschachtschabel/topic-tree-generator-11-2026.git
cd topic-tree-generator-11-2026
cp .env.example .env
# Edit .env: set OPENAI_API_KEY (standalone) or configure B_API_BASE_URL + B_API_ROUTE (or B_API_MODEL)
docker compose -f docker-compose.build.yml up --build -d
```

Verify the running container:

```shell
curl -s http://localhost:8000/health     # {"status":"ok","vocab_snapshot":"..."}
curl -s http://localhost:9000/ready      # 200 if LLM credentials or b-api mode are ready
curl -s http://localhost:9000/metrics    # Prometheus metrics (internal port only)
```

Open the built-in test UI at `http://localhost:8000/ui/` (or OpenAPI docs at `http://localhost:8000/docs`).

**Alternative ports (several APIs on one host):** if `8000`/`9000` are already taken, set different ports in `.env`;
both Compose files use them for the container *and* the host side, Traefik routing and the healthcheck follow:

```shell
# .env
PUBLIC_PORT=8010
INTERNAL_PORT=9010
```

Then the UI is at `http://localhost:8010/ui/` and `/ready` at `http://localhost:9010/ready`. The two ports must differ
and lie in `1–65535`; inside the container (non-root) choose ports `≥ 1024`.

### Option B: Docker Compose – pre-built image behind Traefik (Compose-from-URL / reverse proxy)

Uses [`docker-compose.yml`](docker-compose.yml) with Traefik HTTPS labels and zero required environment variables on first start:

1. Deploy the repository with `docker-compose.yml` (starts cleanly using `.env.example` defaults; no external Docker network required—`TRAEFIK_NETWORK` is created/used automatically).
   Without a domain the service is reachable directly at `http://<server-ip>:18000/` (UI: `/ui/`). Change the host
   port with `HOST_PORT` if `18000` is taken.
2. Configure `.env` with:
   - LLM credentials: `OPENAI_API_KEY=<your-key>` (standalone) **or** `SERVICE_MODE=bapi` + `B_API_BASE_URL` / `B_API_ROUTE`
   - `SERVICE_API_KEYS=<secret>` **together with the LLM key**: the direct port is public and unencrypted, so without
     a service key anyone who finds it can generate trees at your LLM cost (the test UI has a token field for it).
   - Optional hardening: `UI_ENABLED=false`
3. Later, with a domain: `DOMAIN=trees.example.org` (bare hostname only—**no** `https://`, path, or port), point the
   DNS A/AAAA record to the host and redeploy. Traefik terminates TLS and routes HTTPS traffic to container port
   `8000`; port `9000` stays internal only. Then set `HOST_BIND=127.0.0.1` to close the unencrypted direct port.

To pin a specific release tag (recommended for staging/production) instead of `:latest`:

```shell
IMAGE=ghcr.io/janschachtschabel/topic-tree-generator-11-2026:2.1.0 docker compose up -d
```

### Option C: Kubernetes / Helm Chart (`deploy/helm/topic-tree`)

A production-ready Helm chart template (`version` = `appVersion` = `2.1.0`, non-root `uid=10001`, `readOnlyRootFilesystem: true`, two-port `Service` `:8000` / `:9000`, `NetworkPolicy`, `ServiceMonitor`, `PrometheusRule`, `HPA`) is included in [`deploy/helm/topic-tree/`](deploy/helm/topic-tree/) and published as an OCI artifact on every `vX.Y.Z` release tag (reference b-api route template: [`deploy/b-api/route-topic-tree-generator.json`](deploy/b-api/route-topic-tree-generator.json)):

```shell
# Install from the published OCI Helm chart (tag v2.1.0)
helm upgrade --install topic-tree \
  oci://ghcr.io/janschachtschabel/topic-tree-generator-11-2026/charts/topic-tree \
  --version 2.1.0 \
  --set image.repository=ghcr.io/janschachtschabel/topic-tree-generator-11-2026 \
  --set image.tag=2.1.0 \
  --set config.bApiBaseUrl=https://b-api.staging.openeduhub.net \
  --set config.bApiRoute=topic-tree-generator

# Or install/render directly from the local chart template in the repository
helm upgrade --install topic-tree ./deploy/helm/topic-tree -f values-custom.yaml
```

### Option D: Local Python development (without Docker)

Requires **Python 3.13** and [uv](https://docs.astral.sh/uv/):

```shell
uv sync
cp .env.example .env          # set OPENAI_API_KEY or B_API_DEV_KEY
uv run python -m app          # public API :8000 (/docs, /ui/), internal :9000 (/health, /ready, /metrics)
```

Production-like process manager: `uv run gunicorn -c gunicorn.conf.py app.main:app`.

---

## Configuration (Environment Variables)

All settings are read from environment variables or `.env` and have defaults (see [`.env.example`](.env.example)). Empty strings in `.env` are treated as unset.

### Service Mode & Authentication

| Variable | Default | Description |
|---|---|---|
| `SERVICE_ID` | `topic-tree` | Service identifier used in logs, metrics, and cache keys. |
| `SERVICE_MODE` | `auto` | `auto`: `Authorization: Bearer bdt_…` routes via b-api, anything else runs standalone. `bapi`: delegation tokens only. `standalone`: never calls b-api. |
| `SERVICE_API_KEYS` | *(empty)* | Comma-separated bearer keys for standalone auth. Empty = open (no auth required in standalone). |

### Docker & Reverse Proxy (`docker-compose.yml`)

| Variable | Default | Description |
|---|---|---|
| `DOMAIN` | *(empty)* | Bare public hostname for Traefik (`Host(...)`), e.g. `trees.example.org` (no scheme, port, or path). |
| `IMAGE` | `ghcr.io/...:latest` | Pre-built image reference used by `docker-compose.yml`. |
| `TRAEFIK_NETWORK` | `topic-tree-web` | Docker network name used by Traefik and the service container. |
| `TRAEFIK_ENTRYPOINT` | `websecure` | Traefik entrypoint name for HTTPS routing. |
| `TRAEFIK_CERTRESOLVER` | `letsencrypt` | Traefik TLS certificate resolver name. |
| `HOST_PORT` | `18000` | Host port of `docker-compose.yml` for direct access without a domain (`http://<server-ip>:18000/`). |
| `HOST_BIND` | `0.0.0.0` | Host interface for `HOST_PORT`; set `127.0.0.1` once `DOMAIN` is served via Traefik to close the direct path. |
| `TRAEFIK_ROUTER` | `topic-tree` | Traefik router and service name. These names are global in Traefik: give every further instance on the same host its own value (e.g. `topic-tree-staging`), otherwise Traefik load-balances requests across both containers. |
| `PUBLIC_PORT` | `8000` | Public API & UI port; Docker Compose publishes the same port on the host (alternative port per service). |
| `INTERNAL_PORT` | `9000` | Internal port for `/health`, `/ready`, and Prometheus `/metrics` (do not expose publicly); must differ from `PUBLIC_PORT`. |
| `WEB_CONCURRENCY` | `2` | Number of Gunicorn worker processes (~125 MiB idle RAM with 2 workers). |

### LLM Backend (b-api Router & Standalone OpenAI)

| Variable | Default | Description |
|---|---|---|
| `B_API_BASE_URL` | `https://b-api.staging.openeduhub.net` | Base URL of the b-api gateway (router path `/api/v1/llm/router/` is appended automatically). |
| `B_API_ROUTE` | *(empty)* | Option 1: route name at the b-api LLM router (`/api/v1/llm/router/`), e.g. `topic-tree-generator`. **Used first whenever set** (legacy alias: `LLM_MODEL`). The frozen legacy endpoints fall back to `topic-tree-generator` when it is empty. |
| `B_API_MODEL` | *(empty)* | Option 2: a single model (e.g. `gpt-6-luna`), used only while `B_API_ROUTE` is empty. It is sent to the provider endpoint `/api/v1/llm/<B_API_MODEL_PROVIDER>/`. Alternatively the router accepts `provider/model` as a route name (`B_API_ROUTE=openai/gpt-6-luna`). Without route and model, b-api requests answer `503 LLM_NOT_CONFIGURED`. |
| `B_API_MODEL_PROVIDER` | `openai` | Provider of `B_API_MODEL` at the b-api: `openai` or `academiccloud` (alias `B_API_PROVIDER` also accepts `router`). |
| `B_API_DELEGATION_HEADER` | *(empty)* | Custom header name if the b-api proxy sends the delegation token outside `Authorization`. |
| `B_API_DEV_KEY` | *(empty)* | Local developer key for direct b-api staging tests when `OPENAI_API_KEY` is not set. |
| `OPENAI_API_KEY` | *(empty)* | API key for standalone OpenAI or OpenAI-compatible endpoints. |
| `OPENAI_BASE_URL` | *(empty)* | Optional custom base URL for OpenAI-compatible providers. |
| `OPENAI_MODEL` | `gpt-6-luna` | Model name in standalone mode. |

### LLM Parameters, Concurrency & Cost-Control Caps

| Variable | Default | Description |
|---|---|---|
| `LLM_PARAM_FAMILY` | `common` | `common` (`max_completion_tokens` + `reasoning_effort`), `gpt5` (caps reasoning at `low`), or `classic` (`max_tokens`). |
| `LLM_REASONING_EFFORT` | `none` | Reasoning effort: `none`, `minimal`, or `low` (hard-capped at `low` for latency & cost control). |
| `LLM_OUTPUT_MODE` | `json_schema` | Structured output mode: `json_schema` (strict), `json_object`, or `prompt`. |
| `LLM_SEND_PROMPT_CACHE_KEY` | `auto` | Send `prompt_cache_key`: `auto` (on for OpenAI, off for b-api), `true`, or `false`. |
| `LLM_MAX_CONCURRENCY` | `20` | Max parallel LLM calls per worker process (**env-only**, never configurable by API/UI callers). |
| `MAX_TREE_DEPTH` | `3` | Hard upper limit (`1–4`) on `shape.depth`; higher client requests fail with `422 SHAPE_LIMIT_EXCEEDED`. |
| `MAX_NODES_PER_LEVEL` | `20` | Hard upper limit (`2–20`) on `shape.main_topics.max` and `shape.children.max` (`422 SHAPE_LIMIT_EXCEEDED`). |
| `LLM_TIMEOUT_SECONDS` | `120` | Per-LLM-call timeout in seconds (bounded by remaining request deadline). |
| `LLM_MAX_RETRIES` | `3` | SDK transport retries on transient upstream errors (`429`, `5xx`). |
| `REQUEST_TIMEOUT_SECONDS` | `280` | Overall synchronous request deadline (set reverse-proxy/b-api timeout ≥ `310s`). |
| `LEGACY_MAX_RETRIES` | `4` | Retry count for frozen v1 endpoints (legacy alias: `MAX_RETRIES`). |

### External References (`items_ref`, `fulltext.ref`), Logging & UI

| Variable | Default | Description |
|---|---|---|
| `REF_ALLOWED_HOSTS` | *(empty)* | Comma-separated HTTPS host allowlist for `ref` URLs (`.example.org` allows subdomains). Empty = all `ref` URLs rejected (SSRF protection). |
| `REF_MAX_BYTES` | `10485760` | Max download size per referenced resource (10 MiB). |
| `REF_TIMEOUT_SECONDS` | `20` | Download timeout per `ref` URL. |
| `ITEMS_INLINE_MAX` | `500` | Max inline items per request (larger batches use `items_ref`, up to 5,000 items). |
| `MAX_REQUEST_BYTES` | `33554432` | Max request body in bytes (32 MiB); larger bodies get `413 REQUEST_TOO_LARGE`. |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `LOG_FORMAT` | `json` | `json` for container/production logs, `text` for readable local logs. |
| `UI_ENABLED` | `true` | Enables (`true`) or completely disables (`false`) the built-in test UI at `/ui/`. |

---

## Built-in Test UI (`/ui/`)

The service ships with a self-hosted interactive test UI (zero external scripts, zero third-party fonts/CDNs, zero token persistence, switchable **DE / EN** interface with German as default).

- **Enable** (default in local dev and Docker Compose): `UI_ENABLED=true` → accessible at `http://localhost:8000/ui/` (and `/ui` redirects to `/ui/`).
- **Disable** (recommended for production; default in the Helm chart): set `UI_ENABLED=false` in `.env` or container environment. All UI routes (`/ui`, `/ui/`, `/ui/presets`, `/ui/assets/*`) immediately return **`404 Not Found`**. UI routes are never exposed in `/openapi.json`.
- **Capabilities**:
  - Left navigation by task (Thema, Dokument, Ordner, Inhalte gruppieren, Inhalte einsortieren, Baum ändern); each task
    shows only its fields plus an "also include" group for combinations (materials that shape the structure, materials
    that are only sorted in, a structure document as inspiration or guide). 28 examples, filtered per task and split
    into basic examples and combinations (e.g. topic + materials only sorted in), fill the form without starting.
  - "Inhalte einsortieren": a base tree (example, last result or pasted JSON, also a repository tree with `nodeId` and
    without keys) plus materials; the tree is shown read-only and sent as `refine` + `assign_only`.
  - Line editors instead of JSON: materials as `Titel | Schlagworte | Beschreibung`, folders as an indented outline.
    A structure document can also be sorted in as content.
  - "Baum ändern": targeted changes (`feedback.changes`, all eight ops including `describe`) in a row editor with node pickers; "Lock" and
    "Change …" directly on the base or result tree; "Use as base for changes" adopts a result.
  - The request as JSON is always visible and can be edited and sent as is, so every option (e.g. `nodeId`) stays
    reachable. Result card with quality, cost and time metrics, foldable warnings/questions/changes/unassigned, tree
    viewer with duplicate highlighting, copy/save JSON.
---

## Request and response structure (`POST /v2/topic-tree`)

Every field of request and response, with type, default and meaning, is listed in
[`docs/datenformat.md`](docs/datenformat.md) (generated from the models, German). Machine-readable:
[`docs/schemas/`](docs/schemas/); call patterns, roles and the decision table for callers: [`docs/api.md`](docs/api.md).

| Request field | Required | Purpose |
|---|---|---|
| `mode` | yes | `create` (new tree) or `refine` (change `current_tree`) |
| `use_case` | yes | Backbone of the tree: `topic`, `document`, `folders` or `contents` |
| `frame` | yes | Subject, educational context and target group as SkoHub URIs (may be empty lists) |
| `topic` | for `topic` | Topic text; elsewhere it narrows the scope and names the tree |
| `items` / `items_ref` | depends | Materials and documents; each with a role in `use` (`structure`, `content`, both, none), optional `fulltext` (text or `ref`) and `path` |
| `folders`, `folders_use` | for `folders` | Existing folder tree (`title`, `items`, `subcollections`); `folders_use` is its role elsewhere |
| `shape` | no | `depth`, `main_topics`/`children` ranges, `extra_topics` |
| `hints` | no | `context`, `include`, `exclude`, `order`, `description_length`, `language` |
| `options` | no | `assign_contents`, `multi_assign`, `min_confidence`, `improve`, `assign_only`, `auto_metadata` |
| `current_tree`, `feedback` | for `refine` | The previous result or any existing tree (nodes need only `title`; `key` and `nodeId` are optional) and the change request (`text`, `changes`, `locked`) |

| Response field | Content |
|---|---|
| `metadata` | Title, description, `version`, vocabulary labels and `generation` (all settings of the run; send it back for the next run) |
| `collection[]` | The tree: per node `key` (stable across runs), `nodeId` (if sent in `current_tree`), `title`, `shorttitle`, `status`, `origin`, edu-sharing `properties`, `contents[]` (`id`, `nodeId`, `confidence`), `subcollections[]` |
| `unassigned[]` | Items not sorted in, with `reason` (`off_topic`, `low_confidence`, `no_matching_node`, `excluded`) |
| `changes[]` | Applied changes (refine, or `folders` + `improve`, then `source: service`) |
| `questions[]` | Questions about unclear feedback; the unclear part is not applied |
| `warnings[]` | Everything that failed or stood out, with a fixed `code` (never a silent gap) |

A full request/response pair: [`docs/examples/topic_with_items.json`](docs/examples/topic_with_items.json) →
[`docs/examples/responses/topic_with_items.json`](docs/examples/responses/topic_with_items.json). Errors are
`{"error": {"code", "message", "trace_id"}}`; all codes are listed in `docs/api.md`.

## Use Cases & Examples (`POST /v2/topic-tree`)

All examples below work directly against `http://localhost:8000/v2/topic-tree` (also saved under [`docs/examples/`](docs/examples/)). If `SERVICE_API_KEYS` is configured in standalone mode, add `-H "Authorization: Bearer <key>"`.

**Automatic `shape` defaults when omitted:**
- **Pure `topic` (without structure items)**: applies target-group recommendations (`5–15` main topics and `3` levels for school/vocational/higher-ed; `5–10` and `2` levels for early childhood; `5–12` and `2` levels for adult/organizational contexts). Requested `extra_topics` (`"general"`, `"methodology"`) count toward the Level-1 `main_topics` total.
- **Input-driven requests (`document`, `contents`, `folders`, or `topic` with `"structure"` items)**: width follows the supplied input up to `MAX_NODES_PER_LEVEL` (`20`, e.g. a full curriculum with 20 main areas), while depth stays bounded by `MAX_TREE_DEPTH` (`3`).

### 1. `topic` – Generate a tree from a topic

Generates a balanced topic tree from a topic string and OEH vocabulary frame. Set `"options": {"auto_metadata": true}` on interdisciplinary topics to let the service classify each node onto exact German vocabulary labels and map them deterministically to SkoHub URIs.

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

*(Minimal call: `curl -s http://localhost:8000/v2/topic-tree -H 'Content-Type: application/json' -d @docs/examples/topic_minimal.json`)*

### 2. `document` – Derive a tree from a structure document (curriculum / textbook TOC)

Pass one or more Markdown documents with `"use": ["structure"]` (optionally with page markers such as `<!-- page: 12 -->`). Additional items with `"use": ["content"]` are automatically sorted into the resulting tree.

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

### 3. `folders` – Keep and optionally improve an uploaded folder hierarchy

Preserves the caller's folder tree (`origin.type="folder"`), writes descriptions/keywords for each folder, and keeps assigned items with confidence `1.0`. Set `"options": {"improve": true}` to let the service rename generic folders (like `Neuer Ordner (2)`) or fix the structure; every applied change is reported in `changes[]`.

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

### 4. `contents` – Cluster unstructured items into a new tree

Induces thematic groups directly from the supplied items (`origin.type="cluster"`) and assigns every item with confidence scores; off-topic items are listed in `unassigned[]`.

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

### 5. `refine` – Iterate on an existing tree with feedback & locked branches

Pass the previous response's `collection`, `metadata.version`, and `metadata.generation` (optionally also `metadata.title` and `metadata.description` as `title`/`description`, so the refined tree keeps them) inside `current_tree`, plus `feedback.text`, structured `feedback.changes`, and `feedback.locked` keys to protect finalized branches.

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

**Targeted changes (`feedback.changes`)** are applied without the LLM (except `split`), together with or instead of `feedback.text`:

| `op` | Required fields | Effect |
|---|---|---|
| `add` | `title` (+ optional `parent`, key or title) | New node; without `parent` on the main level |
| `remove` | `key` | Removes the branch; its items move to `unassigned` |
| `rename` | `key`, `title` | New title; short title and description are rewritten |
| `edit` | `key`, `properties` | Sets properties such as `cclom:general_keyword` |
| `move` | `key` (+ `to`) | Moves under `to`; without `to` (or `null`) to the main level |
| `merge` | `keys` (≥ 2), `title` | Merges nodes into the first key |
| `split` | `key`, `hint` | Splits a node as described (LLM) |
| `describe` | `key` (+ optional `hint`) | Rewrites description and keywords with the tree as context, following `hint` (LLM); see use case 7 |

Seven of them in one request: `curl -s http://localhost:8000/v2/topic-tree -H 'Content-Type: application/json' -d @docs/examples/refine_changes.json`.
Locked keys (`feedback.locked`) and their branches never change; a change that would touch them is rejected with
`CHANGE_REJECTED`. The response marks each node's `status` (`new`, `changed`, `moved`, `unchanged`), lists the
applied `changes` and counts the version up (`v1` → `v2`). For the next run send back `collection`,
`metadata.version`, `metadata.generation` and (to keep them) `metadata.title`/`metadata.description` as
`current_tree` (see `docs/api.md`, "Änderungen an einem Baum einreichen").

### 6. Sort contents into an existing tree (`refine` + `assign_only`)

Fills a tree that already exists, for example a collection tree from edu-sharing, with contents and changes nothing
else: no restructuring, no new descriptions, no shape checks, and every node's `properties` come back exactly as sent
(the `frame` only helps the assignment). Nodes need only a `title`; missing `key`s are assigned, a `nodeId` per node is
passed through, so each assignment maps back to its collection. `use_case` does not matter here (`topic` is fine), a
`generation` is optional; `metadata.generation.frame` keeps the frame the tree was made with. Off-topic or unmatched items land in `unassigned`; `options.auto_metadata` and `feedback`
are ignored with a warning. In the test UI this is the task "Inhalte einsortieren".

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

Answer (shortened): the node `Linsen` keeps `"nodeId": "n-linsen"` and gains
`"contents": [{"id": "c9", "nodeId": "n-c9", "confidence": 0.9}]`; every node has `status: "unchanged"`.

### 7. Describe nodes (`describe` change, successor of `/generate-collection-description`)

`{"op": "describe", "key": …, "hint": …}` in `feedback.changes` writes a fresh description and keywords for the node,
knowing its path, siblings and the whole tree, so the text sets the node apart from its neighbours. The optional
`hint` (up to 1,000 characters) is the basis or wish for the text, e.g. the free text the legacy endpoint took.
The structure stays; locked nodes are rejected with `CHANGE_REJECTED`, a node that a later change in the same request
removes, merges away or splits with `CHANGE_REJECTED` too, and a node the model left out with `DESCRIBE_FAILED`. As in
every `refine` with feedback, nodes without any description are described in the same run (on a large tree from the
repository without descriptions that means one call per 10 nodes), the `frame` is set on nodes that lack it, and
keywords are tidied. For a single collection send a tree with one node.
Example: [`docs/examples/describe.json`](docs/examples/describe.json).

### 8. Combining Use Cases (e.g. Topic + Items)

`use_case` picks the source that forms the backbone; roles decide how every other input flows in. Tree generation and content assignment are decoupled and controlled per item via `"use"` (`"content"`, `"structure"`, both, or none) and for the folder structure via `folders_use`:

| Combination Goal | Request Setup | Behaviour |
|---|---|---|
| **Topic + sort items into it** *(top-down)* | `use_case: "topic"` + `topic` + `items` *(no `use` or `["content"]`)* | Plans the tree systematically from `topic`, then assigns `items` with confidence. |
| **Topic + items also inspire branches** *(hybrid)* | `use_case: "topic"` + `topic` + `items` with `"use": ["structure", "content"]` | Feeds up to 50 items (titles, keywords, descriptions + up to 5 fulltext excerpts) as supplementary inputs into `plan_structure` (marking extra input-driven main topics `status: "suggested"`), then assigns all content items. |
| **Cluster items within a topic** *(bottom-up)* | `use_case: "contents"` + `topic` + `items` | Induces clusters from `items` scoped to `topic`; off-topic items land in `unassigned` (`off_topic`). Items marked `"use": ["content"]` only are sorted in without skewing clusters. |
| **Curriculum document + topic + items** | `use_case: "document"` + optional `topic` + Markdown `"structure"` item(s) + `"content"` items | Derives the tree from curriculum headings (`origin.document`), uses `topic` as focus/title, and assigns content items. |
| **Folders + topic + loose items + curriculum** | `use_case: "folders"` + `folders` + `items` (folder items + loose `"content"` items + optional `"structure"` doc) + `options.improve: true` | Keeps folder assignments (`confidence: 1.0`), improves folder structure using `topic` and supplementary docs, and sorts remaining loose items into matching folders. |
| **Topic, curriculum or items + folders** | `use_case: "topic"`, `"document"` or `"contents"` + `folders` + optional `folders_use` | The folder structure as a whole gets a role like `use` (default `["structure", "content"]`): its tree inspires the plan, and each file's folder path is a hint for the assignment. `[]` accepts it unused (`INPUT_IGNORED`). See `docs/api.md` for the caller decision table. |
| **Refine + feedback + new items** | `mode: "refine"` + `current_tree` + `feedback` + new `items` | Applies structural changes (honoring `locked`), describes new/renamed nodes, and assigns the new `items` into the updated tree in the same call. |

More combination requests in [`docs/examples/`](docs/examples/): `combo_topic_folders.json` (topic + folder structure
with `folders_use` + an item with `path`), `combo_document_topic_contents.json` (curriculum + topic + topic list +
contents) and `contents_with_curriculum.json` (contents clustered with a curriculum full text).

Hybrid `topic` + `items` example:

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

## Tests and checks

```shell
uv run pytest -q                                # full suite incl. E2E server, gunicorn smoke test & helm checks
uv run ruff check && uv run ruff format --check # lint & formatting (line length 120)
helm lint --strict deploy/helm/topic-tree       # Helm chart validation
uv run python -m scripts.export_schemas         # regenerate docs/schemas after model changes
uv run python -m scripts.build_vocab_snapshot   # refresh bundled OEH vocabulary labels
uv run python -m scripts.probe_llm --model <route> --base-url <router-url>
uv run python -m scripts.loadtest --url http://localhost:8000/v2/topic-tree --payload docs/examples/topic_full.json
```

## Repository layout

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
docs/          API reference, JSON schemas, request examples, benchmarks, design plan
```
