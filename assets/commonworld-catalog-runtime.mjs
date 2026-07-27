const MANIFEST_URL = './catalog/runtime/manifest.v1.json';
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const SHARD_KEY_PATTERN = /^[0-9a-f]{2}$/;
const IDENTITY_PATTERN = /^[a-z][a-z0-9-]{2,95}$/;
const THEME_PATTERN = /^[a-z][a-z0-9-]{1,63}$/;
const LANGUAGE_PATTERN = /^[a-z]{2,3}(?:-[A-Z]{2})?$/;
const ACTION_VALUES = new Set(['visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate']);
const ACCESS_VALUES = new Set(['public', 'membership', 'restricted']);
const ACTIVITY_VALUES = new Set(['active', 'paused', 'seasonal', 'unknown', 'ended']);
const DETAIL_RECORD_KEYS = new Set(['schema_version', 'id', 'title', 'summary', 'themes', 'actions', 'presence', 'relations', 'provenance', 'curation', 'links', 'handoff', 'activity', 'languages', 'access']);

function assertObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} is not an object`);
  return value;
}

function assertDescriptor(value, label) {
  const descriptor = assertObject(value, label);
  if (!Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 0) throw new Error(`${label} has invalid byte length`);
  if (typeof descriptor.sha256 !== 'string' || !SHA256_PATTERN.test(descriptor.sha256)) throw new Error(`${label} has invalid SHA-256`);
  if (typeof descriptor.url !== 'string' || !descriptor.url) throw new Error(`${label} has invalid URL`);
  return descriptor;
}

function assertString(value, label) {
  if (typeof value !== 'string' || !value || value.trim() !== value) throw new Error(`${label} is not a non-empty trimmed string`);
  return value;
}

function assertBoundedString(value, label, { minLength = 1, maxLength = Infinity, pattern = null } = {}) {
  assertString(value, label);
  const length = [...value].length;
  if (length < minLength || length > maxLength) throw new Error(`${label} has invalid length`);
  if (pattern && !pattern.test(value)) throw new Error(`${label} has invalid format`);
  return value;
}

function assertStringArray(value, label, { minItems = 0, maxItems = Infinity, pattern = null, allowed = null } = {}) {
  if (!Array.isArray(value) || value.length < minItems || value.length > maxItems) throw new Error(`${label} has invalid item count`);
  const seen = new Set();
  for (const item of value) {
    assertString(item, `${label} item`);
    if (pattern && !pattern.test(item)) throw new Error(`${label} contains an invalid value`);
    if (allowed && !allowed.has(item)) throw new Error(`${label} contains an unsupported value`);
    if (seen.has(item)) throw new Error(`${label} contains a duplicate value`);
    seen.add(item);
  }
  return value;
}

function assertExactKeys(value, allowedKeys, label) {
  for (const key of Object.keys(value)) {
    if (!allowedKeys.has(key)) throw new Error(`${label} contains an unexpected field`);
  }
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, '0')).join('');
}

function documentRootFor(manifestUrl) {
  const fallback = 'http://localhost/';
  const pageUrl = new URL(globalThis.location?.href ?? fallback);
  const manifestAbsolute = new URL(manifestUrl, pageUrl);
  const documentRoot = globalThis.location?.href ? new URL('./', pageUrl) : new URL('/', manifestAbsolute);
  return { documentRoot, manifestAbsolute };
}

function resolveCatalogUrl(relativeUrl, documentRoot, label) {
  const resolved = new URL(relativeUrl, documentRoot);
  if (resolved.origin !== documentRoot.origin) throw new Error(`${label} must remain same-origin`);
  if (!resolved.pathname.startsWith(documentRoot.pathname)) throw new Error(`${label} escapes the document root`);
  return resolved.href;
}

function validateShardIndex(index, label, knownShardKeys) {
  assertObject(index, label);
  for (const [value, keys] of Object.entries(index)) {
    if (!value || !Array.isArray(keys)) throw new Error(`${label} contains an invalid entry`);
    const seen = new Set();
    for (const key of keys) {
      if (typeof key !== 'string' || !SHARD_KEY_PATTERN.test(key) || !knownShardKeys.has(key)) {
        throw new Error(`${label} references an unknown shard`);
      }
      if (seen.has(key)) throw new Error(`${label} contains a duplicate shard`);
      seen.add(key);
    }
  }
}

function validateDetailsManifest(value, manifest) {
  const details = assertObject(value, 'manifest details');
  assertExactKeys(details, new Set(['strategy', 'descriptor_version', 'url_template', 'entry_count', 'detail_set_sha256', 'project_schema_version']), 'manifest details');
  if (details.strategy !== 'content-addressed-shard-descriptors') throw new Error('unsupported catalog detail strategy');
  if (details.descriptor_version !== '1.0') throw new Error('unsupported catalog detail descriptor');
  if (details.url_template !== 'catalog/runtime/details/{sha256}.v1.json') throw new Error('unsupported catalog detail URL template');
  if (!Number.isSafeInteger(details.entry_count) || details.entry_count !== manifest.entry_count) throw new Error('catalog detail entry count mismatch');
  if (typeof details.detail_set_sha256 !== 'string' || !SHA256_PATTERN.test(details.detail_set_sha256)) throw new Error('invalid catalog detail set hash');
  if (details.project_schema_version !== 4) throw new Error('unsupported catalog project schema');
  return details;
}

function validateManifest(value) {
  const manifest = assertObject(value, 'manifest');
  if (manifest.kind !== 'commonworld.catalog_runtime_manifest' || manifest.version !== '1.0') throw new Error('unsupported catalog manifest');
  if (typeof manifest.generation !== 'string' || !SHA256_PATTERN.test(manifest.generation)) throw new Error('invalid catalog generation');
  if (!Number.isSafeInteger(manifest.entry_count) || manifest.entry_count < 0) throw new Error('invalid catalog entry count');
  if (typeof manifest.source_catalog_sha256 !== 'string' || !SHA256_PATTERN.test(manifest.source_catalog_sha256)) throw new Error('invalid source catalog hash');
  assertDescriptor(manifest.world_index, 'manifest world index descriptor');
  assertDescriptor(manifest.aggregate, 'manifest aggregate descriptor');
  validateDetailsManifest(manifest.details, manifest);
  const shards = assertObject(manifest.shards, 'manifest shards');
  if (shards.strategy !== 'sha256-prefix' || shards.prefix_length !== 2 || !Array.isArray(shards.entries)) throw new Error('unsupported catalog shard strategy');
  const shardKeys = new Set();
  const shardDescriptors = new Map();
  for (const entry of shards.entries) {
    const descriptor = assertDescriptor(entry, 'manifest shard descriptor');
    if (typeof entry.key !== 'string' || !SHARD_KEY_PATTERN.test(entry.key) || shardKeys.has(entry.key)) throw new Error('invalid or duplicate catalog shard key');
    if (!Number.isSafeInteger(entry.entry_count) || entry.entry_count < 1) throw new Error('invalid catalog shard entry count');
    shardKeys.add(entry.key);
    shardDescriptors.set(entry.key, descriptor);
  }
  const shardEntryCount = [...shardDescriptors.values()].reduce((sum, descriptor) => sum + descriptor.entry_count, 0);
  if (shardEntryCount !== manifest.entry_count) throw new Error('catalog manifest shard entry count sum mismatch');
  return { manifest, shardKeys, shardDescriptors };
}

function validateAggregate(value, manifest, shardKeys) {
  const aggregate = assertObject(value, 'aggregate');
  if (aggregate.kind !== 'commonworld.catalog_aggregate' || aggregate.version !== '1.0') throw new Error('unsupported catalog aggregate');
  if (!Number.isSafeInteger(aggregate.entry_count) || aggregate.entry_count !== manifest.entry_count) throw new Error('catalog aggregate entry count mismatch');
  if (aggregate.source_catalog_sha256 !== manifest.source_catalog_sha256) throw new Error('catalog aggregate source mismatch');
  if (!Number.isSafeInteger(aggregate.spatial_cell_degrees) || aggregate.spatial_cell_degrees <= 0 || 360 % aggregate.spatial_cell_degrees !== 0 || 180 % aggregate.spatial_cell_degrees !== 0) throw new Error('invalid aggregate spatial cell size');
  validateShardIndex(aggregate.themes, 'aggregate themes', shardKeys);
  validateShardIndex(aggregate.spatial_cells, 'aggregate spatial cells', shardKeys);
  validateShardIndex(aggregate.digital, 'aggregate digital index', shardKeys);
  return aggregate;
}

function validatePosition(value, label) {
  if (!Array.isArray(value) || value.length !== 2) throw new Error(`${label} is not a longitude-latitude position`);
  const [longitude, latitude] = value;
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) throw new Error(`${label} has invalid longitude`);
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) throw new Error(`${label} has invalid latitude`);
  return value;
}

function positionsEqual(left, right) {
  return left[0] === right[0] && left[1] === right[1];
}

function validateLinearRing(value, label) {
  if (!Array.isArray(value) || value.length < 4) throw new Error(`${label} is not a valid linear ring`);
  value.forEach((position, index) => validatePosition(position, `${label} position ${index}`));
  if (!positionsEqual(value[0], value.at(-1))) throw new Error(`${label} is not closed`);
  return value;
}

function validatePolygonCoordinates(value, label) {
  if (!Array.isArray(value) || value.length < 1) throw new Error(`${label} is not a polygon coordinate array`);
  value.forEach((ring, index) => validateLinearRing(ring, `${label} ring ${index}`));
  return value;
}

function validateCompactGeometry(value, label) {
  const geometry = assertObject(value, label);
  assertExactKeys(geometry, new Set(['type', 'coordinates']), label);
  if (geometry.type === 'Point') validatePosition(geometry.coordinates, `${label} coordinates`);
  else if (geometry.type === 'Polygon') validatePolygonCoordinates(geometry.coordinates, `${label} coordinates`);
  else if (geometry.type === 'MultiPolygon') {
    if (!Array.isArray(geometry.coordinates) || geometry.coordinates.length < 1) throw new Error(`${label} is not a multipolygon coordinate array`);
    geometry.coordinates.forEach((polygon, index) => validatePolygonCoordinates(polygon, `${label} polygon ${index}`));
  } else {
    throw new Error(`${label} has unsupported geometry type`);
  }
  return geometry;
}

function validateDetailDescriptor(value, label, identifier, generation) {
  const descriptor = assertDescriptor(value, label);
  assertExactKeys(descriptor, new Set(['version', 'identity', 'generation', 'url', 'sha256', 'bytes']), label);
  if (descriptor.version !== '1.0') throw new Error(`${label} has unsupported version`);
  if (descriptor.identity !== identifier) throw new Error(`${label} identity mismatch`);
  if (descriptor.generation !== generation) throw new Error(`${label} generation mismatch`);
  if (descriptor.url !== `catalog/runtime/details/${descriptor.sha256}.v1.json`) throw new Error(`${label} has invalid content-addressed URL`);
  return descriptor;
}

function validateCompactRecord(value, label, generation) {
  const record = assertObject(value, label);
  assertExactKeys(record, new Set(['id', 'title', 'themes', 'actions', 'languages', 'access', 'presence', 'activity', 'detail']), label);
  assertBoundedString(record.id, `${label} id`, { minLength: 3, maxLength: 96, pattern: IDENTITY_PATTERN });
  assertBoundedString(record.title, `${label} title`, { minLength: 2, maxLength: 140 });
  assertStringArray(record.themes, `${label} themes`, { minItems: 1, maxItems: 8, pattern: THEME_PATTERN });
  assertStringArray(record.actions, `${label} actions`, { minItems: 1, allowed: ACTION_VALUES });
  assertStringArray(record.languages, `${label} languages`, { pattern: LANGUAGE_PATTERN });
  if (record.access !== null && !ACCESS_VALUES.has(record.access)) throw new Error(`${label} has invalid access type`);
  if (!ACTIVITY_VALUES.has(record.activity)) throw new Error(`${label} has invalid activity status`);
  validateDetailDescriptor(record.detail, `${label} detail`, record.id, generation);
  const presence = assertObject(record.presence, `${label} presence`);
  assertExactKeys(presence, new Set(['geographic', 'digital']), `${label} presence`);
  if (typeof presence.digital !== 'boolean') throw new Error(`${label} digital presence is not boolean`);
  if (!Array.isArray(presence.geographic)) throw new Error(`${label} geographic presence is not an array`);
  for (const [index, locationValue] of presence.geographic.entries()) {
    const locationLabel = `${label} geographic presence ${index}`;
    const location = assertObject(locationValue, locationLabel);
    assertExactKeys(location, new Set(['mode', 'geometry']), locationLabel);
    if (!['exact', 'approximate'].includes(location.mode)) throw new Error(`${locationLabel} has invalid mode`);
    validateCompactGeometry(location.geometry, `${locationLabel} geometry`);
  }
  return record;
}

function validateCatalogShard(value, descriptor, key, manifest) {
  const shard = assertObject(value, 'catalog shard');
  assertExactKeys(shard, new Set(['kind', 'version', 'key', 'records']), 'catalog shard');
  if (shard.kind !== 'commonworld.catalog_shard' || shard.version !== '1.0') throw new Error('unsupported catalog shard');
  if (shard.key !== key) throw new Error('catalog shard key mismatch');
  if (!Array.isArray(shard.records)) throw new Error('catalog shard records are not an array');
  if (shard.records.length !== descriptor.entry_count) throw new Error('catalog shard entry count mismatch');
  const ids = new Set();
  for (const [index, recordValue] of shard.records.entries()) {
    const record = validateCompactRecord(recordValue, `catalog shard record ${index}`, manifest.generation);
    if (ids.has(record.id)) throw new Error('catalog shard contains duplicate identity');
    ids.add(record.id);
  }
  return shard;
}

function publicGeographicProjection(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} is not an array`);
  const result = [];
  for (const [index, locationValue] of value.entries()) {
    const location = assertObject(locationValue, `${label} ${index}`);
    if (!['exact', 'approximate', 'hidden'].includes(location.mode)) throw new Error(`${label} ${index} has invalid mode`);
    if (location.mode === 'hidden') {
      if ('geometry' in location) throw new Error(`${label} ${index} exposes hidden geometry`);
      continue;
    }
    validateCompactGeometry(location.geometry, `${label} ${index} geometry`);
    result.push({ mode: location.mode, geometry: location.geometry });
  }
  return result;
}

