const MANIFEST_URL = './catalog/runtime/manifest.v1.json';
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const SHARD_KEY_PATTERN = /^[0-9a-f]{2}$/;

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
    for (const key of keys) {
      if (typeof key !== 'string' || !SHARD_KEY_PATTERN.test(key) || !knownShardKeys.has(key)) {
        throw new Error(`${label} references an unknown shard`);
      }
    }
  }
}

function validateManifest(value) {
  const manifest = assertObject(value, 'manifest');
  if (manifest.kind !== 'commonworld.catalog_runtime_manifest' || manifest.version !== '1.0') throw new Error('unsupported catalog manifest');
  if (typeof manifest.generation !== 'string' || !SHA256_PATTERN.test(manifest.generation)) throw new Error('invalid catalog generation');
  if (!Number.isSafeInteger(manifest.entry_count) || manifest.entry_count < 0) throw new Error('invalid catalog entry count');
  if (typeof manifest.source_catalog_sha256 !== 'string' || !SHA256_PATTERN.test(manifest.source_catalog_sha256)) throw new Error('invalid source catalog hash');
  const shards = assertObject(manifest.shards, 'manifest shards');
  if (shards.strategy !== 'sha256-prefix' || shards.prefix_length !== 2 || !Array.isArray(shards.entries)) throw new Error('unsupported catalog shard strategy');
  const shardKeys = new Set();
  for (const entry of shards.entries) {
    const descriptor = assertDescriptor(entry, 'manifest shard descriptor');
    if (typeof entry.key !== 'string' || !SHARD_KEY_PATTERN.test(entry.key) || shardKeys.has(entry.key)) throw new Error('invalid or duplicate catalog shard key');
    if (!Number.isSafeInteger(entry.entry_count) || entry.entry_count < 1) throw new Error('invalid catalog shard entry count');
    shardKeys.add(entry.key);
    void descriptor;
  }
  assertDescriptor(manifest.aggregate, 'manifest aggregate descriptor');
  return { manifest, shardKeys };
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
  if (manifestAbsolute.origin !== documentRoot.origin) throw new Error('catalog manifest must remain same-origin');
  const manifestResponse = await fetchImpl(manifestAbsolute.href, { headers: { Accept: 'application/json' }, cache: 'no-cache', credentials: 'same-origin' });
  if (!manifestResponse.ok) throw new Error(`catalog manifest HTTP ${manifestResponse.status}`);
  const { manifest, shardKeys } = validateManifest(await manifestResponse.json());
  const aggregateDescriptor = manifest.aggregate;
  const aggregateUrl = resolveCatalogUrl(aggregateDescriptor.url, documentRoot, 'catalog aggregate URL');
  const aggregate = validateAggregate(await fetchVerifiedJson(aggregateUrl, aggregateDescriptor, { fetchImpl, cryptoImpl }), manifest, shardKeys);
  return Object.freeze({ manifest: Object.freeze(manifest), aggregate: Object.freeze(aggregate), aggregateUrl });
}
