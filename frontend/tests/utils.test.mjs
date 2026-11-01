import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  MSG_MISSING, MSG_UNSUPPORTED, formatBytes, formatHours, isAudioFile, isValidContact, msgTooLarge,
  normaliseTicketId, safeUrl, trackHash, validateFile, TICKET_ID_RE,
} from '../services/utils.js';

const file = (name, size) => ({ name, size });

test('validateFile accepts supported types within the size limit', () => {
  for (const n of ['a.jpg', 'a.JPEG', 'a.png', 'a.mp3', 'a.wav', 'a.m4a']) assert.equal(validateFile(file(n, 1000)).ok, true, n);
});

test('validateFile rejects oversize, unsupported and missing files with the spec messages', () => {
  assert.deepEqual(validateFile(file('a.png', 10 * 1048576 + 1)), { ok: false, code: 'size', message: 'Please use a file smaller than 10 MB' });
  assert.equal(validateFile(file('a.png', 10 * 1048576)).ok, true); // exactly at the limit is fine
  assert.equal(validateFile(file('a.exe', 10)).message, MSG_UNSUPPORTED);
  assert.equal(validateFile(file('noextension', 10)).code, 'type');
  assert.equal(validateFile(null).message, MSG_MISSING);
  assert.equal(validateFile(file('a.png', 0)).code, 'empty');
});

test('msgTooLarge follows the configured limit', () => {
  assert.equal(msgTooLarge(5 * 1048576), 'Please use a file smaller than 5 MB');
});

test('isValidContact: optional email or 10-digit phone', () => {
  for (const ok of ['', '  ', 'a@b.co', 'first.last+tag@mail.example.org', '9876543210', '98765 43210', '+91 9876543210']) assert.equal(isValidContact(ok), true, ok);
  for (const bad of ['12345', 'a@b', '<script>', '98765432101', 'name@']) assert.equal(isValidContact(bad), false, bad);
});

test('formatHours', () => {
  assert.equal(formatHours(null), '—');
  assert.equal(formatHours(0.4), 'under 1 hour');
  assert.equal(formatHours(1), '1 hour');
  assert.equal(formatHours(25.75), '25.8 hours');
  assert.equal(formatHours(24), '24 hours');
  assert.equal(formatHours(72), '3 days');
});

test('ticket id helpers', () => {
  assert.equal(normaliseTicketId('  civ-2026-0001 '), 'CIV-2026-0001');
  assert.ok(TICKET_ID_RE.test('CIV-2026-0001'));
  assert.ok(!TICKET_ID_RE.test('CIV-26-1'));
  assert.equal(trackHash('CIV-2026-0001'), '#/track/CIV-2026-0001');
});

test('safeUrl only allows http(s) and same-origin paths', () => {
  assert.equal(safeUrl('https://x.test/a.jpg'), 'https://x.test/a.jpg');
  assert.equal(safeUrl('/media/abc.png'), '/media/abc.png');
  for (const bad of ['javascript:alert(1)', '//evil.test/x', 'data:text/html,hi', 'ftp://x', null, undefined, 5]) assert.equal(safeUrl(bad), '', String(bad));
});

test('misc', () => {
  assert.equal(formatBytes(512), '512 B');
  assert.equal(formatBytes(2048), '2 KB');
  assert.equal(formatBytes(5 * 1048576), '5.0 MB');
  assert.equal(isAudioFile({ name: 'v.M4A' }), true);
  assert.equal(isAudioFile({ name: 'p.png' }), false);
});
