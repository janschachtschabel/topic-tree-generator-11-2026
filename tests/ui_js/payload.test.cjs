// Unit tests for the request builder of the test UI (form state -> POST /v2/topic-tree body).
const test = require("node:test");
const assert = require("node:assert/strict");
const B = require("../../app/ui/static/payload.js");

function form(overrides = {}) {
  return {
    task: "topic",
    topic: "Optik",
    frame: { discipline_uri: ["d"], educational_context_uri: [], intended_end_user_role_uri: [] },
    shape: {},
    hints: { language: "de", descriptionLength: 60 },
    options: { assignContents: true, multiAssign: true, minConfidence: 0.6 },
    extras: {},
    limits: { max_nodes_per_level: 20 },
    ...overrides,
  };
}

function throwsKey(fn, key) {
  assert.throws(fn, (err) => err.message === key);
}

test("topic with both material lists maps the use per list", () => {
  const p = B.build(form({
    extras: { structureMaterials: true, contentMaterials: true },
    materialsA: "Lochkamera | Licht",
    materialsB: "Spiegel",
  }));
  assert.equal(p.mode, "create");
  assert.equal(p.use_case, "topic");
  assert.equal(p.topic, "Optik");
  assert.deepEqual(p.items.map((i) => [i.id, i.use]), [["a1", ["structure", "content"]], ["b1", ["content"]]]);
});

test("text in switched-off extras never leaks into the request", () => {
  const p = B.build(form({ materialsA: "X", materialsB: "Y", documentMarkdown: "# Doc", folderOutline: "A" }));
  assert.equal(p.items, undefined);
  assert.equal(p.folders, undefined);
});

test("topic is required for the topic task", () => {
  throwsKey(() => B.build(form({ topic: "  " })), "err.topicRequired");
});

test("topic plus document as inspiration", () => {
  const p = B.build(form({ extras: { document: true }, documentMarkdown: "# Lehrplan" }));
  assert.deepEqual(p.items[0].use, ["structure"]);
  assert.deepEqual(p.items[0].fulltext, { format: "markdown", text: "# Lehrplan" });
});

test("document task: text or link, topic only as frame extra", () => {
  const p = B.build(form({ task: "document", documentRef: "https://example.org/lp.md", documentTitle: "LP" }));
  assert.equal(p.use_case, "document");
  assert.equal(p.topic, undefined);
  assert.deepEqual(p.items[0], {
    id: "doc1",
    use: ["structure"],
    properties: { "cm:title": ["LP"] },
    fulltext: { format: "markdown", ref: "https://example.org/lp.md" },
  });
  const withTopic = B.build(form({ task: "document", documentMarkdown: "# A", extras: { topicFrame: true } }));
  assert.equal(withTopic.topic, "Optik");
  throwsKey(() => B.build(form({ task: "document" })), "err.documentRequired");
  throwsKey(() => B.build(form({ task: "document", documentMarkdown: "x", documentRef: "https://a" })), "err.documentBoth");
});

test("folders task builds folders and file items, improve only here", () => {
  const p = B.build(form({
    task: "folders",
    folderOutline: "Optik\n  - Licht",
    options: { improve: true, assignContents: true },
    extras: { contentMaterials: true },
    materialsB: "Lose Datei",
  }));
  assert.equal(p.use_case, "folders");
  assert.deepEqual(p.folders, [{ title: "Optik", items: ["f1"], subcollections: [] }]);
  assert.deepEqual(p.items.map((i) => i.id), ["f1", "b1"]);
  assert.equal(p.options.improve, true);
  assert.equal(B.build(form({ options: { improve: true } })).options.improve, false);
  throwsKey(() => B.build(form({ task: "folders", folderOutline: "" })), "err.foldersRequired");
});

test("folder outline errors name the field and line", () => {
  assert.throws(
    () => B.build(form({ task: "folders", folderOutline: "A\n   B" })),
    (err) => err.message === "err.folderIndent" && err.vars.line === 2,
  );
});

test("contents task needs structure materials unless items_ref is given", () => {
  throwsKey(() => B.build(form({ task: "contents" })), "err.materialsRequired");
  const p = B.build(form({ task: "contents", materialsA: "A\nB", extras: { topicFrame: true } }));
  assert.equal(p.use_case, "contents");
  assert.equal(p.items.length, 2);
  const ref = B.build(form({ task: "contents", itemsRef: "https://example.org/items.json" }));
  assert.equal(ref.items_ref, "https://example.org/items.json");
  assert.equal(ref.items, undefined);
  throwsKey(() => B.build(form({ task: "contents", materialsA: "A", itemsRef: "https://x" })), "err.itemsAndRef");
});

test("refine takes use_case from the base tree and sends feedback", () => {
  const base = { collection: [{ key: "k", title: "K" }], generation: { use_case: "folders" } };
  const p = B.build(form({
    task: "refine",
    currentTree: base,
    feedback: { text: "mehr Praxis", locked: ["k"], rows: [{ op: "rename", key: "k", title: "Neu" }] },
    options: { assignOnly: true },
  }));
  assert.equal(p.mode, "refine");
  assert.equal(p.use_case, "folders");
  assert.equal(p.topic, undefined);
  assert.deepEqual(p.feedback, { text: "mehr Praxis", locked: ["k"], changes: [{ op: "rename", key: "k", title: "Neu" }] });
  assert.equal(p.options.assign_only, true);
  assert.equal(B.build(form({ task: "refine", currentTree: { collection: [] } })).use_case, "topic");
  assert.equal(B.build(form({ options: { assignOnly: true } })).options.assign_only, false);
  throwsKey(() => B.build(form({ task: "refine" })), "err.currentTreeRequired");
});

