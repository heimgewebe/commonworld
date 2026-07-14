export const DEFAULT_CAMERA = Object.freeze({
  lng: 8,
  lat: 24,
  zoom: 1.15,
  bearing: 0,
  pitch: 0,
});

export const DIGITAL_LAYER_TRANSITION_MS = 760;

export const LAYERS = Object.freeze([
  Object.freeze({ id: 'knowledge_data', label: 'Wissen und offene Daten', themes: ['knowledge', 'open-data', 'research', 'documentation'] }),
  Object.freeze({ id: 'software_infrastructure', label: 'Freie Software und Infrastruktur', themes: ['free-software', 'open-source', 'infrastructure', 'platform'] }),
  Object.freeze({ id: 'media_culture', label: 'Offene Medien und Kultur', themes: ['open-media', 'culture', 'archives', 'creative-commons'] }),
  Object.freeze({ id: 'learning_education', label: 'Freies Lernen und Bildung', themes: ['education', 'open-educational-resources', 'learning'] }),
  Object.freeze({ id: 'communication_networks', label: 'Kommunikation und Netze', themes: ['communication', 'community-network', 'federation', 'protocol'] }),
  Object.freeze({ id: 'mixed_other', label: 'Gemischte und weitere digitale Commons', themes: [] }),
]);

