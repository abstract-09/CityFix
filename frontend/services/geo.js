// Map maths: fit a set of lon/lat points into an SVG viewport. Pure functions, unit-tested.
export const DEFAULT_CENTER = { lon: 84.8512, lat: 25.5562 };
export const MARKER_HEX = { red: '#C62828', orange: '#E07B00', yellow: '#D9A400', green: '#17753F' };

function walk(coords, out) {
  if (!Array.isArray(coords)) return;
  if (typeof coords[0] === 'number') out.push([coords[0], coords[1]]);
  else coords.forEach((c) => walk(c, out));
}

export function collectPoints(tickets = [], geojson = null) {
  const points = tickets.map((t) => [t.longitude, t.latitude]);
  for (const f of (geojson && geojson.features) || []) walk(f.geometry && f.geometry.coordinates, points);
  return points;
}

export function fitBounds(points, padRatio = 0.1) {
  let pts = points;
  if (!pts.length) pts = [[DEFAULT_CENTER.lon - 0.01, DEFAULT_CENTER.lat - 0.007], [DEFAULT_CENTER.lon + 0.01, DEFAULT_CENTER.lat + 0.007]];
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const [lon, lat] of pts) {
    minLon = Math.min(minLon, lon); maxLon = Math.max(maxLon, lon);
    minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
  }
  const MIN_SPAN = 0.004; // avoid a degenerate view when there is a single point
  if (maxLon - minLon < MIN_SPAN) { const c = (minLon + maxLon) / 2; minLon = c - MIN_SPAN / 2; maxLon = c + MIN_SPAN / 2; }
  if (maxLat - minLat < MIN_SPAN) { const c = (minLat + maxLat) / 2; minLat = c - MIN_SPAN / 2; maxLat = c + MIN_SPAN / 2; }
  const padLon = (maxLon - minLon) * padRatio;
  const padLat = (maxLat - minLat) * padRatio;
  return { minLon: minLon - padLon, maxLon: maxLon + padLon, minLat: minLat - padLat, maxLat: maxLat + padLat };
}

// Equirectangular projection with longitude scaled by cos(latitude); north is up.
export function makeProjection(bounds, width, height) {
  const k = Math.cos((((bounds.minLat + bounds.maxLat) / 2) * Math.PI) / 180);
  const spanX = (bounds.maxLon - bounds.minLon) * k;
  const spanY = bounds.maxLat - bounds.minLat;
  const scale = Math.min(width / spanX, height / spanY);
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanY * scale) / 2;
  return {
    scale,
    project: (lon, lat) => [offX + (lon - bounds.minLon) * k * scale, offY + (bounds.maxLat - lat) * scale],
  };
}

export function polygonsOf(geometry) {
  if (!geometry) return [];
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  return geometry.type === 'MultiPolygon' ? geometry.coordinates : [];
}

export function linesOf(geometry) {
  if (!geometry) return [];
  if (geometry.type === 'LineString') return [geometry.coordinates];
  return geometry.type === 'MultiLineString' ? geometry.coordinates : [];
}
