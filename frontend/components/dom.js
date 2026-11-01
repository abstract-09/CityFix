// Tiny DOM builder. Strings are always inserted as text nodes, never as HTML,
// so report text, descriptions and officer notes cannot inject markup (XSS).
const SVG_NS = 'http://www.w3.org/2000/svg';

function apply(el, attrs) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false || key === 'value') continue;
    if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else el.setAttribute(key, value === true ? '' : String(value));
  }
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

function normalise(attrs, children) {
  if (attrs instanceof Node || typeof attrs === 'string' || typeof attrs === 'number' || Array.isArray(attrs)) {
    return [{}, [attrs, ...children]];
  }
  return [attrs || {}, children];
}

export function h(tag, attrs, ...children) {
  [attrs, children] = normalise(attrs, children);
  const el = document.createElement(tag);
  apply(el, attrs);
  append(el, children);
  if (attrs.value !== undefined && attrs.value !== null) el.value = attrs.value; // after <option>s exist
  return el;
}

export function s(tag, attrs, ...children) {
  [attrs, children] = normalise(attrs, children);
  const el = document.createElementNS(SVG_NS, tag);
  apply(el, attrs);
  append(el, children);
  return el;
}

export function replace(container, ...nodes) {
  container.replaceChildren(...nodes.flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false));
}
