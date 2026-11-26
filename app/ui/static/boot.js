/* Wires DOM events of the test UI and loads presets and vocabularies from /ui/presets. */
(() => {
  "use strict";

  const A = () => window.TopicTreeApp;

  function renderTaskCards() {
    const { $, t, state, selectTask, TASKS } = A();
    $("task-cards").replaceChildren(...TASKS.map((task) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "task-card";
      const title = document.createElement("strong");
      title.textContent = t(`task.${task}`);
      const text = document.createElement("span");
      text.textContent = t(`intro.${task}`);
      const count = document.createElement("span");
      count.className = "task-card-count";
      const own = state.presets.filter((p) => p.task === task);
      const combos = own.filter((p) => p.combo).length;
      count.textContent = t(combos ? (combos === 1 ? "task.examplesCombo1" : "task.examplesCombo") : "task.examples", { n: own.length, c: combos });
      card.append(title, text, count);
      card.addEventListener("click", () => selectTask(task));
      return card;
    }));
  }

  function switchLanguage(lang) {
    const { $, t, state, setStatus, refresh, renderSuccess } = A();
    window.TopicTreeI18n.setLang(lang);
    for (const grp of document.querySelectorAll("optgroup[data-i18n-group]")) grp.label = t(grp.dataset.i18nGroup);
    $("shape-limits-note").textContent = t("shape.limits", {
      dMax: state.limits.max_tree_depth, wMax: state.limits.max_nodes_per_level,
    });
    A().setJsonOverride(state.jsonOverride);
    const selected = $("f-preset").value;
    A().fillPresetSelect();
    $("f-preset").value = selected;
    state.changes.refresh();
    renderTaskCards();
    refresh();
    if (state.lastResponse && !$("result-area").hidden) renderSuccess(state.lastResponse, state.lastSeconds);
    setStatus(...state.status);
  }

  async function copyJson() {
    const { state, setStatus } = A();
    if (!state.lastResponse) return;
    // The Clipboard API exists only in secure contexts (HTTPS/localhost); plain-HTTP deployments reject it.
    try {
      await navigator.clipboard.writeText(JSON.stringify(state.lastResponse, null, 2));
      setStatus("status.copied");
    } catch {
      setStatus("status.copyFailed");
    }
  }

  function downloadJson() {
    const { state } = A();
    if (!state.lastResponse) return;
    const blob = new Blob([JSON.stringify(state.lastResponse, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `topic-tree-${state.lastResponse.metadata.version || "v2"}.json`;
    a.click();
    // Revoking synchronously can cancel the download in some browsers (e.g. Firefox).
    setTimeout(() => URL.revokeObjectURL(a.href), 0);
  }

  function wireEvents() {
    const app = A();
    const { $, state } = app;
    const form = $("tree-form");
    form.addEventListener("submit", (e) => { e.preventDefault(); app.submitForm(); });
    form.addEventListener("input", (e) => { if (e.target.id !== "f-json") app.refresh(); });
    form.addEventListener("change", (e) => { if (e.target.id !== "f-json" && e.target.id !== "f-preset") app.refresh(); });
    for (const btn of document.querySelectorAll(".task-btn")) btn.addEventListener("click", () => app.selectTask(btn.dataset.task));
    for (const btn of document.querySelectorAll(".lang-btn")) btn.addEventListener("click", () => switchLanguage(btn.dataset.lang));
    $("f-preset").addEventListener("change", (e) => {
      const preset = state.presets.find((p) => p.id === e.target.value);
      if (preset) app.applyPreset(preset);
    });
    $("btn-reset").addEventListener("click", () => {
      window.TopicTreeForm.resetFields(state);
      $("f-preset").value = "";
      app.selectTask(state.task);
      app.setStatus("status.reset");
    });
    $("f-discipline").addEventListener("change", (e) => {
      const uri = e.target.value;
      if (uri && !state.disciplineUris.includes(uri) && state.disciplineUris.length < 20) state.disciplineUris.push(uri);
      e.target.value = "";
      app.refresh();
    });
    $("f-fb-locked").addEventListener("input", (e) => {
      state.lockedKeys = new Set(e.target.value.split(",").map((s) => s.trim()).filter(Boolean));
    });
    $("f-current-tree").addEventListener("change", app.readBaseJson);
    $("btn-adopt").addEventListener("click", app.adoptResult);
    $("btn-use-refine").addEventListener("click", app.adoptResult);
    $("btn-add-change").addEventListener("click", () => state.changes.addRow({}));
    $("btn-json-edit").addEventListener("click", () => { app.setJsonOverride(true); $("f-json").focus(); });
    $("btn-json-reset").addEventListener("click", () => { app.setJsonOverride(false); app.refresh(); });
  }

  function wireResultEvents() {
    const app = A();
    const { $, state } = app;
    $("btn-cancel").addEventListener("click", () => state.controller?.abort());
    $("btn-retry").addEventListener("click", app.submitForm);
    $("btn-copy-json").addEventListener("click", copyJson);
    $("btn-download-json").addEventListener("click", downloadJson);
    $("opt-show-details").addEventListener("change", (e) => {
      for (const id of ["tree-container", "base-tree"]) $(id).classList.toggle("compact-tree", !e.target.checked);
    });
    $("opt-show-keys").addEventListener("change", (e) => {
      for (const id of ["tree-container", "base-tree"]) $(id).classList.toggle("show-keys", e.target.checked);
    });
    $("btn-expand-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), true));
    $("btn-collapse-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), false));
    $("tree-filter").addEventListener("input", (e) => window.TopicTreeView.filterTree($("tree-container"), e.target.value));
    for (const tab of document.querySelectorAll(".tab-btn")) {
      tab.addEventListener("click", () => {
        state.rawTab = tab.dataset.tab;
        for (const other of document.querySelectorAll(".tab-btn")) {
          other.classList.toggle("active", other === tab);
          other.setAttribute("aria-selected", String(other === tab));
        }
        app.renderRaw();
      });
    }
  }

  async function loadPresets() {
    const app = A();
    const { $, state } = app;
    const data = await (await fetch("/ui/presets")).json();
    state.limits = data.limits || state.limits;
    $("service-version").textContent = `v${data.version}`;
    $("f-depth").max = String(state.limits.max_tree_depth);
    for (const id of ["f-main-min", "f-main-max", "f-child-min", "f-child-max"]) $(id).max = String(state.limits.max_nodes_per_level);
    app.populateSelect($("f-discipline"), data.vocabs.discipline, "group.school");
    app.populateSelect($("f-discipline"), data.vocabs.hochschulfaechersystematik, "group.uni");
    app.populateSelect($("f-context"), data.vocabs.educationalContext);
    app.populateSelect($("f-role"), data.vocabs.intendedEndUserRole);
    state.presets = data.presets;
  }

  async function init() {
    const app = A();
    const { $, state } = app;
    state.changes = window.TopicTreeChanges.mount($("changes-editor"), {
      getNodes: () => window.TopicTreeParsers.treeNodeOptions(state.currentTree ? state.currentTree.collection : []),
      onChange: () => app.refresh(),
    });
    wireEvents();
    wireResultEvents();
    try {
      await loadPresets();
    } catch {
      app.showFormError(app.t("error.presetsLoad"));
    }
    switchLanguage("de");
    app.selectTask("topic");
    app.setStatus("status.ready");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
