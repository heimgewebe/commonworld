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

export function hasDigitalPresence(record) {
  return record?.presence?.digital?.available === true;
}

export function deriveLayer(record) {
  if (!hasDigitalPresence(record)) return null;
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

export const RING_ORBIT_MIN_DURATION_S = 24;
export const RING_ORBIT_MAX_DURATION_S = 96;
const RING_ORBIT_SATURATION_COUNT = 48;

export function ringOrbitDuration(entryCount) {
  const count = Number.isInteger(entryCount) && entryCount > 0 ? entryCount : 1;
  const boundedCount = clamp(count, 1, RING_ORBIT_SATURATION_COUNT);
  const scale = boundedCount === 1 ? 0 : Math.log(boundedCount) / Math.log(RING_ORBIT_SATURATION_COUNT);
  const seconds = RING_ORBIT_MIN_DURATION_S + (RING_ORBIT_MAX_DURATION_S - RING_ORBIT_MIN_DURATION_S) * scale;
  return rounded(clamp(seconds, RING_ORBIT_MIN_DURATION_S, RING_ORBIT_MAX_DURATION_S), 2);
}

export function ringOrbitDirection(ringIndex) {
  const index = Number.isInteger(ringIndex) && ringIndex >= 0 ? ringIndex : 0;
  return index % 2 === 0 ? 1 : -1;
}

export function ringOrbitStartAngle(ringIndex) {
  const index = Number.isInteger(ringIndex) && ringIndex >= 0 ? ringIndex : 0;
  return (index * 61) % 360;
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

export const INTENT_FILTER_VALUES = Object.freeze({
  presence: Object.freeze(['geographic', 'digital']),
  action: Object.freeze(['visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate']),
  access: Object.freeze(['public', 'membership', 'restricted', 'unknown']),
  freshness: Object.freeze(['current', 'stale', 'unknown']),
  curation: Object.freeze(['listed', 'verified', 'featured', 'unknown']),
});

const filterParameter = (parameters, name) => {
  const value = parameters.get(name);
  return INTENT_FILTER_VALUES[name]?.includes(value) ? value : null;
};

const languageFilterParameter = (parameters) => {
  const value = parameters.get('language');
  return value === 'unknown' || /^[a-z]{2,3}(?:-[A-Z]{2})?$/.test(value ?? '') ? value : null;
};

function normalizedPresenceFilters(values) {
  const requested = new Set(Array.isArray(values) ? values : []);
  return INTENT_FILTER_VALUES.presence.filter((value) => requested.has(value));
}

export function stateFromSearch(search = '', knownProjectIds = []) {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const known = new Set(knownProjectIds);
  const project = parameters.get('project');
  const layer = parameters.get('layer');
  const presence = normalizedPresenceFilters(parameters.getAll('presence'));
  return {
    camera: cameraFromSearch(search),
    project: project && known.has(project) ? project : null,
    layer: LAYERS.some((entry) => entry.id === layer) ? layer : null,
    view: parameters.get('view') === 'layers' ? 'layers' : 'globe',
    surface: parameters.get('surface') === 'text' ? 'text' : 'globe',
    query: normalizeQuery(parameters.get('q')),
    presence: Object.freeze(presence),
    action: filterParameter(parameters, 'action'),
    language: languageFilterParameter(parameters),
    access: filterParameter(parameters, 'access'),
    freshness: filterParameter(parameters, 'freshness'),
    curation: filterParameter(parameters, 'curation'),
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
  for (const name of ['action', 'access', 'freshness', 'curation']) {
    const value = state?.[name];
    if (INTENT_FILTER_VALUES[name].includes(value)) parameters.set(name, value);
  }
  for (const presence of normalizedPresenceFilters(state?.presence)) {
    parameters.append('presence', presence);
  }
  const language = state?.language;
  if (language === 'unknown' || /^[a-z]{2,3}(?:-[A-Z]{2})?$/.test(language ?? '')) {
    parameters.set('language', language);
  }
  return '?' + parameters.toString();
}

export const INTENT_SEARCH_RESULT_LIMIT = 50;
export const INTENT_SEARCH_CACHE_LIMIT = 128;

const ACTION_INTENT_TERMS = Object.freeze({
  use: Object.freeze(['nutzen', 'verwenden', 'ausprobieren']),
  learn: Object.freeze(['lernen', 'wissen', 'bildung', 'informieren']),
  contribute: Object.freeze(['mitmachen', 'beitragen', 'beteiligen']),
  volunteer: Object.freeze(['ehrenamt', 'ehrenamtlich', 'helfen']),
  donate: Object.freeze(['spenden', 'unterstützen']),
  visit: Object.freeze(['besuchen', 'vor ort']),
  contact: Object.freeze(['kontakt', 'kontaktieren']),
  replicate: Object.freeze(['nachmachen', 'übertragen', 'gründen']),
  borrow: Object.freeze(['ausleihen', 'leihen']),
});

const THEME_INTENT_TERMS = Object.freeze({
  knowledge: Object.freeze(['wissen']),
  'open-data': Object.freeze(['offene daten', 'freie daten']),
  research: Object.freeze(['forschung']),
  documentation: Object.freeze(['dokumentation']),
  'free-software': Object.freeze(['freie software']),
  'open-source': Object.freeze(['open source', 'quelloffen']),
  infrastructure: Object.freeze(['infrastruktur']),
  platform: Object.freeze(['plattform']),
  'open-media': Object.freeze(['offene medien', 'freie medien']),
  culture: Object.freeze(['kultur']),
  archives: Object.freeze(['archive', 'archiv']),
  'creative-commons': Object.freeze(['creative commons', 'freie inhalte']),
  education: Object.freeze(['bildung']),
  'open-educational-resources': Object.freeze(['freie bildungsmaterialien', 'offene lernmaterialien']),
  learning: Object.freeze(['lernen']),
  communication: Object.freeze(['kommunikation']),
  'community-network': Object.freeze(['gemeinschaftsnetz', 'community netz']),
  federation: Object.freeze(['föderation', 'föderiert']),
  protocol: Object.freeze(['protokoll']),
  housing: Object.freeze(['wohnen', 'wohnraum']),
  'community-land': Object.freeze(['gemeinschaftsland', 'gemeinschaftlicher boden']),
  'shared-space': Object.freeze(['gemeinschaftsraum', 'gemeinsamer raum']),
});

const PRESENCE_INTENT_TERMS = Object.freeze({
  digital: Object.freeze(['digital', 'online', 'ortsunabhängig']),
  geographic: Object.freeze(['geografisch', 'vor ort', 'lokal']),
});
const COMBINED_PRESENCE_INTENT_TERMS = Object.freeze(['beides', 'vor ort und digital']);

const FIELD_WEIGHTS = Object.freeze({
  title: 120,
  location: 100,
  action: 85,
  presence: 70,
  theme: 65,
  digital: 55,
  summary: 45,
  link: 35,
});

export function normalizeSearchText(value) {
  return String(value ?? '')
    .toLocaleLowerCase('de')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .replace(/&/g, ' und ')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

export function searchTokens(value) {
  const normalized = normalizeSearchText(value);
  return normalized ? normalized.split(' ') : [];
}

function validPosition(value) {
  return Array.isArray(value)
    && value.length === 2
    && value.every((number) => Number.isFinite(number))
    && value[0] >= -180 && value[0] <= 180
    && value[1] >= -90 && value[1] <= 90;
}

function validLinearRing(value) {
  return Array.isArray(value)
    && value.length >= 4
    && value.every(validPosition)
    && value[0][0] === value.at(-1)[0]
    && value[0][1] === value.at(-1)[1];
}

function validGeometryCoordinates(type, coordinates) {
  if (type === 'Point') return validPosition(coordinates);
  if (type === 'Polygon') return Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(validLinearRing);
  if (type === 'MultiPolygon') {
    return Array.isArray(coordinates)
      && coordinates.length > 0
      && coordinates.every((polygon) => Array.isArray(polygon) && polygon.length > 0 && polygon.every(validLinearRing));
  }
  return false;
}

export function publicGeographicRepresentationKind(location) {
  if (!location || typeof location !== 'object' || location.mode === 'hidden') return null;
  const type = location?.geometry?.type;
  const coordinates = location?.geometry?.coordinates;
  if (!validGeometryCoordinates(type, coordinates)) return null;
  if (location.mode === 'approximate') {
    return type === 'Point' && Number.isFinite(location.uncertainty_meters_min) && location.uncertainty_meters_min > 0
      ? 'approximate_zone'
      : null;
  }
  if (location.mode !== 'exact') return null;
  if (type === 'Point') return 'exact_anchor';
  if (type === 'Polygon' || type === 'MultiPolygon') return 'public_extent';
  return null;
}

export function publicGeographicLocations(record) {
  const locations = record?.presence?.geographic;
  return Array.isArray(locations)
    ? locations.filter((location) => publicGeographicRepresentationKind(location) !== null)
    : [];
}

function vocabularyValues(value, vocabulary) {
  return [value, ...(vocabulary[value] ?? [])];
}

function recordSearchFields(record) {
  const fields = [];
  const append = (field, reason, values) => {
    const clean = values.flat().filter((value) => typeof value === 'string' && value.trim());
    if (clean.length) fields.push({ field, reason, values: clean });
  };
  append('title', 'Name', [record?.title]);
  append('summary', 'Beschreibung', [record?.summary]);
  append('theme', 'Thema', (record?.themes ?? []).flatMap((theme) => vocabularyValues(theme, THEME_INTENT_TERMS)));
  append('action', 'Möglichkeit', (record?.actions ?? []).flatMap((action) => vocabularyValues(action, ACTION_INTENT_TERMS)));

  const geographicLocations = publicGeographicLocations(record);
  const isGeographic = geographicLocations.length > 0;
  const isDigital = hasDigitalPresence(record);
  const axes = [];
  if (isGeographic) axes.push('geographic');
  if (isDigital) axes.push('digital');
  const presenceTerms = axes.flatMap((axis) => vocabularyValues(axis, PRESENCE_INTENT_TERMS));
  if (isGeographic && isDigital) presenceTerms.push(...COMBINED_PRESENCE_INTENT_TERMS);
  append('presence', 'Präsenz', presenceTerms);

  append('location', 'Ort', geographicLocations.map(({ label }) => label));
  append('digital', 'Digitale Präsenz', [record?.presence?.digital?.label, record?.presence?.digital?.reach]);
  append('link', 'Offizieller Link', (record?.links ?? []).map(({ label, type }) => [label, type]));
  return fields;
}

function recordLanguageValues(record) {
  if (Array.isArray(record?.languages)) return record.languages.filter((value) => typeof value === 'string');
  return Array.isArray(record?.languages?.codes) ? record.languages.codes.filter((value) => typeof value === 'string') : [];
}

function recordAccessValue(record) {
  if (typeof record?.access === 'string') return record.access;
  return typeof record?.access?.type === 'string' ? record.access.type : null;
}

function recordFreshness(record, today) {
  const nextReview = record?.curation?.next_review_at;
  const activity = record?.activity?.status;
  if (typeof nextReview !== 'string' || typeof activity !== 'string') return 'unknown';
  if (nextReview < today || !['active', 'seasonal'].includes(activity)) return 'stale';
  return 'current';
}

export function recordMatchesIntentFilters(record, filters = {}, today = new Date().toISOString().slice(0, 10)) {
  if (filters.layer && deriveLayer(record) !== filters.layer) return false;

  if (Array.isArray(filters.presence) && filters.presence.length > 0) {
    if (filters.presence.includes('geographic') && publicGeographicLocations(record).length === 0) return false;
    if (filters.presence.includes('digital') && !hasDigitalPresence(record)) return false;
  }

  if (filters.action && !(record?.actions ?? []).includes(filters.action)) return false;
  if (filters.language) {
    const languages = recordLanguageValues(record);
    if (filters.language === 'unknown' ? languages.length !== 0 : !languages.includes(filters.language)) return false;
  }
  if (filters.access) {
    const access = recordAccessValue(record);
    if (filters.access === 'unknown' ? access !== null : access !== filters.access) return false;
  }
  if (filters.freshness && recordFreshness(record, today) !== filters.freshness) return false;
  if (filters.curation && record?.curation?.state !== filters.curation) return false;
  return true;
}

function lowerBound(values, target) {
  let low = 0;
  let high = values.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (values[middle] < target) low = middle + 1;
    else high = middle;
  }
  return low;
}

function freezeSearchResult(result) {
  return Object.freeze({
    ...result,
    reasons: Object.freeze([...result.reasons]),
  });
}

export function prepareIntentSearchIndex(records, { cacheLimit = INTENT_SEARCH_CACHE_LIMIT } = {}) {
  const sourceRecords = Array.isArray(records) ? records : [];
  const recordsById = new Map(sourceRecords.map((record) => [record.id, record]));
  const postings = new Map();
  const normalizedTitles = new Map();
  const boundedCacheLimit = Math.max(1, Number.isInteger(cacheLimit) ? cacheLimit : INTENT_SEARCH_CACHE_LIMIT);
  const cache = new Map();

  for (const record of sourceRecords) {
    normalizedTitles.set(record.id, normalizeSearchText(record.title));
    for (const { field, reason, values } of recordSearchFields(record)) {
      const weight = FIELD_WEIGHTS[field] ?? 1;
      const uniqueTokens = new Set(values.flatMap(searchTokens));
      for (const token of uniqueTokens) {
        let byProject = postings.get(token);
        if (!byProject) {
          byProject = new Map();
          postings.set(token, byProject);
        }
        const previous = byProject.get(record.id);
        if (!previous || previous.score < weight) byProject.set(record.id, Object.freeze({ score: weight, reason }));
      }
    }
  }

  const sortedTerms = Object.freeze([...postings.keys()].sort());

  const postingsForToken = (token) => {
    const exact = postings.get(token);
    if (exact) return exact;
    if (token.length < 2) return null;
    const combined = new Map();
    for (let index = lowerBound(sortedTerms, token); index < sortedTerms.length; index += 1) {
      const term = sortedTerms[index];
      if (!term.startsWith(token)) break;
      for (const [identifier, match] of postings.get(term)) {
        const previous = combined.get(identifier);
        if (!previous || previous.score < match.score) combined.set(identifier, match);
      }
    }
    return combined.size ? combined : null;
  };

  const search = ({ query = '', filters = {}, limit = INTENT_SEARCH_RESULT_LIMIT, today = new Date().toISOString().slice(0, 10) } = {}) => {
    const normalizedQuery = normalizeSearchText(query);
    const boundedLimit = Math.max(1, Math.min(200, Number.isInteger(limit) ? limit : INTENT_SEARCH_RESULT_LIMIT));
    const cacheKey = JSON.stringify([normalizedQuery, filters, boundedLimit, today]);
    if (cache.has(cacheKey)) return cache.get(cacheKey);

    const queryGroups = [];
    for (const token of [...new Set(searchTokens(normalizedQuery))]) {
      const group = postingsForToken(token);
      if (group) queryGroups.push(group);
    }

    let candidates = null;
    if (normalizedQuery && queryGroups.length === 0) candidates = new Map();
    else if (queryGroups.length) {
      candidates = new Map([...queryGroups[0]].map(([identifier, match]) => [identifier, { score: match.score, reasons: new Set([match.reason]) }]));
      for (const group of queryGroups.slice(1)) {
        for (const [identifier, candidate] of candidates) {
          const match = group.get(identifier);
          if (!match) candidates.delete(identifier);
          else {
            candidate.score += match.score;
            candidate.reasons.add(match.reason);
          }
        }
      }
    }

    const selectedRecords = candidates === null
      ? sourceRecords.map((record) => ({ record, score: 0, reasons: new Set() }))
      : [...candidates].map(([identifier, candidate]) => ({ record: recordsById.get(identifier), ...candidate }));

    const results = selectedRecords
      .filter(({ record }) => record && recordMatchesIntentFilters(record, filters, today))
      .map(({ record, score, reasons }) => {
        const title = normalizedTitles.get(record.id) ?? '';
        const phraseBonus = normalizedQuery && title === normalizedQuery ? 300 : (normalizedQuery && title.startsWith(normalizedQuery) ? 160 : 0);
        return freezeSearchResult({ id: record.id, record, score: score + phraseBonus, reasons: [...reasons] });
      })
      .sort((left, right) => right.score - left.score || left.record.title.localeCompare(right.record.title, 'de') || left.id.localeCompare(right.id))
      .slice(0, boundedLimit);

    const frozen = Object.freeze(results);
    cache.set(cacheKey, frozen);
    if (cache.size > boundedCacheLimit) cache.delete(cache.keys().next().value);
    return frozen;
  };

  return Object.freeze({
    indexedRecordCount: sourceRecords.length,
    indexedTermCount: postings.size,
    cacheLimit: boundedCacheLimit,
    recordsById,
    search,
    matchingRecords(options = {}) {
      return Object.freeze(search(options).map(({ record }) => record));
    },
    cacheSize() {
      return cache.size;
    },
  });
}

export function filterRecords(records, state = {}) {
  if (state.searchIndex?.matchingRecords) {
    return state.searchIndex.matchingRecords({
      query: state.query,
      filters: {
        layer: state.layer ?? null,
        presence: state.presence ?? null,
        action: state.action ?? null,
        language: state.language ?? null,
        access: state.access ?? null,
        freshness: state.freshness ?? null,
        curation: state.curation ?? null,
      },
      limit: Math.max(INTENT_SEARCH_RESULT_LIMIT, state.limit ?? INTENT_SEARCH_RESULT_LIMIT),
      today: state.today,
    });
  }
  const query = normalizeSearchText(normalizeQuery(state.query));
  return (Array.isArray(records) ? records : []).filter((record) => {
    if (!recordMatchesIntentFilters(record, state, state.today)) return false;
    if (!query) return true;
    return recordSearchFields(record).some(({ values }) => normalizeSearchText(values.join(' ')).includes(query));
  });
}

export function recordPresentationLabel(record) {
  const isGeo = publicGeographicLocations(record).length > 0;
  const isDigital = hasDigitalPresence(record);
  const layer = deriveLayer(record);
  const digitalLabel = `Digital${layer ? ` · ${LAYERS.find(({ id }) => id === layer)?.label ?? 'Digitale Commons'}` : ''}`;

  if (isGeo && isDigital) return `Vor Ort · ${digitalLabel}`;
  if (isGeo) return 'Vor Ort';
  if (isDigital) return digitalLabel;
  return 'Commons';
}



function cloneCoordinates(value) {
  return Array.isArray(value) ? value.map(cloneCoordinates) : value;
}

const EARTH_RADIUS_METERS = 6371008.8;
const UNCERTAINTY_ZONE_VERTEX_COUNT = 64;
export const PUBLIC_MAP_COLLECTION_CACHE_LIMIT = 64;
const EMPTY_CATALOG_RECORDS = Object.freeze([]);
const catalogProjectionCache = new WeakMap();

function freezeCatalogSnapshot(value) {
  if (!value || typeof value !== 'object') return value;
  const pending = [value];
  const seen = new WeakSet();
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current || typeof current !== 'object' || seen.has(current)) continue;
    seen.add(current);
    for (const child of Object.values(current)) {
      if (child && typeof child === 'object') pending.push(child);
    }
    Object.freeze(current);
  }
  return value;
}

export function geodesicDistanceMeters(origin, destination) {
  if (!Array.isArray(origin) || origin.length !== 2 || !origin.every(Number.isFinite)) return Number.NaN;
  if (!Array.isArray(destination) || destination.length !== 2 || !destination.every(Number.isFinite)) return Number.NaN;
  const radians = Math.PI / 180;
  const originLatitude = origin[1] * radians;
  const destinationLatitude = destination[1] * radians;
  const latitudeDelta = (destination[1] - origin[1]) * radians;
  const longitudeDelta = (destination[0] - origin[0]) * radians;
  const haversine = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(originLatitude) * Math.cos(destinationLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(clamp(haversine, 0, 1)));
}

function approximateUncertaintyZone(location) {
  const center = location?.geometry?.coordinates;
  const radiusMeters = finite(location?.uncertainty_meters_min, 0);
  if (!Array.isArray(center) || center.length !== 2 || !center.every(Number.isFinite) || radiusMeters <= 0) return null;
  const longitude = center[0] * Math.PI / 180;
  const latitude = center[1] * Math.PI / 180;
  const angularDistance = radiusMeters / EARTH_RADIUS_METERS;
  const ring = [];
  for (let index = 0; index < UNCERTAINTY_ZONE_VERTEX_COUNT; index += 1) {
    const bearing = 2 * Math.PI * index / UNCERTAINTY_ZONE_VERTEX_COUNT;
    const targetLatitude = Math.asin(
      Math.sin(latitude) * Math.cos(angularDistance)
      + Math.cos(latitude) * Math.sin(angularDistance) * Math.cos(bearing),
    );
    const targetLongitude = longitude + Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude),
      Math.cos(angularDistance) - Math.sin(latitude) * Math.sin(targetLatitude),
    );
    const longitudeDegrees = ((targetLongitude * 180 / Math.PI + 540) % 360) - 180;
    ring.push([longitudeDegrees, targetLatitude * 180 / Math.PI]);
  }
  ring.push([...ring[0]]);
  return { type: 'Polygon', coordinates: [ring] };
}

