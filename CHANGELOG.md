# Changelog

## 2.0.0 (unreleased)

New
- `POST /v2/topic-tree`: four use cases (`topic`, `document`, `folders`, `contents`), `mode: refine` with text or
  structured feedback, content assignment with confidence, stable node keys, `warnings` and `questions` instead of
  silent gaps, `metadata.generation` for reuse. Format: `docs/schemas/`, examples: `docs/examples/`, `docs/api.md`.
- Runs behind the b-api (delegation token forwarded unchanged) or standalone (OpenAI-compatible endpoint, optional
  service keys); detected per request (`SERVICE_MODE=auto`).
- Faster and cheaper generation: skeleton first, one call per main topic (8×5×3: 9 instead of 49 calls), static
  system prompt and shared prompt prefixes for provider caching, per-process concurrency cap.
- Optional built-in test UI under `/ui/` with ready-to-run sample scenarios for all use cases, interactive tree
  viewer, token/cache/timing metrics and diagnostics (`UI_ENABLED=false` disables it completely; off by default in Helm).
- Operations (Leitfaden): gunicorn with several workers, internal port with `/health`, `/ready`, `/metrics`,
  JSON logs with B3 / `x-client-trace-id`, non-root image, Helm chart `deploy/helm/topic-tree`.

Changed (operators)
- Vocabulary labels come from a bundled snapshot; the service no longer needs network access at start-up.
  Labels are now reliably German (previously German or English at random) – visible in legacy prompts only.
- `/_ping` and `/health` stay reachable but are no longer listed in the OpenAPI spec.
- A bearer token that is not a delegation token is no longer forwarded to the b-api by the v2 endpoint. Direct
  callers with their own b-api key use the b-api proxy, or `B_API_DEV_KEY` for local development.
- Container command: `gunicorn -c gunicorn.conf.py app.main:app` (was `fastapi run main.py`). Ports 8000 and 9000.
- `B_API_BASE_URL` may now be the plain base URL; the old full router URL still works.

Unchanged
- `/generate-topic-tree` and `/generate-collection-description`: same request, response and behaviour.
