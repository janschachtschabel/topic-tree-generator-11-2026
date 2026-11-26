// Unit tests for the pure line parsers of the test UI (run with `node --test tests/ui_js/`).
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../../app/ui/static/parsers.js");

test("material line with title, keywords and description", () => {
  const { items, errors } = P.parseMaterialLines("Lochkamera bauen | Licht, Experiment | Ein Versuch", "a", ["content"]);
  assert.deepEqual(errors, []);
  assert.deepEqual(items, [
    {
      id: "a1",
      use: ["content"],
      properties: {
        "cm:title": ["Lochkamera bauen"],
        "cclom:general_keyword": ["Licht", "Experiment"],
        "cm:description": ["Ein Versuch"],
      },
    },
  ]);
});

test("title-only lines, trailing pipes, CRLF and blank lines", () => {
  const { items, errors } = P.parseMaterialLines("Eins |\r\n\r\n  Zwei  \r\n| nur Schlagwort", "b", ["structure", "content"]);
  assert.deepEqual(items.map((i) => i.id), ["b1", "b2"]);
  assert.deepEqual(items[0].properties, { "cm:title": ["Eins"] });
  assert.deepEqual(items[1].use, ["structure", "content"]);
  assert.deepEqual(errors, [{ line: 4, key: "err.materialTitle" }]);
});

test("folder outline with nested folders and files", () => {
  const text = "Optik\n  - Licht und Schatten\n  Linsen\n    - Sammellinse\nNeuer Ordner (2)\n  - Reflexion";
  const { folders, items, errors } = P.parseFolderOutline(text);
  assert.deepEqual(errors, []);
  assert.deepEqual(folders, [
    { title: "Optik", items: ["f1"], subcollections: [{ title: "Linsen", items: ["f2"], subcollections: [] }] },
    { title: "Neuer Ordner (2)", items: ["f3"], subcollections: [] },
  ]);
  assert.deepEqual(items.map((i) => [i.id, i.properties["cm:title"][0], i.use]), [
    ["f1", "Licht und Schatten", ["content"]],
    ["f2", "Sammellinse", ["content"]],
    ["f3", "Reflexion", ["content"]],
  ]);
});

test("tabs count as two spaces", () => {
  const { folders, errors } = P.parseFolderOutline("A\n\tB\n\t\t- x");
  assert.deepEqual(errors, []);
  assert.equal(folders[0].subcollections[0].title, "B");
});

test("odd indentation and orphan files are errors with line numbers", () => {
  assert.deepEqual(P.parseFolderOutline("A\n   B").errors, [{ line: 2, key: "err.folderIndent" }]);
  assert.deepEqual(P.parseFolderOutline("- lose\nA").errors, [{ line: 1, key: "err.fileWithoutFolder" }]);
  assert.deepEqual(P.parseFolderOutline("A\n    B").errors, [{ line: 2, key: "err.folderIndent" }]);
});

test("folder outline round trip from payload", () => {
  const folders = [
    { title: "Optik", items: ["c1", "c2"], subcollections: [{ title: "Linsen", items: ["c3"], subcollections: [] }] },
    { title: "Leer", items: [], subcollections: [] },
  ];
  const items = [
    { id: "c1", properties: { "cm:title": ["Licht"] } },
    { id: "c2", properties: { "cm:title": ["Lochkamera"] } },
    { id: "c3", properties: { "cm:title": ["Sammellinse"] } },
  ];
  const text = P.folderOutlineFromPayload(folders, items);
  assert.equal(text, "Optik\n  - Licht\n  - Lochkamera\n  Linsen\n    - Sammellinse\nLeer");
  const back = P.parseFolderOutline(text);
  assert.equal(back.folders[0].subcollections[0].title, "Linsen");
  assert.equal(back.items.length, 3);
});

test("material lines from items, null when not representable", () => {
  const items = [
    { id: "x", properties: { "cm:title": ["T"], "cclom:general_keyword": ["a", "b"], "cm:description": ["D"] } },
    { id: "y", properties: { "cm:title": ["Nur Titel"] } },
    { id: "z", properties: { "cm:description": ["ohne Titel"] } },
  ];
  assert.equal(P.materialLinesFromItems(items.slice(0, 2)), "T | a, b | D\nNur Titel");
  assert.equal(P.materialLinesFromItems([{ id: "q", nodeId: "n", properties: { "cm:title": ["T"] } }]), null);
  assert.equal(P.materialLinesFromItems([{ id: "q", fulltext: { text: "x" }, properties: { "cm:title": ["T"] } }]), null);
  assert.equal(P.materialLinesFromItems([items[2]]), null);
});

test("tree node options in pre-order with depth", () => {
  const nodes = [
    { key: "a", title: "A", subcollections: [{ key: "a1", title: "A1", subcollections: [] }] },
    { key: "b", title: "B" },
  ];
  assert.deepEqual(P.treeNodeOptions(nodes), [
    { key: "a", title: "A", depth: 1 },
    { key: "a1", title: "A1", depth: 2 },
    { key: "b", title: "B", depth: 1 },
  ]);
});

test("countNodes counts nodes without service keys too", () => {
  assert.equal(P.countNodes([{ title: "A", subcollections: [{ title: "B" }, { key: "k", title: "C" }] }, { title: "D" }]), 4);
  assert.equal(P.countNodes(undefined), 0);
});

test("countKeyless counts nodes the change editor cannot offer", () => {
  const tree = [{ title: "A", subcollections: [{ key: "k-b", title: "B" }, { title: "C" }] }, { key: "k-d", title: "D" }];
  assert.equal(P.countKeyless(tree), 2);
  assert.equal(P.countKeyless([{ key: "k", title: "K", subcollections: [] }]), 0);
  assert.equal(P.countKeyless(undefined), 0);
});

test("presetOptionLabel drops the combination prefix only inside the combination group", () => {
  assert.equal(P.presetOptionLabel("Kombination: Thema + Materialien", true), "Thema + Materialien");
  assert.equal(P.presetOptionLabel("Kombination: Thema + Materialien", false), "Kombination: Thema + Materialien");
  assert.equal(P.presetOptionLabel("Optik Sek I", true), "Optik Sek I");
});
