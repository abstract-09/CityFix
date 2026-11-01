import { h } from './dom.js';
import { CATEGORY_ICONS, icon } from './icons.js';

export function banner(kind, message, { onDismiss, actionLabel, onAction } = {}) {
  const role = kind === 'error' ? 'alert' : 'status';
  return h('div', { class: `banner banner--${kind}`, role },
    icon(kind === 'error' ? 'alert' : kind === 'success' ? 'check' : 'pin', { size: 20 }),
    h('p', { class: 'banner__text' }, message),
    actionLabel ? h('button', { type: 'button', class: 'btn btn--quiet btn--small', onclick: onAction }, actionLabel) : null,
    onDismiss ? h('button', { type: 'button', class: 'btn btn--quiet btn--small', 'aria-label': 'Dismiss message', onclick: onDismiss }, icon('x', { size: 16 })) : null);
}

export function spinner(label = 'Loading') {
  return h('span', { class: 'spinner', role: 'status', 'aria-label': label });
}

export function loadingBlock(text = 'Loading…') {
  return h('div', { class: 'loading' }, spinner(text), h('span', text));
}

const STATUS_CLASS = { Received: 'received', 'In Progress': 'progress', Resolved: 'resolved' };

export function statusBadge(status) {
  return h('span', { class: `badge badge--${STATUS_CLASS[status] || 'received'}` }, status);
}

export function severityPill(severity) {
  return h('span', { class: `pill pill--${String(severity).toLowerCase()}` }, h('span', { class: 'pill__dot', 'aria-hidden': 'true' }), `${severity} severity`);
}

export function categoryLabel(category, size = 18) {
  return h('span', { class: 'category' }, icon(CATEGORY_ICONS[category] || 'dots', { size }), category);
}

export function field({ id, label, hint, control, error }) {
  return h('div', { class: 'field' },
    h('label', { class: 'field__label', for: id }, label),
    control,
    hint ? h('p', { class: 'field__hint', id: `${id}-hint` }, hint) : null,
    h('p', { class: 'field__error', id: `${id}-error`, role: 'alert', hidden: !error }, error || ''));
}

export function emptyState(title, body) {
  return h('div', { class: 'empty' }, h('p', { class: 'empty__title' }, title), body ? h('p', { class: 'muted' }, body) : null);
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}