test("partial shape ranges are completed like before", () => {
  const p = B.build(form({ shape: { depth: 2, mainMax: 4, childMin: 3, extraGeneral: true } }));
  assert.deepEqual(p.shape, {
    depth: 2,
    main_topics: { min: 4, max: 4 },
    children: { min: 3, max: 8 },
    extra_topics: ["general"],
  });
  assert.equal(B.build(form()).shape, undefined);
  throwsKey(() => B.build(form({ shape: { mainMin: 5, mainMax: 3 } })), "err.mainRange");
});

test("change rows: each op with its required fields", () => {
  const { changes, errors } = B.validateChanges([
    { op: "add", title: "Neu", parent: "p" },
    { op: "remove", key: "a" },
    { op: "rename", key: "a", title: "B" },
    { op: "edit", key: "a", description: "Text" },
    { op: "move", key: "a", to: "" },
    { op: "move", key: "a", to: "p" },
    { op: "merge", keys: ["a", "b"], title: "AB" },
    { op: "split", key: "a", hint: "nach Epochen" },
  ]);
  assert.deepEqual(errors, []);
  assert.deepEqual(changes, [
    { op: "add", title: "Neu", parent: "p" },
    { op: "remove", key: "a" },
    { op: "rename", key: "a", title: "B" },
    { op: "edit", key: "a", properties: { "cm:description": ["Text"] } },
    { op: "move", key: "a", to: null },
    { op: "move", key: "a", to: "p" },
    { op: "merge", keys: ["a", "b"], title: "AB" },
    { op: "split", key: "a", hint: "nach Epochen" },
  ]);
});

test("change rows: missing fields are reported per row", () => {
  const { errors } = B.validateChanges([
    { op: "rename", key: "a", title: " " },
    { op: "merge", keys: ["a"], title: "X" },
    { op: "split", key: "", hint: "" },
  ]);
  assert.deepEqual(errors, [
    { row: 1, field: "title" },
    { row: 2, field: "keys" },
    { row: 3, field: "key" },
    { row: 3, field: "hint" },
  ]);
  throwsKey(
    () => B.build(form({ task: "refine", currentTree: { collection: [] }, feedback: { rows: [{ op: "remove" }] } })),
    "err.changeField",
  );
});

test("refine: new material ids never collide with contents of the base tree", () => {
  const base = {
    collection: [{ key: "k", title: "K", contents: [{ id: "b1" }], subcollections: [{ key: "c", title: "C", contents: [{ id: "b3" }] }] }],
    generation: { use_case: "topic" },
  };
  const p = B.build(form({ task: "refine", currentTree: base, extras: { contentMaterials: true }, materialsB: "Neu 1\nNeu 2\nNeu 3" }));
  assert.deepEqual(p.items.map((i) => i.id), ["b2", "b4", "b5"]);
});

test("refine: hints, options and shape equal to the base generation are left out so they are inherited", () => {
  const generation = {
    use_case: "folders",
    hints: { context: null, include: ["X"], exclude: [], order: null, description_length: 40, language: "en" },
    options: { improve: true, assign_contents: true, assign_only: false, multi_assign: true, min_confidence: 0.8, auto_metadata: false },
    shape: { depth: 2, main_topics: { min: 3, max: 6 }, children: { min: 2, max: 5 }, extra_topics: [] },
  };
  const same = form({
    task: "refine",
    currentTree: { collection: [], generation },
    hints: { include: ["X"], descriptionLength: 40, language: "en" },
    options: { improve: true, assignContents: true, multiAssign: true, minConfidence: 0.8 },
    shape: { depth: 2, mainMin: 3, mainMax: 6, childMin: 2, childMax: 5 },
  });
  const p = B.build(same);
  assert.equal(p.hints, undefined);
  assert.equal(p.options, undefined);
  assert.equal(p.shape, undefined);
  const changed = B.build({ ...same, hints: { ...same.hints, language: "de" }, options: { ...same.options, assignOnly: true } });
  assert.equal(changed.hints.language, "de");
  assert.equal(changed.options.assign_only, true);
  assert.equal(changed.options.improve, true, "improve of the base survives a refine");
});

test("change rows keep extra merge keys and other edited properties", () => {
  const { changes } = B.validateChanges([
    { op: "merge", keys: ["a", "b", "c"], title: "ABC" },
    { op: "edit", key: "a", description: "D", otherProps: { "cclom:general_keyword": ["k"] } },
  ]);
  assert.deepEqual(changes[0].keys, ["a", "b", "c"]);
  assert.deepEqual(changes[1].properties, { "cclom:general_keyword": ["k"], "cm:description": ["D"] });
});

test("document can be structure and content at once", () => {
  const p = B.build(form({ task: "document", documentMarkdown: "# A", extras: { documentContent: true } }));
  assert.deepEqual(p.items[0].use, ["structure", "content"]);
});

test("a second document goes along with a linked first one and needs a first one", () => {
  const p = B.build(form({ task: "document", documentRef: "https://x.example/a.md", document2Markdown: "# Zwei" }));
  assert.deepEqual(p.items.map((i) => i.id), ["doc1", "doc2"]);
  throwsKey(() => B.build(form({ extras: { document: true }, document2Markdown: "# Zwei" })), "err.doc2WithoutDoc");
});

test("folders in topic carry their role; the default role is left out", () => {
  const outline = "Optik\n  - Licht";
  const both = B.build(form({ extras: { folders: true }, folderOutline: outline, foldersUse: "structure+content" }));
  assert.equal(both.folders_use, undefined);
  assert.equal(both.folders[0].title, "Optik");
  const none = B.build(form({ extras: { folders: true }, folderOutline: outline, foldersUse: "none" }));
  assert.deepEqual(none.folders_use, []);
});
