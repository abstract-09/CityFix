import { api } from './services/api.js';
import { h, replace } from './components/dom.js';
import { banner, loadingBlock } from './components/ui.js';

const app = document.getElementById('app');
const ROUTES = [
  { re: /^\/?$/, nav: 'report', load: () => import('./pages/report.js') },
  { re: /^\/track(?:\/([^/?]+))?$/, nav: 'track', load: () => import('./pages/track.js') },
  { re: /^\/dashboard$/, nav: 'dashboard', load: () => import('./pages/dashboard.js') },
  { re: /^\/officer$/, nav: 'officer', load: () => import('./pages/officer.js') },
  { re: /^\/admin$/, nav: 'admin', load: () => import('./pages/admin.js') },
];

let meta = null;
let leaveHandlers = [];
let routeId = 0;

function setNav(active) {
  document.querySelectorAll('[data-nav]').forEach((a) => {
    if (a.dataset.nav === active) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

async function ensureMeta() {
  if (meta) return meta;
  meta = await api.meta();
  return meta;
}

function failure(err) {
  return h('section', { class: 'page page--narrow' },
    banner('error', err.message || 'Something went wrong', { actionLabel: 'Try again', onAction: route }));
}

async function route() {
  const id = ++routeId;
  leaveHandlers.forEach((fn) => { try { fn(); } catch { /* ignore */ } });
  leaveHandlers = [];

  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, query = ''] = raw.split('?');
  const match = ROUTES.map((r) => ({ r, m: r.re.exec(path) })).find((x) => x.m);
  setNav(match ? match.r.nav : '');
  replace(app, loadingBlock());

  if (!match) {
    replace(app, h('section', { class: 'page page--narrow' }, h('h1', { class: 'page__title' }, 'Page not found'),
      h('p', 'That page does not exist. ', h('a', { href: '#/' }, 'Go to the report form'), '.')));
    return;
  }
  try {
    const [mod] = await Promise.all([match.r.load(), ensureMeta()]);
    if (id !== routeId) return; // a newer navigation took over
    replace(app);
    const params = { id: match.m[1] ? decodeURIComponent(match.m[1]) : null, query };
    await mod.render(app, params, { meta, onLeave: (fn) => leaveHandlers.push(fn) });
    if (id === routeId) { window.scrollTo(0, 0); app.focus({ preventScroll: true }); }
  } catch (err) {
    if (id === routeId) replace(app, failure(err));
  }
}

window.addEventListener('hashchange', route);
route();
