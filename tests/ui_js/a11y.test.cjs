// Accessible names and keyboard focus of the tree view and the change editor (fake DOM, no browser).
const test = require("node:test");
const assert = require("node:assert/strict");
const { load } = require("./fakedom.cjs");

const NODES = [{ key: "k-optik", title: "Optik", subcollections: [{ key: "k-linsen", title: "Linsen" }] }];

test("tree buttons carry the node title in their accessible name, in both languages", () => {
  const { W, document } = load(["i18n.js", "tree.js"]);
  const box = document.createElement("div");
  W.TopicTreeView.renderTree(box, NODES, new Set(), () => true, {}, () => {});
  const names = (cls) => box.querySelectorAll(cls).map((b) => b.getAttribute("aria-label"));
  assert.deepEqual(names("button.lock-btn").filter((n) => n.endsWith("sperren")), ["„Optik“ sperren", "„Linsen“ sperren"]);
  assert.deepEqual(names("button.edit-btn"), ["„Optik“ ändern", "„Linsen“ ändern"]);
  W.TopicTreeI18n.setLang("en");
  W.TopicTreeView.renderTree(box, NODES, new Set(), () => true, {}, () => {});
  assert.deepEqual(names("button.edit-btn"), ["Change “Optik”", "Change “Linsen”"]);
  assert.equal(names("button.lock-btn")[0], "Lock “Optik”");
});

function editor() {
  const { W, document } = load(["i18n.js", "changes.js"]);
  const box = document.createElement("div");
  const add = document.createElement("button");
  const changes = W.TopicTreeChanges.mount(box, { getNodes: () => [], focusFallback: () => add });
  return { changes, box, add, document };
}

test("changing a row's operation keeps focus on that row's operation select", () => {
  const { changes, box, document } = editor();
  changes.setChanges([{ op: "rename", key: "a" }, { op: "remove", key: "b" }]);
  const op = box.children[1].querySelector("select.change-op");
  op.value = "move";
  op.dispatch("change");
  assert.equal(document.activeElement, box.children[1].querySelector("select.change-op"));
  assert.equal(document.activeElement.value, "move");
});

test("removing a row moves focus to the next row, or to the add button after the last one", () => {
  const { changes, box, add, document } = editor();
  changes.setChanges([{ op: "rename", key: "a" }, { op: "remove", key: "b" }, { op: "remove", key: "c" }]);
  box.children[0].querySelector("button.change-remove").dispatch("click");
  assert.equal(document.activeElement, box.children[0].querySelector("select.change-op"));
  box.children[1].querySelector("button.change-remove").dispatch("click");
  assert.equal(document.activeElement, box.children[0].querySelector("select.change-op"));
  box.children[0].querySelector("button.change-remove").dispatch("click");
  assert.equal(document.activeElement, add);
});

test("a new row gets the focus", () => {
  const { changes, box, document } = editor();
  changes.setChanges([{ op: "rename", key: "a" }]);
  changes.addRow({ op: "rename", key: "b" });
  assert.equal(document.activeElement, box.children[1].querySelector("select.change-op"));
});
