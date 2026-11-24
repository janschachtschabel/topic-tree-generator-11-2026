/* Pure DOM rendering for the Themenbaum viewer (zero innerHTML with untrusted text). */
(() => {
  "use strict";

  const t = (key, vars) => (window.TopicTreeI18n ? window.TopicTreeI18n.t(key, vars) : key);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function normTitle(title) {
    return (title || "").trim().toLowerCase();
  }

  function countTitles(nodes) {
    const counts = new Map();
    function visit(list) {
      for (const n of list || []) {
        const key = normTitle(n.title);
        if (key) counts.set(key, (counts.get(key) || 0) + 1);
        visit(n.subcollections || []);
      }
    }
    visit(nodes);
    return counts;
  }

  function formatOrigin(origin) {
    if (!origin) return "";
    if (origin.type === "document") {
      const parts = [`${t("tree.origin.doc")} ${origin.id || ""}`.trim()];
      if (origin.section) parts.push(`${t("tree.origin.section")} „${origin.section}“`);
      if (origin.page != null) parts.push(`${t("tree.origin.page")} ${origin.page}`);
      return parts.join(" · ");
    }
    if (origin.type === "folder") return `${t("tree.origin.folder")}: ${origin.path || ""}`;
    if (origin.type === "cluster") return t("tree.origin.cluster");
    if (origin.type === "feedback") return t("tree.origin.feedback");
    return "";
  }

  function computeTreeStats(nodes) {
    const byLevel = {};
    const titleCounts = countTitles(nodes);
    let total = 0;
    let withDesc = 0;
    let totalContents = 0;
    let duplicates = 0;

    function visit(list, depth) {
      for (const n of list || []) {
        total += 1;
        byLevel[depth] = (byLevel[depth] || 0) + 1;
        if ((titleCounts.get(normTitle(n.title)) || 0) > 1) duplicates += 1;
        const desc = (n.properties && n.properties["cm:description"] && n.properties["cm:description"][0]) || "";
        if (desc.trim()) withDesc += 1;
        totalContents += (n.contents || []).length;
        visit(n.subcollections || [], depth + 1);
      }
    }
    visit(nodes, 1);
    return {
      total,
      byLevel,
      descPct: total ? Math.round((withDesc / total) * 100) : 0,
      totalContents,
      duplicates,
    };
  }

  function renderNode(node, depth, lockedSet, onToggleLock, vocabLabels, titleCounts) {
    const children = node.subcollections || [];
    const hasChildren = children.length > 0;
    const isDuplicate = (titleCounts.get(normTitle(node.title)) || 0) > 1;
    const item = el("div", `tree-node${isDuplicate ? " is-duplicate" : ""}`);
    item.setAttribute("role", "treeitem");
    item.setAttribute("aria-expanded", hasChildren ? "true" : "false");
    item.dataset.key = node.key || "";

    const head = el("div", "node-head");
    const toggle = el("button", `node-toggle${hasChildren ? "" : " leaf"}`, "▾");
    toggle.type = "button";
    toggle.setAttribute("aria-label", hasChildren ? t("tree.toggleAria", { title: node.title }) : "");
    head.appendChild(toggle);

    head.appendChild(el("span", "level-tag", `E${depth}`));
    const titleEl = el("span", `node-title${hasChildren ? " expandable" : ""}`, node.title);
    head.appendChild(titleEl);
    if (hasChildren) {
      head.appendChild(el("span", "node-count", `(${children.length})`));
    }
    if ((node.contents || []).length) {
      const count = node.contents.length;
      const unit = count === 1 ? t("tree.contentSingular") : t("tree.contentPlural");
      head.appendChild(el("span", "node-count", `· ${count} ${unit}`));
    }
    if (node.shorttitle && node.shorttitle !== node.title) {
      head.appendChild(el("span", "node-short", node.shorttitle));
    }
    if (node.key) head.appendChild(el("span", "node-key", node.key));
    if (isDuplicate) {
      const dupBadge = el("span", "status-badge duplicate", t("tree.badge.duplicate"));
      dupBadge.title = t("tree.badge.duplicateTitle");
      head.appendChild(dupBadge);
    }
    if (node.status) {
      const statusText = t(`tree.status.${node.status}`) || node.status;
      head.appendChild(el("span", `status-badge ${node.status}`, statusText));
    }

    if (node.key) {
      const isLocked = lockedSet.has(node.key);
      const lockBtn = el("button", "lock-btn", isLocked ? t("tree.locked") : t("tree.lock"));
      lockBtn.type = "button";
      lockBtn.setAttribute("aria-pressed", String(isLocked));
      lockBtn.title = t("tree.lockTitle");
      lockBtn.addEventListener("click", () => {
        const nowLocked = onToggleLock(node.key);
        lockBtn.setAttribute("aria-pressed", String(nowLocked));
        lockBtn.textContent = nowLocked ? t("tree.locked") : t("tree.lock");
      });
      head.appendChild(lockBtn);
    }
    item.appendChild(head);

    const body = el("div", "node-body");
    const originText = formatOrigin(node.origin);
    if (originText) body.appendChild(el("div", "node-origin", originText));

    const props = node.properties || {};
    const metaUris = [
      ...(props["ccm:taxonid"] || []),
      ...(props["ccm:educationalcontext"] || []),
      ...(props["ccm:educationalintendedenduserrole"] || []),
    ];
    if (metaUris.length) {
      const mRow = el("div", "pill-row");
      for (const uri of metaUris) {
        const lbl = (vocabLabels && vocabLabels[uri]) || uri.split("/").pop();
        const pill = el("span", "meta-pill", lbl);
        pill.title = uri;
        mRow.appendChild(pill);
      }
      body.appendChild(mRow);
    }

    const desc = (props["cm:description"] && props["cm:description"][0]) || "";
    body.appendChild(el("p", desc ? "node-desc" : "node-desc missing", desc || t("tree.noDesc")));

    const keywords = props["cclom:general_keyword"] || [];
    if (keywords.length) {
      const kwRow = el("div", "pill-row");
      for (const kw of keywords) kwRow.appendChild(el("span", "kw-pill", kw));
      body.appendChild(kwRow);
    }

    const contents = node.contents || [];
    if (contents.length) {
      const cRow = el("div", "pill-row");
      for (const c of contents) {
        const conf = c.confidence != null ? ` · ${c.confidence.toFixed(2)}` : "";
        const nid = c.nodeId ? ` (${c.nodeId})` : "";
        cRow.appendChild(el("span", "content-pill", `${t("tree.contentPrefix")} ${c.id}${nid}${conf}`));
      }
      body.appendChild(cRow);
    }
    item.appendChild(body);

    const childBox = el("div", "node-children");
    if (hasChildren) {
      childBox.setAttribute("role", "group");
      for (const child of children) {
        childBox.appendChild(renderNode(child, depth + 1, lockedSet, onToggleLock, vocabLabels, titleCounts));
      }
      const toggleBranch = () => {
        const open = !childBox.hidden;
        childBox.hidden = open;
        toggle.textContent = open ? "▸" : "▾";
        item.setAttribute("aria-expanded", String(!open));
      };
      toggle.addEventListener("click", toggleBranch);
      titleEl.addEventListener("click", toggleBranch);
    } else {
      childBox.hidden = true;
    }
    item.appendChild(childBox);

    const searchHaystack = [node.title, node.shorttitle, node.key, desc, ...keywords].join(" ").toLowerCase();
    item.dataset.search = searchHaystack;
    return item;
  }

  function renderTree(container, nodes, lockedSet, onToggleLock, vocabLabels) {
    container.replaceChildren();
    const titleCounts = countTitles(nodes);
    for (const root of nodes || []) {
      container.appendChild(renderNode(root, 1, lockedSet, onToggleLock, vocabLabels || {}, titleCounts));
    }
  }

  function setAllExpanded(container, expand) {
    for (const item of container.querySelectorAll(".tree-node")) {
      const toggle = item.querySelector(":scope > .node-head > .node-toggle");
      const childBox = item.querySelector(":scope > .node-children");
      if (!childBox || !toggle || toggle.classList.contains("leaf")) continue;
      childBox.hidden = !expand;
      toggle.textContent = expand ? "▾" : "▸";
      item.setAttribute("aria-expanded", String(expand));
    }
  }

  function filterTree(container, rawQuery) {
    const q = (rawQuery || "").trim().toLowerCase();
    function matchNode(item) {
      const childItems = Array.from(item.querySelectorAll(":scope > .node-children > .tree-node"));
      const childMatched = childItems.map(matchNode).some(Boolean);
      const selfMatched = !q || (item.dataset.search || "").includes(q);
      const visible = selfMatched || childMatched;
      item.classList.toggle("hidden-by-filter", !visible);
      if (q && childMatched) {
        const childBox = item.querySelector(":scope > .node-children");
        const toggle = item.querySelector(":scope > .node-head > .node-toggle");
        if (childBox) childBox.hidden = false;
        if (toggle && !toggle.classList.contains("leaf")) toggle.textContent = "▾";
      }
      return visible;
    }
    for (const root of container.querySelectorAll(":scope > .tree-node")) matchNode(root);
  }

  window.TopicTreeView = { computeTreeStats, renderTree, setAllExpanded, filterTree };
})();
