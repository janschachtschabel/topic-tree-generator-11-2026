# Calling POST /v2/topic-tree

> 🇩🇪 Deutsche Fassung: [`../de/api.md`](../de/api.md) · Overview of all documents: [`../README.md`](../README.md)

Complete examples live in [`docs/examples/`](../examples/) (requests) and
[`docs/examples/responses/`](../examples/responses/) (response). Every request and response field with type, default
and meaning is listed in [`data-format.md`](data-format.md); machine-readable schemas are in [`docs/schemas/`](../schemas/).
For interactive testing in the browser, the optional built-in test UI is available at `/ui/` (controlled by
`UI_ENABLED=true|false`). Calls are synchronous and typically take 5 to 45 seconds (large 3-level trees ~25–45 s).

## Authentication

- Via the b-api: the proxy forwards the delegation token (`Authorization: Bearer bdt_…`); nothing else to do.
- Standalone: without authentication, or with `Authorization: Bearer <service key>` when `SERVICE_API_KEYS` is set.
  In `auto` mode a `bdt_…` token counts as a call via the b-api and is not checked against the service keys
  (the b-api checks it on the first LLM call). A public instance that should only accept service keys runs
  with `SERVICE_MODE=standalone`.

## Shortest call

```json
{"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}}
```

If `shape` is omitted, the service chooses depth and width to fit the call:
- **Topic only (`use_case: "topic"` without structure items):** recommended range per audience (`5–15` main nodes and at most `3` levels for school, vocational education and higher education; `5–10` or `5–12` and at most `2` levels for early childhood education or further training/organisations). Requested `extra_topics` (`general`, `methodology`) count normally towards the total on level 1.
- **Structure-driven input (`document`, `contents`, `folders`, and `topic` with `"structure"` items):** width follows the input up to `MAX_NODES_PER_LEVEL` (default `20`, e.g. a curriculum with 20 topic areas); depth stays limited to `MAX_TREE_DEPTH` (default `3`).
A range with only one bound (e.g. `"main_topics": {"max": 4}`) takes the other bound from this range (or from
`generation` for `refine`) and adjusts it so that the bound sent applies.
Server-side limits (`MAX_TREE_DEPTH`, `MAX_NODES_PER_LEVEL`) cannot be exceeded per request (`422 SHAPE_LIMIT_EXCEEDED`).

## Per use case

| File | Use case | What happens |
|---|---|---|
| `topic_minimal.json`, `topic_full.json` | topic | Complete title skeleton in one call, deterministic duplicate removal, then parallel description batches (10 nodes each, with the full structure in the cache prefix) |
| `document.json` | document | Outline from the headings, section and page per node |
| `folders.json` | folders | Folders stay; with `options.improve`, applied improvements come back as `changes` |
| `contents.json` | contents | Groups built from the contents (incl. duplicate removal), assignment with confidence |
| `refine_feedback.json` | refine | Feedback as text; `locked` protects branches |
| `assign_only.json` | refine + `assign_only` | Sort contents into an existing tree from the repository (`nodeId`, without keys); nodes stay unchanged |
| `describe.json` | refine + `describe` | Rewrite one node's description with tree context and a hint |
| `refine_changes.json` | refine | Seven targeted changes (all except `describe`), plus free text, a locked branch and a new content item |
| `topic_with_items.json` | topic | Topic and two content items; the matching response: `responses/topic_with_items.json` |
| `combo_topic_folders.json` | topic + folders | Folder structure inspires the outline (`folders_use`); folder paths and `path` help with assignment (`path` does not shape the outline) |
| `combo_document_topic_contents.json` | document + topic + contents | Curriculum as skeleton, `topic` narrows the scope, a topic list without text supplements it, contents are assigned |
| `contents_with_curriculum.json` | contents + curriculum | Groups from contents, the curriculum full text feeds in, one content item is only assigned |

## Combining use cases (e.g. topic + contents)

**Basic rule:** `use_case` determines which source forms the skeleton of the tree. The roles (`use` per entry in
`items`, `folders_use` for the whole folder structure) determine how all other sources feed in. Anything that is
sent but not used is reported as `INPUT_IGNORED`.

### For callers such as a chatbot: marked elements → request

