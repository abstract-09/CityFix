// End-to-end smoke test: real page modules + real backend, minimal DOM. Run via scripts/smoke.sh.
import assert from 'node:assert/strict';
import { all, buttonWith, byClass, byId, install, visibleText } from './dom-shim.mjs';

const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:8123';
const PASS = process.env.SMOKE_PASSWORD || 'demo-pass-1';
const { appEl, fireWindow } = install(BASE);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, what, ms = 5000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch { /* retry */ } await sleep(25); }
  throw new Error(`Timed out waiting for: ${what}\nPage text: ${visibleText(appEl).slice(0, 600)}`);
}
async function go(hash, expect) {
  location.hash = hash;
  await fireWindow('hashchange');
  await until(() => visibleText(appEl).includes(expect), `${hash} to show "${expect}"`);
}
const text = () => visibleText(appEl);
let passed = 0;
const step = (name) => { passed += 1; console.log(`  ok  ${name}`); };
const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...new Array(64).fill(0)]);

// Boot through the real router
await import('../../main.js');
await until(() => text().includes('Report an issue'), 'router to render the report page');
step('router renders the report page');

// ---- report page ----------------------------------------------------------
await until(() => text().includes('25.556200, 84.851200'), 'GPS coordinates');
await until(() => text().includes('Road Construction Department Bihar'), 'route preview');
step('GPS captured and routing preview shown');

const form = all(appEl, (n) => n.localName === 'form')[0];
await form.dispatch('submit');
assert.ok(text().includes('Please attach media and ensure GPS location permission is enabled'));
step('submitting without media shows the required-field message');

const fileInput = byId(appEl, 'media-input');
fileInput.files = [new File([new Uint8Array(11 * 1048576)], 'big.png')];
await fileInput.dispatch('change');
assert.ok(text().includes('Please use a file smaller than 10 MB'));
step('oversize file rejected client-side');

fileInput.files = [new File(['hello'], 'notes.txt')];
await fileInput.dispatch('change');
assert.ok(text().includes('Unsupported file format'));
step('unsupported file type rejected and field reset');

fileInput.files = [new File([PNG], 'pothole.png', { type: 'image/png' })];
await fileInput.dispatch('change');
assert.ok(text().includes('pothole.png'));
byId(appEl, 'category').value = 'Water Leak';
byId(appEl, 'contact').value = 'smoke@example.com';
await form.dispatch('submit');
await until(() => text().includes('Report submitted'), 'success screen');
const code = /CIV-\d{4}-\d{4}/.exec(text())[0];
assert.ok(text().includes('Keep this code'));
step(`report created: ${code}`);

// ---- tracking -------------------------------------------------------------
await go(`#/track/${code}`, 'History');
assert.ok(text().includes('Water Leak') && text().includes('Received'));
step('tracking page shows the new ticket and its history');

await go('#/track/CIV-2026-0003', 'Photo from the department');
assert.ok(text().includes('Resolved') && text().includes('Municipal Corporation') && text().includes('Lamp replaced'));
step('resolved sample ticket shows proof section and timeline');

await go('#/track', 'Track a ticket');
byId(appEl, 'ticket-code').value = 'CIV-9999-9999';
await all(appEl, (n) => n.localName === 'form')[0].dispatch('submit');
await until(() => text().includes('Ticket not found. Please check your tracking reference code'), '404 message');
assert.equal(byId(appEl, 'ticket-code').value, '');
step('unknown ticket shows the not-found message and clears the field');

// ---- public dashboard -----------------------------------------------------
await go('#/dashboard', 'Department response times');
await until(() => byClass(appEl, 'map-marker').length >= 3, 'map markers');
assert.ok(text().includes('25.8 hours'), 'avg resolution for Municipal Corporation');
const marker = byClass(appEl, 'map-marker')[0];
await marker.dispatch('click');
await until(() => text().includes('Open ticket'), 'marker detail');
const before = byClass(appEl, 'map-marker').length;
const catSel = byId(appEl, 'f-category');
catSel.value = 'Streetlight Defect';
await catSel.dispatch('change');
await until(() => byClass(appEl, 'map-marker').length === 1, 'filtered map');
step(`dashboard: ${before} markers, metrics, marker selection and filters work`);

// ---- officer portal -------------------------------------------------------
await go('#/officer', 'Sign in');
byId(appEl, 'login-user').value = 'officer_rcd';
byId(appEl, 'login-pass').value = 'wrong';
await all(appEl, (n) => n.localName === 'form')[0].dispatch('submit');
await until(() => text().includes('Incorrect username or password'), 'bad-login message');
byId(appEl, 'login-pass').value = PASS;
await all(appEl, (n) => n.localName === 'form')[0].dispatch('submit');
await until(() => text().includes('Queue: Road Construction Department Bihar'), 'officer queue');
assert.ok(text().includes('CIV-2026-0001'));
step('officer login (wrong then right password) shows the department queue');

const rowSelect = () => all(appEl, (n) => n.localName === 'select' && (n.attrs['aria-label'] || '').startsWith('Status for CIV-2026-0001'))[0];
rowSelect().value = 'In Progress';
await rowSelect().dispatch('change');
await buttonWith(appEl, 'Update status').dispatch('click');
await until(() => text().includes('CIV-2026-0001 is now In Progress'), 'status update');
step('officer moves ticket to In Progress');

rowSelect().value = 'Resolved';
await rowSelect().dispatch('change');
assert.ok(text().includes('Photo of the finished repair (required)'));
await buttonWith(appEl, 'Update status').dispatch('click');
assert.ok(text().includes('Mandatory resolution photo proof is required prior to closing ticket'));
const proof = all(appEl, (n) => n.attrs.id === 'proof-CIV-2026-0001')[0];
proof.files = [new File([PNG], 'after.png', { type: 'image/png' })];
await buttonWith(appEl, 'Update status').dispatch('click');
await until(() => text().includes('CIV-2026-0001 is now Resolved'), 'resolution');
step('resolving needs proof, then succeeds with a photo');

// ---- admin ------------------------------------------------------------------
await go('#/admin', 'Sign in');
byId(appEl, 'login-user').value = 'officer_rcd';
byId(appEl, 'login-pass').value = PASS;
await all(appEl, (n) => n.localName === 'form')[0].dispatch('submit');
await until(() => text().includes('not an administrator account'), 'wrong-role message');
byId(appEl, 'login-user').value = 'admin';
byId(appEl, 'login-pass').value = PASS;
await all(appEl, (n) => n.localName === 'form')[0].dispatch('submit');
await until(() => text().includes('citizen1@example.com'), 'admin ticket table with contact');
step('admin sees reporter contact details; officer account is refused');

await buttonWith(appEl, 'Routing').dispatch('click');
await until(() => byId(appEl, 'geojson') && byId(appEl, 'geojson').value.includes('FeatureCollection'), 'boundary editor');
await buttonWith(appEl, 'Validate and save').dispatch('click');
await until(() => text().includes('boundary features'), 'boundary save');
await buttonWith(appEl, 'System').dispatch('click');
await until(() => text().includes('Stub mode'), 'system panel');
step('admin routing editor saves boundaries; system panel reports stub mode');

// Public pages must never show contact details
await go('#/track/CIV-2026-0001', 'History');
assert.ok(!text().includes('citizen1@example.com') && !text().includes('smoke@example.com'));
step('public ticket page does not expose contact details');

console.log(`\nSmoke test passed (${passed} checks).`);
process.exit(0);
