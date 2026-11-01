import { api } from '../services/api.js';
import { h, replace } from '../components/dom.js';
import { createTicketMap } from '../components/map.js';
import { banner, categoryLabel, field, loadingBlock, severityPill, statusBadge } from '../components/ui.js';
import { formatHours, formatTimestamp, trackHash } from '../services/utils.js';

const STATUS_FILTERS = [['', 'All statuses'], ['open', 'Open (not resolved)'], ['Received', 'Received'], ['In Progress', 'In Progress'], ['Resolved', 'Resolved']];

export async function render(container, _params, ctx) {
  const category = h('select', { id: 'f-category', class: 'select', onchange: load },
    h('option', { value: '' }, 'All categories'), ...ctx.meta.categories.map((c) => h('option', { value: c }, c)));
  const status = h('select', { id: 'f-status', class: 'select', onchange: load },
    ...STATUS_FILTERS.map(([v, l]) => h('option', { value: v }, l)));
  const heatToggle = h('input', { id: 'heat', type: 'checkbox', checked: true, onchange: (e) => map.setHeat(e.target.checked) });

  const detail = h('div', { class: 'map-detail', 'aria-live': 'polite' }, h('p', { class: 'muted' }, 'Select a marker to see the report.'));
  const map = createTicketMap({ onSelect: showDetail });
  const ledger = h('div', { class: 'ledger' });
  const deptTable = h('div', { class: 'table-scroll' });
  const bannerSlot = h('div');
  const updated = h('p', { class: 'muted' });

  function showDetail(t) {
    replace(detail,
      h('div', { class: 'map-detail__head' }, h('strong', t.ticket_id), statusBadge(t.status)),
      h('div', { class: 'map-detail__tags' }, categoryLabel(t.category, 16), severityPill(t.severity)),
      h('p', t.description || ''),
      h('p', { class: 'muted' }, `${t.assigned_department}. Reported ${formatTimestamp(t.reported_at)}.`),
      h('a', { class: 'btn btn--secondary btn--small', href: trackHash(t.ticket_id) }, 'Open ticket'));
  }

  function renderMetrics(m) {
    replace(ledger,
      h('div', { class: 'ledger__cell' }, h('p', { class: 'ledger__value' }, String(m.open_tickets)), h('p', 'open reports')),
      h('div', { class: 'ledger__cell' }, h('p', { class: 'ledger__value' }, String(m.resolved_tickets)), h('p', 'resolved')),
      h('div', { class: 'ledger__cell' }, h('p', { class: 'ledger__value' }, formatHours(m.avg_resolution_hours)), h('p', 'average time to resolve')));
    replace(deptTable, h('table', { class: 'table' },
      h('caption', { class: 'sr-only' }, 'Response times by department'),
      h('thead', h('tr', ['Department', 'Open', 'Resolved', 'Avg. time to resolve', 'Avg. age of open reports'].map((c) => h('th', { scope: 'col' }, c)))),
      h('tbody', ...m.departments.map((d) => h('tr',
        h('th', { scope: 'row' }, d.department), h('td', String(d.open)), h('td', String(d.resolved)),
        h('td', formatHours(d.avg_resolution_hours)), h('td', formatHours(d.avg_open_age_hours)))))));
  }

  async function load({ quiet = false } = {}) {
    if (!quiet) replace(bannerSlot, loadingBlock('Loading reports…'));
    try {
      const data = await api.dashboard({ category: category.value, status: status.value });
      replace(bannerSlot, null);
      map.update(data);
      renderMetrics(data.metrics);
      updated.textContent = `Updated ${formatTimestamp(data.generated_at)}`;
      if (!quiet) replace(detail, h('p', { class: 'muted' }, 'Select a marker to see the report.'));
    } catch (err) {
      if (!quiet) replace(bannerSlot, banner('error', err.message, { actionLabel: 'Try again', onAction: () => load() }));
    }
  }

  const legend = h('ul', { class: 'legend', 'aria-label': 'Marker colours' },
    ...[['red', 'Critical'], ['orange', 'Medium'], ['yellow', 'Low'], ['green', 'Resolved']].map(([c, l]) =>
      h('li', h('span', { class: `legend__swatch legend__swatch--${c}`, 'aria-hidden': 'true' }), l)));

  replace(container, h('section', { class: 'page' },
    h('h1', { class: 'page__title' }, 'Public dashboard'),
    h('p', { class: 'lead' }, 'Every report, where it is, and how quickly each department responds.'),
    h('div', { class: 'filters' },
      field({ id: 'f-category', label: 'Issue type', control: category }),
      field({ id: 'f-status', label: 'Status', control: status }),
      h('label', { class: 'check', for: 'heat' }, heatToggle, 'Show heat')),
    bannerSlot, ledger,
    h('div', { class: 'dash-grid' },
      h('div', map.el, legend),
      h('aside', { class: 'card card--flat' }, h('h2', { class: 'card__title' }, 'Selected report'), detail)),
    h('h2', { class: 'section-title' }, 'Department response times'),
    deptTable, updated));

  await load();
  const timer = setInterval(() => load({ quiet: true }), 60000);
  ctx.onLeave(() => clearInterval(timer));
}
