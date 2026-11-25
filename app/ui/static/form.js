/* Form <-> state of the test UI: visibility per task, reading the form, loading presets, the refine base. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const t = (key, vars) => (window.TopicTreeI18n ? window.TopicTreeI18n.t(key, vars) : key);
  const P = () => window.TopicTreeParsers;
  const csv = (text) => String(text || "").split(",").map((s) => s.trim()).filter(Boolean);
  const intOrNull = (id) => {
    const raw = ($(id).value || "").trim();
    if (!raw) return null;
    const n = Number(raw);
    if (!Number.isInteger(n)) throw Object.assign(new Error("err.invalidInt"), { vars: { field: id } });
    return n;
  };

  function show(elOrId, visible) {
    const node = typeof elOrId === "string" ? $(elOrId) : elOrId;
    node.hidden = !visible;
  }

  function syncVisibility(state) {
    const task = state.task;
    for (const node of document.querySelectorAll("[data-tasks]")) show(node, node.dataset.tasks.split(" ").includes(task));
    const useDoc = task === "document" || ($("x-document").checked && (task === "topic" || task === "folders"));
    show("sec-document", useDoc);
    show("sec-materials-a", task === "contents" || (task === "topic" && $("x-structure-materials").checked));
    show("sec-materials-b", $("x-content-materials").checked);
    $("x-content-label").textContent = t(`x.contentMaterials.${task}`);
    $("x-document-label").textContent = t(task === "folders" ? "x.document.folders" : "x.document");
    $("materials-a-label").textContent = t(task === "contents" ? "field.materialsA.contents" : "field.materialsA");
    $("topic-req").textContent = t(task === "topic" ? "topic.req.required" : "topic.req.optional");
    $("topic-help").textContent = t(`help.topic.${task}`);
    $("task-intro").textContent = t(`intro.${task}`);
    $("frame-help").textContent = t(task === "refine" ? "help.frame.refine" : "help.frame");
    $("btn-submit").textContent = t(task === "refine" ? "btn.submit.refine" : "btn.submit.create");
  }

  function readFrame(state) {
    return {
      discipline_uri: [...state.disciplineUris],
      educational_context_uri: $("f-context").value ? [$("f-context").value] : [],
      intended_end_user_role_uri: $("f-role").value ? [$("f-role").value] : [],
    };
  }

  function readForm(state) {
    const task = state.task;
    return {
      task,
      topic: $("f-topic").value,
      frame: readFrame(state),
      shape: {
        depth: intOrNull("f-depth"),
        mainMin: intOrNull("f-main-min"),
        mainMax: intOrNull("f-main-max"),
        childMin: intOrNull("f-child-min"),
        childMax: intOrNull("f-child-max"),
        extraGeneral: task === "topic" && $("f-extra-general").checked,
        extraMethodology: task === "topic" && $("f-extra-methodology").checked,
      },
      hints: {
        context: $("f-hint-context").value,
        order: $("f-hint-order").value,
        language: $("f-hint-lang").value,
        include: csv($("f-hint-include").value),
        exclude: csv($("f-hint-exclude").value),
        descriptionLength: $("f-desc-len").value,
      },
      options: {
        autoMetadata: $("f-opt-auto-meta").checked,
        improve: $("f-opt-improve").checked,
        assignContents: $("f-opt-assign").checked,
        assignOnly: $("f-opt-assign-only").checked,
        multiAssign: $("f-opt-multi").checked,
        minConfidence: $("f-opt-conf").value,
      },
      extras: {
        structureMaterials: $("x-structure-materials").checked,
        contentMaterials: $("x-content-materials").checked,
        document: $("x-document").checked,
        documentContent: $("x-doc-content").checked,
        topicFrame: task === "document" || task === "contents",
      },
      materialsA: $("f-materials-a").value,
      materialsB: $("f-materials-b").value,
      itemsRef: $("f-items-ref").value,
      documentMarkdown: $("f-doc-markdown").value,
      documentRef: $("f-doc-ref").value,
      documentTitle: $("f-doc-title").value,
      folderOutline: $("f-folder-outline").value,
      currentTree: state.currentTree,
      feedback: { text: $("f-fb-text").value, locked: csv($("f-fb-locked").value), rows: state.changes.rows() },
      limits: state.limits,
    };
  }

  const VALUES = {
    "f-topic": "", "f-depth": "", "f-main-min": "", "f-main-max": "", "f-child-min": "", "f-child-max": "",
    "f-desc-len": 60, "f-hint-context": "", "f-hint-order": "", "f-hint-lang": "de", "f-hint-include": "",
    "f-hint-exclude": "", "f-opt-conf": 0.6, "f-materials-a": "", "f-materials-b": "", "f-items-ref": "",
    "f-doc-markdown": "", "f-doc-ref": "", "f-doc-title": "", "f-folder-outline": "", "f-fb-text": "",
    "f-fb-locked": "", "f-context": "", "f-role": "", "f-discipline": "",
  };
  const CHECKS = {
    "f-extra-general": false, "f-extra-methodology": false, "f-opt-auto-meta": false, "f-opt-improve": false,
    "f-opt-assign": true, "f-opt-assign-only": false, "f-opt-multi": true, "x-structure-materials": false,
    "x-content-materials": false, "x-document": false,
    "x-doc-content": false,
  };

  function resetFields(state) {
    for (const [id, value] of Object.entries(VALUES)) $(id).value = value;
    for (const [id, value] of Object.entries(CHECKS)) $(id).checked = value;
    state.disciplineUris = [];
    state.lockedKeys = new Set();
    state.changes.setChanges([]);
    setBase(state, null);
  }

  /** With `setSelectValue`, frame, shape, hints and options of the base's generation are loaded into the form. */
  function setBase(state, tree, setSelectValue) {
    state.currentTree = tree;
    if (tree && tree.generation && setSelectValue) applySettings(state, tree.generation, setSelectValue);
    $("f-current-tree").value = tree ? JSON.stringify(tree, null, 2) : "";
    const count = tree ? P().treeNodeOptions(tree.collection).length : 0;
    $("base-summary").textContent = tree
      ? t("base.summary", {
        title: tree.title || "–",
        version: tree.version || "–",
        n: count,
        useCase: (tree.generation && tree.generation.use_case) || "topic",
      })
      : t("base.none");
    state.changes.refresh();
  }


  const BOTH = ["structure", "content"];

  /** Roles of an item as the service reads them: a missing `use` means the use case default, `[]` means neither. */
  function rolesOf(item, task) {
    if (Array.isArray(item.use)) return item.use;
    return task === "contents" ? BOTH : ["content"];
  }

  /** Splits preset items into the form's slots; `null` when something only the JSON view can hold. */
  function splitItems(task, payload) {
    const items = payload.items || [];
    const folderIds = new Set();
    (function visit(list) {
      for (const f of list || []) { (f.items || []).forEach((id) => folderIds.add(id)); visit(f.subcollections); }
    })(payload.folders);
    const aAllowed = task === "topic" || task === "contents";
    const docAllowed = ["topic", "document", "folders"].includes(task);
    const slots = { docs: [], a: [], b: [], folderItems: [] };
    for (const item of items) {
      const roles = rolesOf(item, task);
      const isBoth = roles.length === 2 && BOTH.every((role) => roles.includes(role));
      if (folderIds.has(item.id)) slots.folderItems.push(item);
      else if (item.fulltext && roles.includes("structure") && docAllowed && !slots.docs.length) slots.docs.push(item);
      else if (isBoth && aAllowed) slots.a.push(item);
      else slots.b.push({ ...item, use: roles });
    }
    const linesA = P().materialLinesFromItems(slots.a, BOTH);
    const linesB = P().materialLinesFromItems(slots.b, ["content"]);
    if (linesA === null || linesB === null || P().materialLinesFromItems(slots.folderItems) === null) return null;
    return { ...slots, linesA, linesB };
  }

  function applyItems(task, payload, slots) {
    const doc = slots.docs[0];
    if (doc) {
      $("x-document").checked = task !== "document";
      $("x-doc-content").checked = rolesOf(doc, task).includes("content");
      $("f-doc-markdown").value = doc.fulltext.text || "";
      $("f-doc-ref").value = doc.fulltext.ref || "";
      $("f-doc-title").value = ((doc.properties || {})["cm:title"] || [""])[0];
    }
    $("x-structure-materials").checked = task === "topic" && slots.a.length > 0;
    $("f-materials-a").value = slots.linesA;
    $("x-content-materials").checked = slots.b.length > 0;
    $("f-materials-b").value = slots.linesB;
    if (payload.folders) $("f-folder-outline").value = P().folderOutlineFromPayload(payload.folders, slots.folderItems);
    $("f-items-ref").value = payload.items_ref || "";
  }

  function applySettings(state, payload, setSelectValue) {
    const frame = payload.frame || {};
    state.disciplineUris = [...(frame.discipline_uri || [])];
    setSelectValue($("f-context"), (frame.educational_context_uri || [])[0] || "");
    setSelectValue($("f-role"), (frame.intended_end_user_role_uri || [])[0] || "");
    $("f-topic").value = payload.topic || "";
    const shape = payload.shape || {};
    $("f-depth").value = shape.depth ?? "";
    $("f-main-min").value = shape.main_topics?.min ?? "";
    $("f-main-max").value = shape.main_topics?.max ?? "";
    $("f-child-min").value = shape.children?.min ?? "";
    $("f-child-max").value = shape.children?.max ?? "";
    $("f-extra-general").checked = (shape.extra_topics || []).includes("general");
    $("f-extra-methodology").checked = (shape.extra_topics || []).includes("methodology");
    const hints = payload.hints || {};
    $("f-hint-context").value = hints.context || "";
    $("f-hint-order").value = hints.order || "";
    $("f-hint-lang").value = hints.language || "de";
    $("f-hint-include").value = (hints.include || []).join(", ");
    $("f-hint-exclude").value = (hints.exclude || []).join(", ");
    $("f-desc-len").value = hints.description_length ?? 60;
    const o = payload.options || {};
    $("f-opt-auto-meta").checked = Boolean(o.auto_metadata);
    $("f-opt-improve").checked = Boolean(o.improve);
    $("f-opt-assign").checked = o.assign_contents ?? true;
    $("f-opt-assign-only").checked = Boolean(o.assign_only);
    $("f-opt-multi").checked = o.multi_assign ?? true;
    $("f-opt-conf").value = o.min_confidence ?? 0.6;
  }

  /** Loads a preset into the form. Returns false when it needs the JSON view (the form stays reset then). */
  function applyPreset(state, preset, setSelectValue) {
    const payload = preset.payload;
    resetFields(state);
    const slots = splitItems(preset.task, payload);
    if (!slots) return false;
    applySettings(state, payload, setSelectValue);
    applyItems(preset.task, payload, slots);
    if (preset.task === "refine") {
      setBase(state, payload.current_tree);
      const fb = payload.feedback || {};
      $("f-fb-text").value = fb.text || "";
      $("f-fb-locked").value = (fb.locked || []).join(", ");
      state.lockedKeys = new Set(fb.locked || []);
      state.changes.setChanges(fb.changes || []);
    }
    return true;
  }

  window.TopicTreeForm = { syncVisibility, readForm, resetFields, setBase, applyPreset };
})();