The user marks each element as "outline document", "content", both or neither, and optionally provides a folder
structure. The caller chooses the `use_case` in this order; the first matching row applies:

| # | Elements present | `use_case` | Further fields |
|---|---|---|---|
| 1 | Folder structure that should be kept | `folders` | `options.improve: true` if outline documents or the topic should improve it; otherwise it stays unchanged |
| 2 | Outline document with text (e.g. curriculum) | `document` | `topic` narrows to a section; folders and documents without text supplement it |
| 3 | Contents only (no topic as skeleton) | `contents` | `topic` narrows the scope, off-topic contents go to `unassigned` |
| 4 | Topic | `topic` | Outline documents and folders only inspire (up to 50 entries, 5 full-text excerpts of 1,500 characters each) |
| – | An existing tree should only be filled (structure stays) | `mode: refine` + `current_tree` | `options.assign_only: true`, contents in `items`; `use_case: topic` is enough |
| – | An existing tree should be changed | `mode: refine` + `current_tree` | Change request as `feedback`; new contents in `items` |
| – | A collection should be (re)described | `mode: refine` + `current_tree` | `feedback.changes: [{"op": "describe", "key": …, "hint": …}]`; a single collection as a tree with one node |

Mapping roles: outline document → `"use": ["structure"]`, content → `["content"]`, both →
`["structure", "content"]`, neither → `[]`. The same applies to the folder structure in `folders_use` (default: both).

| Role of the folder structure (`folders_use`) | with `use_case: folders` | with `topic`, `document`, `contents` |
|---|---|---|
| missing or `["structure", "content"]` | Folders are the skeleton, their assignments stay (`confidence: 1.0`) | Folder tree inspires the outline; each file's folder path helps with assignment |
| `["structure"]` | Folders are the skeleton, all files are re-assigned | Folder tree inspires the outline; files without folder hint |
| `["content"]` | `422 INVALID_INPUT` (folders are the skeleton here) | only the folder path helps with assignment |
| `[]` | `422 INVALID_INPUT` | accepted, not used (`INPUT_IGNORED`) |

A `path` on an entry (e.g. `"Optik/Linsen"`) acts like a folder path: as a hint for assignment.

Reported limits (`INPUT_IGNORED`): with `mode: refine`, new outline documents and folders do not shape the tree
(phrase the change request as `feedback`); with `options.assign_contents: false`, contents are not assigned;
`shape.extra_topics` applies only to `use_case: topic`.

### Examples

Structure generation and content assignment are decoupled and can be combined freely via the `"use"` field of each entry in `items`:

- **`use_case: "topic"` + `items` without `use` (or `"use": ["content"]`)**: Builds the tree systematically from `topic` and then sorts all `items` in with confidence.
- **`use_case: "topic"` + `items` with `"use": ["structure", "content"]`**: Passes up to 50 materials (title, keywords, short description and up to 5 full-text excerpts; beyond that `INPUTS_TRUNCATED`) to `plan_structure` as additional inspiration (additional main topics get `status: "suggested"`) and sorts all contents into the tree.
- **`use_case: "contents"` + `topic` + `items`**: Builds clusters primarily from the materials within the scope of `topic` (off-topic entries end up in `unassigned` with `off_topic`; pure `"use": ["content"]` entries are only assigned, without distorting the grouping). Full texts of entries with `"structure"` (e.g. a curriculum) feed into the grouping as an excerpt; groups with only one subgroup are dissolved.
- **`use_case: "document"` + optional `topic` + structure document(s) (`"structure"`) + materials (`"content"`)**: Derives the tree from the document outline (`origin.document`; several documents are merged into one outline) and assigns the materials to the sections. Entries with `"structure"` without full text (e.g. a topic list) supplement the outline.
- **`use_case: "topic"`, `"document"` or `"contents"` + `folders`**: The folder structure feeds in according to `folders_use` (see above).
- **`use_case: "folders"` + `folders` + loose additional `items` (+ optional structure document with `options.improve: true`)**: Keeps existing folder assignments (`confidence: 1.0`), improves the folder structure on request and sorts in loose materials.
- **`mode: "refine"` + `feedback` + new `items`**: Applies structural changes while respecting `locked`, describes new/renamed nodes and sorts new materials into the updated tree in the same call.