export const ORBIT_PROFILES = Object.freeze([
  Object.freeze({ rx: 316, ry: 300, rotation: -8 }),
  Object.freeze({ rx: 310, ry: 282, rotation: 20 }),
  Object.freeze({ rx: 304, ry: 268, rotation: 43 }),
  Object.freeze({ rx: 298, ry: 288, rotation: -31 }),
  Object.freeze({ rx: 292, ry: 274, rotation: 63 }),
  Object.freeze({ rx: 286, ry: 294, rotation: -62 }),
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


function orbitalPoint(profile, angleDegrees) {
  const angle = angleDegrees * Math.PI / 180;
  const rotation = profile.rotation * Math.PI / 180;
  const localX = Math.cos(angle) * profile.rx;
  const localY = Math.sin(angle) * profile.ry;
  return {
    x: 320 + localX * Math.cos(rotation) - localY * Math.sin(rotation),
    y: 320 + localX * Math.sin(rotation) + localY * Math.cos(rotation),
  };
}

function outwardDirection(point) {
  const x = point.x - 320;
  const y = point.y - 320;
  const length = Math.max(1, Math.hypot(x, y));
  return { x: x / length, y: y / length };
}

function upperOrbitAngle(profile) {
  const rotation = profile.rotation * Math.PI / 180;
  const coefficientX = Math.sin(rotation) * profile.rx;
  const coefficientY = Math.cos(rotation) * profile.ry;
  return (Math.atan2(coefficientY, coefficientX) + Math.PI) * 180 / Math.PI;
}

export function sphereLabelLayout(layerIndex, recordIndex, recordCount) {
  const layer = Number.isInteger(layerIndex) ? clamp(layerIndex, 0, LAYERS.length - 1) : 0;
  const count = Number.isInteger(recordCount) && recordCount > 0 ? recordCount : 1;
  const index = Number.isInteger(recordIndex) ? clamp(recordIndex, 0, count - 1) : 0;
  const profile = ORBIT_PROFILES[layer];
  const overviewAngle = sphereStartOffset(layer, index, count) * 3.6 - 90;
  const overview = orbitalPoint(profile, overviewAngle);
  const overviewDirection = outwardDirection(overview);
  const sideSpread = (layer - (LAYERS.length - 1) / 2) * 10.8 + (index - (count - 1) / 2) * 4;
  const side = orbitalPoint(profile, upperOrbitAngle(profile) + sideSpread);
  const sideDirection = outwardDirection(side);
  return Object.freeze({
    overviewX: rounded(overview.x, 2),
    overviewY: rounded(overview.y, 2),
    overviewDx: rounded(overviewDirection.x, 4),
    overviewDy: rounded(overviewDirection.y, 4),
    sideX: rounded(side.x, 2),
    sideY: rounded(side.y, 2),
    sideDx: rounded(sideDirection.x, 4),
    sideDy: rounded(sideDirection.y, 4),
  });
}

export function sphereDetailLevel({ diameter, sideView = false } = {}) {
  if (sideView) return 'close';
  const size = Math.max(0, finite(diameter, 0));
  if (size < 360) return 'micro';
  if (size < 620) return 'compact';
  return 'names';
}

export function sphereProjectScale(diameter, detailLevel = 'names') {
  const size = Math.max(1, finite(diameter, 640));
  const targetPixels = detailLevel === 'close' ? 20.5 : detailLevel === 'compact' ? 11.5 : detailLevel === 'micro' ? 10.5 : 12.5;
  return rounded((targetPixels / 12) * (640 / size), 5);
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

const HORIZON_BEARINGS = Object.freeze([0, 45, 90, 135, 180, 225, 270, 315]);

export function globeHorizonCoordinates(center = DEFAULT_CAMERA, angularDistanceDegrees = 89.994) {
  const radians = Math.PI / 180;
  const latitude = clamp(finite(center?.lat, DEFAULT_CAMERA.lat), -85.051129, 85.051129) * radians;
  const longitude = finite(center?.lng, DEFAULT_CAMERA.lng) * radians;
  const distance = clamp(finite(angularDistanceDegrees, 89.994), 1, 89.9999) * radians;
  return HORIZON_BEARINGS.map((bearingDegrees) => {
    const bearing = bearingDegrees * radians;
    const destinationLatitude = Math.asin(
      Math.sin(latitude) * Math.cos(distance)
      + Math.cos(latitude) * Math.sin(distance) * Math.cos(bearing),
    );
    const destinationLongitude = longitude + Math.atan2(
      Math.sin(bearing) * Math.sin(distance) * Math.cos(latitude),
      Math.cos(distance) - Math.sin(latitude) * Math.sin(destinationLatitude),
    );
    return {
      lng: rounded((((destinationLongitude / radians + 540) % 360) + 360) % 360 - 180, 6),
      lat: rounded(destinationLatitude / radians, 6),
    };
  });
}

export function projectedGlobeCircle({ center = null, horizon = [] } = {}) {
  const x = finite(center?.x, Number.NaN);
  const y = finite(center?.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const radii = (Array.isArray(horizon) ? horizon : [])
    .map((point) => {
      const projectedX = finite(point?.x, Number.NaN);
      const projectedY = finite(point?.y, Number.NaN);
      return Number.isFinite(projectedX) && Number.isFinite(projectedY)
        ? Math.hypot(projectedX - x, projectedY - y)
        : Number.NaN;
    })
    .filter((radius) => Number.isFinite(radius) && radius > 0)
    .sort((left, right) => left - right);
  if (radii.length < 4) return null;
  const middle = Math.floor(radii.length / 2);
  const radius = radii.length % 2
    ? radii[middle]
    : (radii[middle - 1] + radii[middle]) / 2;
  return {
    x: rounded(x, 2),
    y: rounded(y, 2),
    diameter: rounded(radius * 2, 2),
  };
}

export function sphereLayout({ width, height, padding = {}, globe = null, sideView = false } = {}) {
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
  const shortestSide = Math.min(stageWidth, stageHeight);
  if (sideView) {
    const diameter = Math.max(stageWidth * 2.3, stageHeight * 2.35);
    const outerTrackTargetY = stageHeight * 0.22;
    const outerTrackRadiusRatio = 316 / 640;
    return {
      x: rounded(stageWidth / 2, 2),
      y: rounded(outerTrackTargetY + diameter * outerTrackRadiusRatio, 2),
      diameter: rounded(diameter, 2),
      globeDiameter: rounded(diameter, 2),
    };
  }
  const x = clamp(finite(globe?.x, fallbackX), 0, stageWidth);
  const y = clamp(finite(globe?.y, fallbackY), 0, stageHeight);
  const fallbackGlobeDiameter = Math.min(availableWidth, availableHeight) * 0.88;
  const maximumSafeDiameter = Math.hypot(stageWidth, stageHeight) * 2.5;
  const globeDiameter = clamp(finite(globe?.diameter, fallbackGlobeDiameter), 1, maximumSafeDiameter);
  return {
    x: rounded(x, 2),
    y: rounded(y, 2),
    diameter: rounded(globeDiameter * 1.18, 2),
    globeDiameter: rounded(globeDiameter, 2),
  };
}

export function digitalLayerCamera(camera = DEFAULT_CAMERA) {
  const bearing = finite(camera?.bearing, DEFAULT_CAMERA.bearing);
  const normalizedBearing = ((((bearing + 18) + 180) % 360) + 360) % 360 - 180;
  return {
    center: [
      clamp(finite(camera?.lng, DEFAULT_CAMERA.lng), -180, 180),
      clamp(finite(camera?.lat, DEFAULT_CAMERA.lat), -85, 85),
    ],
    zoom: clamp(Math.max(1.95, finite(camera?.zoom, DEFAULT_CAMERA.zoom) + 0.72), 0, 8),
    bearing: rounded(normalizedBearing, 1),
    pitch: 52,
    padding: { top: 0, right: 0, bottom: 0, left: 0 },
  };
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

export function sphereOpacityForGlobeRatio(globeViewportRatio) {
  const value = finite(globeViewportRatio, 0);
  if (value <= 1.05) return 1;
  if (value >= 2.1) return 0;
  return Number(((2.1 - value) / 1.05).toFixed(4));
}
