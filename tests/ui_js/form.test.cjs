// Form <-> payload round trips of the test UI with a minimal fake DOM (no browser needed).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const STATIC = path.join(__dirname, "..", "..", "app", "ui", "static");

function element() {
  let value = "";
  return {
    get value() { return value; },
    set value(x) { value = String(x ?? ""); },
    checked: false, textContent: "", hidden: false, dataset: {},
    setAttribute() {}, addEventListener() {}, appendChild(c) { return c; }, replaceChildren() {},
  };
}

function load() {
  const els = {};
  const document = { getElementById: (id) => (els[id] ||= element()), querySelectorAll: () => [], createElement: element };
  const ctx = { window: {}, document, Option: function () {}, console };
  vm.createContext(ctx);
  for (const file of ["parsers.js", "payload.js", "changes.js", "form.js"]) {
    const source = fs.readFileSync(path.join(STATIC, file), "utf8").replace('typeof module === "object" && module.exports', "false");
    vm.runInContext(source, ctx);
  }
  const W = ctx.window;
  const state = { task: "refine", disciplineUris: [], limits: { max_tree_depth: 3, max_nodes_per_level: 20 } };
  state.changes = W.TopicTreeChanges.mount(element(), { getNodes: () => [] });
  W.TopicTreeForm.resetFields(state);
  return { W, els, state };
}

function adopt(generation) {
  const { W, els, state } = load();
  const tree = { version: "v2", collection: [{ key: "k-a", title: "A", subcollections: [] }], generation };
  W.TopicTreeForm.setBase(state, tree, (select, value) => { select.value = value; });
  els["f-fb-text"].value = "Neues Hauptthema Alltagsanwendungen";
  return W.TopicTreePayload.build(W.TopicTreeForm.readForm(state));
}

const OPTIONS = { improve: false, assign_contents: true, multi_assign: true, min_confidence: 0.6, auto_metadata: false };

test("adopting an assign-only result does not switch assign_only on for the next feedback", () => {
  const payload = adopt({ use_case: "topic", frame: {}, options: { ...OPTIONS, assign_only: true } });
  assert.equal(payload.options?.assign_only ?? false, false);
  assert.equal(payload.feedback.text, "Neues Hauptthema Alltagsanwendungen");
});

test("a refine keeps the extra topics of the base instead of sending an empty list", () => {
  const shape = { depth: 2, main_topics: { min: 3, max: 6 }, children: { min: 2, max: 5 }, extra_topics: ["general"] };
  const payload = adopt({ use_case: "topic", frame: {}, shape, options: { ...OPTIONS, assign_only: false } });
  assert.ok(payload.shape === undefined || payload.shape.extra_topics?.includes("general"));
});

test("a base without generation clears hidden extra-topic boxes left from an earlier run", () => {
  const { W, els, state } = load();
  els["f-extra-general"].checked = true;
  W.TopicTreeForm.setBase(state, { version: "v1", collection: [{ key: "k-a", title: "A", subcollections: [] }] }, (s, v) => { s.value = v; });
  els["f-fb-text"].value = "Mehr Beispiele";
  const payload = W.TopicTreePayload.build(W.TopicTreeForm.readForm(state));
  assert.ok(!payload.shape?.extra_topics?.length);
});

test("a refine keeps every educational context and role of the base frame", () => {
  // Regression: the single selects kept only the first value; the service then wrote that onto every node.
  const frame = { discipline_uri: ["d"], educational_context_uri: ["sek1", "sek2"], intended_end_user_role_uri: ["teacher", "learner"] };
  const { W, state } = load();
  W.TopicTreeForm.setBase(state, { version: "v2", collection: [], generation: { use_case: "topic", frame } }, (s, v) => { s.value = v; });
  const read = W.TopicTreeForm.readForm(state).frame;
  assert.deepEqual([...read.educational_context_uri], ["sek1", "sek2"]);
  assert.deepEqual([...read.intended_end_user_role_uri], ["teacher", "learner"]);
});

test("an include term with a comma survives loading and reading", () => {
  const { W, state } = load();
  const generation = { use_case: "topic", frame: {}, hints: { include: ["Licht, Farbe", "Auge"], exclude: ["A"] } };
  W.TopicTreeForm.setBase(state, { version: "v2", collection: [], generation }, (s, v) => { s.value = v; });
  const hints = W.TopicTreeForm.readForm(state).hints;
  assert.deepEqual([...hints.include], ["Licht, Farbe", "Auge"]);
  assert.deepEqual([...hints.exclude], ["A"]);
});

test("a preset whose folder files carry more than a title needs the JSON view", () => {
  // Regression: keywords, descriptions and roles of folder files were dropped when loading into the form.
  const { W, state } = load();
  state.task = "folders";
  const payload = {
    mode: "create", use_case: "folders", frame: {},
    folders: [{ title: "Optik", items: ["f1"], subcollections: [] }],
    items: [{ id: "f1", properties: { "cm:title": ["Spiegel"], "cclom:general_keyword": ["Reflexion"] } }],
  };
  assert.equal(W.TopicTreeForm.applyPreset(state, { task: "folders", payload }, (s, v) => { s.value = v; }), false);
});

const FOREIGN = { title: "Physik", collection: [{ title: "Licht", nodeId: "n1", subcollections: [{ title: "Linsen", nodeId: "n2" }] }] };

test("a preset that only fits the JSON view still shows its base", () => {
  // Regression: the JSON path skipped setBase, so the base view said "no base" although current_tree was sent.
  const { W, els, state } = load();
  state.task = "assign";
  const payload = { mode: "refine", use_case: "topic", frame: {}, current_tree: FOREIGN, items: [{ id: "x", nodeId: "n9" }] };
  assert.equal(W.TopicTreeForm.applyPreset(state, { task: "assign", payload }, (s, v) => { s.value = v; }), false);
  assert.equal(state.currentTree, FOREIGN);
  assert.equal(els["base-summary"].textContent, "base.summary");
});

test("renderBaseSummary rebuilds the summary from state (language switch)", () => {
  const { W, els, state } = load();
  W.TopicTreeForm.setBase(state, FOREIGN);
  els["base-summary"].textContent = "stale";
  W.TopicTreeForm.renderBaseSummary(state);
  assert.equal(els["base-summary"].textContent, "base.summary");
  W.TopicTreeForm.setBase(state, null);
  assert.equal(els["base-summary"].textContent, "base.none");
});

test("a keyless base in refine explains how its nodes get keys", () => {
  const { W, els, state } = load();
  W.TopicTreeForm.setBase(state, FOREIGN);
  assert.equal(els["keyless-hint"].hidden, false);
  assert.equal(els["keyless-hint"].textContent, "base.keyless");
  W.TopicTreeForm.setBase(state, { version: "v2", collection: [{ key: "k-a", title: "A" }] });
  assert.equal(els["keyless-hint"].hidden, true);
  state.task = "assign";
  W.TopicTreeForm.setBase(state, FOREIGN);
  assert.equal(els["keyless-hint"].hidden, true);
});