function detailProjection(record, label) {
  const presence = assertObject(record.presence, `${label} presence`);
  const digital = assertObject(presence.digital, `${label} digital presence`);
  if (typeof digital.available !== 'boolean') throw new Error(`${label} digital availability is not boolean`);
  const activity = assertObject(record.activity, `${label} activity`);
  if (!ACTIVITY_VALUES.has(activity.status)) throw new Error(`${label} has invalid activity status`);
  const languages = record.languages == null
    ? []
    : assertStringArray(assertObject(record.languages, `${label} languages`).codes, `${label} language codes`, { pattern: LANGUAGE_PATTERN });
  const access = record.access == null
    ? null
    : assertObject(record.access, `${label} access`).type;
  if (access !== null && !ACCESS_VALUES.has(access)) throw new Error(`${label} has invalid access type`);
  return {
    id: record.id,
    title: record.title,
    themes: record.themes,
    actions: record.actions,
    languages,
    access,
    presence: {
      geographic: publicGeographicProjection(presence.geographic, `${label} geographic presence`),
      digital: digital.available,
    },
    activity: activity.status,
  };
}

function stableComparisonValue(value) {
  if (Array.isArray(value)) return value.map(stableComparisonValue);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, stableComparisonValue(value[key])]),
  );
}

function stableComparisonJson(value) {
  return JSON.stringify(stableComparisonValue(value));
}

