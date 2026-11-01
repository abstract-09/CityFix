import { api, session } from '../services/api.js';
import { h, replace } from '../components/dom.js';
import { icon } from '../components/icons.js';
import { loginForm } from '../components/loginForm.js';
import { banner, categoryLabel, emptyState, loadingBlock, severityPill, statusBadge } from '../components/ui.js';
import { MSG_PROOF, formatHours, formatTimestamp, trackHash } from '../services/utils.js';

const NEXT = { Received: ['Received', 'In Progress'], 'In Progress': ['In Progress', 'Resolved'], Resolved: ['Resolved'] };

export async function render(container, _params, ctx) {
  const s = session.get();
  if (!s || !s.user || s.user.role !== 'officer') {
    replace(container, h('section', { class: 'page page--narrow' },
      h('h1', { class: 'page__title' }, 'Officer portal'),
      loginForm({ role: 'officer', title: 'Sign in', intro: 'For department officers. Your queue shows only reports routed to your department.', onSuccess: () => render(container, _params, ctx) })));
    return;
  }

  const bannerSlot = h('div');
  const tableSlot = h('div', { class: 'table-scroll' });
  const filter = h('select', { id: 'q-status', class: 'select', 'aria-label': 'Filter by status', onchange: load },
    h('option', { value: '' }, 'All statuses'), ...ctx.meta.statuses.map((x) => h('option', { value: x }, x)));
  const say = (kind, msg) => replace(bannerSlot, banner(kind, msg, { onDismiss: () => replace(bannerSlot, null) }));

  function row(t) {
    const select = h('select', { class: 'select select--small', 'aria-label': `Status for ${t.ticket_id}`, disabled: t.status === 'Resolved', onchange: sync },
      ...NEXT[t.status].map((x) => h('option', { value: x }, x)));
    select.value = t.status;
    const proof = h('input', { type: 'file', accept: 'image/png,image/jpeg,.jpg,.jpeg,.png', class: 'input', id: `proof-${t.ticket_id}` });
    const note = h('input', { type: 'text', class: 'input', maxlength: 300, placeholder: 'Optional note shown on the public ticket', 'aria-label': 'Note' });
    const proofError = h('p', { class: 'field__error', role: 'alert', hidden: true }, MSG_PROOF);
    const infoText = h('input', { type: 'text', class: 'input', maxlength: 300, placeholder: 'What do you need from the reporter?', 'aria-label': 'Question for the reporter' });
    const resolvePanel = h('div', { class: 'row-extra__panel', hidden: true },
      h('label', { class: 'field__label', for: proof.id }, 'Photo of the finished repair (required)'), proof, proofError, note);
    const infoPanel = h('div', { class: 'row-extra__panel', hidden: true }, infoText,
      h('button', { type: 'button', class: 'btn btn--secondary btn--small', onclick: sendInfo }, 'Post question to ticket'));
    const extra = h('tr', { class: 'row-extra' }, h('td', { colspan: 7 }, resolvePanel, infoPanel));
    const act = h('button', { type: 'button', class: 'btn btn--primary btn--small', onclick: apply }, 'Update status');
    if (t.status === 'Resolved') act.disabled = true;

    function sync() { resolvePanel.hidden = select.value !== 'Resolved'; proofError.hidden = true; }

    async function apply() {
      if (select.value === t.status) { say('info', `${t.ticket_id} is already ${t.status}.`); return; }
      act.disabled = true;
      try {
        if (select.value === 'In Progress') await api.startWork(t.ticket_id, note.value.trim() || undefined);
        else {
          if (!proof.files[0]) { proofError.hidden = false; proof.focus(); act.disabled = false; return; }
          const fd = new FormData();
          fd.append('resolution_proof', proof.files[0], proof.files[0].name);
          if (note.value.trim()) fd.append('note', note.value.trim());
          await api.resolve(t.ticket_id, fd);
        }
        say('success', `${t.ticket_id} is now ${select.value}.`);
        await load({ keepBanner: true });
      } catch (err) {
        if (err.status === 401) { render(container, _params, ctx); return; }
        say('error', err.message);
        act.disabled = false;
      }
    }

    async function sendInfo() {
      try {
        await api.requestInfo(t.ticket_id, infoText.value);
        say('success', `Question posted on ${t.ticket_id}. The reporter will see it when they track the ticket.`);
        infoText.value = ''; infoPanel.hidden = true;
      } catch (err) { say('error', err.message); }
    }

    const main = h('tr', {},
      h('th', { scope: 'row' }, h('a', { href: trackHash(t.ticket_id) }, t.ticket_id)),
      h('td', categoryLabel(t.category, 16)),
      h('td', severityPill(t.severity)),
      h('td', t.report_count > 1 ? `${t.report_count} reports` : '1 report'),
      h('td', h('span', formatTimestamp(t.reported_at)), h('br'), h('span', { class: 'muted' }, `${t.status === 'Resolved' ? 'Took' : 'Open for'} ${formatHours(t.elapsed_hours)}`)),
      h('td', t.status === 'Resolved' ? statusBadge(t.status) : select),
      h('td', { class: 'actions' }, act,
        t.status !== 'Resolved' ? h('button', { type: 'button', class: 'btn btn--quiet btn--small', onclick: () => { infoPanel.hidden = !infoPanel.hidden; } }, 'Ask reporter') : null));
    return [main, extra];
  }

  async function load({ keepBanner = false } = {}) {
    if (!keepBanner) replace(bannerSlot, null);
    replace(tableSlot, loadingBlock('Loading your queue…'));
    try {
      const data = await api.queue(filter.value);
      title.textContent = data.department;
      replace(tableSlot, data.tickets.length ? h('table', { class: 'table table--queue' },
        h('caption', { class: 'sr-only' }, 'Reports assigned to your department'),
        h('thead', h('tr', ['Ticket', 'Issue', 'Severity', 'Reports', 'Submitted', 'Status', 'Action'].map((c) => h('th', { scope: 'col' }, c)))),
        h('tbody', ...data.tickets.flatMap(row))) : emptyState('Nothing in this queue', 'New reports for your department will appear here.'));
    } catch (err) {
      if (err.status === 401) { render(container, _params, ctx); return; }
      replace(tableSlot, null);
      say('error', err.message);
    }
  }

  const title = h('span', '');
  replace(container, h('section', { class: 'page' },
    h('div', { class: 'toolbar' },
      h('h1', { class: 'page__title' }, 'Queue: ', title),
      h('div', { class: 'toolbar__actions' }, filter,
        h('button', { type: 'button', class: 'btn btn--secondary', onclick: () => { session.clear(); render(container, _params, ctx); } }, icon('logout', { size: 16 }), 'Sign out'))),
    h('p', { class: 'lead' }, 'Most urgent first. Closing a report needs a photo of the finished work.'),
    bannerSlot, tableSlot));
  await load();
}
