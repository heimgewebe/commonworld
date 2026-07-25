const MANIFEST_URL = './catalog/runtime/manifest.v1.json';

function assertObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} is not an object`);
  return value;
}

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, '0')).join('');
}

export async function verifyCatalogPayload(bytes, descriptor, cryptoImpl = globalThis.crypto) {
  if (!(bytes instanceof Uint8Array)) throw new TypeError('catalog payload must be Uint8Array');
  if (!descriptor || !Number.isInteger(descriptor.bytes) || typeof descriptor.sha256 !== 'string') throw new Error('invalid catalog descriptor');
  if (bytes.byteLength !== descriptor.bytes) throw new Error(`catalog byte length mismatch: expected ${descriptor.bytes}, got ${bytes.byteLength}`);
  if (!cryptoImpl?.subtle) throw new Error('WebCrypto unavailable for catalog integrity check');
  const digest = hex(await cryptoImpl.subtle.digest('SHA-256', bytes));
  if (digest !== descriptor.sha256) throw new Error('catalog SHA-256 mismatch');
  return bytes;
}

async function fetchVerifiedJson(url, descriptor, { fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  const response = await fetchImpl(url, { headers: { Accept: 'application/json' }, cache: 'no-cache' });
  if (!response.ok) throw new Error(`catalog HTTP ${response.status} for ${url}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  await verifyCatalogPayload(bytes, descriptor, cryptoImpl);
  return JSON.parse(new TextDecoder().decode(bytes));
}

export function spatialCellForCoordinates(longitude, latitude, cellDegrees = 10) {
  if (![longitude, latitude, cellDegrees].every(Number.isFinite) || cellDegrees <= 0) throw new TypeError('invalid spatial cell coordinates');
  const xMax = Math.ceil(360 / cellDegrees) - 1;
  const yMax = Math.ceil(180 / cellDegrees) - 1;
  const x = Math.min(xMax, Math.max(0, Math.floor((longitude + 180) / cellDegrees)));
  const y = Math.min(yMax, Math.max(0, Math.floor((latitude + 90) / cellDegrees)));
  return `${String(x).padStart(2, '0')}:${String(y).padStart(2, '0')}`;
}

function keysForValues(index, values) {
  const result = new Set();
  for (const value of values ?? []) for (const key of index?.[value] ?? []) result.add(key);
  return result;
}

export function selectAggregateShardKeys(aggregate, { themes = [], spatialCells = [], digital = null } = {}) {
  assertObject(aggregate, 'aggregate');
  const dimensions = [];
  if (themes.length) dimensions.push(keysForValues(aggregate.themes, themes));
  if (spatialCells.length) dimensions.push(keysForValues(aggregate.spatial_cells, spatialCells));
  if (digital === true) dimensions.push(new Set(aggregate.digital?.available ?? []));
  if (digital === false) dimensions.push(new Set(aggregate.digital?.unavailable ?? []));
  if (!dimensions.length) return [];
  const [first, ...rest] = dimensions;
  return [...first].filter((key) => rest.every((dimension) => dimension.has(key))).sort();
}

export async function loadCatalogAggregate({ manifestUrl = MANIFEST_URL, fetchImpl = globalThis.fetch, cryptoImpl = globalThis.crypto } = {}) {
  const manifestResponse = await fetchImpl(manifestUrl, { headers: { Accept: 'application/json' }, cache: 'no-cache' });
  if (!manifestResponse.ok) throw new Error(`catalog manifest HTTP ${manifestResponse.status}`);
  const manifest = assertObject(await manifestResponse.json(), 'manifest');
  if (manifest.kind !== 'commonworld.catalog_runtime_manifest' || manifest.version !== '1.0') throw new Error('unsupported catalog manifest');
  const aggregateDescriptor = assertObject(manifest.aggregate, 'manifest aggregate descriptor');
  const manifestAbsolute = new URL(manifestUrl, globalThis.location?.href ?? 'http://localhost/');
  const documentRoot = globalThis.location?.href ? new URL('./', globalThis.location.href) : new URL('/', manifestAbsolute);
  const aggregateUrl = new URL(aggregateDescriptor.url, documentRoot).href;
  const aggregate = await fetchVerifiedJson(aggregateUrl, aggregateDescriptor, { fetchImpl, cryptoImpl });
  if (aggregate.kind !== 'commonworld.catalog_aggregate' || aggregate.version !== '1.0') throw new Error('unsupported catalog aggregate');
  return Object.freeze({ manifest, aggregate, aggregateUrl });
}
