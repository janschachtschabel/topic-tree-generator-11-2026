/* The base tree of "Baum ändern" and "Inhalte einsortieren": locks, node actions, adopting a result, base JSON. */
(() => {
  "use strict";

  const A = () => window.TopicTreeApp;
  const F = () => window.TopicTreeForm;

  function toggleLock(key) {
    const { $, state, refresh } = A();
    if (state.lockedKeys.has(key)) state.lockedKeys.delete(key);
    else state.lockedKeys.add(key);
    $("f-fb-locked").value = [...state.lockedKeys].join(", ");
    refresh();
    renderBase();
    return state.lockedKeys.has(key);
  }

  const resultShown = () => Boolean(A().state.lastResponse) && !A().$("result-area").hidden;

  // Actions on the result tree first make that result the base, so keys and locks refer to the tree on screen.
  function lockOnResult(key) {
    adoptResult();
    return toggleLock(key);
  }

  function editNode(key) {
    const { $, state } = A();
    if (resultShown()) adoptResult();
    state.changes.addRow({ op: "rename", key });
    $("changes-editor").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function renderBase() {
    const { $, t, state } = A();
    const tree = ["refine", "assign"].includes(state.task) ? state.currentTree : null;
    $("base-area").hidden = !tree || !$("result-area").hidden;
    if (!tree) return;
    $("base-heading").textContent = t("base.heading", { title: tree.title || "–", version: tree.version || "–" });
    $("base-tree-label").textContent = t(state.task === "assign" ? "base.tree.assign" : "base.tree");
    if (state.task === "assign") window.TopicTreeView.renderTree($("base-tree"), tree.collection, new Set(), null, {});
    else window.TopicTreeView.renderTree($("base-tree"), tree.collection, state.lockedKeys, toggleLock, {}, editNode);
  }

  function adoptResult() {
    const { $, state, setStatus, selectTask } = A();
    const resp = state.lastResponse;
    if (!resp) return;
    const generation = resp.metadata.generation || {};
    F().setBase(state, {
      version: resp.metadata.version,
      title: resp.metadata.title,
      description: resp.metadata.description,
      collection: resp.collection,
      generation,
    }, A().setSelectValue);
    // Feedback and materials of the last run are already in the adopted tree; start the next change from scratch.
    $("f-fb-text").value = "";
    $("f-materials-b").value = "";
    $("x-content-materials").checked = false;
    state.lockedKeys = new Set();
    $("f-fb-locked").value = "";
    state.changes.setChanges([]);
    $("result-area").hidden = true;
    selectTask("refine");
    setStatus("status.adopted", { version: resp.metadata.version });
  }

  function readBaseJson() {
    const { $, t, state, showFormError, refresh } = A();
    const raw = $("f-current-tree").value.trim();
    try {
      F().setBase(state, raw ? JSON.parse(raw) : null, A().setSelectValue);
      showFormError("");
    } catch {
      showFormError(t("err.json", { field: "current_tree" }));
    }
    refresh();
    renderBase();
  }

  window.TopicTreeBase = { toggleLock, lockOnResult, editNode, renderBase, adoptResult, readBaseJson };
})();