function compactProjection(record) {
  return {
    id: record.id,
    title: record.title,
    themes: record.themes,
    actions: record.actions,
    languages: record.languages,
    access: record.access,
    presence: record.presence,
    activity: record.activity,
  };
}

function validateCatalogDetail(value, compactRecordValue) {
  const detail = assertObject(value, 'catalog detail');
  assertExactKeys(detail, DETAIL_RECORD_KEYS, 'catalog detail');
  if (detail.schema_version !== 4) throw new Error('catalog detail uses an unsupported project schema');
  assertBoundedString(detail.id, 'catalog detail id', { minLength: 3, maxLength: 96, pattern: IDENTITY_PATTERN });
  if (detail.id !== compactRecordValue.id) throw new Error('catalog detail identity mismatch');
  assertBoundedString(detail.title, 'catalog detail title', { minLength: 2, maxLength: 140 });
  assertBoundedString(detail.summary, 'catalog detail summary', { minLength: 20, maxLength: 500 });
  assertStringArray(detail.themes, 'catalog detail themes', { minItems: 1, maxItems: 8, pattern: THEME_PATTERN });
  assertStringArray(detail.actions, 'catalog detail actions', { minItems: 1, allowed: ACTION_VALUES });
  assertObject(detail.provenance, 'catalog detail provenance');
  assertObject(detail.curation, 'catalog detail curation');
  if (!Array.isArray(detail.links) || detail.links.length < 1) throw new Error('catalog detail links are invalid');
  if (detail.relations != null && !Array.isArray(detail.relations)) throw new Error('catalog detail relations are invalid');
  if (detail.handoff != null) assertObject(detail.handoff, 'catalog detail handoff');
  const projected = detailProjection(detail, 'catalog detail');
  if (stableComparisonJson(projected) !== stableComparisonJson(compactProjection(compactRecordValue))) {
    throw new Error('catalog detail compact parity mismatch');
  }
  return detail;
}