function publicGeometry(location, representationKind) {
  if (representationKind === 'approximate_zone') return approximateUncertaintyZone(location);
  return {
    type: location.geometry.type,
    coordinates: cloneCoordinates(location.geometry.coordinates),
  };
}

function publicMapFeature(record, location) {
  const representationKind = publicGeographicRepresentationKind(location);
  if (!representationKind) return null;
  return Object.freeze({
    type: 'Feature',
    id: record.id + ':' + location.id,
    geometry: freezeCatalogSnapshot(publicGeometry(location, representationKind)),
    properties: Object.freeze({
      project_id: record.id,
      location_id: location.id,
      title: record.title ?? record.id,
      location_label: location.label ?? record.title ?? record.id,
      location_mode: location.mode,
      representation_kind: representationKind,
      uncertainty_meters_min: location.mode === 'approximate' ? finite(location.uncertainty_meters_min, 0) : 0,
    }),
  });
}

function featureCollection(features) {
  return Object.freeze({ type: 'FeatureCollection', features: Object.freeze(features) });
}

function buildEvidencedRelations(records, recordsById) {
  const relations = [];
  for (const record of records) {
    for (const relation of Array.isArray(record?.relations) ? record.relations : []) {
      const target = recordsById.get(relation?.target_id);
      if (!target || !Array.isArray(relation?.source_ids) || relation.source_ids.length === 0) continue;
      relations.push(Object.freeze({
        source_project_id: record.id,
        source_title: record.title ?? record.id,
        target_project_id: target.id,
        target_title: target.title ?? target.id,
        relation_type: relation.type,
        source_ids: Object.freeze([...relation.source_ids]),
        note: relation.note ?? '',
      }));
    }
  }
  return Object.freeze(relations);
}

