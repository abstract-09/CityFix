// Pure helpers (no DOM access) so they can be unit-tested with `node --test`.
export const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;
export const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'mp3', 'wav', 'm4a'];
export const TICKET_ID_RE = /^CIV-\d{4}-\d{4,}$/;
export const MSG_MISSING = 'Please attach media and ensure GPS location permission is enabled';
export const MSG_UNSUPPORTED = 'Unsupported file format. Please upload JPG, PNG, or MP3 files';
export const MSG_PROOF = 'Mandatory resolution photo proof is required prior to closing ticket';

export function fileExt(name) {
  const m = /\.([a-z0-9]+)$/i.exec(name || '');
  return m ? m[1].toLowerCase() : '';
}

export function msgTooLarge(maxBytes = DEFAULT_MAX_BYTES) {
  return `Please use a file smaller than ${Number((maxBytes / 1048576).toFixed(1))} MB`;
}

export function validateFile(file, { maxBytes = DEFAULT_MAX_BYTES, allowed = ALLOWED_EXTENSIONS } = {}) {
  if (!file) return { ok: false, code: 'missing', message: MSG_MISSING };
  if (file.size === 0) return { ok: false, code: 'empty', message: 'That file is empty. Please choose another one' };
  if (file.size > maxBytes) return { ok: false, code: 'size', message: msgTooLarge(maxBytes) };
  if (!allowed.includes(fileExt(file.name))) return { ok: false, code: 'type', message: MSG_UNSUPPORTED };
  return { ok: true };
}

export function isAudioFile(file) {
  return ['mp3', 'wav', 'm4a'].includes(fileExt(file && file.name));
}

export function isValidContact(value) {
  const text = (value || '').trim();
  if (!text) return true; // optional
  if (text.length <= 254 && /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/.test(text)) return true;
  const digits = text.replace(/[\s-]/g, '').replace(/^\+91/, '');
  return /^\d{10}$/.test(digits);
}

export function normaliseTicketId(value) {
  return (value || '').trim().toUpperCase();
}

export function trackHash(ticketId) {
  return `#/track/${encodeURIComponent(ticketId)}`;
}

export function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

export function formatCoord(n) {
  return Number(n).toFixed(6);
}

export function formatTimestamp(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function formatHours(hours) {
  if (hours === null || hours === undefined || Number.isNaN(hours)) return '—';
  if (hours < 1) return 'under 1 hour';
  if (hours < 48) {
    const n = Number(hours.toFixed(1));
    return `${n} ${n === 1 ? 'hour' : 'hours'}`;
  }
  return `${Number((hours / 24).toFixed(1))} days`;
}

export const SEVERITY_RANK = { Critical: 0, Medium: 1, Low: 2 };

// Only http(s) and same-origin paths may be used as media sources.
export function safeUrl(url) {
  if (typeof url !== 'string') return '';
  if (/^https?:\/\//i.test(url)) return url;
  return url.startsWith('/') && !url.startsWith('//') ? url : '';
}

export function osmUrl(lat, lon) {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}`;
}