export function createCatalogLoadCache(limit) {
  if (!Number.isSafeInteger(limit) || limit < 1) throw new TypeError('catalog cache limit must be a positive integer');
  const entries = new Map();
  return Object.freeze({
    get size() { return entries.size; },
    keys() { return [...entries.keys()]; },
    clear() { entries.clear(); },
    load(key, loader) {
      assertString(key, 'catalog cache key');
      if (typeof loader !== 'function') throw new TypeError('catalog cache loader must be a function');
      const cached = entries.get(key);
      if (cached) {
        entries.delete(key);
        entries.set(key, cached);
        return cached;
      }
      const request = Promise.resolve().then(loader);
      entries.set(key, request);
      while (entries.size > limit) entries.delete(entries.keys().next().value);
      void request.catch(() => {
        if (entries.get(key) === request) entries.delete(key);
      });
      return request;
    },
  });
}

export async function verifyCatalogPayload(bytes, descriptor, cryptoImpl = globalThis.crypto) {
  if (!(bytes instanceof Uint8Array)) throw new TypeError('catalog payload must be Uint8Array');
  const checked = assertDescriptor(descriptor, 'catalog descriptor');
  if (bytes.byteLength !== checked.bytes) throw new Error(`catalog byte length mismatch: expected ${checked.bytes}, got ${bytes.byteLength}`);
  if (!cryptoImpl?.subtle) throw new Error('WebCrypto unavailable for catalog integrity check');
  const digest = hex(await cryptoImpl.subtle.digest('SHA-256', bytes));
  if (digest !== checked.sha256) throw new Error('catalog SHA-256 mismatch');
  return bytes;
}