function buildCatalogProjection(records) {
  const recordsById = new Map(records.filter((record) => record?.id).map((record) => [record.id, record]));
  const projectIds = records.filter((record) => record?.id).map((record) => record.id);
  const featuresByProjectId = new Map();
  const allFeatures = [];
  for (const record of records) {
    if (!record?.id) continue;
    const projectFeatures = [];
    const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
    for (const location of locations) {
      if (!location || location.mode === 'hidden' || !location.geometry) continue;
      const feature = publicMapFeature(record, location);
      if (!feature) continue;
      projectFeatures.push(feature);
      allFeatures.push(feature);
    }
    featuresByProjectId.set(record.id, Object.freeze(projectFeatures));
  }

  const collections = new Map([['*', featureCollection(allFeatures)]]);
  const relations = buildEvidencedRelations(records, recordsById);

  function collectionFor(visibleProjectIds = null) {
    if (visibleProjectIds === null || visibleProjectIds === undefined) return collections.get('*');
    const requested = visibleProjectIds instanceof Set
      ? visibleProjectIds
      : new Set(Array.isArray(visibleProjectIds) ? visibleProjectIds : []);
    const visibleIds = projectIds.filter((identifier) => requested.has(identifier));
    const key = 'ids:' + visibleIds.join('\u001f');
    const cached = collections.get(key);
    if (cached) {
      collections.delete(key);
      collections.set(key, cached);
      return cached;
    }
    const features = visibleIds.flatMap((identifier) => featuresByProjectId.get(identifier) ?? []);
    const collection = featureCollection(features);
    while (collections.size >= PUBLIC_MAP_COLLECTION_CACHE_LIMIT) {
      const oldest = [...collections.keys()].find((candidate) => candidate !== '*');
      if (!oldest) break;
      collections.delete(oldest);
    }
    collections.set(key, collection);
    return collection;
  }

  return Object.freeze({
    recordsById,
    relations,
    publicMapFeatureCollection: collectionFor,
  });
}

