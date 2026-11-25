# Test-UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Rebuild the `/ui/` test page around a task navigation ("Ausgangslage + Zusätze"), line editors for
materials and folders, a structured change editor for `refine`, and a fuller preset catalogue.

**Architecture:** Plain browser scripts without a build step. Pure logic (line parsers, request building, change
validation) lives in `parsers.js` and `payload.js`, which also export via `module.exports` so `node --test` can test
them; DOM code lives in `changes.js`, `result.js`, `app.js`. Python serves the files and the presets.

**Tech Stack:** FastAPI static routes, vanilla JS (ES2020), CSS; pytest; Node's built-in test runner (no dependency).

**Spec:** `docs/superpowers/specs/2026-11-25-test-ui-redesign-design.md`

## Global Constraints

- No external fonts, scripts, CDNs; no `@import`/`@font-face`; no `innerHTML` with untrusted text.
- No new dependency (Python or JS). JS tests run with `node --test`; pytest skips them when `node` is missing.
- Token never stored (no localStorage/sessionStorage), only sent as `Authorization` header to `/v2/topic-tree`.
- UI texts German (default) and English via `i18n.js`; identifiers/comments English.
- Files ≤ ~300 lines (dictionary file `i18n.js` exempt), functions ≤ ~50 lines.
- `[hidden] { display: none !important; }` stays in CSS; API contract unchanged.

## Review Focus

- Material line with only a title, trailing `|`, blank lines or CRLF → item with title only; blank lines skipped.
- Folder outline with odd indentation (3 spaces, tabs) or a file line before any folder → error naming the line.
- Switching task after loading a preset → fields of other tasks do not leak into the request.
- JSON expert mode edited by hand, then task switched → form wins again; the edited JSON is not sent silently.
- Refine base without `generation.use_case` → `use_case: "topic"`; change rows with missing fields → error per row.

---

### Task 1: Pure parsers (`parsers.js`)

**Files:**
- Create: `app/ui/static/parsers.js`
- Create: `tests/ui_js/parsers.test.cjs`, `tests/api/test_ui_js.py`

**Interfaces:**
- Produces `TopicTreeParsers` (window global and `module.exports`):
  - `parseMaterialLines(text: string, idPrefix: string, use: string[]) -> {items: Item[], errors: {line:number, key:string}[]}`;
    line format `Titel | kw1, kw2 | Beschreibung`; ids `${idPrefix}${n}` counting non-blank lines from 1.
  - `parseFolderOutline(text: string) -> {folders: FolderNode[], items: Item[], errors}`; 2 spaces per level,
    tabs count as 2 spaces, `- Titel` is a file (item id `f1…`, `use: ["content"]`) of the folder above;
    error keys `err.folderIndent`, `err.fileWithoutFolder`.
  - `folderOutlineFromPayload(folders, items) -> string` (inverse, for presets).
  - `materialLinesFromItems(items) -> string` (inverse, for presets; items with fulltext/nodeId are not
    representable → returns `null`).
  - `treeNodeOptions(collection) -> {key, title, depth}[]` (pre-order).

- [x] Step 1: write `tests/ui_js/parsers.test.cjs` with `node:test` cases: full line, title-only line, CRLF,
  blank lines, `a1`/`a2` ids, use passed through; folder outline 2 levels with files; 3-space indent → error line 2;
  file before folder → error line 1; round trip `folderOutlineFromPayload(parseFolderOutline(x))` for the
  `folders_upload` preset text; `treeNodeOptions` depth order.
- [x] Step 2: write `tests/api/test_ui_js.py::test_ui_js_unit_tests` running `node --test tests/ui_js/` (skip if
  `shutil.which("node")` is None), assert returncode 0, show stdout on failure.
- [x] Step 3: run `uv run pytest tests/api/test_ui_js.py -q` → FAIL (module missing).
- [x] Step 4: implement `parsers.js`.
- [x] Step 5: run → PASS; commit `feat(ui): add line parsers for materials and folders`.

### Task 2: Request builder (`payload.js`)

**Files:**
- Create: `app/ui/static/payload.js`, `tests/ui_js/payload.test.cjs`

**Interfaces:**
- Consumes Task 1.
- Produces `TopicTreePayload.build(form) -> payload` (throws `Error` whose `message` is an i18n key, with
  `.vars`). `form` is a plain object:
  `{task: "topic"|"document"|"folders"|"contents"|"refine", topic, frame:{discipline_uri[],educational_context_uri[],intended_end_user_role_uri[]}, shape:{depth,mainMin,mainMax,childMin,childMax,extraGeneral,extraMethodology}, hints:{context,order,language,include,exclude,descriptionLength}, options:{autoMetadata,improve,assignContents,assignOnly,multiAssign,minConfidence}, extras:{structureMaterials:bool, contentMaterials:bool, document:bool, topicFrame:bool}, materialsA, materialsB, itemsRef, documentMarkdown, documentRef, documentTitle, folderOutline, currentTree, feedback:{text, locked[], rows[]}, limits}`.
  Mapping per spec table "Abdeckung"; fields of hidden extras are ignored; `use_case` for refine =
  `currentTree.generation.use_case || "topic"`.