## Roles per entry (`use`)

Each entry in `items` carries one of four roles, independent of the use case and in addition to `folders`:

| `use` | Role | Effect |
|---|---|---|
| `["structure"]` | Outline (e.g. curriculum) | shapes the structure, is not assigned |
| `["content"]` | Content | is assigned, does not shape the structure |
| `["structure", "content"]` | both | shapes the structure and is assigned itself |
| `[]` | neither | is accepted but neither used nor assigned (not even in a folder from `folders`) |

If `use` is missing, the use case default applies: `["structure", "content"]` for `contents`, otherwise `["content"]`.
A structure document with full text may also be content (`["structure", "content"]`): it provides the outline and is
then assigned to a node itself. Entries with `[]` do not appear in `unassigned`.

## Automatic node metadata (`options.auto_metadata`)

If `options.auto_metadata: true` is set and a field in `frame` is empty or has several values (e.g. an
interdisciplinary topic), the service first narrows `ccm:taxonid`, `ccm:educationalcontext` and
`ccm:educationalintendedenduserrole` per node deterministically from the assigned contents, and classifies the
remaining nodes via exact German vocabulary labels, which are mapped deterministically to canonical SkoHub URIs.

## Next run

Send back `collection` as `current_tree.collection`, `metadata.generation` as `current_tree.generation`,
`metadata.version` as `current_tree.version` and (optionally) `metadata.title`/`metadata.description` as
`current_tree.title`/`current_tree.description`, and add only the new `feedback`. The service takes missing settings
from `generation` (except `options.assign_only`, which applies only to the one call). This works field by field:
whoever sends only `options: {"assign_only": true}` or `hints: {"context": …}` keeps all other options and hints from
`generation`. A `current_tree` without `version` counts as `v1`. With `mode: create`, a `current_tree` that is sent
is ignored (warning `INPUT_IGNORED`).

A changed `frame` replaces the old frame values on existing nodes; nodes narrowed on purpose and locked branches
(`locked`) keep their values.

New `items` in a follow-up run need their own ids: an id that is already assigned in the tree counts as the same
material and stays in its place (warning `ITEM_ALREADY_PLACED`); if it carries a different `nodeId` than in the tree,
the service responds with `422 ID_CONFLICT`.

If text feedback creates a new node next to deeper branches, the service adds its subtopics down to the depth of the
neighbouring branches (warning `EXPAND_FAILED` or `EXPAND_INCOMPLETE` if this fails). Structured `add` changes create
exactly the one node.

Change operations in `feedback.changes`: `move` without `to` (or with `to: null`) moves a node to the main level.
`remove`, `split` and merging a node away via `merge` (all except the first key) are rejected (`CHANGE_REJECTED`) if
a locked node lies below it; so is a `split` whose node an earlier change in the same request has already removed or
split. If splitting fails at the language model, `SPLIT_FAILED` is returned and the rest of the feedback is still
applied. Keys of removed nodes are not reassigned within the same request.

In the test UI (`/ui/`) this is called "Baum ändern" (change tree): base from an example, the last result or JSON,
all eight operations (`add`, `remove`, `rename`, `edit`, `describe`, `move`, `merge`, `split`) as rows with node
selection, plus free text, locked branches and new materials. Combinations of use cases (e.g. topic + materials) run
there via "Zusätzlich einbeziehen" (also include).

## Submitting changes to a tree (`mode: refine`)

1. Send back the last result: `collection` → `current_tree.collection`, `metadata.version` →
   `current_tree.version`, `metadata.generation` → `current_tree.generation` (see "Next run").
2. Describe the request in `feedback`, free-form or targeted (both work in one request):
   - `feedback.text`: free text, e.g. "Farben als eigenes Hauptthema" (colours as a separate main topic). The language
     model turns it into changes; anything unclear comes back as `questions` and is not applied (the rest is).
   - `feedback.changes`: targeted changes, applied without the language model (except `split`).
   - `feedback.locked`: keys of nodes that stay unchanged together with their branch.
3. Send new contents to be assigned as `items` (with their own ids).

