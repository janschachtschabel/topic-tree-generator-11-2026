/* Pure request builder of the test UI: form state -> body of POST /v2/topic-tree. Errors carry i18n keys. */
(() => {
  "use strict";

  const Parsers = typeof module === "object" && module.exports ? require("./parsers.js") : window.TopicTreeParsers;

  const TASKS = {
    topic: { mode: "create", useCase: "topic" },
    document: { mode: "create", useCase: "document" },
    folders: { mode: "create", useCase: "folders" },
    contents: { mode: "create", useCase: "contents" },
    refine: { mode: "refine", useCase: null },
  };

  const REQUIRED = {
    add: ["title"],
    remove: ["key"],
    rename: ["key", "title"],
    edit: ["key", "description"],
    move: ["key"],
    merge: ["keys", "title"],
    split: ["key", "hint"],
  };

  function fail(key, vars = {}) {
    const err = new Error(key);
    err.vars = vars;
    return err;
  }

  const text = (value) => String(value ?? "").trim();
  const isSet = (value) => value !== null && value !== undefined && value !== "";

  function buildShape(shape, limits) {
    const s = shape || {};
    const cap = (limits && limits.max_nodes_per_level) || 20;
    if (isSet(s.mainMin) && isSet(s.mainMax) && s.mainMin > s.mainMax) throw fail("err.mainRange");
    if (isSet(s.childMin) && isSet(s.childMax) && s.childMin > s.childMax) throw fail("err.childRange");
    const out = {};
    if (isSet(s.depth)) out.depth = s.depth;
    if (isSet(s.mainMin) || isSet(s.mainMax)) {
      out.main_topics = {
        min: isSet(s.mainMin) ? s.mainMin : Math.min(6, s.mainMax),
        max: isSet(s.mainMax) ? s.mainMax : Math.min(cap, Math.max(12, s.mainMin)),
      };
    }
    if (isSet(s.childMin) || isSet(s.childMax)) {
      out.children = {
        min: isSet(s.childMin) ? s.childMin : Math.min(3, s.childMax),
        max: isSet(s.childMax) ? s.childMax : Math.min(cap, Math.max(8, s.childMin)),
      };
    }
    const extras = [...(s.extraGeneral ? ["general"] : []), ...(s.extraMethodology ? ["methodology"] : [])];
    if (extras.length) out.extra_topics = extras;
    return Object.keys(out).length ? out : undefined;
  }

  function buildHints(hints) {
    const h = hints || {};
    const language = text(h.language || "de").toLowerCase();
    if (!/^[a-z]{2}$/.test(language)) throw fail("err.langCode");
    const out = { description_length: Number(h.descriptionLength) || 60, language };
    if (text(h.context)) out.context = text(h.context);
    if (text(h.order)) out.order = text(h.order);
    if ((h.include || []).length) out.include = [...h.include];
    if ((h.exclude || []).length) out.exclude = [...h.exclude];
    return out;
  }

  function buildOptions(options, task, generation) {
    const o = options || {};
    const inheritedImprove = Boolean(generation && generation.options && generation.options.improve);
    return {
      auto_metadata: Boolean(o.autoMetadata),
      improve: task === "refine" ? inheritedImprove : task === "folders" && Boolean(o.improve),
      assign_contents: o.assignContents !== false,
      assign_only: task === "refine" && Boolean(o.assignOnly),
      multi_assign: o.multiAssign !== false,
      min_confidence: isSet(o.minConfidence) ? Number(o.minConfidence) : 0.6,
    };
  }

  function parsed(result, field) {
    if (result.errors.length) {
      const first = result.errors[0];
      throw fail(first.key, { field, line: first.line });
    }
    return result;
  }

  function documentItem(form, required) {
    const markdown = text(form.documentMarkdown);
    const ref = text(form.documentRef);
    if (markdown && ref) throw fail("err.documentBoth");
    if (!markdown && !ref) {
      if (required) throw fail("err.documentRequired");
      return null;
    }
    const title = text(form.documentTitle) || text(form.topic) || "Strukturdokument";
    return {
      id: "doc1",
      use: ["structure"],
      properties: { "cm:title": [title] },
      fulltext: ref ? { format: "markdown", ref } : { format: "markdown", text: markdown },
    };
  }

  function collectItems(form, payload) {
    const task = form.task;
    const extras = form.extras || {};
    const items = [];
    if (task === "folders") {
      const outline = parsed(Parsers.parseFolderOutline(form.folderOutline), "folders");
      if (!outline.folders.length) throw fail("err.foldersRequired");
      payload.folders = outline.folders;
      items.push(...outline.items);
    }
    const useDocument = task === "document" || (extras.document && (task === "topic" || task === "folders"));
    const doc = useDocument ? documentItem(form, task === "document") : null;
    if (doc) items.push(doc);
    if (task === "contents" || (task === "topic" && extras.structureMaterials)) {
      const listA = parsed(Parsers.parseMaterialLines(form.materialsA, "a", ["structure", "content"]), "materialsA");
      items.push(...listA.items);
    }
    if (extras.contentMaterials) {
      items.push(...parsed(Parsers.parseMaterialLines(form.materialsB, "b", ["content"]), "materialsB").items);
    }
    const itemsRef = text(form.itemsRef);
    if (itemsRef && items.length) throw fail("err.itemsAndRef");
    if (task === "contents" && !itemsRef && !items.length) throw fail("err.materialsRequired");
    if (itemsRef) payload.items_ref = itemsRef;
    if (task === "refine") renameColliding(items, placedIds(form.currentTree));
    if (items.length) payload.items = items;
  }

  /** Content ids already placed in the base tree: the service skips re-sent ids, so new items must not reuse them. */
  function placedIds(tree) {
    const ids = new Set();
    (function visit(nodes) {
      for (const node of nodes || []) {
        for (const ref of node.contents || []) ids.add(ref.id);
        visit(node.subcollections);
      }
    })(tree && tree.collection);
    return ids;
  }

  function renameColliding(items, reserved) {
    const used = new Set(reserved);
    for (const item of items) {
      if (used.has(item.id)) {
        const prefix = item.id.replace(/\d+$/, "");
        let n = 1;
        while (used.has(`${prefix}${n}`)) n += 1;
        item.id = `${prefix}${n}`;
      }
      used.add(item.id);
    }
  }

  /** Drops null, empty strings and empty lists, sorts keys: makes sent and stored settings comparable. */
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      const out = {};
      for (const key of Object.keys(value).sort()) {
        const v = value[key];
        if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) continue;
        out[key] = canonical(v);
      }
      return out;
    }
    return value;
  }

  const sameAs = (a, b) => b !== undefined && b !== null && JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));

  /** Refine inherits hints, options and shape from the base when they are left out; only send what changed. */
  function inheritUnchanged(payload, generation) {
    if (!generation) return;
    if (sameAs(payload.hints, generation.hints)) delete payload.hints;
    if (payload.shape && sameAs(payload.shape, generation.shape)) delete payload.shape;
    const stored = generation.options;
    if (stored && !payload.options.assign_only && sameAs({ ...payload.options }, { ...stored, assign_only: false })) {
      delete payload.options;
    }
  }

  function changeFromRow(row) {
    const out = { op: row.op };
    if (row.op === "add") {
      out.title = text(row.title);
      if (text(row.parent)) out.parent = text(row.parent);
    } else if (row.op === "merge") {
      out.keys = [...row.keys];
      out.title = text(row.title);
    } else {
      out.key = text(row.key);
      if (row.op === "rename") out.title = text(row.title);
      if (row.op === "edit") out.properties = { ...(row.otherProps || {}), "cm:description": [text(row.description)] };
      if (row.op === "move") out.to = text(row.to) || null;
      if (row.op === "split") out.hint = text(row.hint);
    }
    return out;
  }

  /** Change-editor rows -> `feedback.changes`; errors name the 1-based row and the missing field. */
  function validateChanges(rows) {
    const changes = [];
    const errors = [];
    (rows || []).forEach((row, index) => {
      const required = REQUIRED[row.op];
      if (!required) {
        errors.push({ row: index + 1, field: "op" });
        return;
      }
      const missing = required.filter((field) =>
        field === "keys" ? (row.keys || []).filter(Boolean).length < 2 : !text(row[field]),
      );
      for (const field of missing) errors.push({ row: index + 1, field });
      if (!missing.length) changes.push(changeFromRow({ ...row, keys: (row.keys || []).filter(Boolean) }));
    });
    return { changes, errors };
  }

  function buildFeedback(feedback) {
    const f = feedback || {};
    const { changes, errors } = validateChanges(f.rows);
    if (errors.length) throw fail("err.changeField", errors[0]);
    const out = {};
    if (text(f.text)) out.text = text(f.text);
    if ((f.locked || []).length) out.locked = [...f.locked];
    if (changes.length) out.changes = changes;
    return Object.keys(out).length ? out : undefined;
  }

  function build(form) {
    const task = TASKS[form.task];
    if (!task) throw fail("err.unknownTask");
    const extras = form.extras || {};
    const payload = { mode: task.mode, use_case: task.useCase, frame: form.frame };
    if (form.task === "refine") {
      const tree = form.currentTree;
      if (!tree || !Array.isArray(tree.collection)) throw fail("err.currentTreeRequired");
      payload.use_case = (tree.generation && tree.generation.use_case) || "topic";
      payload.current_tree = tree;
      const feedback = buildFeedback(form.feedback);
      if (feedback) payload.feedback = feedback;
    }
    const topic = text(form.topic);
    if (form.task === "topic" && !topic) throw fail("err.topicRequired");
    const topicSent = form.task === "topic" || (extras.topicFrame && ["document", "contents"].includes(form.task));
    if (topicSent && topic) payload.topic = topic;
    collectItems(form, payload);
    const shape = buildShape(form.shape, form.limits);
    if (shape) payload.shape = shape;
    payload.hints = buildHints(form.hints);
    const generation = form.task === "refine" ? form.currentTree.generation : null;
    payload.options = buildOptions(form.options, form.task, generation);
    if (generation) inheritUnchanged(payload, generation);
    return payload;
  }

  const api = { build, validateChanges, TASKS };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof window === "object") window.TopicTreePayload = api;
})();
