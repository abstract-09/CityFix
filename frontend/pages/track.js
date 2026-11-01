import { api } from '../services/api.js';
import { h, replace } from '../components/dom.js';
import { icon } from '../components/icons.js';
import { renderTicket } from '../components/ticketCard.js';
import { banner, loadingBlock } from '../components/ui.js';
import { normaliseTicketId } from '../services/utils.js';

export async function render(container, params, ctx) {
  const input = h('input', { id: 'ticket-code', class: 'input input--code', type: 'text', placeholder: 'CIV-2026-0001', autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', 'aria-label': 'Ticket code' });
  const bannerSlot = h('div');
  const result = h('div', { class: 'slot' });
  let current = null;
  let timer = null;

  async function lookup(rawId, { silent = false } = {}) {
    const id = normaliseTicketId(rawId);
    if (!id) { input.focus(); return; }
    if (!silent) replace(result, loadingBlock('Looking up your ticket…'));
    try {
      const ticket = await api.getTicket(id);
      current = id;
      replace(bannerSlot, null);
      replace(result, renderTicket(ticket));
      input.value = id;
      history.replaceState(null, '', `#/track/${encodeURIComponent(id)}`);
    } catch (err) {
      if (silent) return; // keep showing the last good result during background refreshes
      current = null;
      replace(result, null);
      if (err.status === 404) input.value = '';
      replace(bannerSlot, banner('error', err.message));
      input.focus();
    }
  }

  const form = h('form', { class: 'lookup', onsubmit: (e) => { e.preventDefault(); lookup(input.value); } },
    input, h('button', { class: 'btn btn--primary', type: 'submit' }, icon('search', { size: 18 }), 'Track ticket'));

  let flash = null;
  try { flash = JSON.parse(sessionStorage.getItem('cityfix.flash')); sessionStorage.removeItem('cityfix.flash'); } catch { /* ignore */ }

  replace(container, h('section', { class: 'page page--narrow' },
    h('h1', { class: 'page__title' }, 'Track a ticket'),
    h('p', { class: 'lead' }, 'Enter the code you received when you reported the issue.'),
    form, flash ? banner(flash.kind || 'info', flash.message) : null, bannerSlot, result));

  const initial = params.id || new URLSearchParams(params.query || '').get('id');
  if (initial) await lookup(initial);
  else input.focus();

  // Refresh quietly every 30 seconds so status changes appear without a reload.
  timer = setInterval(() => { if (current) lookup(current, { silent: true }); }, 30000);
  ctx.onLeave(() => clearInterval(timer));
}
