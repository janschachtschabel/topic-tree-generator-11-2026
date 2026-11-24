# topic-tree (Themenbaum-Dienst)

FastAPI service that generates collection structures ("Themenbäume") for edu-sharing with an LLM:
from a topic, from a structure document such as a curriculum, from uploaded folders and files, or from
unstructured contents. Drafts can be refined with feedback, and content items are assigned to nodes.

- `POST /v2/topic-tree` – current API (format in `docs/schemas/`, calls in `docs/api.md`)
- `POST /generate-topic-tree`, `POST /generate-collection-description` – legacy v1, unchanged
- Design and decisions: `docs/plans/2026-11-24-topic-tree-v2.md` · Operations: `docs/steckbrief.md` · Measurements & cost model: `docs/measurements/2026-11-24-openai-gpt-6-luna.md`

## How it works

```
request → input checks → load refs (allow-listed) → strategy per use case → assign contents
        → duplicates, short titles, keys, status, shape checks → answer with warnings/questions
```

`topic` plans a skeleton in one call and expands each main topic in parallel (one call each). `document` turns the
heading outline into the tree; `folders` keeps the folders (optionally improved); `contents` groups the items.
`mode: refine` applies structured changes, then interpreted text feedback; locked nodes stay untouched.
All prompts live in `app/prompts/`; `system.md` is static so providers can cache it.

## Requirements

Python 3.13 and [uv](https://docs.astral.sh/uv/).

## Run locally

```shell
uv sync
cp .env.example .env          # set OPENAI_API_KEY (standalone) or call it through the b-api
uv run python -m app          # public API :8000 (docs at /docs), internal :9000 (/health, /ready, /metrics)
```

Production-like: `uv run gunicorn -c gunicorn.conf.py app.main:app` or `docker compose up --build`.

Shortest call (standalone with an OpenAI key):

```shell
curl -s localhost:8000/v2/topic-tree -H 'Content-Type: application/json' -d @docs/examples/topic_minimal.json
```

## Modes

| Incoming | `SERVICE_MODE=auto` (default) |
|---|---|
| `Authorization: Bearer bdt_…` (b-api delegation token) | LLM via the b-api router, token forwarded unchanged |
| other bearer or none | standalone: `OPENAI_API_KEY`/`OPENAI_BASE_URL`; `SERVICE_API_KEYS` enforces auth if set |

`bapi` accepts only delegation tokens; `standalone` never uses the b-api. All settings: `.env.example`.

## Tests and checks

```shell
uv run pytest -q                       # includes a real gunicorn smoke test and helm checks if helm is installed
uv run ruff check && uv run ruff format --check
helm lint --strict deploy/helm/topic-tree
uv run python -m scripts.export_schemas         # regenerate docs/schemas after model changes
uv run python -m scripts.build_vocab_snapshot   # refresh vocabulary labels
uv run python -m scripts.probe_llm --model <route> --base-url <router-url>   # which LLM features a route supports
uv run python -m scripts.loadtest --url http://localhost:8000/v2/topic-tree --payload docs/examples/topic_full.json
```

## Layout

```
app/api        HTTP layer (v2 endpoint, errors, deps, OpenAPI examples)
app/pipeline   orchestrator, strategies per use case, LLM steps, input loading, finalize
app/domain     tree, keys, shape rules, change operations, status (no I/O, no LLM)
app/schemas    request/response models
app/llm        backend selection and the JSON client (no streaming, one repair, concurrency cap)
app/context    tracing and caller/mode detection
app/legacy     frozen v1 endpoints
deploy/helm    Helm chart
```
