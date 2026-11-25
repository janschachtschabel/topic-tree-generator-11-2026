# Changelog

## Unreleased

Changed
- Test UI (`/ui/`) rebuilt around a task navigation with combinations as add-ons, line editors for materials and
  folders, a row editor for targeted changes (`refine`), an always-visible editable request JSON, and 19 task-grouped
  examples (new: Kita, Hochschule, topic + document, folders + loose files, contents with sort-in-only items, all
  change ops, changes + new items, frame change, roles per item).
- `refine`: an item whose id is already placed in `current_tree` is no longer skipped silently. The same material
  keeps its place with warning `ITEM_ALREADY_PLACED`; a different material (other `nodeId`) under that id is rejected
  with `422 ID_CONFLICT`.
- Items accept `"use": []` (neither structure nor content); before, an empty list fell back to the use case
  default. A structure document may also be content. The test UI sets the role per line with a leading marker
  (`[G]` structure, `[I]` content, `[GI]` both, `[-]` neither) and has "also sort the document in as content".

## 2.0.0 (2026-11-25)

New
- `POST /v2/topic-tree`: four use cases (`topic`, `document`, `folders`, `contents`), `mode: refine` with text or
  structured feedback, content assignment with confidence, stable node keys, `warnings` and `questions` instead of
  silent gaps, `metadata.generation` for reuse. Format: `docs/schemas/`, examples: `docs/examples/`, `docs/api.md`.
- Runs behind the b-api (delegation token forwarded unchanged) or standalone (OpenAI-compatible endpoint, optional
  service keys); detected per request (`SERVICE_MODE=auto`).
- Faster and cheaper generation: the full title skeleton in one call, deterministic duplicate removal, then node
  descriptions in parallel batches of 10 (8×5×3: 18 instead of 49 calls, run in one parallel wave), static system
  prompt and shared prompt prefixes for provider caching, per-process concurrency cap.
- `current_tree` accepts optional `title` and `description` so `refine` keeps the tree's title and description.
- Optional built-in test UI under `/ui/` with ready-to-run sample scenarios for all use cases, interactive tree
  viewer, token/cache/timing metrics and diagnostics (`UI_ENABLED=false` disables it completely; off by default in Helm).
- Operations (Leitfaden): gunicorn with several workers (`graceful_timeout=290s`), internal port with `/health`,
  `/ready`, `/metrics`, JSON logs with B3 / `x-client-trace-id` (propagated on both v2 and legacy v1 endpoints),
  digest-pinned non-root image, Dependabot, and versioned Helm chart `deploy/helm/topic-tree` published to GHCR OCI on
  `vX.Y.Z` tags.
- Resilient degraded fallback (`LLM_DEGRADED` warning) for `document` and `folders` when the LLM is unavailable;
  permanent b-api `503` errors (`Model pricing unavailable`, `NOT_ELIGIBLE`) answered as `502` without `Retry-After`.
- Unified Level-1 counting (`extra_topics` count toward `main_topics`) and input-driven width up to 20 nodes per level
  when `shape` is omitted on `document`/`contents`/`folders` (`5–15` recommendation on pure `topic`).

Changed (operators)
- Vocabulary labels come from a bundled snapshot; the service no longer needs network access at start-up.
  Labels are now reliably German (previously German or English at random) – visible in legacy prompts only.
- `/_ping` and `/health` stay reachable but are no longer listed in the OpenAPI spec.
- A bearer token that is not a delegation token is no longer forwarded to the b-api by the v2 endpoint. Direct
  callers with their own b-api key use the b-api proxy, or `B_API_DEV_KEY` for local development.
- Container command: `gunicorn -c gunicorn.conf.py app.main:app` (was `fastapi run main.py`). Ports 8000 and 9000.
- `B_API_BASE_URL` may now be the plain base URL; the old full router URL still works.
- b-api: a route at the router (`B_API_ROUTE`) is used first whenever it is set; otherwise v2 sends a single model
  (`B_API_MODEL`, e.g. `gpt-6-luna`) to its provider endpoint `/api/v1/llm/<B_API_MODEL_PROVIDER>/` (`openai` by
  default, or `academiccloud`). The router also accepts `provider/model` as a route name. `B_API_ROUTE` no longer
  defaults to `topic-tree-generator` (that route does not exist yet); the frozen legacy endpoints keep it as their
  fallback. An upstream 400/404/422 now explains that route/model and endpoint probably do not match.
- `PUBLIC_PORT` / `INTERNAL_PORT` now also drive both Compose files (host port mapping, Traefik service port,
  healthcheck), so a service can move to alternative ports with one change in `.env`. Both ports are validated
  (`1–65535`, must differ).
- `docker-compose.yml`: Traefik router/service name configurable via `TRAEFIK_ROUTER` (default `topic-tree`), so a
  second instance on the same host gets its own routing instead of sharing one load-balanced service.
- `docker-compose.yml` runs without a domain: the API and UI are reachable at `http://<server-ip>:18000/`
  (`HOST_PORT`); after setting `DOMAIN`, `HOST_BIND=127.0.0.1` closes the direct path.

Unchanged
- `/generate-topic-tree` and `/generate-collection-description`: frozen request and response schemas preserved; now
  also callable in standalone mode (`OPENAI_API_KEY` / `SERVICE_API_KEYS`) consistently with `/v2/topic-tree`.
