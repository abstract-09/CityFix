import { api, session } from '../services/api.js';
import { h, replace } from '../components/dom.js';
import { icon } from '../components/icons.js';
import { loginForm } from '../components/loginForm.js';
import { banner, field, loadingBlock, statusBadge } from '../components/ui.js';
import { trackHash } from '../services/utils.js';

export async function render(container, _params, ctx) {
  const s = session.get();
  if (!s || !s.user || s.user.role !== 'admin') {
    replace(container, h('section', { class: 'page page--narrow' },
      h('h1', { class: 'page__title' }, 'Admin console'),
      loginForm({ role: 'admin', title: 'Sign in', intro: 'For system administrators.', onSuccess: () => render(container, _params, ctx) })));
    return;
  }

  const bannerSlot = h('div');
  const panel = h('div', { class: 'slot' });
  const say = (kind, msg) => replace(bannerSlot, banner(kind, msg, { onDismiss: () => replace(bannerSlot, null) }));
  const guard = (err) => { if (err.status === 401) { render(container, _params, ctx); return true; } say('error', err.message); return false; };

  const tabs = [['tickets', 'Reports and AI'], ['routing', 'Routing'], ['system', 'System and demo data']];
  const tabBar = h('div', { class: 'tabs', role: 'tablist' });
  function drawTabs(active) {
    replace(tabBar, ...tabs.map(([id, label]) => h('button', {
      type: 'button', role: 'tab', class: `tab${id === active ? ' is-active' : ''}`, 'aria-selected': id === active ? 'true' : 'false',
      onclick: () => show(id),
    }, label)));
  }

  async function show(id) {
    drawTabs(id);
    replace(bannerSlot, null);
    replace(panel, loadingBlock());
    try { await ({ tickets: ticketsPanel, routing: routingPanel, system: systemPanel })[id](); } catch (e) { replace(panel, null); guard(e); }
  }

  async function ticketsPanel() {
    const { tickets } = await api.adminTickets();
    replace(panel, h('div', { class: 'table-scroll' }, h('table', { class: 'table' },
      h('caption', { class: 'sr-only' }, 'All reports with AI output and reporter contact'),
      h('thead', h('tr', ['Ticket', 'Status', 'Final category', 'AI result', 'Confidence', 'Contact', 'Department'].map((c) => h('th', { scope: 'col' }, c)))),
      h('tbody', ...tickets.map((t) => h('tr',
        h('th', { scope: 'row' }, h('a', { href: trackHash(t.ticket_id) }, t.ticket_id)),
        h('td', statusBadge(t.status)),
        h('td', `${t.category} (${t.severity})`),
        h('td', h('details', h('summary', t.ai.mode ? `${t.ai.category || '–'} / ${t.ai.severity || '–'} via ${t.ai.mode}` : 'No AI result'),
          h('p', { class: 'muted' }, t.ai.description || 'No description'))),
        h('td', t.ai.confidence == null ? '–' : t.ai.confidence.toFixed(2)),
        h('td', t.reporter_contact || h('span', { class: 'muted' }, 'None given')),
        h('td', t.assigned_department)))))));
  }

  async function routingPanel() {
    const [geo, { departments }] = await Promise.all([api.adminBoundaries(), api.adminDepartments()]);
    const area = h('textarea', { id: 'geojson', class: 'textarea textarea--code', rows: 16, spellcheck: 'false', 'aria-describedby': 'geojson-hint' });
    area.value = JSON.stringify(geo, null, 2);
    const save = h('button', { type: 'button', class: 'btn btn--primary', onclick: async () => {
      let parsed;
      try { parsed = JSON.parse(area.value); } catch (e) { say('error', `That is not valid JSON: ${e.message}`); return; }
      try { const r = await api.saveBoundaries(parsed); say('success', `Saved ${r.features} boundary features. New reports use them straight away.`); } catch (e) { guard(e); }
    } }, 'Validate and save boundaries');
    const rows = departments.map((d) => {
      const input = h('input', { id: `dept-${d.name}`, class: 'input', type: 'email', placeholder: 'dispatch@example.org' });
      input.value = d.email || '';
      return h('div', { class: 'dept-row' }, field({ id: `dept-${d.name}`, label: d.name, control: input }),
        h('button', { type: 'button', class: 'btn btn--secondary', onclick: async () => {
          try { await api.saveDepartment(d.name, input.value.trim()); say('success', `Saved the contact address for ${d.name}.`); } catch (e) { guard(e); }
        } }, 'Save'));
    });
    replace(panel,
      h('div', { class: 'card' }, h('h2', { class: 'card__title' }, 'GIS boundaries'),
        h('p', { class: 'muted', id: 'geojson-hint' }, 'A GeoJSON FeatureCollection. Each feature needs properties.type of ward, state_highway or national_highway. Reports within 50 m of a highway go to its authority; reports inside a ward go to the Municipal Corporation.'),
        area, save),
      h('div', { class: 'card' }, h('h2', { class: 'card__title' }, 'Department contact addresses'),
        h('p', { class: 'muted' }, 'Stored for officers to use. CityFix never emails or dispatches anyone on its own.'), ...rows));
  }

  async function systemPanel() {
    const health = await api.health();
    const reset = h('input', { id: 'seed-reset', type: 'checkbox' });
    const extra = h('input', { id: 'seed-extra', class: 'input', type: 'number', min: 0, max: 200, value: 0 });
    const go = h('button', { type: 'button', class: 'btn btn--primary', onclick: async () => {
      if (reset.checked && !window.confirm('This deletes every report and restores the three sample reports. Continue?')) return;
      try {
        const r = await api.seed({ reset: reset.checked, extra: Number(extra.value) || 0 });
        say('success', `Done. ${r.tickets_added} reports added.`);
      } catch (e) { guard(e); }
    } }, 'Generate demo data');
    replace(panel,
      h('div', { class: 'card' }, h('h2', { class: 'card__title' }, 'System health'),
        h('dl', { class: 'facts' },
          h('dt', 'Database'), h('dd', health.database),
          h('dt', 'AI service'), h('dd', health.ai_service === 'stub_mode' ? 'Stub mode (no real AI calls)' : health.ai_service),
          h('dt', 'Routing'), h('dd', 'Local GeoJSON boundaries'),
          h('dt', 'Checked'), h('dd', health.time))),
      h('div', { class: 'card' }, h('h2', { class: 'card__title' }, 'Demo data'),
        h('p', { class: 'muted' }, 'Add random reports around Bihta to see the heat map and response-time tables fill up.'),
        field({ id: 'seed-extra', label: 'Extra demo reports (0 to 200)', control: extra }),
        h('label', { class: 'check', for: 'seed-reset' }, reset, 'Reset to the three sample reports first'), go));
  }

  replace(container, h('section', { class: 'page' },
    h('div', { class: 'toolbar' }, h('h1', { class: 'page__title' }, 'Admin console'),
      h('button', { type: 'button', class: 'btn btn--secondary', onclick: () => { session.clear(); render(container, _params, ctx); } }, icon('logout', { size: 16 }), 'Sign out')),
    tabBar, bannerSlot, panel));
  await show('tickets');
}
