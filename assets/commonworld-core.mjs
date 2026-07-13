export const DEFAULT_CAMERA = Object.freeze({
  lng: 8,
  lat: 24,
  zoom: 1.15,
  bearing: 0,
  pitch: 0,
});

export const LAYERS = Object.freeze([
  Object.freeze({ id: 'knowledge_data', label: 'Wissen und offene Daten', themes: ['knowledge', 'open-data', 'research', 'documentation'] }),
  Object.freeze({ id: 'software_infrastructure', label: 'Freie Software und Infrastruktur', themes: ['free-software', 'open-source', 'infrastructure', 'platform'] }),
  Object.freeze({ id: 'media_culture', label: 'Offene Medien und Kultur', themes: ['open-media', 'culture', 'archives', 'creative-commons'] }),
  Object.freeze({ id: 'learning_education', label: 'Freies Lernen und Bildung', themes: ['education', 'open-educational-resources', 'learning'] }),
  Object.freeze({ id: 'communication_networks', label: 'Kommunikation und Netze', themes: ['communication', 'community-network', 'federation', 'protocol'] }),
  Object.freeze({ id: 'mixed_other', label: 'Gemischte und weitere digitale Commons', themes: [] }),
]);

const finite = (value, fallback) => {
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
const rounded = (value, digits) => Number(value.toFixed(digits));

export function deriveLayer(record) {
  const digital = record?.presence?.digital;
  if (!digital || digital.available !== true) return null;
  const themes = new Set(Array.isArray(record.themes) ? record.themes : []);
  const scores = LAYERS.filter((layer) => layer.id !== 'mixed_other').map((layer) => ({
    id: layer.id,
    score: layer.themes.reduce((total, theme) => total + (themes.has(theme) ? 1 : 0), 0),
  }));
  const maximum = Math.max(0, ...scores.map(({ score }) => score));
  const winners = scores.filter(({ score }) => score === maximum && score > 0);
  return winners.length === 1 ? winners[0].id : 'mixed_other';
}

export function binaryFragment(identifier, length = 12) {
  let hash = 2166136261;
  for (const character of String(identifier)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  let bits = hash.toString(2).padStart(32, '0');
  while (bits.length < length) bits += bits;
  return bits.slice(0, length);
}

export function sphereStartOffset(layerIndex, recordIndex, recordCount) {
  const count = Number.isInteger(recordCount) && recordCount > 0 ? recordCount : 1;
  const layer = Number.isInteger(layerIndex) && layerIndex >= 0 ? layerIndex : 0;
  const index = Number.isInteger(recordIndex) && recordIndex >= 0 ? recordIndex : 0;
  const normalized = ((index / count + layer * 0.43) % 1 + 1) % 1;
  return Number((8 + normalized * 72).toFixed(4));
}

export function cameraFromSearch(search = '') {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  return {
    lng: clamp(finite(parameters.get('lng'), DEFAULT_CAMERA.lng), -180, 180),
    lat: clamp(finite(parameters.get('lat'), DEFAULT_CAMERA.lat), -85, 85),
    zoom: clamp(finite(parameters.get('z'), DEFAULT_CAMERA.zoom), 0, 8),
    bearing: clamp(finite(parameters.get('b'), DEFAULT_CAMERA.bearing), -180, 180),
    pitch: clamp(finite(parameters.get('p'), DEFAULT_CAMERA.pitch), 0, 70),
  };
}

export function normalizeQuery(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ').slice(0, 120);
}

export function stateFromSearch(search = '', knownProjectIds = []) {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const known = new Set(knownProjectIds);
  const project = parameters.get('project');
  const layer = parameters.get('layer');
  return {
    camera: cameraFromSearch(search),
    project: project && known.has(project) ? project : null,
    layer: LAYERS.some((entry) => entry.id === layer) ? layer : null,
    view: parameters.get('view') === 'layers' ? 'layers' : 'globe',
    surface: parameters.get('surface') === 'text' ? 'text' : 'globe',
    query: normalizeQuery(parameters.get('q')),
  };
}

const serializedNumber = (value, digits) => rounded(value, digits).toString();

export function searchFromState(state) {
  const parameters = new URLSearchParams();
  const camera = state?.camera ?? DEFAULT_CAMERA;
  parameters.set('lng', serializedNumber(clamp(finite(camera.lng, DEFAULT_CAMERA.lng), -180, 180), 4));
  parameters.set('lat', serializedNumber(clamp(finite(camera.lat, DEFAULT_CAMERA.lat), -85, 85), 4));
  parameters.set('z', serializedNumber(clamp(finite(camera.zoom, DEFAULT_CAMERA.zoom), 0, 8), 2));
  if (Math.abs(finite(camera.bearing, 0)) >= 0.05) parameters.set('b', serializedNumber(clamp(finite(camera.bearing, 0), -180, 180), 1));
  if (Math.abs(finite(camera.pitch, 0)) >= 0.05) parameters.set('p', serializedNumber(clamp(finite(camera.pitch, 0), 0, 70), 1));
  if (state?.view === 'layers') parameters.set('view', 'layers');
  if (state?.surface === 'text') parameters.set('surface', 'text');
  if (state?.layer && LAYERS.some((entry) => entry.id === state.layer)) parameters.set('layer', state.layer);
  if (state?.project) parameters.set('project', state.project);
  const query = normalizeQuery(state?.query);
  if (query) parameters.set('q', query);
  return `?${parameters.toString()}`;
}

export function filterRecords(records, state = {}) {
  const query = normalizeQuery(state.query).toLocaleLowerCase('de');
  return (Array.isArray(records) ? records : []).filter((record) => {
    if (state.layer && deriveLayer(record) !== state.layer) return false;
    if (!query) return true;
    const searchable = [record?.title, record?.summary, ...(record?.themes ?? []), ...(record?.actions ?? [])]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('de');
    return searchable.includes(query);
  });
}

export function sphereLayout({ width, height, zoom = DEFAULT_CAMERA.zoom, padding = {}, center = null, sideView = false } = {}) {
  const stageWidth = Math.max(1, finite(width, 1));
  const stageHeight = Math.max(1, finite(height, 1));
  const left = clamp(finite(padding.left, 0), 0, stageWidth - 1);
  const right = clamp(finite(padding.right, 0), 0, stageWidth - left - 1);
  const top = clamp(finite(padding.top, 0), 0, stageHeight - 1);
  const bottom = clamp(finite(padding.bottom, 0), 0, stageHeight - top - 1);
  const availableWidth = Math.max(1, stageWidth - left - right);
  const availableHeight = Math.max(1, stageHeight - top - bottom);
  const fallbackX = left + availableWidth / 2;
  const fallbackY = top + availableHeight / 2;
  const x = clamp(finite(center?.x, fallbackX), 0, stageWidth);
  const y = clamp(finite(center?.y, fallbackY), 0, stageHeight);
  const scale = 2 ** (clamp(finite(zoom, DEFAULT_CAMERA.zoom), 0, 8) - DEFAULT_CAMERA.zoom);
  const minimum = Math.min(stageWidth, stageHeight) * (sideView ? 0.22 : 0.36);
  const maximum = Math.min(stageWidth, stageHeight) * 1.6;
  const base = Math.min(availableWidth, availableHeight) * (sideView ? 0.96 : 0.98);
  const diameter = clamp(sideView ? base : base * scale, minimum, maximum);
  return { x: rounded(x, 2), y: rounded(y, 2), diameter: rounded(diameter, 2) };
}

export function mapCamera(map) {
  const center = map.getCenter();
  return {
    lng: center.lng,
    lat: center.lat,
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  };
}

export function mapFailurePolicy({ providerReadbackFailed = false } = {}) {
  return Object.freeze({ degraded: true, replaceStyle: providerReadbackFailed === true });
}

export function sphereOpacityForZoom(zoom) {
  const value = finite(zoom, DEFAULT_CAMERA.zoom);
  if (value <= 1.8) return 1;
  if (value >= 2.6) return 0;
  return Number(((2.6 - value) / 0.8).toFixed(4));
}
