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
