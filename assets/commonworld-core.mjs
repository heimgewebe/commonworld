export const DEFAULT_CAMERA = Object.freeze({
  lng: 8,
  lat: 24,
  zoom: 1.15,
  bearing: 0,
  pitch: 0,
});

export const MAX_MAP_ZOOM = 18;
export const DIGITAL_LAYER_TRANSITION_MS = 1080;
const DIGITAL_LAYER_MAX_ZOOM = 8;

export const LAYERS = Object.freeze([
  Object.freeze({ id: 'knowledge_data', label: 'Wissen und offene Daten', trackLabel: 'Wissen', themes: ['knowledge', 'open-data', 'research', 'documentation'] }),
  Object.freeze({ id: 'software_infrastructure', label: 'Freie Software und Infrastruktur', trackLabel: 'Software', themes: ['free-software', 'open-source', 'infrastructure', 'platform'] }),
  Object.freeze({ id: 'media_culture', label: 'Offene Medien und Kultur', trackLabel: 'Medien', themes: ['open-media', 'culture', 'archives', 'creative-commons'] }),
  Object.freeze({ id: 'learning_education', label: 'Freies Lernen und Bildung', trackLabel: 'Lernen', themes: ['education', 'open-educational-resources', 'learning'] }),
  Object.freeze({ id: 'communication_networks', label: 'Kommunikation und Netze', trackLabel: 'Netze', themes: ['communication', 'community-network', 'federation', 'protocol'] }),
  Object.freeze({ id: 'mixed_other', label: 'Gemischte und weitere digitale Commons', trackLabel: 'Weitere', themes: [] }),
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


export function binaryName(value) {
  return [...new TextEncoder().encode(String(value ?? ''))]
    .map((byte) => byte.toString(2).padStart(8, '0'))
    .join(' ');
}

export function ribbonRepeatCount(recordCount, minimumSegments = 12) {
  const count = Number.isInteger(recordCount) && recordCount > 0 ? recordCount : 1;
  const minimum = Number.isInteger(minimumSegments) && minimumSegments > 0 ? minimumSegments : 12;
  return clamp(Math.ceil(minimum / count), 2, 6);
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


export function sphereDetailLevel({ diameter, sideView = false } = {}) {
  if (sideView) return 'close';
  const size = Math.max(0, finite(diameter, 0));
  if (size < 360) return 'micro';
  if (size < 620) return 'compact';
  return 'names';
}


export function cameraFromSearch(search = '') {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  return {
    lng: clamp(finite(parameters.get('lng'), DEFAULT_CAMERA.lng), -180, 180),
    lat: clamp(finite(parameters.get('lat'), DEFAULT_CAMERA.lat), -85, 85),
    zoom: clamp(finite(parameters.get('z'), DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM),
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
  parameters.set('z', serializedNumber(clamp(finite(camera.zoom, DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM), 2));
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
    if (state.layer && (record?.presence?.digital?.available !== true || deriveLayer(record) !== state.layer)) return false;
    if (!query) return true;
    const searchable = [record?.title, record?.summary, ...(record?.themes ?? []), ...(record?.actions ?? [])]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('de');
    return searchable.includes(query);
  });
}

export function recordPresentationLabel(record) {
  const kind = record?.kind;
  const layer = deriveLayer(record);
  if (kind === 'hybrid') return `Hybrid${layer ? ` · ${LAYERS.find(({ id }) => id === layer)?.label ?? 'Digitale Commons'}` : ''}`;
  if (kind === 'geographic') return 'Geografisch';
  if (kind === 'digital') return `Digital${layer ? ` · ${LAYERS.find(({ id }) => id === layer)?.label ?? 'Digitale Commons'}` : ''}`;
  return 'Commons';
}

function geometryRepresentationKind(location) {
  if (location?.mode === 'approximate') return 'approximate_anchor';
  const type = location?.geometry?.type;
  if (location?.mode === 'exact' && type === 'Point') return 'exact_anchor';
  if (location?.mode === 'exact' && (type === 'Polygon' || type === 'MultiPolygon')) return 'public_extent';
  return null;
}

function cloneCoordinates(value) {
  return Array.isArray(value) ? value.map(cloneCoordinates) : value;
}

export function publicMapFeatureCollection(records, visibleProjectIds = null) {
  const visible = visibleProjectIds instanceof Set ? visibleProjectIds : null;
  const features = [];
  for (const record of Array.isArray(records) ? records : []) {
    if (!record?.id || (visible && !visible.has(record.id))) continue;
    const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
    for (const location of locations) {
      if (!location || location.mode === 'hidden' || !location.geometry) continue;
      const representationKind = geometryRepresentationKind(location);
      if (!representationKind) continue;
      features.push({
        type: 'Feature',
        id: `${record.id}:${location.id}`,
        geometry: {
          type: location.geometry.type,
          coordinates: cloneCoordinates(location.geometry.coordinates),
        },
        properties: {
          project_id: record.id,
          location_id: location.id,
          title: record.title ?? record.id,
          project_kind: record.kind ?? 'geographic',
          location_label: location.label ?? record.title ?? record.id,
          location_mode: location.mode,
          representation_kind: representationKind,
          uncertainty_meters_min: location.mode === 'approximate' ? finite(location.uncertainty_meters_min, 0) : 0,
        },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

export function evidencedRelations(records) {
  const values = Array.isArray(records) ? records : [];
  const byId = new Map(values.filter((record) => record?.id).map((record) => [record.id, record]));
  const relations = [];
  for (const record of values) {
    for (const relation of Array.isArray(record?.relations) ? record.relations : []) {
      const target = byId.get(relation?.target_id);
      if (!target || !Array.isArray(relation?.source_ids) || relation.source_ids.length === 0) continue;
      relations.push({
        source_project_id: record.id,
        source_title: record.title ?? record.id,
        target_project_id: target.id,
        target_title: target.title ?? target.id,
        relation_type: relation.type,
        source_ids: [...relation.source_ids],
        note: relation.note ?? '',
      });
    }
  }
  return relations;
}

function formattedUncertainty(meters) {
  const value = Math.max(0, finite(meters, 0));
  if (value >= 1000 && value % 1000 === 0) return `${value / 1000} km`;
  return `${Math.round(value)} m`;
}

export function recordLocationSummaries(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  return locations.map((location) => {
    const label = location?.label ?? 'Ort';
    if (location?.mode === 'hidden') return `${label} · Ort verborgen`;
    if (location?.mode === 'approximate') return `${label} · ungefähr, mindestens ${formattedUncertainty(location.uncertainty_meters_min)} Unschärfe`;
    const type = location?.geometry?.type;
    if (type === 'Polygon' || type === 'MultiPolygon') return `${label} · öffentliche Fläche`;
    return `${label} · exakter öffentlicher Punkt`;
  });
}

export function semanticZoomLevel(zoom, selectedProjectId = null) {
  if (selectedProjectId) return 'focus';
  const value = clamp(finite(zoom, DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM);
  if (value < 1.8) return 'planet';
  if (value < 3.4) return 'macroregion';
  if (value < 5.5) return 'region';
  return 'local';
}

function spatialIdentityCount(records) {
  return (Array.isArray(records) ? records : []).filter((record) =>
    (Array.isArray(record?.presence?.geographic) ? record.presence.geographic : []).some((location) => location?.mode !== 'hidden' && location?.geometry),
  ).length;
}

function focusSpatialSummary(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  const visible = locations.filter((location) => location?.mode !== 'hidden' && location?.geometry).length;
  const hidden = locations.filter((location) => location?.mode === 'hidden').length;
  const kind = record?.kind === 'hybrid' ? 'Hybrid' : record?.kind === 'geographic' ? 'Geografisch' : 'Digital';
  const publicLabel = `${visible} ${visible === 1 ? 'öffentlicher Ort' : 'öffentliche Orte'}`;
  const hiddenLabel = `${hidden} ${hidden === 1 ? 'verborgener Ort' : 'verborgene Orte'}`;
  return hidden ? `${kind} · ${publicLabel} · ${hiddenLabel}` : `${kind} · ${publicLabel}`;
}

export function semanticLocationLine({
  zoom = DEFAULT_CAMERA.zoom,
  records = [],
  selectedProjectId = null,
  selectedRecord = null,
} = {}) {
  const selected = selectedProjectId
    ? (selectedRecord?.id === selectedProjectId
      ? selectedRecord
      : (Array.isArray(records) ? records : []).find(({ id }) => id === selectedProjectId))
    : null;
  const level = semanticZoomLevel(zoom, selected?.id ?? null);
  if (selected) {
    return {
      level,
      crumbs: ['Erde', 'Commons', selected.title ?? selected.id],
      summary: focusSpatialSummary(selected),
    };
  }
  const count = spatialIdentityCount(records);
  const countLabel = `${count} räumlich belegte Commons`;
  if (level === 'planet') return { level, crumbs: ['Erde', 'Gesamtansicht'], summary: countLabel };
  if (level === 'macroregion') return { level, crumbs: ['Erde', 'Großregion'], summary: `${countLabel} · regionale Zusammenhänge` };
  if (level === 'region') return { level, crumbs: ['Erde', 'Region'], summary: `${countLabel} · öffentliche Flächen und ungefähre Orte` };
  return { level, crumbs: ['Erde', 'Lokaler Zusammenhang'], summary: `${countLabel} · öffentliche Punkte, Flächen und Beziehungen` };
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
    const diameter = Math.max(stageWidth * 2.05, stageHeight * 2.25);
    return {
      x: rounded(stageWidth * 0.08, 2),
      y: rounded(stageHeight * 0.58, 2),
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
    diameter: rounded(globeDiameter * 1.32, 2),
    globeDiameter: rounded(globeDiameter, 2),
  };
}

export function digitalLayerCamera(camera = DEFAULT_CAMERA) {
  const bearing = finite(camera?.bearing, DEFAULT_CAMERA.bearing);
  const normalizedBearing = ((((bearing + 28) + 180) % 360) + 360) % 360 - 180;
  return {
    center: [
      clamp(finite(camera?.lng, DEFAULT_CAMERA.lng), -180, 180),
      clamp(finite(camera?.lat, DEFAULT_CAMERA.lat), -85, 85),
    ],
    zoom: clamp(Math.max(2.15, finite(camera?.zoom, DEFAULT_CAMERA.zoom) + 1.05), 0, DIGITAL_LAYER_MAX_ZOOM),
    bearing: rounded(normalizedBearing, 1),
    pitch: 58,
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