export function prepareCatalogProjection(records) {
  const values = Array.isArray(records) ? records : EMPTY_CATALOG_RECORDS;
  let projection = catalogProjectionCache.get(values);
  if (!projection) {
    freezeCatalogSnapshot(values);
    projection = buildCatalogProjection(values);
    catalogProjectionCache.set(values, projection);
  }
  return projection;
}

export function publicMapFeatureCollection(records, visibleProjectIds = null) {
  return prepareCatalogProjection(records).publicMapFeatureCollection(visibleProjectIds);
}

export function publicProjectNavigationTarget(publicMapData, projectId) {
  const features = Array.isArray(publicMapData?.features) ? publicMapData.features : [];
  const coordinates = [];
  const collect = (value) => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && Number.isFinite(Number(value[0])) && Number.isFinite(Number(value[1]))) {
      coordinates.push([Number(value[0]), Number(value[1])]);
      return;
    }
    for (const nested of value) collect(nested);
  };
  for (const feature of features) {
    if (feature?.properties?.project_id !== projectId) continue;
    collect(feature?.geometry?.coordinates);
  }
  if (coordinates.length === 0) return null;
  let west = coordinates[0][0];
  let east = coordinates[0][0];
  let south = coordinates[0][1];
  let north = coordinates[0][1];
  for (const [longitude, latitude] of coordinates.slice(1)) {
    west = Math.min(west, longitude);
    east = Math.max(east, longitude);
    south = Math.min(south, latitude);
    north = Math.max(north, latitude);
  }
  if (west === east && south === north) {
    return Object.freeze({ kind: 'point', center: Object.freeze([west, south]), zoom: 15 });
  }
  return Object.freeze({
    kind: 'bounds',
    bounds: Object.freeze([
      Object.freeze([west, south]),
      Object.freeze([east, north]),
    ]),
  });
}

