import { h, s } from './dom.js';
import { icon } from './icons.js';
import { MARKER_HEX, collectPoints, fitBounds, linesOf, makeProjection, polygonsOf } from '../services/geo.js';

const W = 900;
const H = 560;
const RADIUS = { Critical: 11, Medium: 9, Low: 7 };
const HEAT_RADIUS = { Critical: 46, Medium: 38, Low: 30 };

// Dependency-free SVG map: ward polygons, highway lines, severity markers, optional heat glow, pan and zoom.
export function createTicketMap({ onSelect }) {
  let tickets = [];
  let boundaries = null;
  let heat = true;
  let selectedId = null;
  let proj = null;
  const view = { x: 0, y: 0, w: W, h: H };

  const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'map-svg', role: 'group', 'aria-label': 'Map of reported civic issues. Each marker opens a report.' });
  const gradient = (name) => s('radialGradient', { id: `heat-${name}` },
    s('stop', { offset: '0%', 'stop-color': MARKER_HEX[name], 'stop-opacity': '0.55' }),
    s('stop', { offset: '100%', 'stop-color': MARKER_HEX[name], 'stop-opacity': '0' }));
  const gBounds = s('g');
  const gHeat = s('g');
  const gMarkers = s('g');
  svg.append(s('defs', gradient('red'), gradient('orange'), gradient('yellow')),
    s('rect', { x: -6000, y: -6000, width: 12000, height: 12000, class: 'map-bg' }), gBounds, gHeat, gMarkers);

  const path = (pts, close) => pts.map((p, i) => {
    const [x, y] = proj.project(p[0], p[1]);
    return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join('') + (close ? 'Z' : '');

  function drawBoundaries() {
    gBounds.replaceChildren();
    const k = view.w / W;
    for (const f of (boundaries && boundaries.features) || []) {
      const type = f.properties && f.properties.type;
      if (type === 'ward') {
        for (const rings of polygonsOf(f.geometry)) {
          gBounds.append(s('path', { d: rings.map((r) => path(r, true)).join(''), class: 'map-ward', 'fill-rule': 'evenodd' }));
          const xs = rings[0].map((p) => proj.project(p[0], p[1]));
          const cx = (Math.min(...xs.map((p) => p[0])) + Math.max(...xs.map((p) => p[0]))) / 2;
          const cy = (Math.min(...xs.map((p) => p[1])) + Math.max(...xs.map((p) => p[1]))) / 2;
          if (f.properties.name) gBounds.append(s('text', { x: cx, y: cy, class: 'map-label', 'font-size': 14 * k, 'text-anchor': 'middle' }, f.properties.name));
        }
      } else {
        for (const line of linesOf(f.geometry)) {
          gBounds.append(s('path', { d: path(line, false), class: type === 'national_highway' ? 'map-nh' : 'map-sh', 'stroke-width': (type === 'national_highway' ? 5 : 3.5) * k }));
        }
      }
    }
  }

  function drawHeat() {
    gHeat.replaceChildren();
    if (!heat) return;
    for (const t of tickets) {
      if (t.status === 'Resolved') continue;
      const [x, y] = proj.project(t.longitude, t.latitude);
      const r = HEAT_RADIUS[t.severity] * (1 + Math.min(t.report_count - 1, 4) * 0.15);
      gHeat.append(s('circle', { cx: x, cy: y, r, fill: `url(#heat-${t.marker})`, 'pointer-events': 'none' }));
    }
  }

  function select(ticket) {
    selectedId = ticket.ticket_id;
    drawMarkers();
    if (onSelect) onSelect(ticket);
  }

  function drawMarkers() {
    gMarkers.replaceChildren();
    const k = view.w / W; // keeps markers a constant on-screen size while zooming
    for (const t of tickets) {
      const [x, y] = proj.project(t.longitude, t.latitude);
      const resolved = t.status === 'Resolved';
      const r = (resolved ? 8 : RADIUS[t.severity]) * k;
      const label = `${t.ticket_id}, ${t.category}, ${t.status}${resolved ? '' : `, ${t.severity} severity`}`;
      const g = s('g', {
        class: `map-marker${t.ticket_id === selectedId ? ' is-selected' : ''}`, tabindex: '0', role: 'button',
        'aria-label': label, transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})`,
      },
      s('title', label),
      s('circle', { r: r + 4 * k, class: 'map-marker__ring' }),
      s('circle', { r, fill: MARKER_HEX[t.marker], stroke: '#fff', 'stroke-width': 2 * k }),
      resolved ? s('path', { d: `M${-0.45 * r} 0L${-0.1 * r} ${0.38 * r}L${0.5 * r} ${-0.38 * r}`, stroke: '#fff', 'stroke-width': 1.8 * k, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }) : null);
      g.addEventListener('click', () => { if (!moved) select(t); });
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(t); } });
      gMarkers.append(g);
    }
  }

  function applyView(full = true) {
    svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
    svg.classList.toggle('is-zoomed', view.w < W * 0.999);
    if (full) { drawBoundaries(); drawMarkers(); }
  }

  function resetView() {
    Object.assign(view, { x: 0, y: 0, w: W, h: H });
    applyView();
  }

  function zoomAt(factor, fx = 0.5, fy = 0.5) {
    const w = Math.min(W * 1.6, Math.max(W / 40, view.w * factor));
    const hh = (H * w) / W;
    view.x += fx * (view.w - w);
    view.y += fy * (view.h - hh);
    view.w = w;
    view.h = hh;
    applyView();
  }

  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 0.8 : 1.25, (e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height);
  }, { passive: false });

  let drag = null;
  let moved = false;
  svg.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, id: e.pointerId, captured: false }; moved = false; });
  svg.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    if (!moved && Math.abs(dx) + Math.abs(dy) > 4) moved = true;
    if (!moved) return;
    if (!drag.captured) { svg.setPointerCapture(drag.id); drag.captured = true; } // capture only once dragging, so plain clicks still reach markers
    const rect = svg.getBoundingClientRect();
    view.x = drag.vx - (dx * view.w) / rect.width;
    view.y = drag.vy - (dy * view.h) / rect.height;
    applyView(false);
    svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  });
  const endDrag = () => { drag = null; setTimeout(() => { moved = false; }, 0); };
  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);

  const emptyNote = h('p', { class: 'map-empty', hidden: true }, 'No reports match these filters.');
  const controls = h('div', { class: 'map-controls' },
    h('button', { type: 'button', class: 'btn btn--secondary btn--icon', 'aria-label': 'Zoom in', onclick: () => zoomAt(0.7) }, icon('plus')),
    h('button', { type: 'button', class: 'btn btn--secondary btn--icon', 'aria-label': 'Zoom out', onclick: () => zoomAt(1.4) }, icon('minus')),
    h('button', { type: 'button', class: 'btn btn--secondary btn--icon', 'aria-label': 'Reset map view', onclick: resetView }, icon('refresh')));

  return {
    el: h('div', { class: 'map-wrap' }, svg, controls, emptyNote),
    update(data) {
      tickets = data.tickets || [];
      boundaries = data.boundaries || null;
      if (!tickets.some((t) => t.ticket_id === selectedId)) selectedId = null;
      proj = makeProjection(fitBounds(collectPoints(tickets, boundaries)), W, H);
      emptyNote.hidden = tickets.length > 0;
      drawHeat();
      resetView();
    },
    setHeat(on) { heat = on; if (proj) drawHeat(); },
  };
}
