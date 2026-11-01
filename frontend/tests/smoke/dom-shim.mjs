// Just enough DOM for CityFix's pages to run in Node. Not a browser: it checks wiring and logic, not layout.
export class Node {
  constructor() { this.childNodes = []; this.parentNode = null; }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(''); }
  set textContent(v) { this.replaceChildren(String(v)); }
  append(...items) {
    for (const i of items) {
      const n = i instanceof Node ? i : new Text(String(i));
      if (n.parentNode) n.parentNode.removeChild(n);
      n.parentNode = this;
      this.childNodes.push(n);
    }
  }
  removeChild(n) { const i = this.childNodes.indexOf(n); if (i >= 0) this.childNodes.splice(i, 1); n.parentNode = null; }
  replaceChildren(...items) { this.childNodes.forEach((c) => { c.parentNode = null; }); this.childNodes = []; this.append(...items); }
  replaceWith(n) {
    const p = this.parentNode; if (!p) return;
    if (n.parentNode) n.parentNode.removeChild(n);
    p.childNodes[p.childNodes.indexOf(this)] = n; n.parentNode = p; this.parentNode = null;
  }
  *walk() { for (const c of this.childNodes) { yield c; if (c.walk) yield* c.walk(); } }
}
export class Text extends Node {
  constructor(t) { super(); this.data = t; }
  get textContent() { return this.data; }
  set textContent(v) { this.data = v; }
}
export class Element extends Node {
  constructor(tag) {
    super(); this.localName = tag; this.tagName = tag.toUpperCase(); this.attrs = {}; this.listeners = {};
    this.dataset = {}; this.value = ''; this.hidden = false; this.disabled = false; this.checked = false; this.files = [];
    this._cls = new Set();
    const self = this;
    this.classList = {
      add: (...c) => c.forEach((x) => self._cls.add(x)), remove: (...c) => c.forEach((x) => self._cls.delete(x)),
      contains: (c) => self._cls.has(c), toggle: (c, f) => { (f === undefined ? !self._cls.has(c) : f) ? self._cls.add(c) : self._cls.delete(c); },
    };
  }
  get className() { return [...this._cls].join(' '); }
  set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
    if (k === 'class') this.className = v;
    if (k === 'hidden') this.hidden = true;
    if (k === 'disabled') this.disabled = true;
    if (k === 'checked') this.checked = true;
  }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  async dispatch(type, extra = {}) {
    for (const f of this.listeners[type] || []) await f({ type, target: this, preventDefault() {}, stopPropagation() {}, ...extra });
  }
  focus() {} select() {} scrollIntoView() {} setPointerCapture() {}
  getBoundingClientRect() { return { left: 0, top: 0, width: 900, height: 560 }; }
  matches(sel) {
    if (sel.startsWith('.')) return this._cls.has(sel.slice(1));
    return this.localName === sel;
  }
  querySelector(sel) { for (const n of this.walk()) if (n instanceof Element && n.matches(sel)) return n; return null; }
}

export function install(apiBase) {
  const appEl = new Element('main');
  const store = new Map();
  const windowListeners = {};
  const g = globalThis;
  g.Node = Node;
  g.document = {
    createElement: (t) => new Element(t), createElementNS: (_n, t) => new Element(t),
    createTextNode: (t) => new Text(String(t)),
    getElementById: () => appEl, querySelectorAll: () => [],
  };
  g.window = {
    CITYFIX_CONFIG: { apiBase }, scrollTo() {}, confirm: () => true, matchMedia: () => ({ matches: false }),
    addEventListener: (t, f) => { (windowListeners[t] ||= []).push(f); },
  };
  g.location = { hash: '' };
  g.history = { replaceState() {} };
  g.sessionStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
  Object.defineProperty(g, 'navigator', { configurable: true, value: {
    geolocation: { getCurrentPosition: (ok) => ok({ coords: { latitude: 25.5562, longitude: 84.8512, accuracy: 12 } }) },
    clipboard: { writeText: async () => {} },
  } });
  return { appEl, fireWindow: async (t) => { for (const f of windowListeners[t] || []) await f({ type: t }); } };
}

export const all = (root, pred) => [...root.walk()].filter((n) => n instanceof Element && pred(n));
export const byClass = (root, c) => all(root, (n) => n._cls.has(c));
export const byId = (root, id) => all(root, (n) => n.attrs.id === id)[0];
export const buttonWith = (root, text) => all(root, (n) => n.localName === 'button' && n.textContent.includes(text))[0];
export const visibleText = (root) => {
  const parts = [];
  (function visit(n) {
    if (n instanceof Text) { parts.push(n.data); return; }
    if (n.hidden) return;
    n.childNodes.forEach(visit);
  })(root);
  return parts.join('');
};
