import { h } from './dom.js';
import { icon } from './icons.js';
import { categoryLabel, severityPill, statusBadge } from './ui.js';
import { formatCoord, formatHours, formatTimestamp, osmUrl, safeUrl } from '../services/utils.js';

function mediaBlock(url, type, alt) {
  const src = safeUrl(url);
  const fallback = () => h('div', { class: 'media-fallback' }, icon(type === 'audio' ? 'mic' : 'image', { size: 28 }),
    h('p', type === 'audio' ? 'Voice note unavailable' : 'Photo preview unavailable'));
  if (!src) return fallback();
  if (type === 'audio') return h('audio', { controls: true, src, class: 'media-audio', 'aria-label': alt });
  const img = h('img', { src, alt, class: 'media-img', loading: 'lazy' });
  img.addEventListener('error', () => img.replaceWith(fallback()));
  return img;
}

function eventTitle(ev) {
  if (ev.kind === 'created') return 'Report received';
  if (ev.kind === 'info_request') return 'Information requested';
  if (ev.kind === 'duplicate_report') return 'Another report merged';
  return ev.status;
}

function fact(label, value) {
  return [h('dt', label), h('dd', value)];
}

export function renderTicket(t) {
  const hasHistory = Array.isArray(t.history) && t.history.length > 0;
  const resolved = t.status === 'Resolved';
  return h('article', { class: 'card ticket' },
    h('header', { class: 'ticket__head' },
      h('div', h('h2', { class: 'ticket__code' }, t.ticket_id), categoryLabel(t.category)),
      statusBadge(t.status)),
    h('div', { class: 'ticket__body' },
      h('div', { class: 'ticket__media' }, mediaBlock(t.media_url, t.media_type, `Reported issue ${t.ticket_id}`)),
      h('dl', { class: 'facts' },
        ...fact('Department', t.assigned_department),
        t.jurisdiction ? fact('Area', t.jurisdiction) : null,
        ...fact('Priority', severityPill(t.severity)),
        ...fact('Submitted', formatTimestamp(t.reported_at)),
        ...fact('Location', h('span', `${formatCoord(t.latitude)}, ${formatCoord(t.longitude)} `,
          h('a', { href: osmUrl(t.latitude, t.longitude), target: '_blank', rel: 'noopener noreferrer', class: 'link-inline' }, 'Open map', icon('external', { size: 14 })))),
        ...fact(resolved ? 'Time to resolve' : 'Open for', formatHours(t.elapsed_hours)),
        t.report_count > 1 ? fact('Reports merged', `${t.report_count} people reported this`) : null)),
    t.description ? h('p', { class: 'ticket__desc' }, t.description) : null,
    resolved && t.resolution_proof_url ? h('section', { class: 'ticket__proof' },
      h('h3', 'Photo from the department'),
      mediaBlock(t.resolution_proof_url, 'image', `Completed repair for ${t.ticket_id}`)) : null,
    hasHistory ? h('section', { class: 'ticket__history' },
      h('h3', 'History'),
      h('ol', { class: 'timeline' }, ...t.history.map((ev) => h('li', { class: `timeline__item timeline__item--${ev.kind}` },
        h('span', { class: 'timeline__dot', 'aria-hidden': 'true' }),
        h('div', h('p', { class: 'timeline__title' }, eventTitle(ev)),
          ev.message ? h('p', { class: 'timeline__msg' }, ev.message) : null,
          h('p', { class: 'timeline__meta muted' }, `${formatTimestamp(ev.at)} by ${ev.actor === 'system' ? 'CityFix' : ev.actor}`)))))) : null);
}
