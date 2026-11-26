# Changelog

## 2.2.0 (2026-11-26)

New
- Sorting into an existing tree is its own use case: `refine` + `options.assign_only` now returns every node exactly as
  sent (`properties` untouched, no frame stamping, no `auto_metadata`, which is reported as `INPUT_IGNORED`), so a
  collection tree from the repository can be filled with contents only. Test UI task "Inhalte einsortieren" with a
  foreign-tree example; README use case 6, `docs/api.md` section and decision table.
- `nodeId` on tree nodes: `current_tree` nodes may carry the repository id of their collection; it comes back
  unchanged on the node (before, it was dropped silently).
- Change `describe` (`feedback.changes`, `key` + optional `hint`): rewrites description and keywords of chosen nodes
  with the whole tree as context. It is the v2 successor of `/generate-collection-description`, which stays frozen.
  Test UI: row editor op "Neu beschreiben" and an example.

- `/docs` (Swagger): the endpoint description explains backbones, roles (`use`, `folders_use`), common combinations,
  `refine` with `assign_only` and `describe`, the main options with defaults and the answer; the drop-down has an
  example with its own explanation for each combination (topic + contents both ways, topic + curriculum, topic +
  folders, document + topic + contents, contents + curriculum, contents + folders as hint, folders improved by a
  curriculum, folders as outline only) and for refine with new items. Option field texts name default, effect and
  cost; tag texts lead from the legacy endpoints to v2.
- Test UI: the example picker separates basic examples from combinations, task cards count the combinations, and
  the topic task has "Thema + Materialien nur einsortieren".

Fixed
- Test UI: the base summary counted only nodes with a key (a repository tree showed "0 Knoten").

Final audit 26.11.2026 (`docs/audits/2026-11-26-abschlussaudit.md`)
- `describe` and refresh: a description or keywords set with `edit` win (a `describe` of the same node is rejected
  with `CHANGE_REJECTED`); a renamed, merged or split node whose description is not rewritten is reported
  (`DESCRIBE_FAILED`), a failed batch only once; two `describe` of one node keep both hints.
- `assign_only`: a changed `frame` is reported (`INPUT_IGNORED`); labels and audience follow the tree's own frame.
- A refine without structural change and without a sent `shape` gives no `SHAPE_*` warnings (describing a single
  collection warned about the width of the main level).
- Every LLM call has its own B3 span id; `fulltext.ref`/`items_ref` only on port 443; the internal port answers
  other methods with JSON 405; document excerpts and node descriptions stay on one line in all prompts.
- Helm: PodDisruptionBudget (on by default), `serviceMonitor.labels`/`prometheusRule.labels`, alerts
  `TopicTreeDown` and `TopicTreeServerErrors`, LLM error alert ignores callers' 401/403 and needs a minimum of
  calls, every alert has a description and runbook link, `promtool test rules` in CI, no service account token in
  the pod, probe timeouts.
- Docs in German and English: `README.md`/`README.de.md`, `docs/de/` and `docs/en/` (API guide, data format,
  operations and handover guide with runbook, service profile, changes since 0.4); tests keep the pairs in sync and
  every relative link resolvable.

## 2.1.0 (2026-11-26)

New
- `folders_use` (see below), and the release workflow can publish a tag by hand (`workflow_dispatch`); the tag
  `v2.0.0` of 25.11.2026 was never published as image or chart, so `2.1.0` is the first versioned release on GHCR.

Fixed (full audit 26.11.2026, `docs/audits/2026-11-26-gesamtaudit.md`)
- `refine`: contents left out by an inherited `assign_contents: false` are reported (`INPUT_IGNORED`).
- `contents`: lone subgroups dissolve before the depth cut, so no level is lost; structure full texts beyond the fifth
  that get no excerpt are reported (`INPUTS_TRUNCATED`).
