/* Editor for targeted changes (`feedback.changes`): one row per operation, node pickers from the base tree. */
(() => {
  "use strict";

  const t = (key, vars) => (window.TopicTreeI18n ? window.TopicTreeI18n.t(key, vars) : key);
  const OPS = ["rename", "move", "add", "edit", "merge", "split", "remove"];
  // Fields shown per op, in order. "key2" is the second node of a merge.
  const FIELDS = {
    add: ["parent", "title"],
    remove: ["key"],
    rename: ["key", "title"],
    edit: ["key", "description"],
    move: ["key", "to"],
    merge: ["key", "key2", "title"],
    split: ["key", "hint"],
  };
  const TOP_LEVEL = new Set(["parent", "to"]);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /** Change from a request (`feedback.changes[]`) -> editor row. */
  function rowFromChange(change) {
    const row = { op: change.op, key: change.key || "", title: change.title || "", hint: change.hint || "" };
    row.parent = change.parent || "";
    row.to = change.to || "";
    row.description = ((change.properties || {})["cm:description"] || [""])[0];
    if (change.op === "merge") [row.key = "", row.key2 = ""] = change.keys || [];
    return row;
  }

  /** Editor row -> row as expected by TopicTreePayload.validateChanges. */
  function toPayloadRow(row) {
    return row.op === "merge" ? { ...row, keys: [row.key, row.key2] } : { ...row };
  }

  function nodeSelect(row, field, nodes) {
    const select = el("select", "change-node");
    select.setAttribute("aria-label", t(`change.field.${field}`));
    const empty = TOP_LEVEL.has(field) ? t("change.topLevel") : t("change.pickNode");
    select.appendChild(new Option(empty, ""));
    let known = !row[field];
    for (const node of nodes) {
      const indent = "  ".repeat(node.depth - 1);
      select.appendChild(new Option(`${indent}${node.title}`, node.key));
      if (node.key === row[field]) known = true;
    }
    if (!known) select.appendChild(new Option(row[field], row[field]));
    select.value = row[field] || "";
    select.addEventListener("change", () => { row[field] = select.value; });
    return select;
  }

  function textInput(row, field) {
    const input = el(field === "description" ? "textarea" : "input", "change-text");
    if (field !== "description") input.type = "text";
    else input.rows = 2;
    input.value = row[field] || "";
    input.placeholder = t(`change.ph.${field}`);
    input.setAttribute("aria-label", t(`change.field.${field}`));
    input.addEventListener("input", () => { row[field] = input.value; });
    return input;
  }

  function mount(container, { getNodes, onChange }) {
    let rows = [];

    function renderRow(row, index) {
      const box = el("div", "change-row");
      const head = el("div", "change-head");
      head.appendChild(el("span", "change-num", `${index + 1}.`));
      const op = el("select", "change-op");
      op.setAttribute("aria-label", t("change.op"));
      for (const name of OPS) op.appendChild(new Option(t(`change.op.${name}`), name));
      op.value = row.op;
      op.addEventListener("change", () => { row.op = op.value; render(); });
      head.appendChild(op);
      const remove = el("button", "change-remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", t("change.removeRow", { n: index + 1 }));
      remove.addEventListener("click", () => { rows.splice(index, 1); render(); });
      head.appendChild(remove);
      box.appendChild(head);
      const nodes = getNodes();
      for (const field of FIELDS[row.op]) {
        const line = el("label", "change-field");
        line.appendChild(el("span", "change-label", t(`change.field.${field}`)));
        const isNode = ["key", "key2", "parent", "to"].includes(field);
        line.appendChild(isNode ? nodeSelect(row, field, nodes) : textInput(row, field));
        box.appendChild(line);
      }
      return box;
    }

    function render() {
      container.replaceChildren(...rows.map(renderRow));
      container.hidden = rows.length === 0;
      if (onChange) onChange();
    }

    return {
      rows: () => rows.map(toPayloadRow),
      setChanges(changes) { rows = (changes || []).map(rowFromChange); render(); },
      addRow(row) { rows.push({ op: "rename", ...row }); render(); },
      refresh: render,
    };
  }

  window.TopicTreeChanges = { mount, OPS };
})();
