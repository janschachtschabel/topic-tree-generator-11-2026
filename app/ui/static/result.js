/* Result view of the test UI: metrics card (quality, cost, time) and foldable diagnostics. Pure DOM, no innerHTML. */
(() => {
  "use strict";

  const I = () => window.TopicTreeI18n;
  const t = (key, vars) => (I() ? I().t(key, vars) : key);
  const num = (n) => (I() ? I().formatNumber(n) : String(n));
  const sec = (s) => (I() ? I().formatSeconds(s) : Number(s).toFixed(1));

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function pair(label, value, tone) {
    const wrap = el("span", "metric-pair");
    wrap.appendChild(el("span", "metric-k", label));
    wrap.appendChild(el("span", tone ? `metric-v ${tone}` : "metric-v", value));
    return wrap;
  }

  function row(label, items) {
    const line = el("div", "metric-row");
    line.appendChild(el("span", "metric-group-label", label));
    const box = el("div", "metric-items");
    box.append(...items);
    line.appendChild(box);
    return line;
  }

  function renderMetrics(target, resp, clientSeconds) {
    const stats = window.TopicTreeView.computeTreeStats(resp.collection);
    const gen = resp.metadata.generation || {};
    const usage = gen.usage || {};
    const prompt = usage.prompt_tokens || 0;
    const cached = usage.cached_tokens || 0;
    const output = usage.completion_tokens || 0;
    const cachePct = prompt ? Math.round((cached / prompt) * 100) : 0;
    const levels = Object.entries(stats.byLevel).map(([lvl, cnt]) => `E${lvl}: ${cnt}`).join(" · ");
    const warnings = (resp.warnings || []).length;
    const unassigned = (resp.unassigned || []).length;
    const quality = [
      pair(t("metric.nodes"), `${num(stats.total)}${levels ? ` (${levels})` : ""}`),
      pair(t("metric.described"), `${stats.descPct} %`, stats.descPct < 100 ? "warn" : ""),
      pair(t("metric.warnings"), num(warnings), warnings ? "warn" : "ok"),
      pair(t("metric.assigned"), num(stats.totalContents)),
      pair(t("metric.unassigned"), num(unassigned)),
    ];
    if (stats.duplicates) quality.push(pair(t("metric.duplicates"), num(stats.duplicates), "warn"));
    if ((resp.questions || []).length) quality.push(pair(t("metric.questions"), num(resp.questions.length), "warn"));
    const duration = usage.duration_ms != null ? usage.duration_ms / 1000 : clientSeconds;
    target.replaceChildren(
      row(t("metric.group.quality"), quality),
      row(t("metric.group.cost"), [
        pair(t("metric.tokens"), num(prompt + output)),
        pair(t("metric.cached"), `${num(cached)} (${cachePct} %)`),
        pair(t("metric.output"), num(output)),
        pair(t("metric.model"), gen.model || "–"),
      ]),
      row(t("metric.group.time"), [
        pair(t("metric.duration"), `${sec(duration)} s`),
        pair(t("metric.llmCalls"), num(usage.llm_calls ?? 0)),
        pair(t("metric.failed"), num(usage.failed_calls ?? 0), usage.failed_calls ? "warn" : ""),
        pair(t("metric.version"), resp.metadata.version + (resp.metadata.based_on ? ` ← ${resp.metadata.based_on}` : "")),
      ]),
    );
  }

  function fold(titleKey, lines, tone, open) {
    const box = el("details", `card fold diag ${tone || ""}`);
    box.open = Boolean(open);
    const summary = el("summary");
    summary.appendChild(el("span", "", t(titleKey, { n: lines.length })));
    box.appendChild(summary);
    const list = el("ul", "diag-list");
    for (const line of lines) list.appendChild(el("li", "", line));
    box.appendChild(list);
    return box;
  }

  function changeLine(c) {
    const target = c.title || c.to || (c.keys || []).join(" + ") || "";
    return `${t(`change.op.${c.op}`)} ${c.key || ""}${target ? ` → ${target}` : ""} · ${t(`change.from.${c.from}`)}`;
  }

  function renderDiagnostics(target, resp) {
    const blocks = [];
    const warnings = resp.warnings || [];
    if (warnings.length) {
      const lines = warnings.map((w) => {
        const where = [w.key, w.step].filter(Boolean).join(" / ");
        return `[${w.code}] ${w.message}${where ? ` (${where})` : ""}`;
      });
      blocks.push(fold("diag.warnings", lines, "warn", true));
    }
    if ((resp.questions || []).length) {
      blocks.push(fold("diag.questions", resp.questions.map((q) => q.text), "info", true));
    }
    if ((resp.changes || []).length) blocks.push(fold("diag.changes", resp.changes.map(changeLine), "", true));
    if ((resp.unassigned || []).length) {
      const lines = resp.unassigned.map(
        (u) => `${u.id}${u.nodeId ? ` (${u.nodeId})` : ""}: ${t(`reason.${u.reason}`)}`,
      );
      blocks.push(fold("diag.unassigned", lines, "", false));
    }
    target.replaceChildren(...blocks);
    target.hidden = blocks.length === 0;
  }

  window.TopicTreeResult = { renderMetrics, renderDiagnostics };
})();
