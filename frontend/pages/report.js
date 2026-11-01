import { api } from '../services/api.js';
import { h, replace } from '../components/dom.js';
import { icon } from '../components/icons.js';
import { banner, categoryLabel, copyText, field, severityPill, spinner } from '../components/ui.js';
import { DEFAULT_MAX_BYTES, MSG_MISSING, formatBytes, formatCoord, isAudioFile, isValidContact, trackHash, validateFile } from '../services/utils.js';

const DEMO_LOCATION = { lat: 25.5562, lon: 84.8512 };
const ACCEPT = 'image/png,image/jpeg,audio/mpeg,audio/wav,audio/mp4,audio/x-m4a,.jpg,.jpeg,.png,.mp3,.wav,.m4a';

export async function render(container, _params, ctx) {
  const maxBytes = (ctx.meta.max_upload_mb || 10) * 1024 * 1024 || DEFAULT_MAX_BYTES;
  const state = { file: null, previewUrl: null, geo: null, geoStatus: 'locating', route: null, submitting: false };

  const bannerSlot = h('div', { class: 'slot' });
  const fileSlot = h('div');
  const locationSlot = h('div');
  const routeSlot = h('p', { class: 'route-line', hidden: true });
  const setBanner = (node) => replace(bannerSlot, node);

  // ---- file ---------------------------------------------------------------
  const input = h('input', { id: 'media-input', class: 'sr-only', type: 'file', accept: ACCEPT, onchange: (e) => choose(e.target.files[0]) });
  const cameraInput = h('input', { class: 'sr-only', type: 'file', accept: 'image/*', capture: 'environment', tabindex: '-1', 'aria-hidden': 'true', onchange: (e) => choose(e.target.files[0]) });
  const dropzone = h('label', { class: 'dropzone', for: 'media-input' },
    icon('upload', { size: 28 }),
    h('span', { class: 'dropzone__title' }, 'Add a photo or voice note'),
    h('span', { class: 'muted' }, `Drop a file here or choose one. JPG, PNG, MP3, WAV or M4A, up to ${Number((maxBytes / 1048576).toFixed(1))} MB.`));
  ['dragenter', 'dragover'].forEach((n) => dropzone.addEventListener(n, (e) => { e.preventDefault(); dropzone.classList.add('is-dragover'); }));
  ['dragleave', 'drop'].forEach((n) => dropzone.addEventListener(n, (e) => { e.preventDefault(); dropzone.classList.remove('is-dragover'); }));
  dropzone.addEventListener('drop', (e) => choose(e.dataTransfer.files[0]));

  function resetFile() {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.file = null; state.previewUrl = null; input.value = ''; cameraInput.value = '';
    drawFile();
  }

  function choose(file) {
    if (!file) return;
    const check = validateFile(file, { maxBytes });
    if (!check.ok) {
      if (check.code === 'type') resetFile(); // unsupported type: clear the upload field
      setBanner(banner('error', check.message, { onDismiss: () => setBanner(null) }));
      return;
    }
    setBanner(null);
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.file = file;
    state.previewUrl = isAudioFile(file) ? null : URL.createObjectURL(file);
    drawFile();
  }

  function drawFile() {
    dropzone.classList.remove('is-invalid');
    if (!state.file) {
      const camera = window.matchMedia && window.matchMedia('(pointer: coarse)').matches
        ? h('button', { type: 'button', class: 'btn btn--secondary', onclick: () => cameraInput.click() }, icon('camera'), 'Take a photo') : null;
      replace(fileSlot, dropzone, camera);
      return;
    }
    replace(fileSlot, h('div', { class: 'file-chip' },
      state.previewUrl ? h('img', { src: state.previewUrl, alt: 'Preview of the selected photo', class: 'file-chip__img' })
        : h('div', { class: 'file-chip__audio' }, icon('mic', { size: 28 })),
      h('div', { class: 'file-chip__info' }, h('p', { class: 'file-chip__name' }, state.file.name), h('p', { class: 'muted' }, formatBytes(state.file.size))),
      h('button', { type: 'button', class: 'btn btn--quiet', onclick: resetFile }, icon('x', { size: 16 }), 'Remove file')));
  }

  // ---- location -----------------------------------------------------------
  const latInput = h('input', { id: 'manual-lat', class: 'input', inputmode: 'decimal', placeholder: '25.556200', autocomplete: 'off' });
  const lonInput = h('input', { id: 'manual-lon', class: 'input', inputmode: 'decimal', placeholder: '84.851200', autocomplete: 'off' });
  const locationBox = h('div', { class: 'location', 'aria-live': 'polite' });

  function setGeo(lat, lon, accuracy, source) {
    state.geo = { lat, lon, accuracy, source };
    state.geoStatus = 'ready';
    drawLocation();
    previewRoute();
  }

  function locate() {
    if (!('geolocation' in navigator)) { state.geoStatus = 'unsupported'; drawLocation(); return; }
    state.geoStatus = 'locating';
    state.geo = null;
    drawLocation();
    navigator.geolocation.getCurrentPosition(
      (pos) => setGeo(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, 'gps'),
      (err) => { state.geoStatus = err.code === 1 ? 'denied' : 'unavailable'; drawLocation(); },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
  }

  function useManual() {
    const lat = Number(latInput.value);
    const lon = Number(lonInput.value);
    if (latInput.value.trim() === '' || lonInput.value.trim() === '' || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      setBanner(banner('error', 'Enter a latitude between -90 and 90 and a longitude between -180 and 180', { onDismiss: () => setBanner(null) }));
      return;
    }
    setBanner(null);
    setGeo(lat, lon, null, 'manual');
  }

  function drawLocation() {
    locationBox.classList.remove('is-invalid');
    const st = state.geoStatus;
    locationBox.className = `location location--${st}`;
    const retry = h('button', { type: 'button', class: 'btn btn--secondary btn--small', onclick: locate }, icon('refresh', { size: 16 }), st === 'ready' ? 'Refresh location' : 'Try again');
    if (st === 'locating') replace(locationBox, spinner('Finding your location'), h('p', 'Finding your location…'));
    else if (st === 'ready') {
      const g = state.geo;
      replace(locationBox, icon('pin', { size: 24 }),
        h('div', h('p', { class: 'location__coords' }, `${formatCoord(g.lat)}, ${formatCoord(g.lon)}`),
          h('p', { class: 'muted' }, g.source === 'gps' ? `From your device, accurate to about ${Math.round(g.accuracy)} m` : 'Entered by hand')),
        retry);
    } else {
      const why = st === 'denied' ? 'Location access is blocked. Allow it in your browser settings, then try again, or enter coordinates below.'
        : st === 'unsupported' ? 'This browser cannot share your location. Enter coordinates below.'
          : "We couldn't read your location. Try again, or enter coordinates below.";
      replace(locationBox, icon('alert', { size: 24 }), h('p', why), retry);
    }
  }

  let routeToken = 0;
  async function previewRoute() {
    const my = ++routeToken;
    routeSlot.hidden = true;
    try {
      const r = await api.routePreview(state.geo.lat, state.geo.lon);
      if (my !== routeToken) return;
      replace(routeSlot, icon('check', { size: 16 }), ' This report goes to ', h('strong', r.assigned_department), r.jurisdiction ? ` (${r.jurisdiction})` : '');
      routeSlot.hidden = false;
    } catch { /* the preview is a convenience; submission still routes on the server */ }
  }

  const manual = h('details', { class: 'manual' },
    h('summary', 'Enter coordinates by hand'),
    h('div', { class: 'manual__grid' },
      field({ id: 'manual-lat', label: 'Latitude', control: latInput }),
      field({ id: 'manual-lon', label: 'Longitude', control: lonInput })),
    h('div', { class: 'row' },
      h('button', { type: 'button', class: 'btn btn--secondary btn--small', onclick: useManual }, 'Use these coordinates'),
      h('button', { type: 'button', class: 'btn btn--quiet btn--small', onclick: () => { latInput.value = DEMO_LOCATION.lat; lonInput.value = DEMO_LOCATION.lon; useManual(); } }, 'Use the demo location (Bihta)')));

  // ---- details & submit ---------------------------------------------------
  const category = h('select', { id: 'category', class: 'select' },
    h('option', { value: '' }, 'Let CityFix decide'),
    ...ctx.meta.categories.map((c) => h('option', { value: c }, c)));
  const contact = h('input', { id: 'contact', class: 'input', type: 'text', inputmode: 'email', autocomplete: 'off', placeholder: 'name@example.com or 10-digit number' });
  const contactField = field({ id: 'contact', label: 'Contact (optional)', control: contact, hint: 'Only system administrators can see this. It is never shown on the map or ticket page.' });
  const contactError = () => contactField.querySelector('.field__error');
  const submitBtn = h('button', { type: 'submit', class: 'btn btn--primary btn--large' }, 'Submit report');

  function setSubmitting(on) {
    state.submitting = on;
    submitBtn.disabled = on;
    replace(submitBtn, on ? [spinner('Submitting'), ' Submitting…'] : 'Submit report');
  }

  function markInvalid({ file, geo }) {
    if (file) dropzone.classList.add('is-invalid');
    if (geo) locationBox.classList.add('is-invalid');
    (file ? dropzone : locationBox).scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }

  async function submit() {
    if (state.submitting) return;
    contactError().hidden = true;
    const missing = { file: !state.file, geo: !state.geo };
    if (missing.file || missing.geo) { markInvalid(missing); setBanner(banner('error', MSG_MISSING)); return; }
    if (!isValidContact(contact.value)) {
      const e = contactError(); e.textContent = 'Enter an email address or a 10-digit phone number'; e.hidden = false; contact.focus(); return;
    }
    setBanner(null);
    const fd = new FormData();
    fd.append('media', state.file, state.file.name);
    fd.append('latitude', Number(state.geo.lat).toFixed(6));
    fd.append('longitude', Number(state.geo.lon).toFixed(6));
    if (state.geo.accuracy != null) fd.append('accuracy', String(state.geo.accuracy));
    if (category.value) fd.append('category', category.value);
    if (contact.value.trim()) fd.append('contact', contact.value.trim());

    setSubmitting(true);
    try {
      const data = await api.createTicket(fd);
      if (data.merged) {
        sessionStorage.setItem('cityfix.flash', JSON.stringify({ kind: 'info', message: data.message }));
        location.hash = trackHash(data.ticket_id);
        return;
      }
      showSuccess(data);
    } catch (err) {
      if (err.status === 415) resetFile();
      if (err.status === 400) markInvalid({ file: !state.file, geo: !state.geo });
      const retryable = err.status === 0 || err.status >= 500;
      setBanner(banner('error', err.message, retryable ? { actionLabel: 'Try again', onAction: submit } : { onDismiss: () => setBanner(null) }));
    } finally {
      setSubmitting(false);
    }
  }

  const form = h('form', { class: 'card form', novalidate: true, onsubmit: (e) => { e.preventDefault(); submit(); } },
    h('fieldset', { class: 'fieldset' }, h('legend', 'Photo or voice note'), fileSlot, cameraInput, input),
    h('fieldset', { class: 'fieldset' }, h('legend', 'Location'), locationBox, routeSlot, manual),
    h('fieldset', { class: 'fieldset' }, h('legend', 'Details'),
      field({ id: 'category', label: 'Type of issue', control: category, hint: 'Leave this on automatic unless you are sure.' }),
      contactField),
    submitBtn);

  // ---- success ------------------------------------------------------------
  function showSuccess(data) {
    const link = h('input', { class: 'input', readonly: true, value: data.url, 'aria-label': 'Link to your ticket' });
    const copy = h('button', { type: 'button', class: 'btn btn--secondary', onclick: async () => {
      const ok = await copyText(data.url);
      if (!ok) { link.select(); }
      replace(copy, icon('check', { size: 16 }), ok ? 'Copied' : 'Press Ctrl+C to copy');
    } }, icon('copy', { size: 16 }), 'Copy link');
    replace(container,
      h('section', { class: 'page' },
        h('h1', { class: 'page__title' }, 'Report submitted'),
        data.triage_warning ? banner('info', `${data.triage_warning}. An officer will review your report.`) : null,
        h('div', { class: 'stub' },
          h('div', { class: 'stub__main' },
            h('p', 'Keep this code to follow your report:'),
            h('p', { class: 'stub__code' }, data.ticket_id),
            h('p', 'Sent to ', h('strong', data.assigned_department), data.jurisdiction ? ` (${data.jurisdiction})` : ''),
            h('div', { class: 'stub__tags' }, categoryLabel(data.category), severityPill(data.severity)),
            h('p', { class: 'stub__desc' }, data.description)),
          h('div', { class: 'stub__side' },
            h('a', { class: 'btn btn--primary', href: trackHash(data.ticket_id) }, 'View ticket status'),
            h('div', { class: 'copy-row' }, link, copy),
            h('button', { type: 'button', class: 'btn btn--quiet', onclick: () => render(container, _params, ctx) }, 'Report another issue')))));
    window.scrollTo(0, 0);
  }

  replace(container, h('section', { class: 'page page--narrow' },
    h('h1', { class: 'page__title' }, 'Report an issue'),
    h('p', { class: 'lead' }, 'Add a photo or voice note. CityFix reads your location, finds the department responsible, and gives you a code to follow the repair.'),
    bannerSlot, form));
  drawFile();
  drawLocation();
  locate();
}