async function fetchVerifiedJson(url, descriptor, { fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  if (typeof fetchImpl !== 'function') throw new Error('Fetch unavailable for catalog request');
  const response = await fetchImpl(url, { headers: { Accept: 'application/json' }, cache: 'no-cache', credentials: 'same-origin' });
  if (!response.ok) throw new Error(`catalog HTTP ${response.status} for ${url}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  await verifyCatalogPayload(bytes, descriptor, cryptoImpl);
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch (error) {
    throw new Error(`invalid catalog JSON for ${url}`, { cause: error });
  }
}

export async function shardKeyForIdentity(identifier, cryptoImpl = globalThis.crypto) {
  assertBoundedString(identifier, 'catalog identity', { minLength: 3, maxLength: 96, pattern: IDENTITY_PATTERN });
  if (!cryptoImpl?.subtle) throw new Error('WebCrypto unavailable for catalog shard key');
  const digest = await cryptoImpl.subtle.digest('SHA-256', new TextEncoder().encode(identifier));
  return hex(digest).slice(0, 2);
}

export function spatialCellForCoordinates(longitude, latitude, cellDegrees = 10) {
  if (![longitude, latitude, cellDegrees].every(Number.isFinite) || longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90 || cellDegrees <= 0 || 360 % cellDegrees !== 0 || 180 % cellDegrees !== 0) {
    throw new TypeError('invalid spatial cell coordinates');
  }
  const xMax = 360 / cellDegrees - 1;
  const yMax = 180 / cellDegrees - 1;
  const x = Math.min(xMax, Math.floor((longitude + 180) / cellDegrees));
  const y = Math.min(yMax, Math.floor((latitude + 90) / cellDegrees));
  return `${String(x).padStart(2, '0')}:${String(y).padStart(2, '0')}`;
}

function keysForValues(index, values) {
  const result = new Set();
  for (const value of values ?? []) for (const key of index?.[value] ?? []) result.add(key);
  return result;
}

export function selectAggregateShardKeys(aggregate, { themes = [], spatialCells = [], digital = null } = {}) {
  assertObject(aggregate, 'aggregate');
  if (!Array.isArray(themes) || !Array.isArray(spatialCells)) throw new TypeError('aggregate selection values must be arrays');
  const dimensions = [];
  if (themes.length) dimensions.push(keysForValues(aggregate.themes, themes));
  if (spatialCells.length) dimensions.push(keysForValues(aggregate.spatial_cells, spatialCells));
  if (digital === true) dimensions.push(new Set(aggregate.digital?.available ?? []));
  if (digital === false) dimensions.push(new Set(aggregate.digital?.unavailable ?? []));
  if (!dimensions.length || dimensions.some((dimension) => dimension.size === 0)) return [];
  const [first, ...rest] = dimensions.sort((left, right) => left.size - right.size);
  return [...first].filter((key) => rest.every((dimension) => dimension.has(key))).sort();
}

export async function loadCatalogAggregate({ manifestUrl = MANIFEST_URL, fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  if (typeof fetchImpl !== 'function') throw new Error('Fetch unavailable for catalog manifest');
  const { documentRoot, manifestAbsolute } = documentRootFor(manifestUrl);
  const manifestResolvedUrl = resolveCatalogUrl(manifestAbsolute.href, documentRoot, 'catalog manifest URL');
  const manifestResponse = await fetchImpl(manifestResolvedUrl, { headers: { Accept: 'application/json' }, cache: 'no-cache', credentials: 'same-origin' });
  if (!manifestResponse.ok) throw new Error(`catalog manifest HTTP ${manifestResponse.status}`);
  const { manifest, shardKeys } = validateManifest(await manifestResponse.json());
  const aggregateDescriptor = manifest.aggregate;
  const aggregateUrl = resolveCatalogUrl(aggregateDescriptor.url, documentRoot, 'catalog aggregate URL');
  const aggregate = validateAggregate(await fetchVerifiedJson(aggregateUrl, aggregateDescriptor, { fetchImpl, cryptoImpl }), manifest, shardKeys);
  return deepFreeze({
    manifest,
    aggregate,
    aggregateUrl,
    documentRoot: documentRoot.href,
  });
}

export async function loadCatalogShard(platform, key, { fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  if (typeof key !== 'string' || !SHARD_KEY_PATTERN.test(key)) throw new Error('invalid catalog shard key');
  const context = assertObject(platform, 'catalog platform');
  const { manifest, shardDescriptors } = validateManifest(context.manifest);
  const descriptor = shardDescriptors.get(key);
  if (!descriptor) throw new Error('catalog shard is not declared by the manifest');
  if (typeof context.documentRoot !== 'string') throw new Error('catalog platform has no document root');
  const documentRoot = new URL(context.documentRoot);
  const shardUrl = resolveCatalogUrl(descriptor.url, documentRoot, 'catalog shard URL');
  const shard = validateCatalogShard(
    await fetchVerifiedJson(shardUrl, descriptor, { fetchImpl, cryptoImpl }),
    descriptor,
    key,
    manifest,
  );
  for (const record of shard.records) {
    if (await shardKeyForIdentity(record.id, cryptoImpl) !== key) throw new Error('catalog shard contains an identity for another key');
  }
  return deepFreeze({ key, shardUrl, records: shard.records });
}

export async function loadCatalogDetail(platform, compactRecordValue, { fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  const context = assertObject(platform, 'catalog platform');
  const { manifest } = validateManifest(context.manifest);
  const compactRecord = validateCompactRecord(compactRecordValue, 'catalog detail compact record', manifest.generation);
  if (typeof context.documentRoot !== 'string') throw new Error('catalog platform has no document root');
  const documentRoot = new URL(context.documentRoot);
  const detailUrl = resolveCatalogUrl(compactRecord.detail.url, documentRoot, 'catalog detail URL');
  const record = validateCatalogDetail(
    await fetchVerifiedJson(detailUrl, compactRecord.detail, { fetchImpl, cryptoImpl }),
    compactRecord,
  );
  return deepFreeze({
    identity: record.id,
    generation: manifest.generation,
    detailUrl,
    record,
  });
}
