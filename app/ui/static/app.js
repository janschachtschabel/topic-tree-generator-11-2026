/* Controller of the optional Topic-Tree v2 test UI. No external dependencies, the token is never persisted. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const I = () => window.TopicTreeI18n;
  const t = (key, vars) => (I() ? I().t(key, vars) : key);
  const sec = (s) => (I() ? I().formatSeconds(s) : Number(s).toFixed(1));
  const F = () => window.TopicTreeForm;
  const TASKS = ["topic", "document", "folders", "contents", "refine"];

  const state = {
    task: "topic",
    presets: [],
    vocabIndex: {},
    disciplineUris: [],
    lockedKeys: new Set(),
    currentTree: null,
    changes: null,
    limits: { max_tree_depth: 3, max_nodes_per_level: 20 },
    jsonOverride: false,
    lastRequest: null,
    lastResponse: null,
    lastSeconds: 0,
    rawTab: "response",
    controller: null,
    timerId: null,
    status: ["status.ready", {}],
  };

  function setStatus(key, vars = {}) {
    state.status = [key, vars];
    $("status-message").textContent = t(key, vars);
  }

  function showFormError(message) {
    $("form-error").hidden = !message;
    $("form-error").textContent = message || "";
  }

  function errorText(err) {
    const vars = { ...(err.vars || {}) };
    const label = (key, raw) => (t(key) === key ? raw : t(key));
    if (vars.row) vars.field = label(`change.field.${vars.field}`, vars.field);
    else if (vars.field) vars.field = label(`fieldname.${vars.field}`, vars.field);
    return t(err.message, vars);
  }

  // --- vocabulary selects and discipline chips -------------------------------------------------------------
  function populateSelect(select, options, groupKey) {
    const target = groupKey ? document.createElement("optgroup") : select;
    if (groupKey) {
      target.dataset.i18nGroup = groupKey;
      target.label = t(groupKey);
      select.appendChild(target);
    }
    for (const opt of options || []) {
      target.appendChild(new Option(opt.label, opt.uri));
      state.vocabIndex[opt.uri] = opt.label.replace(/^—\s+/, "");
    }
  }

  function setSelectValue(select, uri) {
    if (uri && !Array.from(select.options).some((o) => o.value === uri)) select.appendChild(new Option(uri, uri));
    select.value = uri || "";
  }

  function renderChips() {
    const box = $("discipline-chips");
    box.replaceChildren(...state.disciplineUris.map((uri) => {
      const name = state.vocabIndex[uri] || uri.split("/").pop();
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.append(name);
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "chip-remove";
      rm.textContent = "×";
      rm.setAttribute("aria-label", t("chip.removeAria", { name }));
      rm.addEventListener("click", () => {
        state.disciplineUris = state.disciplineUris.filter((u) => u !== uri);
        refresh();
      });
      chip.appendChild(rm);
      return chip;
    }));
    box.hidden = state.disciplineUris.length === 0;
  }

  // --- task navigation, presets, JSON view -------------------------------------------------------------------
  function fillPresetSelect() {
    const select = $("f-preset");
    select.replaceChildren(new Option(t("preset.placeholder"), ""));
    for (const p of state.presets.filter((x) => x.task === state.task)) select.appendChild(new Option(p.title, p.id));
  }

  function selectTask(task, { keepJson = false } = {}) {
    state.task = task;
    for (const btn of document.querySelectorAll(".task-btn")) {
      btn.classList.toggle("active", btn.dataset.task === task);
      btn.setAttribute("aria-pressed", String(btn.dataset.task === task));
    }
    if (!keepJson) setJsonOverride(false);
    fillPresetSelect();
    refresh();
  }

  function setJsonOverride(on) {
    state.jsonOverride = on;
    $("f-json").readOnly = !on;
    $("btn-json-edit").hidden = on;
    $("btn-json-reset").hidden = !on;
    $("json-help").textContent = t(on ? "help.json.editing" : "help.json");
  }

  function refresh() {
    F().syncVisibility(state);
    renderChips();
    renderBase();
    if (state.jsonOverride) return;
    try {
      $("f-json").value = JSON.stringify(window.TopicTreePayload.build(F().readForm(state)), null, 2);
    } catch (err) {
      $("f-json").value = `// ${errorText(err)}`;
    }
  }

  function applyPreset(preset) {
    const fits = F().applyPreset(state, preset, setSelectValue);
    selectTask(preset.task, { keepJson: !fits });
    if (fits) {
      setStatus("status.presetLoaded", { title: preset.title });
    } else {
      $("f-json").value = JSON.stringify(preset.payload, null, 2);
      setJsonOverride(true);
      $("acc-json").open = true;
      setStatus("status.presetJson", { title: preset.title });
    }
    $("f-preset").value = preset.id;
    showFormError("");
  }

  // --- refine base -------------------------------------------------------------------------------------
  function toggleLock(key) {
    if (state.lockedKeys.has(key)) state.lockedKeys.delete(key);
    else state.lockedKeys.add(key);
    $("f-fb-locked").value = [...state.lockedKeys].join(", ");
    refresh();
    return state.lockedKeys.has(key);
  }

  function editNode(key) {
    if (state.task !== "refine") adoptResult();
    state.changes.addRow({ op: "rename", key });
    $("changes-editor").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function renderBase() {
    const tree = state.task === "refine" ? state.currentTree : null;
    $("base-area").hidden = !tree || !$("result-area").hidden;
    if (!tree) return;
    $("base-heading").textContent = t("base.heading", { title: tree.title || "–", version: tree.version || "–" });
    window.TopicTreeView.renderTree($("base-tree"), tree.collection, state.lockedKeys, toggleLock, {}, editNode);
  }

  function adoptResult() {
    const resp = state.lastResponse;
    if (!resp) return;
    const generation = resp.metadata.generation || {};
    F().setBase(state, {
      version: resp.metadata.version,
      title: resp.metadata.title,
      description: resp.metadata.description,
      collection: resp.collection,
      generation,
    });
    $("f-fb-text").value = "";
    state.changes.setChanges([]);
    $("result-area").hidden = true;
    selectTask("refine");
    setStatus("status.adopted", { version: resp.metadata.version });
  }

  function readBaseJson() {
    const raw = $("f-current-tree").value.trim();
    if (!raw) return F().setBase(state, null);
    try {
      F().setBase(state, JSON.parse(raw));
      showFormError("");
    } catch {
      showFormError(t("err.json", { field: "current_tree" }));
    }
    return undefined;
  }

  // --- submit and result -------------------------------------------------------------------------------
  function currentPayload() {
    if (state.jsonOverride) {
      try { return JSON.parse($("f-json").value); } catch { throw new Error("err.jsonRequest"); }
    }
    return window.TopicTreePayload.build(F().readForm(state));
  }

  function setLoading(active, startedAt) {
    $("btn-submit").disabled = active;
    $("loading-state").hidden = !active;
    clearInterval(state.timerId);
    if (!active) return;
    for (const id of ["empty-state", "error-panel", "result-area", "base-area", "view-toggles"]) $(id).hidden = true;
    $("loading-text").textContent = t("loading.text");
    setStatus("status.running");
    state.timerId = setInterval(() => {
      $("loading-timer").textContent = `${sec((performance.now() - startedAt) / 1000)} s`;
    }, 100);
  }

  async function submitForm() {
    showFormError("");
    let payload;
    try { payload = currentPayload(); } catch (err) { showFormError(errorText(err)); return; }
    state.lastRequest = payload;
    state.controller = new AbortController();
    const startedAt = performance.now();
    setLoading(true, startedAt);
    const headers = { "Content-Type": "application/json" };
    const token = $("f-token").value.trim();
    if (token) headers.Authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    try {
      const res = await fetch("/v2/topic-tree", {
        method: "POST", headers, body: JSON.stringify(payload), signal: state.controller.signal,
      });
      let body = null;
      try { body = await res.json(); } catch { body = null; }
      if (res.ok) renderSuccess(body, (performance.now() - startedAt) / 1000);
      else renderError(res.status, body);
    } catch (err) {
      if (err.name === "AbortError") setStatus("status.aborted");
      else renderError(0, { error: { code: "NETWORK_ERROR", message: t("error.unreachable") } });
    } finally {
      setLoading(false, startedAt);
      state.controller = null;
      renderBase();
    }
  }

  function renderSuccess(resp, seconds) {
    state.lastResponse = resp;
    state.lastSeconds = seconds;
    $("result-area").hidden = false;
    $("view-toggles").hidden = false;
    $("btn-adopt").disabled = false;
    const gen = resp.metadata.generation || {};
    const duration = gen.usage && gen.usage.duration_ms != null ? gen.usage.duration_ms / 1000 : seconds;
    setStatus("status.done", { useCase: gen.use_case, mode: gen.mode, model: gen.model || "LLM", sec: sec(duration) });
    $("result-heading").textContent = `${resp.metadata.title || t("tree.defaultTitle")} · ${gen.use_case} · ${gen.mode}`;
    window.TopicTreeResult.renderMetrics($("metrics"), resp, seconds);
    window.TopicTreeResult.renderDiagnostics($("diagnostics-area"), resp);
    $("tree-title").textContent = resp.metadata.title || t("tree.defaultTitle");
    $("tree-description").textContent = resp.metadata.description || "";
    const st = gen.structure;
    $("tree-structure").textContent = st
      ? t("tree.orderLine", { source: st.source, order: st.order }) + ((st.levels || []).length ? ` · ${st.levels.join(" → ")}` : "")
      : "";
    window.TopicTreeView.renderTree(
      $("tree-container"), resp.collection, state.lockedKeys, toggleLock, resp.metadata.vocab_labels || {}, editNode,
    );
    if ($("tree-filter").value) window.TopicTreeView.filterTree($("tree-container"), $("tree-filter").value);
    renderRaw();
  }

  function renderError(status, body) {
    const err = (body && body.error) || {};
    $("error-panel").hidden = false;
    $("error-title").textContent = status ? t("error.http", { status }) : t("error.network");
    $("error-message").textContent = err.message || t("error.generic");
    $("error-code").textContent = err.code || "HTTP_ERROR";
    $("error-trace").textContent = err.trace_id || "–";
    $("error-details").hidden = !err.details;
    $("error-details").textContent = err.details ? JSON.stringify(err.details, null, 2) : "";
    setStatus("status.failed", { code: err.code || status });
  }

  function renderRaw() {
    const data = state.rawTab === "request" ? state.lastRequest : state.lastResponse;
    $("raw-json-pre").textContent = data ? JSON.stringify(data, null, 2) : "";
  }

  window.TopicTreeApp = {
    state, $, t, setStatus, showFormError, populateSelect, selectTask, applyPreset, refresh, submitForm,
    adoptResult, readBaseJson, renderSuccess, renderRaw, setJsonOverride, renderChips, TASKS,
  };
})();
