// Loads every preset (JSON file in argv[2]) into the form with a fake DOM and prints the request the UI would send,
// or null when the preset only fits the JSON view. Used by tests/api/test_ui_presets_form.py.
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

function build(preset) {
  const els = {};
  const document = { getElementById: (id) => (els[id] ||= element()), querySelectorAll: () => [], createElement: element };
  const ctx = { window: {}, document, Option: function () {}, console };
  vm.createContext(ctx);
  for (const file of ["parsers.js", "payload.js", "changes.js", "presetitems.js", "form.js"]) {
    const code = fs.readFileSync(path.join(STATIC, file), "utf8").replace('typeof module === "object" && module.exports', "false");
    vm.runInContext(code, ctx);
  }
  const W = ctx.window;
  const state = { task: preset.task, disciplineUris: [], limits: { max_tree_depth: 3, max_nodes_per_level: 20 } };
  state.changes = W.TopicTreeChanges.mount(element(), { getNodes: () => [] });
  W.TopicTreeForm.resetFields(state);
  if (!W.TopicTreeForm.applyPreset(state, preset, (select, value) => { select.value = value; })) return null;
  return W.TopicTreePayload.build(W.TopicTreeForm.readForm(state));
}

const presets = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
process.stdout.write(JSON.stringify(Object.fromEntries(presets.map((p) => [p.id, build(p)]))));
