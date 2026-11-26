// Minimal fake DOM for node tests of the test UI's DOM scripts (tree.js, changes.js): no browser needed.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const STATIC = path.join(__dirname, "..", "..", "app", "ui", "static");

function makeDocument() {
  const doc = { activeElement: null };
  function matches(node, sel) {
    const [tag, ...classes] = sel.split(".");
    if (tag && node.tagName !== tag.toUpperCase()) return false;
    const own = String(node.className || "").split(/\s+/);
    return classes.every((c) => own.includes(c));
  }
  function element(tag) {
    const node = {
      tagName: String(tag).toUpperCase(), className: "", textContent: "", value: "", hidden: false, dataset: {},
      children: [], attributes: {}, listeners: {}, parent: null,
      setAttribute(k, v) { this.attributes[k] = String(v); },
      getAttribute(k) { return this.attributes[k] ?? null; },
      addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
      dispatch(type) { for (const fn of this.listeners[type] || []) fn({ target: this }); },
      appendChild(child) { child.parent = this; this.children.push(child); return child; },
      append(...items) { for (const x of items) if (typeof x === "object") this.appendChild(x); },
      replaceChildren(...items) { this.children = []; this.append(...items); },
      focus() { doc.activeElement = this; },
      scrollIntoView() {},
      querySelectorAll(sel) {
        const out = [];
        const walk = (n) => { for (const c of n.children) { if (matches(c, sel)) out.push(c); walk(c); } };
        walk(this);
        return out;
      },
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
      contains(other) { for (let n = other; n; n = n.parent) if (n === this) return true; return false; },
    };
    return node;
  }
  doc.createElement = element;
  doc.documentElement = element("html");
  doc.getElementById = () => null;
  doc.querySelectorAll = () => [];
  return doc;
}

/** Loads the given static scripts into a fresh context; returns its `window` and `document`. */
function load(files) {
  const document = makeDocument();
  function Option(text, value) {
    const o = document.createElement("option");
    o.textContent = text;
    o.value = value;
    return o;
  }
  const ctx = { window: {}, document, Option, console };
  vm.createContext(ctx);
  for (const file of files) {
    const code = fs.readFileSync(path.join(STATIC, file), "utf8").replace('typeof module === "object" && module.exports', "false");
    vm.runInContext(code, ctx);
  }
  return { W: ctx.window, document };
}

module.exports = { load };