- Produces `TopicTreePayload.validateChanges(rows) -> {changes, errors}`; row
  `{op, key, keys[], to, title, hint, description}`; required fields as `_REQUIRED_BY_OP`; `edit` maps
  `description` to `properties["cm:description"]`; `move` with empty `to` sends `to: null`; `merge` needs ≥2 keys.

- [x] Step 1: tests: topic + both material lists → `a*` with `["structure","content"]`, `b*` with `["content"]`;
  topic with extras off but text in material fields → no `items`; document with ref → fulltext.ref; folders outline →
  `folders` + `f*` items; contents without materialsA → throws `err.materialsRequired`; refine use_case fallback;
  `itemsRef` plus items → throws `err.itemsAndRef`; shape partial min/max as current UI; every op valid/invalid.
- [x] Step 2: run → FAIL. Step 3: implement. Step 4: run → PASS.
- [x] Step 5: commit `feat(ui): build v2 requests from task form state`.

### Task 3: Presets with tasks and new scenarios

**Files:**
- Modify: `app/ui/presets.py` (split scenario data into `app/ui/presets_refine.py` to stay ≤ ~300 lines)
- Modify: `tests/api/test_ui.py`

**Interfaces:**
- Produces: every preset has `task` ∈ {topic, document, folders, contents, refine}; plus existing `id`, `title`,
  `summary`, `payload`.

- [x] Step 1: tests: every task has ≥2 presets; every `ChangeOp` appears in some preset's `feedback.changes`; a
  preset with `educationalContext/elementarbereich` and one with `hochschule`; existing schema/`check_request`/
  vocab/fully-described checks keep passing; change keys reference existing nodes of `current_tree`.
- [x] Step 2: run → FAIL. Step 3: add presets per spec table (Kita Jahreszeiten, Hochschule Statistik, Dokument +
  Thema, Ordner + lose Dateien, Inhalte teils nur einsortieren, Gezielte Änderungen, Änderung + neue Materialien,
  Rahmen ändern), refresh summaries. Step 4: PASS. Step 5: commit `feat(ui): add task-grouped presets incl. targeted
  changes`.

### Task 4: New page layout, controller, change editor, result view

**Files:**
- Rewrite: `app/ui/static/index.html`, `app/ui/static/app.js`, `app/ui/static/styles.css`
- Create: `app/ui/static/changes.js` (change editor DOM), `app/ui/static/result.js` (metrics, diagnostics, raw JSON)
- Modify: `app/ui/static/tree.js` (add "Ändern …" action next to lock, callback `onEditNode(key)`),
  `app/ui/static/i18n.js`, `app/ui/router.py` (`_ASSETS` += parsers.js, payload.js, changes.js, result.js)
- Modify: `tests/api/test_ui.py` (control ids)

**Interfaces:**
- Consumes Tasks 1–3. `app.js` owns `readForm() -> form` (shape of Task 2), `applyPreset(preset)`,
  `selectTask(task)`. `changes.js` exposes `TopicTreeChanges.mount(container, {getNodes}) -> {rows(), setRows(rows),
  addRow(row)}`. `result.js` exposes `TopicTreeResult.render(resp, clientSeconds, handlers)`.

- [x] Step 1: update `test_ui.py`: nav buttons `data-task` for the 5 tasks; ids `f-preset`, `f-topic`,
  `f-materials-a`, `f-materials-b`, `f-folder-outline`, `f-doc-markdown`, `f-doc-ref`, `f-items-ref`,
  `changes-editor`, `f-fb-text`, `f-fb-locked`, `f-current-tree`, `f-json`, `btn-json-edit`, `shape-limits-note`,
  `opt-show-details`; extras checkboxes `x-structure-materials`, `x-content-materials`, `x-document`,
  (the topic field doubles as frame for document/contents, so no `x-topic-frame`); all scripts served; no CDNs; DE/EN; duplicate highlighting kept.
- [x] Step 2: run → FAIL. Step 3: implement layout per spec (sidebar nav, preset dropdown filtered by task, task
  fields, Rahmen, Zusätze, collapsible Form/Hinweise/Zuordnung/Anmeldung/JSON, sticky primary button; right: status
  line, loading card, result head with actions, metrics QUALITÄT/KOSTEN/ZEIT, collapsible diagnostics, tree).
- [x] Step 4: run full `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` → PASS.
- [x] Step 5: commit `feat(ui): task navigation, change editor and result card layout`.

### Task 5: Browser verification and docs

- [x] Run the app against `tests/stub_openai.py`; with Playwright load each task's presets, submit, check the request
  JSON and the rendered result; run "Als Basis für Änderungen" → add rename/move via node action → submit.
  Screenshots at deviceScaleFactor 2 into `/mnt/project-files/ui-redesign/`.
- [x] Update `docs/api.md` (UI paragraph), CHANGELOG; tick plan boxes; commit `docs: describe the new test UI`.
