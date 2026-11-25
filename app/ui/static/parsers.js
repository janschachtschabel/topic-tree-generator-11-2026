/* Pure line parsers of the test UI: material lines, folder outlines and tree node lists. No DOM access. */
(() => {
  "use strict";

  const TITLE = "cm:title";
  const KEYWORDS = "cclom:general_keyword";
  const DESCRIPTION = "cm:description";
  const INDENT = 2;

  function lines(text) {
    return String(text || "").replace(/\r\n?/g, "\n").split("\n");
  }

  const ROLES = { G: ["structure"], I: ["content"], GI: ["structure", "content"], IG: ["structure", "content"] };
  const NONE = new Set(["-", "–", "0"]);
  const MARKER = /^\[([^\]]*)\]\s*/;

  /** Optional leading role marker: [G] structure, [I] content, [GI] both, [-] neither. `use: null` = unknown marker. */
  function parseRole(text, defaultUse) {
    const match = MARKER.exec(text);
    if (!match) return { use: [...defaultUse], rest: text };
    const code = match[1].replace(/[\s+]/g, "").toUpperCase();
    const use = NONE.has(code) ? [] : ROLES[code] || null;
    return { use: use && [...use], rest: text.slice(match[0].length) };
  }

  function sameUse(a, b) {
    return a.length === b.length && a.every((role) => b.includes(role));
  }

  function roleMarker(use, defaultUse) {
    const roles = use || defaultUse;
    if (sameUse(roles, defaultUse)) return "";
    if (!roles.length) return "[-] ";
    if (roles.length === 2) return "[GI] ";
    return roles[0] === "structure" ? "[G] " : "[I] ";
  }

  function first(item, prop) {
    const values = (item && item.properties && item.properties[prop]) || [];
    return values.length ? String(values[0]) : "";
  }

  /** `[Rolle] Titel | kw1, kw2 | Beschreibung` per line; blank lines are skipped, a missing title is an error. */
  function parseMaterialLines(text, idPrefix, defaultUse) {
    const items = [];
    const errors = [];
    lines(text).forEach((raw, index) => {
      if (!raw.trim()) return;
      const role = parseRole(raw.trim(), defaultUse);
      if (!role.use) {
        errors.push({ line: index + 1, key: "err.roleMarker" });
        return;
      }
      const [title = "", keywords = "", ...rest] = role.rest.split("|").map((part) => part.trim());
      if (!title) {
        errors.push({ line: index + 1, key: "err.materialTitle" });
        return;
      }
      const properties = { [TITLE]: [title] };
      const kws = keywords.split(",").map((k) => k.trim()).filter(Boolean);
      if (kws.length) properties[KEYWORDS] = kws;
      const description = rest.join(" | ").trim();
      if (description) properties[DESCRIPTION] = [description];
      items.push({ id: `${idPrefix}${items.length + 1}`, use: role.use, properties });
    });
    return { items, errors };
  }

  /** Inverse of parseMaterialLines; `null` when an item carries data the line format cannot hold. */
  function materialLinesFromItems(items, defaultUse = ["content"]) {
    const out = [];
    for (const item of items || []) {
      const title = first(item, TITLE);
      if (!title || item.nodeId || item.fulltext || item.path) return null;
      const extra = Object.keys(item.properties || {}).filter((k) => ![TITLE, KEYWORDS, DESCRIPTION].includes(k));
      if (extra.length) return null;
      const keywords = ((item.properties || {})[KEYWORDS] || []).join(", ");
      const description = first(item, DESCRIPTION);
      const parts = [title];
      if (keywords || description) parts.push(keywords);
      if (description) parts.push(description);
      out.push(roleMarker(item.use, defaultUse) + parts.join(" | "));
    }
    return out.join("\n");
  }

  /** Indented outline: one folder per line, 2 spaces (or a tab) per level, `- [Rolle] Titel` is a file of the folder above. */
  function parseFolderOutline(text) {
    const folders = [];
    const items = [];
    const errors = [];
    const stack = [];
    lines(text).forEach((raw, index) => {
      if (!raw.trim()) return;
      const expanded = raw.replace(/\t/g, " ".repeat(INDENT));
      const spaces = expanded.length - expanded.trimStart().length;
      const content = expanded.trim();
      const isFile = /^-\s*/.test(content);
      const level = spaces / INDENT;
      const fail = (key) => errors.push({ line: index + 1, key });
      if (spaces % INDENT !== 0) return fail("err.folderIndent");
      if (isFile) {
        if (!stack.length) return fail("err.fileWithoutFolder");
        if (level < 1 || level > stack.length) return fail("err.folderIndent");
        const role = parseRole(content.replace(/^-\s*/, "").trim(), ["content"]);
        if (!role.use) return fail("err.roleMarker");
        const title = role.rest.trim();
        if (!title) return fail("err.materialTitle");
        const id = `f${items.length + 1}`;
        items.push({ id, use: role.use, properties: { [TITLE]: [title] } });
        stack[level - 1].items.push(id);
        return undefined;
      }
      if (level > stack.length) return fail("err.folderIndent");
      stack.length = level;
      const folder = { title: content, items: [], subcollections: [] };
      (level ? stack[level - 1].subcollections : folders).push(folder);
      stack.push(folder);
      return undefined;
    });
    return { folders, items, errors };
  }

  /** Inverse of parseFolderOutline for presets: item ids are replaced by the items' titles. */
  function folderOutlineFromPayload(folders, items) {
    const titles = new Map(
      (items || []).map((item) => [item.id, roleMarker(item.use, ["content"]) + (first(item, TITLE) || item.id)]),
    );
    const out = [];
    function visit(list, depth) {
      for (const folder of list || []) {
        const pad = " ".repeat(depth * INDENT);
        out.push(`${pad}${folder.title}`);
        for (const id of folder.items || []) out.push(`${pad}${" ".repeat(INDENT)}- ${titles.get(id) || id}`);
        visit(folder.subcollections, depth + 1);
      }
    }
    visit(folders, 0);
    return out.join("\n");
  }

  /** Pre-order list of tree nodes for key pickers. */
  function treeNodeOptions(collection) {
    const out = [];
    function visit(list, depth) {
      for (const node of list || []) {
        if (node.key) out.push({ key: node.key, title: node.title, depth });
        visit(node.subcollections, depth + 1);
      }
    }
    visit(collection, 1);
    return out;
  }

  const api = { parseMaterialLines, materialLinesFromItems, parseFolderOutline, folderOutlineFromPayload, treeNodeOptions };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof window === "object") window.TopicTreeParsers = api;
})();
