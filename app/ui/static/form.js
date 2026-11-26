/* Form <-> state of the test UI: visibility per task, reading the form, loading presets, the refine base. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const t = (key, vars) => (window.TopicTreeI18n ? window.TopicTreeI18n.t(key, vars) : key);
  const P = () => window.TopicTreeParsers;
  const csv = (text) => String(text || "").split(",").map((s) => s.trim()).filter(Boolean);
  // Terms are split at ";" when there is one (so a term may hold a comma), else at ",".
  const terms = (text) => String(text || "").split(String(text || "").includes(";") ? ";" : ",").map((s) => s.trim()).filter(Boolean);
  const joinTerms = (list) => list.join(list.some((x) => x.includes(",")) ? "; " : ", ");
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
    const withA = ["topic", "document", "folders"].includes(task) && $("x-structure-materials").checked;
    show("sec-materials-a", task === "contents" || withA);
    show("sec-folders", task === "folders" || (FOLDER_EXTRA_TASKS().includes(task) && $("x-folders").checked));
    // "Nur Ablage" and "Keins" are not possible where the folders are the backbone.
    if (task === "folders" && !["structure+content", "structure"].includes($("f-folders-use").value)) {
      $("f-folders-use").value = "structure+content";
    }
    show("sec-materials-b", task === "assign" || $("x-content-materials").checked);
    $("x-content-label").textContent = t(`x.contentMaterials.${task}`);
    $("x-document-label").textContent = t(task === "folders" ? "x.document.folders" : "x.document");
    $("materials-a-label").textContent = t(task === "contents" ? "field.materialsA.contents" : "field.materialsA");
    $("materials-b-label").textContent = t(task === "assign" ? "field.materialsB.assign" : "field.materialsB");
    $("topic-req").textContent = t(task === "topic" ? "topic.req.required" : "topic.req.optional");
    $("topic-help").textContent = t(`help.topic.${task}`);
    $("task-intro").textContent = t(`intro.${task}`);
    $("frame-help").textContent = t(["refine", "assign"].includes(task) ? `help.frame.${task}` : "help.frame");
    $("btn-submit").textContent = t(["refine", "assign"].includes(task) ? `btn.submit.${task}` : "btn.submit.create");
  }

  const FOLDER_EXTRA_TASKS = () => window.TopicTreePresetItems.FOLDER_EXTRA_TASKS;

  /** A single select keeps the further values of a loaded frame as long as it still shows the first one. */
  function selected(id, loaded) {
    const value = $(id).value;
    if (!value) return [];
    return loaded && loaded[0] === value ? [...loaded] : [value];
  }

  function readFrame(state) {
    const loaded = state.loadedFrame || {};
    return {
      discipline_uri: [...state.disciplineUris],
      educational_context_uri: selected("f-context", loaded.educational_context_uri),
      intended_end_user_role_uri: selected("f-role", loaded.intended_end_user_role_uri),
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
        // A refine keeps the base's extra topics (loaded from its generation), so they are not lost on the way.
        extraGeneral: (task === "topic" || task === "refine") && $("f-extra-general").checked,
        extraMethodology: (task === "topic" || task === "refine") && $("f-extra-methodology").checked,
      },
      hints: {
        context: $("f-hint-context").value,
        order: $("f-hint-order").value,
        language: $("f-hint-lang").value,
        include: terms($("f-hint-include").value),
        exclude: terms($("f-hint-exclude").value),
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
        structureOnly: $("x-a-structure-only").checked,
        folders: FOLDER_EXTRA_TASKS().includes(task) && $("x-folders").checked,
        contentMaterials: task === "assign" || $("x-content-materials").checked,
        document: $("x-document").checked,
        documentContent: $("x-doc-content").checked,
        topicFrame: task === "document" || task === "contents" || task === "folders",
      },
      materialsA: $("f-materials-a").value,
      materialsB: $("f-materials-b").value,
      itemsRef: $("f-items-ref").value,
      documentMarkdown: $("f-doc-markdown").value,
      documentRef: $("f-doc-ref").value,
      documentTitle: $("f-doc-title").value,
      document2Markdown: $("f-doc2-markdown").value,
      document2Title: $("f-doc2-title").value,
      foldersUse: $("f-folders-use").value,
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
    "f-doc2-markdown": "", "f-doc2-title": "", "f-folders-use": "structure+content",
  };
  const CHECKS = {
    "f-extra-general": false, "f-extra-methodology": false, "f-opt-auto-meta": false, "f-opt-improve": false,
    "f-opt-assign": true, "f-opt-assign-only": false, "f-opt-multi": true, "x-structure-materials": false,
    "x-content-materials": false, "x-document": false,
    "x-doc-content": false, "x-folders": false, "x-a-structure-only": false,
  };

  function resetFields(state) {
    for (const [id, value] of Object.entries(VALUES)) $(id).value = value;
    for (const [id, value] of Object.entries(CHECKS)) $(id).checked = value;
    state.disciplineUris = [];
    state.loadedFrame = {};
    state.lockedKeys = new Set();
    state.changes.setChanges([]);
    setBase(state, null);
  }

  /** With `setSelectValue`, frame, shape, hints and options of the base's generation are loaded into the form. */
  function setBase(state, tree, setSelectValue) {
    state.currentTree = tree;
    if (tree && tree.generation && setSelectValue) {
      // assign_only describes the call that made the base, not the tree: carrying it over would block feedback.
      const generation = { ...tree.generation, options: { ...(tree.generation.options || {}), assign_only: false } };
      applySettings(state, generation, setSelectValue);
    } else if (tree) {
      // The extra-topic boxes are hidden in refine: without a generation, nothing from an earlier run may linger.
      $("f-extra-general").checked = false;
      $("f-extra-methodology").checked = false;
    }
    $("f-current-tree").value = tree ? JSON.stringify(tree, null, 2) : "";
    renderBaseSummary(state);
    state.changes.refresh();
  }

  /** Summary line and keyless hint of the base, from state only (so a language switch can redraw them). */
  function renderBaseSummary(state) {
    const tree = state.currentTree;
    $("base-summary").textContent = tree
      ? t("base.summary", {
        title: tree.title || "–",
        version: tree.version || "–",
        n: P().countNodes(tree.collection),
        useCase: (tree.generation && tree.generation.use_case) || "topic",
      })
      : t("base.none");
    const keyless = tree && state.task === "refine" ? P().countKeyless(tree.collection) : 0;
    for (const id of ["keyless-hint", "base-keyless-hint"]) {
      $(id).hidden = !keyless;
      $(id).textContent = keyless ? t("base.keyless", { n: keyless }) : "";
    }
  }


  function applySettings(state, payload, setSelectValue) {
    const frame = payload.frame || {};
    state.disciplineUris = [...(frame.discipline_uri || [])];
    state.loadedFrame = {
      educational_context_uri: [...(frame.educational_context_uri || [])],
      intended_end_user_role_uri: [...(frame.intended_end_user_role_uri || [])],
    };
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
    $("f-hint-include").value = joinTerms(hints.include || []);
    $("f-hint-exclude").value = joinTerms(hints.exclude || []);
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
    const slots = window.TopicTreePresetItems.splitItems(preset.task, payload);
    if (!slots) {
      // The request goes out as JSON, but its base must still be on screen (form fields stay reset).
      if (["assign", "refine"].includes(preset.task)) setBase(state, payload.current_tree || null);
      return false;
    }
    applySettings(state, payload, setSelectValue);
    window.TopicTreePresetItems.applyItems(preset.task, payload, slots);
    if (preset.task === "assign") setBase(state, payload.current_tree);
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

  window.TopicTreeForm = { syncVisibility, readForm, resetFields, setBase, renderBaseSummary, applyPreset };
})();
