/* Controller for the optional Topic-Tree v2 test UI. Zero external dependencies, zero token persistence. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const numFmt = new Intl.NumberFormat("de-DE");
  const state = {
    presets: [],
    activePresetId: null,
    multiDisciplineUris: null,
    vocabIndex: {},
    lastRequest: null,
    lastResponse: null,
    activeRawTab: "response",
    lockedKeys: new Set(),
    controller: null,
    timerId: null,
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
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
      throw new Error(`Ungültiges JSON in „${fieldName}“: ${err.message}`);
    }
  }

  function populateSelect(selectEl, options, groupLabel) {
    const target = groupLabel ? document.createElement("optgroup") : selectEl;
    if (groupLabel) {
      target.label = groupLabel;
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

  function applyPreset(preset) {
    state.activePresetId = preset.id;
    for (const btn of document.querySelectorAll(".preset-btn")) {
      btn.classList.toggle("active", btn.dataset.presetId === preset.id);
    }
    const p = preset.payload;
    $("f-mode").value = p.mode || "create";
    $("f-use-case").value = p.use_case || "topic";
    $("f-topic").value = p.topic || "";

    const frame = p.frame || {};
    const discUris = frame.discipline_uri || [];
    if (discUris.length > 1) {
      state.multiDisciplineUris = discUris;
      setSelectValue($("f-discipline"), "");
      const names = discUris.map((u) => state.vocabIndex[u] || u.split("/").pop()).join(", ");
      $("multi-discipline-note").textContent = `Mehrfach-Fächer aus Szenario aktiv: ${names}`;
      $("multi-discipline-note").hidden = false;
    } else {
      state.multiDisciplineUris = null;
      $("multi-discipline-note").hidden = true;
      setSelectValue($("f-discipline"), discUris[0] || "");
    }
    setSelectValue($("f-context"), (frame.educational_context_uri || [])[0] || "");
    setSelectValue($("f-role"), (frame.intended_end_user_role_uri || [])[0] || "");

    const shape = p.shape || {};
    $("f-depth").value = shape.depth ?? 3;
    $("f-main-min").value = shape.main_topics?.min ?? 6;
    $("f-main-max").value = shape.main_topics?.max ?? 12;
    $("f-child-min").value = shape.children?.min ?? 3;
    $("f-child-max").value = shape.children?.max ?? 8;
    const extras = shape.extra_topics || [];
    $("f-extra-general").checked = extras.includes("general");
    $("f-extra-methodology").checked = extras.includes("methodology");

    const hints = p.hints || {};
    $("f-hint-context").value = hints.context || "";
    $("f-hint-order").value = hints.order || "";
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

    $("f-items").value = p.items ? JSON.stringify(p.items, null, 2) : "";
    $("f-folders").value = p.folders ? JSON.stringify(p.folders, null, 2) : "";
    $("f-current-tree").value = p.current_tree ? JSON.stringify(p.current_tree, null, 2) : "";

    const fb = p.feedback || {};
    $("f-fb-text").value = fb.text || "";
    $("f-fb-locked").value = (fb.locked || []).join(", ");
    $("f-fb-changes").value = fb.changes?.length ? JSON.stringify(fb.changes, null, 2) : "";
    state.lockedKeys = new Set(fb.locked || []);

    $("acc-items").open = Boolean(p.items && p.items.length);
    $("acc-folders").open = Boolean(p.folders && p.folders.length);
    $("acc-refine").open = p.mode === "refine";
    $("acc-hints").open = Boolean(hints.context || hints.order || (hints.include || []).length || (hints.exclude || []).length);
    $("acc-options").open = Boolean(opts.auto_metadata || opts.improve || opts.assign_only);
    syncModeLabels();
    showFormError("");
    $("status-message").textContent = `Musterszenario „${preset.title}“ geladen – bereit zum Ausführen.`;
  }

  function syncModeLabels() {
    const isRefine = $("f-mode").value === "refine";
    $("btn-submit").textContent = isRefine ? "Entwurf weiterentwickeln" : "Themenbaum erzeugen";
    $("topic-req").textContent = $("f-use-case").value === "topic" && !isRefine ? "(Pflicht)" : "(optional)";
  }

  function buildPayload() {
    const mode = $("f-mode").value;
    const useCase = $("f-use-case").value;
    const payload = {
      mode,
      use_case: useCase,
      frame: {
        discipline_uri: $("f-discipline").value ? [$("f-discipline").value] : (state.multiDisciplineUris || []),
        educational_context_uri: $("f-context").value ? [$("f-context").value] : [],
        intended_end_user_role_uri: $("f-role").value ? [$("f-role").value] : [],
      },
      shape: {
        depth: Number($("f-depth").value) || 3,
        main_topics: { min: Number($("f-main-min").value) || 6, max: Number($("f-main-max").value) || 12 },
        children: { min: Number($("f-child-min").value) || 3, max: Number($("f-child-max").value) || 8 },
        extra_topics: [
          ...($("f-extra-general").checked ? ["general"] : []),
          ...($("f-extra-methodology").checked ? ["methodology"] : []),
        ],
      },
      hints: {
        description_length: Number($("f-desc-len").value) || 60,
        language: "de",
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

    const topic = $("f-topic").value.trim();
    if (topic) payload.topic = topic;
    if ($("f-hint-context").value.trim()) payload.hints.context = $("f-hint-context").value.trim();
    if ($("f-hint-order").value.trim()) payload.hints.order = $("f-hint-order").value.trim();
    const inc = splitCsv($("f-hint-include").value);
    const exc = splitCsv($("f-hint-exclude").value);
    if (inc.length) payload.hints.include = inc;
    if (exc.length) payload.hints.exclude = exc;

    const items = parseOptionalJson($("f-items").value, "items");
    if (items && items.length) payload.items = items;
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

    const mTree = $("metrics-tree");
    mTree.replaceChildren(
      metricPair("Knoten", `${numFmt.format(stats.total)}${levelsText ? ` (${levelsText})` : ""}`),
      metricPair("Beschrieben", `${stats.descPct} %`),
      metricPair("Zugeordnet", numFmt.format(stats.totalContents)),
      metricPair("Version", resp.metadata.version + (resp.metadata.based_on ? ` ← ${resp.metadata.based_on}` : "")),
      metricPair("Warnungen", String((resp.warnings || []).length), (resp.warnings || []).length ? "warn" : "ok"),
      metricPair("Rückfragen", String((resp.questions || []).length)),
    );

    const serverSec = usage.duration_ms != null ? (usage.duration_ms / 1000).toFixed(1) : clientSeconds.toFixed(1);
    const mTime = $("metrics-time");
    mTime.replaceChildren(
      metricPair("Dauer", `${serverSec} s`),
      metricPair("LLM-Aufrufe", String(usage.llm_calls ?? 0)),
      metricPair("Fehlgeschlagen", String(usage.failed_calls ?? 0), (usage.failed_calls || 0) ? "warn" : "ok"),
      metricPair("Modell/Route", gen.model || "–"),
    );

    const mTok = $("metrics-tokens");
    mTok.replaceChildren(
      metricPair("Gesamt", numFmt.format(totalTokens)),
      metricPair("Input ungecacht", numFmt.format(uncachedTokens)),
      metricPair("Input Cache", `${numFmt.format(cachedTokens)} (${cachePct} %)`, cachePct >= 40 ? "ok" : ""),
      metricPair("Output", numFmt.format(completionTokens)),
    );
  }

  function renderDiagnostics(resp) {
    const area = $("diagnostics-area");
    area.replaceChildren();
    const blocks = [];

    if ((resp.warnings || []).length) {
      const card = el("div", "diag-card warn");
      card.appendChild(el("h3", "", `Warnungen (${resp.warnings.length})`));
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
      card.appendChild(el("h3", "", `Rückfragen (${resp.questions.length})`));
      const ul = el("ul", "diag-list");
      for (const q of resp.questions) ul.appendChild(el("li", "", q.text));
      card.appendChild(ul);
      blocks.push(card);
    }

    if ((resp.changes || []).length) {
      const card = el("div", "diag-card");
      card.appendChild(el("h3", "", `Umgesetzte Änderungen (${resp.changes.length})`));
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
      card.appendChild(el("h3", "", `Nicht zugeordnet (${resp.unassigned.length})`));
      const ul = el("ul", "diag-list");
      for (const u of resp.unassigned) {
        ul.appendChild(el("li", "", `${u.id}${u.nodeId ? ` (${u.nodeId})` : ""} – Grund: ${u.reason}`));
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
    $("empty-state").hidden = true;
    $("error-panel").hidden = true;
    $("result-area").hidden = false;
    $("result-actions").hidden = false;

    const gen = resp.metadata.generation || {};
    const usage = gen.usage || {};
    const sec = usage.duration_ms != null ? (usage.duration_ms / 1000).toFixed(1) : clientSeconds.toFixed(1);
    $("status-message").textContent = `Fertig: ${gen.use_case} (${gen.mode}) · ${gen.model || "LLM"} · ${sec} s`;

    renderMetrics(resp, clientSeconds);
    renderDiagnostics(resp);

    $("tree-title").textContent = resp.metadata.title || "Themenbaum";
    $("tree-description").textContent = resp.metadata.description || "";
    const st = gen.structure;
    $("tree-structure").textContent = st
      ? `Ordnungsprinzip (${st.source}): ${st.order}${st.levels?.length ? ` · Ebenen: ${st.levels.join(" → ")}` : ""}`
      : "";

    window.TopicTreeView.renderTree(
      $("tree-container"),
      resp.collection,
      state.lockedKeys,
      onToggleLock,
      resp.metadata.vocab_labels || {},
    );
    $("tree-filter").value = "";
    renderRawJson();
  }

  function renderHttpError(status, body) {
    $("empty-state").hidden = true;
    $("error-panel").hidden = false;
    const err = body?.error || {};
    $("error-title").textContent = status ? `Fehler (HTTP ${status})` : "Netzwerkfehler";
    $("error-message").textContent = err.message || body?.detail || "Die Anfrage konnte nicht verarbeitet werden.";
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
    $("status-message").textContent = `Fehlgeschlagen: ${err.code || status}`;
  }

  function setLoading(active, startedAt) {
    $("btn-submit").disabled = active;
    $("btn-cancel").hidden = !active;
    $("loading-state").hidden = !active;
    if (state.timerId) clearInterval(state.timerId);
    if (active) {
      $("empty-state").hidden = true;
      $("error-panel").hidden = true;
      $("status-message").textContent = "Anfrage an /v2/topic-tree läuft …";
      state.timerId = setInterval(() => {
        const s = ((performance.now() - startedAt) / 1000).toFixed(1).replace(".", ",");
        $("loading-timer").textContent = `${s} s`;
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
        renderSuccess(body, elapsed);
      }
    } catch (err) {
      if (err.name === "AbortError") {
        $("status-message").textContent = "Anfrage abgebrochen.";
      } else {
        renderHttpError(0, { error: { code: "NETWORK_ERROR", message: "Dienst nicht erreichbar." } });
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
    $("status-message").textContent = `Antwort ${current.version} als current_tree übernommen – Rückmeldung eingeben und ausführen.`;
  }

  async function init() {
    $("tree-form").addEventListener("submit", (e) => { e.preventDefault(); submitForm(); });
    $("btn-cancel").addEventListener("click", () => state.controller?.abort());
    $("btn-retry").addEventListener("click", () => submitForm());
    $("f-mode").addEventListener("change", syncModeLabels);
    $("f-use-case").addEventListener("change", syncModeLabels);
    $("f-discipline").addEventListener("change", () => {
      state.multiDisciplineUris = null;
      $("multi-discipline-note").hidden = true;
    });
    $("btn-expand-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), true));
    $("btn-collapse-all").addEventListener("click", () => window.TopicTreeView.setAllExpanded($("tree-container"), false));
    $("tree-filter").addEventListener("input", (e) => window.TopicTreeView.filterTree($("tree-container"), e.target.value));
    $("btn-use-refine").addEventListener("click", adoptForRefine);

    $("btn-copy-json").addEventListener("click", async () => {
      if (!state.lastResponse) return;
      await navigator.clipboard.writeText(JSON.stringify(state.lastResponse, null, 2));
      $("status-message").textContent = "Antwort-JSON in die Zwischenablage kopiert.";
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
        for (const t of document.querySelectorAll(".tab-btn")) {
          const active = t === tab;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", String(active));
        }
        renderRawJson();
      });
    }

    try {
      const res = await fetch("/ui/presets");
      const data = await res.json();
      $("service-version").textContent = `v${data.version}`;
      populateSelect($("f-discipline"), data.vocabs.discipline, "Schulfächer (discipline)");
      populateSelect($("f-discipline"), data.vocabs.hochschulfaechersystematik, "Hochschulfächer (hochschulfaechersystematik)");
      populateSelect($("f-context"), data.vocabs.educationalContext);
      populateSelect($("f-role"), data.vocabs.intendedEndUserRole);
      state.presets = data.presets;

      const list = $("preset-list");
      const emptyGrid = $("empty-presets");
      for (const preset of state.presets) {
        const btn = el("button", "preset-btn");
        btn.type = "button";
        btn.dataset.presetId = preset.id;
        btn.title = preset.summary;
        btn.appendChild(el("span", "preset-tag", preset.badge));
        btn.appendChild(document.createTextNode(preset.title));
        btn.addEventListener("click", () => applyPreset(preset));
        list.appendChild(btn);

        const card = el("button", "empty-preset-card");
        card.type = "button";
        card.appendChild(el("span", "preset-tag", preset.badge));
        card.appendChild(el("strong", "", preset.title));
        card.appendChild(el("span", "", preset.summary));
        card.addEventListener("click", () => applyPreset(preset));
        emptyGrid.appendChild(card);
      }
      if (state.presets.length) applyPreset(state.presets[0]);
    } catch {
      showFormError("Musterszenarien konnten nicht geladen werden.");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
