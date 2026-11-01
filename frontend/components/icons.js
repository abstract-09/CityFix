import { s } from './dom.js';

const P = (d) => ['path', { d }];
const C = (cx, cy, r) => ['circle', { cx, cy, r }];

// Simple outline icons on a 24x24 grid.
const ICONS = {
  pin: [P('M12 21s-6-5.2-6-10a6 6 0 1 1 12 0c0 4.8-6 10-6 10z'), C(12, 11, 2)],
  upload: [P('M12 16V4'), P('M7 9l5-5 5 5'), P('M4 20h16')],
  check: [P('M5 12.5l4.5 4.5L19 7')],
  clock: [C(12, 12, 9), P('M12 7v5l3 2')],
  alert: [P('M12 3l10 18H2z'), P('M12 10v5'), P('M12 18h.01')],
  search: [C(11, 11, 7), P('M20 20l-4-4')],
  road: [P('M8 3L5 21'), P('M16 3l3 18'), P('M12 4v3'), P('M12 10v4'), P('M12 17v3')],
  droplet: [P('M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z')],
  bulb: [P('M9 18h6'), P('M10 21h4'), P('M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z')],
  trash: [P('M4 7h16'), P('M9 7V4h6v3'), P('M6 7l1 13h10l1-13'), P('M10 11v6'), P('M14 11v6')],
  waves: [P('M3 9c2-2 4-2 6 0s4 2 6 0 4-2 6 0'), P('M3 15c2-2 4-2 6 0s4 2 6 0 4-2 6 0')],
  dots: [C(6, 12, 1.4), C(12, 12, 1.4), C(18, 12, 1.4)],
  mic: [P('M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z'), P('M5 11a7 7 0 0 0 14 0'), P('M12 18v3')],
  image: [['rect', { x: 3, y: 4, width: 18, height: 16, rx: 2 }], C(9, 10, 1.5), P('M4 18l5-5 4 4 3-3 4 4')],
  camera: [P('M4 8h3l2-3h6l2 3h3v11H4z'), C(12, 13, 3.5)],
  plus: [P('M12 5v14'), P('M5 12h14')],
  minus: [P('M5 12h14')],
  copy: [['rect', { x: 9, y: 9, width: 11, height: 11, rx: 2 }], P('M5 15V6a2 2 0 0 1 2-2h9')],
  refresh: [P('M4 12a8 8 0 0 1 14-5l2 2'), P('M20 4v5h-5'), P('M20 12a8 8 0 0 1-14 5l-2-2'), P('M4 20v-5h5')],
  logout: [P('M10 4H5v16h5'), P('M15 8l4 4-4 4'), P('M19 12H9')],
  x: [P('M6 6l12 12'), P('M18 6L6 18')],
  external: [P('M14 4h6v6'), P('M20 4l-9 9'), P('M18 14v5H5V6h5')],
};

export const CATEGORY_ICONS = {
  'Road Damage': 'road',
  'Water Leak': 'droplet',
  'Streetlight Defect': 'bulb',
  'Waste Management': 'trash',
  'Drainage Overflow': 'waves',
  Other: 'dots',
};

export function icon(name, { size = 20, label = null, className = '' } = {}) {
  const svg = s('svg', {
    viewBox: '0 0 24 24', width: size, height: size, fill: 'none', stroke: 'currentColor',
    'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    class: `icon ${className}`.trim(),
    role: label ? 'img' : null, 'aria-label': label, 'aria-hidden': label ? null : 'true', focusable: 'false',
  });
  for (const [tag, attrs] of ICONS[name] || ICONS.dots) svg.append(s(tag, attrs));
  return svg;
}