| `op` | Required fields | Effect |
|---|---|---|
| `add` | `title` | New node under `parent` (key or title); without `parent` on the main level |
| `remove` | `key` | Remove the node with its branch; its contents then appear in `unassigned` (`no_matching_node`) unless they are still attached to another node |
| `rename` | `key`, `title` | Change the title; short title and description are rewritten |
| `edit` | `key`, `properties` | Set properties, e.g. `cclom:general_keyword` or `ccm:taxonid` |
| `move` | `key` | Move under `to`; without `to` or with `null` to the main level |
| `merge` | `keys` (at least 2), `title` | Merge nodes; the first key stays |
| `split` | `key`, `hint` | Split the node into several according to the hint (language model) |
| `describe` | `key` | Rewrite description and keywords with tree context; `hint` (optional, up to 1,000 characters) is the basis or a request (language model) |

```json
{
  "mode": "refine",
  "use_case": "topic",
  "current_tree": {"version": "v1", "collection": [{"key": "k-optik", "title": "Optik", "subcollections": []}]},
  "feedback": {
    "changes": [
      {"op": "add", "title": "Farben"},
      {"op": "rename", "key": "k-optik", "title": "Geometrische Optik"}
    ],
    "text": "Beschreibungen alltagsnäher formulieren",
    "locked": []
  },
  "frame": {"discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"]}
}
```

Seven operations together: `docs/examples/refine_changes.json`; `describe` alone: `docs/examples/describe.json`. In
the response, every applied change is listed in `changes` (with `from`: `feedback_changes`, `feedback_text` or
`service`), every node carries `status` (`new`, `changed`, `moved`, `unchanged`, `suggested`), and the version counts
up (`v1` → `v2`, `metadata.based_on` names the previous version). Rejected changes report `CHANGE_REJECTED`.

## Sorting contents into an existing tree (`options.assign_only`)

For a tree that already exists (e.g. collections from edu-sharing) and new contents that only need to go into it:

- `mode: refine`, the tree as `current_tree.collection`, the contents as `items` (role `["content"]`),
  `options.assign_only: true`. `use_case` does not matter (`topic` is enough); `generation` and `version` are optional.
- Per node, `title` and `subcollections` are enough; the service assigns missing `key` values. A `nodeId` on the node
  comes back unchanged, so every assignment can be matched to its collection. (For later structural changes: `merge`
  keeps the `nodeId` of the first node, parts from `split` and new nodes have none; the keys in `changes` show which
  collections are dropped.)
- Structure, title and `properties` of every node stay unchanged (also with a changed `frame`; the frame only helps
  with assignment). No descriptions are written and no shape checks run. Only `shorttitle` follows the response rule
  (at most 20 characters, unique among siblings); `properties` keep the short title that was sent.
- `metadata.generation.frame` keeps the frame the tree was created with (it was not applied, after all).
- `feedback` is not applied (`FEEDBACK_IGNORED`), and an `options.auto_metadata` that is sent is not executed
  (`INPUT_IGNORED`). Contents that do not fit appear in `unassigned`.

In the test UI this is the task "Inhalte einsortieren" (sort in contents).

## Describing nodes (`describe`, successor of `/generate-collection-description`)

`{"op": "describe", "key": "k-linsen", "hint": "Für Klasse 8, mit Alltagsbeispielen"}` in `feedback.changes`
rewrites the node's description and keywords. Unlike the old endpoint, the language model knows the path, the
siblings and the whole tree and sets the text apart from them; the length follows `hints.description_length` (words).
`hint` takes the free text that the old endpoint received as `text_context` (single line, up to 1,000 characters).
Locked nodes and nodes that a later change in the same request removes, merges away or splits are rejected
(`CHANGE_REJECTED`); if the language model omits the node, `DESCRIBE_FAILED` is returned. As with every `refine` with
feedback, nodes without any description are described in the same run (for a large tree without texts, one call per
10 nodes), the `frame` is set on nodes without their own values, and keywords are cleaned up. The old endpoint stays
unchanged for existing callers.

## Page markers in Markdown (use_case document)

Recognised are `<!-- page: N -->`, `<!-- PageNumber="N" -->` (set the page) as well as `<!-- page_break -->`,
`<!-- PageBreak -->` and form feed (count up from page 1). Without markers, `origin.page` stays empty.

## Reading the response

