/* Preset items -> form slots of the test UI: which preset fits the form, and filling its item fields. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const P = () => window.TopicTreeParsers;
  // Tasks where a folder structure can be an extra input next to the task's own backbone.
  const FOLDER_EXTRA_TASKS = ["topic", "document", "contents"];

  /** Roles as one string; a missing `use` means the use case default, `[]` (neither) only fits the JSON view. */
  function sameUse(item, task) {
    if (Array.isArray(item.use)) return [...item.use].sort().join("+");
    return task === "contents" ? "content+structure" : "content";
  }

  /** Splits preset items into the form's slots; `null` when something only the JSON view can hold. */
  function splitItems(task, payload) {
    const items = payload.items || [];
    const folderIds = new Set();
    (function visit(list) {
      for (const f of list || []) { (f.items || []).forEach((id) => folderIds.add(id)); visit(f.subcollections); }
    })(payload.folders);
    const slots = { docs: [], a: [], b: [], folderItems: [], aUse: null };
    for (const item of items) {
      const use = sameUse(item, task);
      if (folderIds.has(item.id)) {
        // The outline holds only titles and the default role: anything more needs the JSON view.
        const extra = Object.keys(item.properties || {}).some((k) => k !== "cm:title");
        if (extra || item.fulltext || item.path || (item.use !== undefined && use !== "content")) return null;
        slots.folderItems.push(item);
      }
      else if (item.fulltext && (use === "structure" || use === "content+structure")) slots.docs.push(item);
      else if (use === "structure" || use === "content+structure") {
        if (slots.aUse && slots.aUse !== use) return null;
        slots.aUse = use;
        slots.a.push(item);
      } else if (use === "content") slots.b.push(item);
      else return null;
    }
    const aAllowed = ["topic", "document", "folders", "contents"].includes(task);
    const docAllowed = ["topic", "document", "folders"].includes(task);
    const docUses = new Set(slots.docs.map((d) => sameUse(d, task)));
    const docsFit = slots.docs.length <= 2 && docUses.size <= 1 && (!slots.docs[1] || slots.docs[1].fulltext.text);
    if (!docsFit || (slots.docs.length && !docAllowed) || (slots.a.length && !aAllowed)) return null;
    if (payload.folders && task !== "folders" && !FOLDER_EXTRA_TASKS.includes(task)) return null;
    const linesA = P().materialLinesFromItems(slots.a);
    const linesB = P().materialLinesFromItems(slots.b);
    if (linesA === null || linesB === null || P().materialLinesFromItems(slots.folderItems) === null) return null;
    return { ...slots, linesA, linesB };
  }

  /** `folders_use` of a request as the value of the form's select. */
  function foldersUseValue(use) {
    if (!Array.isArray(use)) return "structure+content";
    if (!use.length) return "none";
    return use.includes("structure") && use.includes("content") ? "structure+content" : use[0];
  }

  function applyDocuments(task, docs) {
    const [doc, doc2] = docs;
    if (!doc) return;
    $("x-document").checked = task !== "document";
    $("x-doc-content").checked = sameUse(doc, task) === "content+structure";
    $("f-doc-markdown").value = doc.fulltext.text || "";
    $("f-doc-ref").value = doc.fulltext.ref || "";
    $("f-doc-title").value = ((doc.properties || {})["cm:title"] || [""])[0];
    if (doc2) {
      $("f-doc2-markdown").value = doc2.fulltext.text || "";
      $("f-doc2-title").value = ((doc2.properties || {})["cm:title"] || [""])[0];
    }
  }

  function applyItems(task, payload, slots) {
    applyDocuments(task, slots.docs);
    $("x-structure-materials").checked = task !== "contents" && slots.a.length > 0;
    $("x-a-structure-only").checked = slots.aUse === "structure";
    $("f-materials-a").value = slots.linesA;
    $("x-content-materials").checked = slots.b.length > 0;
    $("f-materials-b").value = slots.linesB;
    if (payload.folders) {
      $("f-folder-outline").value = P().folderOutlineFromPayload(payload.folders, slots.folderItems);
      $("x-folders").checked = task !== "folders";
      $("f-folders-use").value = foldersUseValue(payload.folders_use);
    }
    $("f-items-ref").value = payload.items_ref || "";
  }

  window.TopicTreePresetItems = { splitItems, applyItems, FOLDER_EXTRA_TASKS };
})();