export function evidencedRelations(records) {
  return prepareCatalogProjection(records).relations;
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
  return (Array.isArray(records) ? records : []).filter((record) => publicGeographicLocations(record).length > 0).length;
}

function focusSpatialSummary(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  const publicLocations = publicGeographicLocations(record);
  const isGeo = publicLocations.length > 0;
  const isDigital = hasDigitalPresence(record);
  if (isDigital && locations.length === 0) return 'Digital · Ortsunabhängige digitale Präsenz';

  const visible = publicLocations.length;
  const hidden = locations.filter((location) => location?.mode === 'hidden').length;

  let presenceLabel = 'Commons';
  if (isGeo && isDigital) presenceLabel = 'Vor Ort · Digital';
  else if (isGeo) presenceLabel = 'Vor Ort';
  else if (isDigital) presenceLabel = 'Digital';
  else if (hidden > 0) presenceLabel = 'Verborgene Orte';

  if (visible === 0) return `${presenceLabel} · ${hidden} ${hidden === 1 ? 'verborgener Ort' : 'verborgene Orte'}`;

  const publicLabel = `${visible} ${visible === 1 ? 'öffentlicher Ort' : 'öffentliche Orte'}`;
  const hiddenLabel = `${hidden} ${hidden === 1 ? 'verborgener Ort' : 'verborgene Orte'}`;
  return hidden ? `${presenceLabel} · ${publicLabel} · ${hiddenLabel}` : `${presenceLabel} · ${publicLabel}`;
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
