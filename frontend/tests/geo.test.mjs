import assert from 'node:assert/strict';
import { test } from 'node:test';
import { collectPoints, fitBounds, linesOf, makeProjection, polygonsOf } from '../services/geo.js';

const tickets = [{ longitude: 84.8512, latitude: 25.5562 }, { longitude: 84.8550, latitude: 25.5601 }];

test('fitBounds contains every point with padding', () => {
  const b = fitBounds(collectPoints(tickets));
  for (const t of tickets) {
    assert.ok(t.longitude > b.minLon && t.longitude < b.maxLon);
    assert.ok(t.latitude > b.minLat && t.latitude < b.maxLat);
  }
});

test('fitBounds copes with no points and with a single point', () => {
  const empty = fitBounds([]);
  assert.ok(empty.maxLon > empty.minLon && empty.maxLat > empty.minLat);
  const one = fitBounds([[84.85, 25.55]]);
  assert.ok(one.maxLon - one.minLon >= 0.004);
});

test('projection keeps points inside the viewport and north up', () => {
  const b = fitBounds(collectPoints(tickets));
  const { project } = makeProjection(b, 900, 560);
  for (const t of tickets) {
    const [x, y] = project(t.longitude, t.latitude);
    assert.ok(x >= 0 && x <= 900 && y >= 0 && y <= 560, `${x},${y}`);
  }
  const north = project(84.85, b.maxLat)[1];
  const south = project(84.85, b.minLat)[1];
  assert.ok(north < south);
  assert.ok(project(b.maxLon, 25.55)[0] > project(b.minLon, 25.55)[0]); // east is right
});

test('projection preserves aspect ratio (a square degree box is not stretched)', () => {
  const b = { minLon: 84, maxLon: 84.1, minLat: 25, maxLat: 25.1 };
  const { project } = makeProjection(b, 900, 560);
  const [x0, y0] = project(84, 25.1);
  const [x1, y1] = project(84.1, 25);
  const ratio = (x1 - x0) / (y1 - y0);
  assert.ok(Math.abs(ratio - Math.cos((25.05 * Math.PI) / 180)) < 0.01, String(ratio));
});

test('collectPoints reads nested GeoJSON coordinates', () => {
  const geo = { features: [
    { geometry: { type: 'Polygon', coordinates: [[[1, 2], [3, 4], [5, 6], [1, 2]]] } },
    { geometry: { type: 'LineString', coordinates: [[7, 8], [9, 10]] } }] };
  assert.equal(collectPoints([], geo).length, 6);
  assert.equal(polygonsOf(geo.features[0].geometry).length, 1);
  assert.equal(linesOf(geo.features[1].geometry).length, 1);
  assert.deepEqual(linesOf(null), []);
});
