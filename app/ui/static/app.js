/* Controller for the optional Topic-Tree v2 test UI. Zero external dependencies, zero token persistence. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const i18n = () => window.TopicTreeI18n;
  const t = (key, vars) => (i18n() ? i18n().t(key, vars) : key);
  const fmtNum = (n) => (i18n() ? i18n().formatNumber(n) : String(n));
  const fmtSec = (s) => (i18n() ? i18n().formatSeconds(s) : Number(s).toFixed(1));

  const state = {
    presets: [],
    activePresetId: null,
    limits: { max_tree_depth: 3, max_nodes_per_level: 20 },
    disciplineUris: [],
    vocabIndex: {},
    lastRequest: null,
    lastResponse: null,
    lastClientSeconds: 0,
    activeRawTab: "response",
    lockedKeys: new Set(),
    controller: null,
    timerId: null,
    statusKey: "status.ready",
    statusVars: null,
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setStatus(key, vars = null) {
    state.statusKey = key;
    state.statusVars = vars;
    $("status-message").textContent = t(key, vars);
  }

  function splitCsv(text) {
    return (text || "").split(",").map((s) => s.trim()).filter(Boolean);
  }

  function parseOptionalJson(raw, fieldName) {
    const trimmed = (raw || "").trim();
    if (!trimmed) return null;
    try {
      return JSON.parse(trimmed);
    } catch (err) {
      throw new Error(t("err.invalidJson", { field: fieldName, msg: err.message }));
    }
  }

  function populateSelect(selectEl, options, groupKey) {
    const target = groupKey ? document.createElement("optgroup") : selectEl;
    if (groupKey) {
      target.dataset.i18nGroup = groupKey;
      target.label = t(groupKey);
      selectEl.appendChild(target);
    }
    for (const opt of options || []) {
      const o = document.createElement("option");
      o.value = opt.uri;
      o.textContent = opt.label;
      target.appendChild(o);
      state.vocabIndex[opt.uri] = opt.label.replace(/^—\s+/, "");
    }
  }

  function setSelectValue(selectEl, uri) {
    if (!uri) {
      selectEl.value = "";
      return;
    }
    const exists = Array.from(selectEl.options).some((o) => o.value === uri);
    if (!exists) {
      const o = document.createElement("option");
      o.value = uri;
      o.textContent = uri;
      selectEl.appendChild(o);
    }
    selectEl.value = uri;
  }

  function renderDisciplineChips() {
    const box = $("discipline-chips");
    box.replaceChildren();
    for (const uri of state.disciplineUris) {
      const name = state.vocabIndex[uri] || uri.split("/").pop() || uri;
      const chip = el("span", "chip");
      chip.appendChild(document.createTextNode(name));
      const rm = el("button", "chip-remove", "×");
      rm.type = "button";
      rm.setAttribute("aria-label", t("chip.removeAria", { name }));
      rm.addEventListener("click", () => {
        state.disciplineUris = state.disciplineUris.filter((u) => u !== uri);
        renderDisciplineChips();
      });
      chip.appendChild(rm);
      box.appendChild(chip);
    }
    box.hidden = state.disciplineUris.length === 0;
  }

  function addDiscipline(uri) {
    if (!uri || state.disciplineUris.includes(uri) || state.disciplineUris.length >= 20) return;
    state.disciplineUris = [...state.disciplineUris, uri];
    renderDisciplineChips();
  }

  function syncActivePresetCards(presetId) {
    state.activePresetId = presetId || null;
    $("f-preset").value = presetId || "";
    for (const card of document.querySelectorAll(".empty-preset-card")) {
      card.classList.toggle("active", Boolean(presetId) && card.dataset.presetId === presetId);
    }
  }

  function updateShapeLimitsNote() {
    $("shape-limits-note").textContent = t("shape.limits", {
      dMax: state.limits.max_tree_depth,
      wMax: state.limits.max_nodes_per_level,
    });
  }

  function resetForm() {
    syncActivePresetCards(null);
    $("f-mode").value = "create";
    $("f-use-case").value = "topic";
    $("f-topic").value = "";
    state.disciplineUris = [];
    renderDisciplineChips();
    $("f-discipline").value = "";
    $("f-context").value = "";
    $("f-role").value = "";

    $("f-depth").value = "";
    $("f-main-min").value = "";
    $("f-main-max").value = "";
    $("f-child-min").value = "";
    $("f-child-max").value = "";
    $("f-desc-len").value = 60;
    $("f-extra-general").checked = false;
    $("f-extra-methodology").checked = false;

    $("f-hint-context").value = "";
    $("f-hint-order").value = "";
    $("f-hint-lang").value = "de";
    $("f-hint-include").value = "";
    $("f-hint-exclude").value = "";

    $("f-opt-auto-meta").checked = false;
    $("f-opt-improve").checked = false;
    $("f-opt-assign").checked = true;
    $("f-opt-assign-only").checked = false;
    $("f-opt-multi").checked = true;
    $("f-opt-conf").value = 0.6;

    $("f-doc-markdown").value = "";
    $("f-items").value = "";
    $("f-items-ref").value = "";
    $("f-folders").value = "";
    $("f-current-tree").value = "";
    $("f-fb-text").value = "";
    $("f-fb-locked").value = "";
    $("f-fb-changes").value = "";
    state.lockedKeys = new Set();

    $("acc-items").open = false;
    $("acc-folders").open = false;
    $("acc-refine").open = false;
    $("acc-hints").open = false;
    $("acc-options").open = false;
    syncModeLabels();
    showFormError("");
    setStatus("status.reset");
  }

  function applyPreset(preset) {
    syncActivePresetCards(preset.id);
    const p = preset.payload;
    $("f-mode").value = p.mode || "create";
    $("f-use-case").value = p.use_case || "topic";
    $("f-topic").value = p.topic || "";

    const frame = p.frame || {};
    state.disciplineUris = [...(frame.discipline_uri || [])];
    renderDisciplineChips();
    $("f-discipline").value = "";
    setSelectValue($("f-context"), (frame.educational_context_uri || [])[0] || "");
    setSelectValue($("f-role"), (frame.intended_end_user_role_uri || [])[0] || "");

    const shape = p.shape || {};
    $("f-depth").value = shape.depth ?? "";
    $("f-main-min").value = shape.main_topics?.min ?? "";
    $("f-main-max").value = shape.main_topics?.max ?? "";
    $("f-child-min").value = shape.children?.min ?? "";
    $("f-child-max").value = shape.children?.max ?? "";
    const extras = shape.extra_topics || [];
    $("f-extra-general").checked = extras.includes("general");
    $("f-extra-methodology").checked = extras.includes("methodology");

    const hints = p.hints || {};
    $("f-hint-context").value = hints.context || "";
    $("f-hint-order").value = hints.order || "";
    $("f-hint-lang").value = hints.language || "de";
    $("f-hint-include").value = (hints.include || []).join(", ");
    $("f-hint-exclude").value = (hints.exclude || []).join(", ");
    $("f-desc-len").value = hints.description_length ?? 60;

    const opts = p.options || {};
    $("f-opt-auto-meta").checked = Boolean(opts.auto_metadata);
    $("f-opt-improve").checked = Boolean(opts.improve);
    $("f-opt-assign").checked = opts.assign_contents ?? true;
    $("f-opt-assign-only").checked = Boolean(opts.assign_only);
    $("f-opt-multi").checked = opts.multi_assign ?? true;
    $("f-opt-conf").value = opts.min_confidence ?? 0.6;

    $("f-doc-markdown").value = "";
    $("f-items").value = p.items ? JSON.stringify(p.items, null, 2) : "";
    $("f-items-ref").value = p.items_ref || "";
    $("f-folders").value = p.folders ? JSON.stringify(p.folders, null, 2) : "";
    $("f-current-tree").value = p.current_tree ? JSON.stringify(p.current_tree, null, 2) : "";

    const fb = p.feedback || {};
    $("f-fb-text").value = fb.text || "";
    $("f-fb-locked").value = (fb.locked || []).join(", ");
    $("f-fb-changes").value = fb.changes?.length ? JSON.stringify(fb.changes, null, 2) : "";
    state.lockedKeys = new Set(fb.locked || []);

    $("acc-items").open = Boolean((p.items && p.items.length) || p.items_ref);
    $("acc-folders").open = Boolean(p.folders && p.folders.length);
    $("acc-refine").open = p.mode === "refine";
    $("acc-hints").open = Boolean(
      hints.context || hints.order || (hints.language && hints.language !== "de") || (hints.include || []).length || (hints.exclude || []).length,
    );
    $("acc-options").open = Boolean(opts.auto_metadata || opts.improve || opts.assign_only);
    syncModeLabels();
    showFormError("");
    $("tree-form").scrollTop = 0;
    setStatus("status.presetLoaded", { title: preset.title, action: $("btn-submit").textContent });
  }

  function syncModeLabels(autoOpen) {
    const mode = $("f-mode").value;
    const useCase = $("f-use-case").value;
    const isRefine = mode === "refine";
    $("btn-submit").textContent = t(isRefine ? "btn.submit.refine" : "btn.submit.create");
    $("topic-req").textContent = t(useCase === "topic" && !isRefine ? "topic.req.required" : "topic.req.optional");
    if (autoOpen) {
      if (isRefine) $("acc-refine").open = true;
      if (useCase === "document" || useCase === "contents") $("acc-items").open = true;
      if (useCase === "folders") $("acc-folders").open = true;
    }
  }

  function optionalInt(id) {
    const raw = ($(id).value || "").trim();
    if (!raw) return null;
    const n = Number(raw);
    if (!Number.isInteger(n)) throw new Error(t("err.invalidInt", { field: id }));
    return n;
  }

  function buildPayload() {
    const mode = $("f-mode").value;
    const useCase = $("f-use-case").value;
    const depth = optionalInt("f-depth");
    const mainMin = optionalInt("f-main-min");
    const mainMax = optionalInt("f-main-max");
    const childMin = optionalInt("f-child-min");
    const childMax = optionalInt("f-child-max");
    if (mainMin !== null && mainMax !== null && mainMin > mainMax) throw new Error(t("err.mainRange"));
    if (childMin !== null && childMax !== null && childMin > childMax) throw new Error(t("err.childRange"));

    const lang = ($("f-hint-lang").value || "de").trim().toLowerCase();
    if (!/^[a-z]{2}$/.test(lang)) throw new Error(t("err.langCode"));

    const shape = {};
    if (depth !== null) shape.depth = depth;
    const wCap = state.limits.max_nodes_per_level;
    if (mainMin !== null || mainMax !== null) {
      shape.main_topics = {
        min: mainMin ?? Math.min(6, mainMax),
        max: mainMax ?? Math.min(wCap, Math.max(12, mainMin)),
      };
    }
    if (childMin !== null || childMax !== null) {
      shape.children = {
        min: childMin ?? Math.min(3, childMax),
        max: childMax ?? Math.min(wCap, Math.max(8, childMin)),
      };
    }
    const extraTopics = [
      ...($("f-extra-general").checked ? ["general"] : []),
      ...($("f-extra-methodology").checked ? ["methodology"] : []),
    ];
    if (extraTopics.length) shape.extra_topics = extraTopics;

    const payload = {
      mode,
      use_case: useCase,
      frame: {
        discipline_uri: [...state.disciplineUris],
        educational_context_uri: $("f-context").value ? [$("f-context").value] : [],
        intended_end_user_role_uri: $("f-role").value ? [$("f-role").value] : [],
      },
      hints: {
        description_length: Number($("f-desc-len").value) || 60,
        language: lang,
      },
      options: {
        auto_metadata: $("f-opt-auto-meta").checked,
        improve: $("f-opt-improve").checked,
        assign_contents: $("f-opt-assign").checked,
        assign_only: $("f-opt-assign-only").checked,
        multi_assign: $("f-opt-multi").checked,
        min_confidence: Number($("f-opt-conf").value),
      },
    };
    if (Object.keys(shape).length) payload.shape = shape;

    const topic = $("f-topic").value.trim();
    if (topic) payload.topic = topic;
    if ($("f-hint-context").value.trim()) payload.hints.context = $("f-hint-context").value.trim();
    if ($("f-hint-order").value.trim()) payload.hints.order = $("f-hint-order").value.trim();
    const inc = splitCsv($("f-hint-include").value);
    const exc = splitCsv($("f-hint-exclude").value);
    if (inc.length) payload.hints.include = inc;
    if (exc.length) payload.hints.exclude = exc;

    const docMd = $("f-doc-markdown").value.trim();
    const parsedItems = parseOptionalJson($("f-items").value, "items");
    if (parsedItems !== null && !Array.isArray(parsedItems)) throw new Error(t("err.itemsArray"));
    const items = parsedItems ? [...parsedItems] : [];
    if (docMd) {
      items.unshift({
        id: "doc-manual",
        use: ["structure"],
        properties: { "cm:title": [topic || "Strukturdokument"] },
        fulltext: { format: "markdown", text: docMd },
      });
    }
    const itemsRef = $("f-items-ref").value.trim();
    if (items.length && itemsRef) throw new Error(t("err.itemsAndRef"));
    if (items.length) payload.items = items;
    if (itemsRef) payload.items_ref = itemsRef;

    const folders = parseOptionalJson($("f-folders").value, "folders");
    if (folders && folders.length) payload.folders = folders;
    const currentTree = parseOptionalJson($("f-current-tree").value, "current_tree");
    if (currentTree && Object.keys(currentTree).length) payload.current_tree = currentTree;

    const fbText = $("f-fb-text").value.trim();
    const fbLocked = splitCsv($("f-fb-locked").value);
    const fbChanges = parseOptionalJson($("f-fb-changes").value, "feedback.changes");
    if (fbText || fbLocked.length || (fbChanges && fbChanges.length)) {
      payload.feedback = {};
      if (fbText) payload.feedback.text = fbText;
      if (fbLocked.length) payload.feedback.locked = fbLocked;
      if (fbChanges && fbChanges.length) payload.feedback.changes = fbChanges;
    }
    return payload;
  }

  function showFormError(msg) {
    const box = $("form-error");
    box.hidden = !msg;
    box.textContent = msg || "";
  }

  function metricPair(label, value, pillClass) {
    const wrap = el("span", "metric-pair");
    wrap.appendChild(el("span", "metric-k", label));
    wrap.appendChild(el("span", pillClass ? `metric-pill ${pillClass}` : "metric-v", value));
    return wrap;
  }

  function renderMetrics(resp, clientSeconds) {
    const stats = window.TopicTreeView.computeTreeStats(resp.collection);
    const gen = resp.metadata.generation || {};
    const usage = gen.usage || {};
    const promptTokens = usage.prompt_tokens || 0;
    const cachedTokens = usage.cached_tokens || 0;
    const uncachedTokens = Math.max(0, promptTokens - cachedTokens);
    const completionTokens = usage.completion_tokens || 0;
    const totalTokens = promptTokens + completionTokens;
    const cachePct = promptTokens ? Math.round((cachedTokens / promptTokens) * 100) : 0;
    const levelsText = Object.entries(stats.byLevel).map(([lvl, cnt]) => `E${lvl}: ${cnt}`).join(" · ");

    const treeItems = [
      metricPair(t("metric.nodes"), `${fmtNum(stats.total)}${levelsText ? ` (${levelsText})` : ""}`),
      metricPair(t("metric.described"), `${stats.descPct} %`),
      metricPair(t("metric.assigned"), fmtNum(stats.totalContents)),
      metricPair(t("metric.version"), resp.metadata.version + (resp.metadata.based_on ? ` ← ${resp.metadata.based_on}` : "")),
      metricPair(t("metric.warnings"), String((resp.warnings || []).length), (resp.warnings || []).length ? "warn" : "ok"),
      metricPair(t("metric.questions"), String((resp.questions || []).length)),
    ];
    if (stats.duplicates > 0) {
      treeItems.splice(3, 0, metricPair(t("metric.duplicates"), String(stats.duplicates), "warn"));
    }
    $("metrics-tree").replaceChildren(...treeItems);

    const serverSec = usage.duration_ms != null ? fmtSec(usage.duration_ms / 1000) : fmtSec(clientSeconds);
    $("metrics-time").replaceChildren(
      metricPair(t("metric.duration"), `${serverSec} s`),
      metricPair(t("metric.llmCalls"), String(usage.llm_calls ?? 0)),
      metricPair(t("metric.failed"), String(usage.failed_calls ?? 0), (usage.failed_calls || 0) ? "warn" : "ok"),
      metricPair(t("metric.model"), gen.model || "–"),
    );

    $("metrics-tokens").replaceChildren(
      metricPair(t("metric.total"), fmtNum(totalTokens)),
      metricPair(t("metric.uncached"), fmtNum(uncachedTokens)),
      metricPair(t("metric.cached"), `${fmtNum(cachedTokens)} (${cachePct} %)`, cachePct >= 40 ? "ok" : ""),
      metricPair(t("metric.output"), fmtNum(completionTokens)),
    );
  }

  function renderDiagnostics(resp) {
    const area = $("diagnostics-area");
    area.replaceChildren();
    const blocks = [];

    if ((resp.warnings || []).length) {
      const card = el("div", "diag-card warn");
      card.appendChild(el("h3", "", t("diag.warnings", { n: resp.warnings.length })));
      const ul = el("ul", "diag-list");
      for (const w of resp.warnings) {
        const extra = [w.key, w.step].filter(Boolean).join(" / ");
        ul.appendChild(el("li", "", `[${w.code}] ${w.message}${extra ? ` (${extra})` : ""}`));
      }
      card.appendChild(ul);
      blocks.push(card);
    }

    if ((resp.questions || []).length) {
      const card = el("div", "diag-card info");
      card.appendChild(el("h3", "", t("diag.questions", { n: resp.questions.length })));
      const ul = el("ul", "diag-list");
      for (const q of resp.questions) ul.appendChild(el("li", "", q.text));
      card.appendChild(ul);
      blocks.push(card);
    }

    if ((resp.changes || []).length) {
      const card = el("div", "diag-card");
      card.appendChild(el("h3", "", t("diag.changes", { n: resp.changes.length })));
      const ul = el("ul", "diag-list");
      for (const c of resp.changes) {
        const target = c.title || c.to || (c.keys || []).join(", ") || "";
        ul.appendChild(el("li", "", `${c.op} ${c.key || ""} ${target ? `→ ${target}` : ""} (${c.from})`));
      }
      card.appendChild(ul);
      blocks.push(card);
    }

    if ((resp.unassigned || []).length) {
      const card = el("div", "diag-card");
      card.appendChild(el("h3", "", t("diag.unassigned", { n: resp.unassigned.length })));
      const ul = el("ul", "diag-list");
      for (const u of resp.unassigned) {
        ul.appendChild(el("li", "", `${u.id}${u.nodeId ? ` (${u.nodeId})` : ""} – ${t("diag.reason", { reason: u.reason })}`));
      }
      card.appendChild(ul);
      blocks.push(card);
    }

    for (const b of blocks) area.appendChild(b);
    area.hidden = blocks.length === 0;
  }

  function renderRawJson() {
    const data = state.activeRawTab === "request" ? state.lastRequest : state.lastResponse;
    $("raw-json-pre").textContent = data ? JSON.stringify(data, null, 2) : "";
  }

  function onToggleLock(key) {
    if (state.lockedKeys.has(key)) state.lockedKeys.delete(key);
    else state.lockedKeys.add(key);
    $("f-fb-locked").value = Array.from(state.lockedKeys).join(", ");
    return state.lockedKeys.has(key);
  }

  function renderSuccess(resp, clientSeconds) {
    state.lastResponse = resp;
    state.lastClientSeconds = clientSeconds;
    $("empty-state").hidden = true;
    $("error-panel").hidden = true;
    $("result-area").hidden = false;
    $("result-actions").hidden = false;

    const gen = resp.metadata.generation || {};
    const usage = gen.usage || {};
    const sec = usage.duration_ms != null ? fmtSec(usage.duration_ms / 1000) : fmtSec(clientSeconds);
    setStatus("status.done", { useCase: gen.use_case, mode: gen.mode, model: gen.model || "LLM", sec });

    renderMetrics(resp, clientSeconds);
    renderDiagnostics(resp);

    $("tree-title").textContent = resp.metadata.title || t("tree.defaultTitle");
    $("tree-description").textContent = resp.metadata.description || "";
    const st = gen.structure;
    $("tree-structure").textContent = st
      ? t("tree.orderLine", { source: st.source, order: st.order }) + (st.levels?.length ? `${t("tree.levelsSep")}${st.levels.join(" → ")}` : "")
      : "";

    window.TopicTreeView.renderTree(
      $("tree-container"),
      resp.collection,
      state.lockedKeys,
      onToggleLock,
      resp.metadata.vocab_labels || {},
    );
    $("tree-container").classList.toggle("compact-tree", !$("opt-show-details").checked);
    const currentFilter = $("tree-filter").value;
    if (currentFilter) window.TopicTreeView.filterTree($("tree-container"), currentFilter);
    renderRawJson();
  }

  function renderHttpError(status, body) {
    $("empty-state").hidden = true;
    $("error-panel").hidden = false;
    const err = body?.error || {};
    $("error-title").textContent = status ? t("error.http", { status }) : t("error.network");
    $("error-message").textContent = err.message || body?.detail || t("error.generic");
    $("error-code").textContent = err.code || "HTTP_ERROR";
    $("error-status").textContent = String(status || "–");
    $("error-trace").textContent = err.trace_id || "–";
    const details = $("error-details");
    if (err.details) {
      details.hidden = false;
      details.textContent = JSON.stringify(err.details, null, 2);
    } else {
      details.hidden = true;
    }
    setStatus("status.failed", { code: err.code || status });
  }

  function setLoading(active, startedAt) {
    $("btn-submit").disabled = active;
    $("btn-cancel").hidden = !active;
    $("loading-state").hidden = !active;
    if (state.timerId) clearInterval(state.timerId);
    if (active) {
      $("empty-state").hidden = true;
      $("error-panel").hidden = true;
      setStatus("status.running");
      state.timerId = setInterval(() => {
        $("loading-timer").textContent = `${fmtSec((performance.now() - startedAt) / 1000)} s`;
      }, 100);
    }
  }

  async function submitForm() {
    showFormError("");
    let payload;
    try {
      payload = buildPayload();
    } catch (err) {
      showFormError(err.message);
      return;
    }
    state.lastRequest = payload;
    state.controller = new AbortController();
    const startedAt = performance.now();
    setLoading(true, startedAt);

    const headers = { "Content-Type": "application/json" };
    const token = $("f-token").value.trim();
    if (token) headers.Authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    try {
      const res = await fetch("/v2/topic-tree", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        signal: state.controller.signal,
      });
      const elapsed = (performance.now() - startedAt) / 1000;
      let body = null;
      try { body = await res.json(); } catch { body = null; }
      if (!res.ok) {
        renderHttpError(res.status, body);
      } else {
        $("tree-filter").value = "";
        renderSuccess(body, elapsed);
      }
    } catch (err) {
      if (err.name === "AbortError") {
        setStatus("status.aborted");
      } else {
        renderHttpError(0, { error: { code: "NETWORK_ERROR", message: t("error.unreachable") } });
      }
    } finally {
      setLoading(false, startedAt);
      state.controller = null;
    }
  }

  function adoptForRefine() {
    if (!state.lastResponse) return;
    const current = {
      version: state.lastResponse.metadata.version,
      collection: state.lastResponse.collection,
      generation: state.lastResponse.metadata.generation,
    };
    $("f-mode").value = "refine";
    $("f-current-tree").value = JSON.stringify(current, null, 2);
    $("f-fb-locked").value = Array.from(state.lockedKeys).join(", ");
    $("acc-refine").open = true;
    syncModeLabels();
    $("f-fb-text").focus();
    setStatus("status.adopted", { version: current.version });
  }

  function switchLanguage(lang) {
    if (!i18n()) return;
    i18n().setLang(lang);
    for (const grp of document.querySelectorAll("optgroup[data-i18n-group]")) {
      grp.label = t(grp.dataset.i18nGroup);
    }
    updateShapeLimitsNote();
    syncModeLabels(false);
    renderDisciplineChips();
    if (state.lastResponse) {
      renderSuccess(state.lastResponse, state.lastClientSeconds);
    } else if (state.statusKey) {
      const vars = state.statusKey === "status.presetLoaded"
        ? { ...state.statusVars, action: $("btn-submit").textContent }
        : state.statusVars;
      setStatus(state.statusKey, vars);
    }
  }

  async function init() {
    $("tree-form").addEventListener("submit", (e) => { e.preventDefault(); submitForm(); });
    $("btn-cancel").addEventListener("click", () => state.controller?.abort());
    $("btn-retry").addEventListener("click", () => submitForm());
    $("btn-reset").addEventListener("click", resetForm);
    for (const btn of document.querySelectorAll(".lang-btn")) {
      btn.addEventListener("click", () => switchLanguage(btn.dataset.lang));
    }
    $("f-mode").addEventListener("change", () => syncModeLabels(true));
    $("f-use-case").addEventListener("change", () => syncModeLabels(true));
    $("f-discipline").addEventListener("change", (e) => {
      if (e.target.value) {
        addDiscipline(e.target.value);
        e.target.value = "";
      }
    });
    $("f-preset").addEventListener("change", (e) => {
      const preset = state.presets.find((p) => p.id === e.target.value);
      if (preset) applyPreset(preset);
      else resetForm();
    });
    $("opt-show-details").addEventListener("change", (e) => {
      $("tree-container").classList.toggle("compact-tree", !e.target.checked);
    });
    $("btn-expand-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), true));
    $("btn-collapse-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), false));
    $("tree-filter").addEventListener("input", (e) => window.TopicTreeView.filterTree($("tree-container"), e.target.value));
    $("btn-use-refine").addEventListener("click", adoptForRefine);

    $("btn-copy-json").addEventListener("click", async () => {
      if (!state.lastResponse) return;
      await navigator.clipboard.writeText(JSON.stringify(state.lastResponse, null, 2));
      setStatus("status.copied");
    });

    $("btn-download-json").addEventListener("click", () => {
      if (!state.lastResponse) return;
      const blob = new Blob([JSON.stringify(state.lastResponse, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `topic-tree-${state.lastResponse.metadata.version || "v2"}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    });

    $("btn-toggle-json").addEventListener("click", () => {
      const panel = $("raw-json-panel");
      panel.hidden = !panel.hidden;
      $("btn-toggle-json").setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden) renderRawJson();
    });

    for (const tab of document.querySelectorAll(".tab-btn")) {
      tab.addEventListener("click", () => {
        state.activeRawTab = tab.dataset.tab;
        for (const elTab of document.querySelectorAll(".tab-btn")) {
          const active = elTab === tab;
          elTab.classList.toggle("active", active);
          elTab.setAttribute("aria-selected", String(active));
        }
        renderRawJson();
      });
    }

    try {
      const res = await fetch("/ui/presets");
      const data = await res.json();
      $("service-version").textContent = `v${data.version}`;
      if (data.limits) {
        state.limits = data.limits;
        const dMax = data.limits.max_tree_depth;
        const wMax = data.limits.max_nodes_per_level;
        $("f-depth").max = String(dMax);
        $("f-main-min").max = String(wMax);
        $("f-main-max").max = String(wMax);
        $("f-child-min").max = String(wMax);
        $("f-child-max").max = String(wMax);
        updateShapeLimitsNote();
      }
      populateSelect($("f-discipline"), data.vocabs.discipline, "group.school");
      populateSelect($("f-discipline"), data.vocabs.hochschulfaechersystematik, "group.uni");
      populateSelect($("f-context"), data.vocabs.educationalContext);
      populateSelect($("f-role"), data.vocabs.intendedEndUserRole);
      state.presets = data.presets;

      const presetSelect = $("f-preset");
      const emptyGrid = $("empty-presets");
      for (const preset of state.presets) {
        const opt = document.createElement("option");
        opt.value = preset.id;
        opt.textContent = `[${preset.badge}] ${preset.title}`;
        presetSelect.appendChild(opt);

        const card = el("button", "empty-preset-card");
        card.type = "button";
        card.dataset.presetId = preset.id;
        card.appendChild(el("span", "preset-tag", preset.badge));
        card.appendChild(el("strong", "", preset.title));
        card.appendChild(el("span", "", preset.summary));
        card.addEventListener("click", () => applyPreset(preset));
        emptyGrid.appendChild(card);
      }
      if (i18n()) i18n().applyDom();
      syncModeLabels(false);
    } catch {
      showFormError(t("error.presetsLoad"));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
