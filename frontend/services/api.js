// Thin client for the CityFix JSON API. Secrets never live here: the backend holds every API key.
const BASE = ((window.CITYFIX_CONFIG && window.CITYFIX_CONFIG.apiBase) || '') + '/api/v1';
const SESSION_KEY = 'cityfix.session';
const NETWORK_MESSAGE = "Can't reach the CityFix server. Check your connection and try again";

export class ApiError extends Error {
  constructor(status, message, body = null) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export const session = {
  get() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)) || null; } catch { return null; }
  },
  set(value) {
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
  clear() {
    try { sessionStorage.removeItem(SESSION_KEY); } catch { /* storage unavailable */ }
  },
};

async function request(method, path, { json, form, query, auth = false } = {}) {
  const headers = {};
  let body;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  else if (form) body = form;
  if (auth) {
    const s = session.get();
    if (s && s.token) headers.Authorization = `Bearer ${s.token}`;
  }
  let url = BASE + path;
  if (query) {
    const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== '' && v !== null && v !== undefined));
    if ([...qs].length) url += `?${qs}`;
  }
  let res;
  try { res = await fetch(url, { method, headers, body }); } catch { throw new ApiError(0, NETWORK_MESSAGE); }
  let data = null;
  try { const text = await res.text(); data = text ? JSON.parse(text) : null; } catch { /* non-JSON body */ }
  if (!res.ok) {
    if (res.status === 401 && auth) session.clear();
    throw new ApiError(res.status, (data && data.message) || `Request failed (${res.status})`, data);
  }
  return data;
}

const enc = encodeURIComponent;

export const api = {
  meta: () => request('GET', '/meta'),
  health: () => request('GET', '/health'),
  routePreview: (lat, lon) => request('GET', '/route-preview', { query: { latitude: lat, longitude: lon } }),
  createTicket: (form) => request('POST', '/tickets', { form }),
  getTicket: (id) => request('GET', `/tickets/${enc(id)}`),
  dashboard: (filters) => request('GET', '/public/dashboard', { query: filters }),

  login: (username, password) => request('POST', '/auth/login', { json: { username, password } }),
  me: () => request('GET', '/auth/me', { auth: true }),
  queue: (status) => request('GET', '/authority/tickets', { auth: true, query: { status } }),
  startWork: (id, note) => request('PATCH', `/authority/tickets/${enc(id)}`, { auth: true, json: { status: 'In Progress', note } }),
  resolve: (id, form) => request('PATCH', `/authority/tickets/${enc(id)}/resolve`, { auth: true, form }),
  requestInfo: (id, message) => request('POST', `/authority/tickets/${enc(id)}/info-request`, { auth: true, json: { message } }),

  adminTickets: () => request('GET', '/admin/tickets', { auth: true }),
  adminBoundaries: () => request('GET', '/admin/boundaries', { auth: true }),
  saveBoundaries: (geojson) => request('PUT', '/admin/boundaries', { auth: true, json: geojson }),
  adminDepartments: () => request('GET', '/admin/departments', { auth: true }),
  saveDepartment: (name, email) => request('PUT', `/admin/departments/${enc(name)}`, { auth: true, json: { email } }),
  seed: (options) => request('POST', '/admin/seed', { auth: true, json: options }),
};