- The HTTP client shared by all callers keeps no cookies (a b-api cookie of one caller went along with the next
  caller's token).
- `fulltext.ref`: each URL is loaded once, all full texts of a request together are capped (`REF_TOO_LARGE`), and
  compressed bodies are limited by their decoded size.
- v1 LLM calls are bounded by `LLM_TIMEOUT_SECONDS` (before: SDK default of 600 s); format unchanged.
- The B3 debug flag is forwarded as `X-B3-Flags: 1` instead of the invalid `X-B3-Sampled: d`.
- User text (topic, hints, titles, folder names) stays on one line in prompts; the system prompt treats titles,
  descriptions, excerpts and documents as material whose instructions are not followed.
- Test UI: a refine base keeps every educational context and role; include/exclude terms may hold a comma (separate
  with `;`); presets whose folder files carry more than a title open in the JSON view; `contents` with only folders
  asks for structure materials; both JSON areas have accessible names; shape errors name the field.
- Dependencies: the new `pip-audit` job found 46 known vulnerabilities in the locked runtime dependencies (starlette
  0.45, urllib3, python-multipart, jinja2, dnspython, pygments). `fastapi[standard]` is replaced by `fastapi` plus
  `uvicorn[standard]` (the extras pulled in unused CLI, template, form and e-mail packages), FastAPI/Starlette are
  updated (Starlette 1.10), and the `httpx2` loggers are muted like `httpx` (they would log request URLs).
- From the independent review: compressed refs are also bounded by their raw size (data after the end of a gzip
  stream), raw deflate is accepted, the total full-text cap is 10 million characters; item, section and node titles
  stay on one line in every prompt; items already in `current_tree` are not reported as left out.
- Docs: `docs/datenformat.md` lists every request and response field (generated, with a test); `docs/api.md` and the
  README explain how to submit changes (all seven ops) and how to read the response; new examples for every change
  op, combinations with `folders_use` and a request/response pair.
- CI: a release tag never moves `latest`, a version is never published twice (a partial publish is completed on a
  re-run), `uv lock --check`, and a report-only `pip-audit` job. `docs/api.md` lists every warning and error code (with a test).

Changed
- Combinations without silent gaps (26.11.2026): the new field `folders_use` gives the whole folder structure a role
  like `use` (default structure + content), so folders combine with `topic`, `document` and `contents`; folder paths
  and `Item.path` are hints for the assignment; full texts of structure items reach the `contents` grouping;
  structure items without text reach the `document` outline; `INPUT_IGNORED` for folders or structure documents in
  `refine`, contents with `assign_contents: false` and `extra_topics` outside `topic`. `contents` dissolves groups
  with a single subgroup; the extra topics have a defined scope. `docs/api.md` has a decision table for callers
  such as a chatbot. Test UI: folders in every fitting task, a second document, outline-only materials, seven
  combination examples, and a test that every example loads into the form unchanged.
- Leitfaden check (26.11.2026): every log line of a request carries the operator's `x-client-trace-id` as
  `client_trace_id`; an LLM provider called directly (standalone, `OPENAI_API_KEY`) gets no B3 or
  `x-client-trace-id` headers; liveness and readiness probes are configurable in the Helm values (`probes.*`);
  every v2 request and response field has a description in the OpenAPI spec; the Steckbrief matches the current
  state (live-test run times, image size, proxy header approvals, deviations, open points).
- Test UI (`/ui/`) rebuilt around a task navigation with combinations as add-ons, line editors for materials and
  folders, a row editor for targeted changes (`refine`), an always-visible editable request JSON, and 18 task-grouped
  examples (new: Kita, Hochschule, topic + document, folders + loose files, contents with sort-in-only items, all
  change ops, changes + new items, frame change).
- `refine`: an item whose id is already placed in `current_tree` is no longer skipped silently. The same material
  keeps its place with warning `ITEM_ALREADY_PLACED`; a different material (other `nodeId`) under that id is rejected
  with `422 ID_CONFLICT`.
- Items accept `"use": []` (neither structure nor content); before, an empty list fell back to the use case
  default. A structure document may also be content; the test UI has "also sort the document in as content".
- Live test against OpenAI (all UI presets plus a refine chain, `scripts/run_presets.py`) and fixes from it:
  - `document` with a `topic` keeps only the sections that belong to the topic; if one section covers it, its
    subsections become the main topics.
  - Text feedback that adds a node next to deeper branches now also plans its subtopics (one call, warning
    `EXPAND_FAILED` if that fails); proposed subtopics that already stand in the tree are dropped.
  - Node descriptions use one neutral voice (no "du"/"Sie", no imperatives) and start with the subject itself.
- Second full audit (`docs/audits/2026-11-26-audit.md`), all findings fixed with regression tests:
  - `refine`: `remove`, `merge` and `split` can no longer bypass a lock through an unlocked ancestor; a `split` on a
    node removed earlier in the batch is rejected instead of failing with 500; a failed split warns `SPLIT_FAILED`;
    keys of removed nodes are not handed out again.
  - `refine` keeps inherited `options` and `hints` field by field; feedback ignored under `assign_only` is not
    written to the history; a `current_tree` without version counts as `v1`; `create` ignores `current_tree`
    (`INPUT_IGNORED`).
  - Items the model leaves out of the assignment count in `ASSIGN_FAILED`; the `contents` budget covers all levels;
    folders without `improve` warn `INPUT_IGNORED` for structure documents; a heading-less document cut to an excerpt
    warns `OUTLINE_TRUNCATED`; shape ranges with one bound are accepted.
  - Outline parser: `C#` keeps its `#`, inner underscores stay, fences close only with their own marker, setext
    headings, text next to a page marker is kept; `exclude` matches at word starts; property-only edits are `changed`.
  - API: loading refs stops at the request deadline (`REF_FAILED`); unexpected 500s carry the request's `trace_id`;
    404/405 under `/v2/` use the v2 error format.
  - Deploy: Helm renders `REF_MAX_BYTES`/`MAX_REQUEST_BYTES` as plain integers (before: `1.048576e+07`, crash on
    start); Compose waits 300 s on stop.
  - Test UI: adopting an assign-only result no longer blocks the next feedback; refine keeps `extra_topics`.

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