Example: `docs/examples/responses/topic_with_items.json`; all fields: [`data-format.md`](data-format.md#response).

- `metadata`: title, description, version (`v1`, `v2`, …), labels of the vocabulary URIs and `generation`
  (all settings of the run; send it back for the next run).
- `collection[]`: the tree. Per node `key` (stable across refine runs), `title`, `shorttitle`, `status`, `origin`
  (source: `topic`, `document` with section and page, `folder`, `cluster`, `feedback`), `properties` (edu-sharing:
  `cm:title`, `cm:description`, `cclom:general_keyword`, `ccm:taxonid`, …), `contents[]` (`id`, `nodeId`,
  `confidence`) and `subcollections[]`.
- `unassigned[]`: contents not assigned, with reason (`off_topic`, `low_confidence`, `no_matching_node`,
  `excluded`).
- `changes[]`: applied changes (refine, or `folders` with `improve`, then `source: service`).
- `warnings[]`: `{code, message, key?, step?}`: what failed or stood out (e.g. `LLM_DEGRADED`,
  `DESCRIBE_FAILED`, `DESCRIBE_UNKNOWN_KEY`, `METADATA_LABEL_UNKNOWN`, `METADATA_FAILED`, `INPUTS_TRUNCATED`,
  `OUTLINE_FALLBACK`, `DEADLINE_EXCEEDED`, `SHAPE_SINGLE_CHILD`, `SHAPE_UNBALANCED`, `DUPLICATE_TITLE`, `GENERIC_TITLE`,
  `FACET_AS_NODE`, `TOPIC_REPEAT`, `CHANGE_REJECTED`, `SPLIT_FAILED`, `EXPAND_FAILED`, `EXPAND_INCOMPLETE`,
  `FEEDBACK_IGNORED`, `INPUT_IGNORED`, `OUTLINE_TRUNCATED`, `ITEM_ALREADY_PLACED`, `ASSIGN_FAILED`, `VOCAB_UNKNOWN`,
  `SHAPE_DEPTH`, `SHAPE_WIDTH` (language model response too deep or too wide, truncated), `SECTION_UNKNOWN`,
  `ITEMS_SAMPLED`, `UNTITLED_NODE`, `DESCRIPTION_MISSING`, `DESCRIPTION_LENGTH`).
  `ASSIGN_FAILED` also names contents for which the language model gave no answer; they appear in `unassigned`.
  `INPUT_IGNORED` reports inputs that were sent but not used (e.g. outline documents with `folders` without
  `options.improve`, folders with `folders_use: []`, contents with `assign_contents: false`). `OUTLINE_TRUNCATED` also
  reports a document without headings of which only an excerpt was used.
- `questions[]`: follow-up questions about unclear feedback; the unclear part is not applied.
- `metadata.generation.usage`: LLM calls, tokens (of which from the cache), duration.

## Errors

`{"error": {"code", "message", "trace_id", "details"?}}`. 422 invalid or incomplete request
(`MISSING_INPUT`, `INVALID_INPUT`, `INVALID_OPTION`, `SHAPE_LIMIT_EXCEEDED`, `DUPLICATE_ID`, `ID_CONFLICT`, `UNKNOWN_ITEM`,
`ITEMS_TOO_LARGE`, `REF_NOT_ALLOWED`, `REF_INVALID`, `REF_TOO_LARGE` (one reference, or all full texts of a request
together (over 10 million characters), too large), `REF_FAILED` (also when references are not loaded within
`REQUEST_TIMEOUT_SECONDS`) …),
404 `NOT_FOUND` and 405 `METHOD_NOT_ALLOWED` for unknown paths or methods under `/v2/`,
413 `REQUEST_TOO_LARGE` (request larger than `MAX_REQUEST_BYTES`, default 32 MiB),
401 `UNAUTHORIZED` / 403 `FORBIDDEN` for authentication or a missing b-api permission, 501 `NOT_IMPLEMENTED`,
502/503 `LLM_UNAVAILABLE` (503 with `Retry-After` for temporary errors), 503 `LLM_NOT_CONFIGURED`,
500 `INTERNAL` for an unexpected error in the service (without details; the `trace_id` finds the log line, see
[`operations.md`](operations.md)).
