import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import test from 'node:test';
import {
  createCatalogLoadCache,
  loadCatalogAggregate,
  loadCatalogAggregateSegment,
  loadCatalogDetail,
  loadCatalogShard,
  selectAggregateShardKeys,
  selectCatalogShardKeys,
  shardKeyForIdentity,
  spatialCellForCoordinates,
  verifyCatalogPayload,
} from '../../assets/commonworld-catalog-runtime.mjs';

const bytes = (value) => new TextEncoder().encode(JSON.stringify(value));
const descriptor = (value, url = 'catalog/runtime/aggregate.v1.json') => ({ bytes: bytes(value).byteLength, sha256: createHash('sha256').update(bytes(value)).digest('hex'), url });
const sourceHash = 'a'.repeat(64);
const generation = 'b'.repeat(64);
const aggregateStub = { kind: 'commonworld.catalog_aggregate', version: '1.0', entry_count: 1, source_catalog_sha256: sourceHash, spatial_cell_degrees: 10, themes: {}, spatial_cells: {}, digital: { available: [], unavailable: [] } };
const detailsManifest = { strategy: 'content-addressed-shard-descriptors', descriptor_version: '1.0', url_template: 'catalog/runtime/details/{sha256}.v1.json', entry_count: 1, detail_set_sha256: 'c'.repeat(64), project_schema_version: 4 };
const worldDescriptor = descriptor({ records: [] }, 'catalog/runtime/world.v1.json');
const shardDescriptor = { key: '01', entry_count: 1, ...descriptor({ records: [] }, 'catalog/runtime/shards/01.v1.json') };

function response(value, { ok = true, status = 200 } = {}) {
  const payload = bytes(value);
  return { ok, status, json: async () => value, arrayBuffer: async () => payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength) };
}

function detailRecord(identifier = 'debian') {
  return {
    schema_version: 4,
    id: identifier,
    title: identifier === 'debian' ? 'Debian' : `Project ${identifier}`,
    summary: `A sufficiently detailed summary for ${identifier}.`,
    themes: ['software'],
    actions: ['use'],
    presence: { geographic: [], digital: { available: true, reach: 'global', label: 'Online', source_ids: ['official-source'] } },
    activity: { status: 'active' },
    provenance: { sources: [] },
    curation: { state: 'verified' },
    links: [{}],
    languages: { codes: ['en'] },
  };
}

function detailDescriptor(record, activeGeneration = generation) {
  const checked = descriptor(record, 'placeholder');
  return {
    version: '1.0',
    identity: record.id,
    generation: activeGeneration,
    url: `catalog/runtime/details/${checked.sha256}.v1.json`,
    sha256: checked.sha256,
    bytes: checked.bytes,
  };
}

function compactRecord(identifier = 'debian', { detail = detailRecord(identifier), activeGeneration = generation } = {}) {
  return {
    id: identifier,
    title: identifier === 'debian' ? 'Debian' : `Project ${identifier}`,
    themes: ['software'],
    actions: ['use'],
    languages: ['en'],
    access: null,
    presence: { digital: true, geographic: [] },
    activity: 'active',
    detail: detailDescriptor(detail, activeGeneration),
  };
}

function manifestForShard(shardEntry, { entryCount = shardEntry.entry_count, activeGeneration = generation, aggregate = aggregateStub } = {}) {
  return {
    kind: 'commonworld.catalog_runtime_manifest',
    version: '1.0',
    generation: activeGeneration,
    entry_count: entryCount,
    source_catalog_sha256: sourceHash,
    world_index: worldDescriptor,
    aggregate: descriptor({ ...aggregate, entry_count: entryCount }),
    details: { ...detailsManifest, entry_count: entryCount },
    shards: { strategy: 'sha256-prefix', prefix_length: 2, entries: [shardEntry] },
  };
}

function platformForShard(shard, { entryCount = shard.records.length, descriptorKey = shard.key, url = `catalog/runtime/shards/${descriptorKey}.v1.json`, documentRoot = 'https://commonworld.test/', activeGeneration = generation } = {}) {
  const shardEntry = { key: descriptorKey, entry_count: entryCount, ...descriptor(shard, url) };
  return { manifest: manifestForShard(shardEntry, { entryCount, activeGeneration }), documentRoot };
}

test('integrity verification rejects changed catalog bytes', async () => {
  const payload = bytes({ ok: true });
  await verifyCatalogPayload(payload, { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex'), url: 'catalog/runtime/test.json' }, webcrypto);
  await assert.rejects(() => verifyCatalogPayload(bytes({ ok: false }), { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex'), url: 'catalog/runtime/test.json' }, webcrypto));
});

test('aggregate loader binds manifest descriptor and payload', async () => {
  const aggregate = { ...aggregateStub, digital: { available: ['01'], unavailable: [] } };
  const manifest = manifestForShard(shardDescriptor, { aggregate });
  manifest.aggregate = descriptor(aggregate);
  const calls = [];
  const fetchImpl = async (url) => { calls.push(String(url)); return calls.length === 1 ? response(manifest) : response(aggregate); };
  const loaded = await loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto });
  assert.equal(loaded.aggregate.kind, aggregate.kind);
  assert.equal(loaded.documentRoot, 'https://commonworld.test/');
  assert(Object.isFrozen(loaded) && Object.isFrozen(loaded.manifest) && Object.isFrozen(loaded.manifest.shards.entries));
  assert(Object.isFrozen(loaded.aggregate) && Object.isFrozen(loaded.aggregate.digital.available));
  assert.deepEqual(calls, ['https://commonworld.test/catalog/runtime/manifest.v1.json', 'https://commonworld.test/catalog/runtime/aggregate.v1.json']);
});

test('aggregate loader binds relative runtime URLs to the rendered release base after canonical URL cleanup', async () => {
  const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const originalLocation = Object.getOwnPropertyDescriptor(globalThis, 'location');
  const aggregate = { ...aggregateStub, digital: { available: ['01'], unavailable: [] } };
  const manifest = manifestForShard(shardDescriptor, { aggregate });
  manifest.aggregate = descriptor(aggregate);
  const calls = [];
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { baseURI: 'https://commonworld.test/releases/abc123/' } });
  Object.defineProperty(globalThis, 'location', { configurable: true, value: { href: 'https://commonworld.test/' } });
  try {
    const loaded = await loadCatalogAggregate({
      fetchImpl: async (url) => { calls.push(String(url)); return calls.length === 1 ? response(manifest) : response(aggregate); },
      cryptoImpl: webcrypto,
    });
    assert.equal(loaded.documentRoot, 'https://commonworld.test/releases/abc123/');
    assert.deepEqual(calls, [
      'https://commonworld.test/releases/abc123/catalog/runtime/manifest.v1.json',
      'https://commonworld.test/releases/abc123/catalog/runtime/aggregate.v1.json',
    ]);
  } finally {
    if (originalDocument) Object.defineProperty(globalThis, 'document', originalDocument);
    else delete globalThis.document;
    if (originalLocation) Object.defineProperty(globalThis, 'location', originalLocation);
    else delete globalThis.location;
  }
});

test('aggregate loader rejects manifest URLs that escape the browser document root before fetching', async () => {
  const originalLocation = Object.getOwnPropertyDescriptor(globalThis, 'location');
  let calls = 0;
  Object.defineProperty(globalThis, 'location', { configurable: true, value: { href: 'https://commonworld.test/app/index.html' } });
  try {
    await assert.rejects(
      () => loadCatalogAggregate({ manifestUrl: '../outside/manifest.v1.json', fetchImpl: async () => { calls += 1; return response({}); }, cryptoImpl: webcrypto }),
      /document root/,
    );
    assert.equal(calls, 0);
  } finally {
    if (originalLocation) Object.defineProperty(globalThis, 'location', originalLocation);
    else delete globalThis.location;
  }
});

test('aggregate selection intersects active dimensions', () => {
  const aggregate = { themes: { water: ['01', '02'], food: ['02'] }, spatial_cells: { '10:08': ['02', '03'] }, digital: { available: ['02', '04'], unavailable: ['01', '03'] } };
  assert.deepEqual(selectAggregateShardKeys(aggregate, { themes: ['water'], spatialCells: ['10:08'], digital: true }), ['02']);
  assert.deepEqual(selectAggregateShardKeys(aggregate, { themes: ['food'] }), ['02']);
  assert.deepEqual(selectAggregateShardKeys(aggregate), []);
});

test('identity shard keys use the first two SHA-256 hex characters', async () => {
  const expected = createHash('sha256').update('debian').digest('hex').slice(0, 2);
  assert.equal(await shardKeyForIdentity('debian', webcrypto), expected);
  await assert.rejects(() => shardKeyForIdentity(' debian', webcrypto), /trimmed string/);
  await assert.rejects(() => shardKeyForIdentity('Bad-ID', webcrypto), /invalid format/);
});

test('catalog shard loading binds manifest URL, bytes, hash, key and records', async () => {
  const key = await shardKeyForIdentity('debian', webcrypto);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [compactRecord()] };
  const platform = platformForShard(shard);
  const calls = [];
  const loaded = await loadCatalogShard(platform, key, { fetchImpl: async (url) => { calls.push(String(url)); return response(shard); }, cryptoImpl: webcrypto });
  assert.equal(loaded.key, key);
  assert.equal(loaded.records[0].id, 'debian');
  assert(Object.isFrozen(loaded) && Object.isFrozen(loaded.records) && Object.isFrozen(loaded.records[0]));
  assert(Object.isFrozen(loaded.records[0].presence) && Object.isFrozen(loaded.records[0].detail));
  assert.deepEqual(calls, [`https://commonworld.test/catalog/runtime/shards/${key}.v1.json`]);
});

test('catalog shard loading rejects undeclared, cross-origin and document-root escaping URLs', async () => {
  const key = await shardKeyForIdentity('debian', webcrypto);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [compactRecord()] };
  const fetchImpl = async () => response(shard);
  await assert.rejects(() => loadCatalogShard(platformForShard(shard), 'ff', { fetchImpl, cryptoImpl: webcrypto }), /not declared/);
  await assert.rejects(() => loadCatalogShard(platformForShard(shard, { url: 'https://evil.test/shard.json' }), key, { fetchImpl, cryptoImpl: webcrypto }), /same-origin/);
  await assert.rejects(() => loadCatalogShard(platformForShard(shard, { url: '../outside.json', documentRoot: 'https://commonworld.test/app/' }), key, { fetchImpl, cryptoImpl: webcrypto }), /document root/);
});

test('catalog shard loading rejects changed bytes and can be retried cleanly', async () => {
  const key = await shardKeyForIdentity('debian', webcrypto);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [compactRecord()] };
  const changed = { ...shard, key: 'ff' };
  const platform = platformForShard(shard);
  let calls = 0;
  const fetchImpl = async () => response(++calls === 1 ? changed : shard);
  await assert.rejects(() => loadCatalogShard(platform, key, { fetchImpl, cryptoImpl: webcrypto }), /catalog (byte length|SHA-256) mismatch/);
  const loaded = await loadCatalogShard(platform, key, { fetchImpl, cryptoImpl: webcrypto });
  assert.equal(loaded.records[0].id, 'debian');
  assert.equal(calls, 2);
});

test('catalog shard loading validates payload key, entry count, duplicate IDs and compact records', async () => {
  const key = await shardKeyForIdentity('debian', webcrypto);
  const record = compactRecord();
  const cases = [
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key: 'ff', records: [record] }, { descriptorKey: key }, /key mismatch/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [record] }, { entryCount: 2 }, /entry count mismatch/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [record, record] }, {}, /duplicate identity/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, detail: { ...record.detail, url: '../escape.json' } }] }, {}, /content-addressed URL/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, detail: { ...record.detail, generation: 'd'.repeat(64) } }] }, {}, /generation mismatch/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, languages: ['en', 'en'] }] }, {}, /duplicate value/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, presence: { geographic: [{ mode: 'exact', geometry: { type: 'Point', coordinates: [null, 10] } }], digital: false } }] }, {}, /longitude/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, id: 'Bad-ID', detail: { ...record.detail, identity: 'Bad-ID' } }] }, {}, /invalid format/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, themes: [] }] }, {}, /invalid item count/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, themes: ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'] }] }, {}, /invalid item count/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, themes: ['Bad Theme'] }] }, {}, /invalid value/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, actions: ['execute'] }] }, {}, /unsupported value/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, languages: ['english'] }] }, {}, /invalid value/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, access: 'private' }] }, {}, /invalid access/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, activity: 'future' }] }, {}, /invalid activity/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, presence: { geographic: [{ mode: 'exact', geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] } }], digital: false } }] }, {}, /unsupported geometry type/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, presence: { geographic: [{ mode: 'exact', geometry: { type: 'Point', coordinates: [181, 0] } }], digital: false } }] }, {}, /longitude/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, presence: { geographic: [{ mode: 'exact', geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1]]] } }], digital: false } }] }, {}, /not closed/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, unexpected: true }] }, {}, /unexpected field/],
  ];
  for (const [shard, options, pattern] of cases) {
    const platform = platformForShard(shard, options);
    await assert.rejects(() => loadCatalogShard(platform, key, { fetchImpl: async () => response(shard), cryptoImpl: webcrypto }), pattern);
  }
});

test('catalog shard loading preserves optional languages and coordinate-free hidden-only presence', async () => {
  const key = await shardKeyForIdentity('debian', webcrypto);
  const detail = { ...detailRecord(), languages: undefined, presence: { geographic: [{ id: 'hidden-location', mode: 'hidden' }], digital: { available: false, source_ids: ['official-source'] } } };
  delete detail.languages;
  const record = { ...compactRecord('debian', { detail }), languages: [], presence: { geographic: [], digital: false } };
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [record] };
  const loaded = await loadCatalogShard(platformForShard(shard), key, { fetchImpl: async () => response(shard), cryptoImpl: webcrypto });
  assert.deepEqual(loaded.records[0].languages, []);
  assert.deepEqual(loaded.records[0].presence, { geographic: [], digital: false });
});

test('catalog shard loading rejects identities assigned to another SHA-256 prefix', async () => {
  const actualKey = await shardKeyForIdentity('debian', webcrypto);
  const wrongKey = actualKey === '00' ? '01' : '00';
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key: wrongKey, records: [compactRecord()] };
  await assert.rejects(() => loadCatalogShard(platformForShard(shard), wrongKey, { fetchImpl: async () => response(shard), cryptoImpl: webcrypto }), /another key/);
});

test('catalog detail loading binds generation, identity, content-addressed URL, bytes and hash', async () => {
  const record = detailRecord();
  const compact = compactRecord('debian', { detail: record });
  const key = await shardKeyForIdentity('debian', webcrypto);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [compact] };
  const platform = platformForShard(shard);
  const calls = [];
  const loaded = await loadCatalogDetail(platform, compact, { fetchImpl: async (url) => { calls.push(String(url)); return response(record); }, cryptoImpl: webcrypto });
  assert.equal(loaded.identity, 'debian');
  assert.equal(loaded.generation, generation);
  assert.equal(loaded.record.summary, record.summary);
  assert.deepEqual(compact.presence, { digital: true, geographic: [] });
  assert(Object.isFrozen(loaded) && Object.isFrozen(loaded.record) && Object.isFrozen(loaded.record.presence));
  assert.deepEqual(calls, [`https://commonworld.test/${compact.detail.url}`]);
});

test('catalog detail loading fails closed on path, bytes, schema, identity and compact parity mismatches', async () => {
  const record = detailRecord();
  const compact = compactRecord('debian', { detail: record });
  const key = await shardKeyForIdentity('debian', webcrypto);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [compact] };
  const platform = platformForShard(shard);
  const crossOrigin = { ...compact, detail: { ...compact.detail, url: `https://evil.test/${compact.detail.sha256}.v1.json` } };
  await assert.rejects(() => loadCatalogDetail(platform, crossOrigin, { fetchImpl: async () => response(record), cryptoImpl: webcrypto }), /(content-addressed URL|same-origin)/);
  await assert.rejects(() => loadCatalogDetail(platform, compact, { fetchImpl: async () => response({ ...record, summary: `${record.summary} changed` }), cryptoImpl: webcrypto }), /catalog (byte length|SHA-256) mismatch/);
  const wrongSchema = { ...record, schema_version: 5 };
  const schemaCompact = compactRecord('debian', { detail: wrongSchema });
  await assert.rejects(() => loadCatalogDetail(platformForShard({ ...shard, records: [schemaCompact] }), schemaCompact, { fetchImpl: async () => response(wrongSchema), cryptoImpl: webcrypto }), /unsupported project schema/);
  const wrongIdentity = { ...record, id: 'debian-other', title: 'Project debian-other' };
  const identityCompact = { ...compact, detail: detailDescriptor(wrongIdentity) };
  identityCompact.detail = { ...identityCompact.detail, identity: 'debian' };
  await assert.rejects(() => loadCatalogDetail(platformForShard({ ...shard, records: [identityCompact] }), identityCompact, { fetchImpl: async () => response(wrongIdentity), cryptoImpl: webcrypto }), /identity mismatch/);
  const parityRecord = { ...record, title: 'Different title' };
  const parityCompact = { ...compact, detail: { ...detailDescriptor(parityRecord), identity: 'debian' } };
  await assert.rejects(() => loadCatalogDetail(platformForShard({ ...shard, records: [parityCompact] }), parityCompact, { fetchImpl: async () => response(parityRecord), cryptoImpl: webcrypto }), /compact parity mismatch/);
});

test('bounded catalog load cache retries failures and evicts least-recently-used entries', async () => {
  const cache = createCatalogLoadCache(2);
  let attempts = 0;
  await assert.rejects(() => cache.load('failed', async () => { attempts += 1; throw new Error('failed'); }), /failed/);
  assert.equal(cache.size, 0);
  assert.equal(await cache.load('failed', async () => { attempts += 1; return 'recovered'; }), 'recovered');
  assert.equal(attempts, 2);
  await cache.load('second', async () => 'second');
  await cache.load('failed', async () => 'unused');
  await cache.load('third', async () => 'third');
  assert.deepEqual(cache.keys(), ['failed', 'third']);
  cache.clear();
  assert.equal(cache.size, 0);
});

test('spatial cell calculation is bounded at world edges', () => {
  assert.equal(spatialCellForCoordinates(-180, -90), '00:00');
  assert.equal(spatialCellForCoordinates(180, 90), '35:17');
  assert.equal(spatialCellForCoordinates(0, 0), '18:09');
});

test('aggregate loader rejects inconsistent shard sums, detail counts and duplicate aggregate shard references', async () => {
  const aggregate = { ...aggregateStub, themes: { software: ['01', '01'] } };
  const sumMismatchManifest = manifestForShard(shardDescriptor, { entryCount: 2, aggregate });
  let calls = 0;
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl: async () => { calls += 1; return response(sumMismatchManifest); }, cryptoImpl: webcrypto }),
    /entry count sum mismatch/,
  );
  assert.equal(calls, 1);

  const detailMismatchManifest = { ...manifestForShard(shardDescriptor), details: { ...detailsManifest, entry_count: 2 } };
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl: async () => response(detailMismatchManifest), cryptoImpl: webcrypto }),
    /detail entry count mismatch/,
  );

  const duplicateManifest = manifestForShard(shardDescriptor, { aggregate });
  duplicateManifest.aggregate = descriptor(aggregate);
  const fetchImpl = async (url) => String(url).includes('manifest') ? response(duplicateManifest) : response(aggregate);
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }),
    /duplicate shard/,
  );
});

test('aggregate loader rejects cross-origin descriptors and unknown shards', async () => {
  const aggregate = { ...aggregateStub, themes: { water: ['ff'] } };
  const manifest = manifestForShard(shardDescriptor, { aggregate });
  manifest.aggregate = descriptor(aggregate);
  const fetchImpl = async (_url) => _url.toString().includes('manifest') ? response(manifest) : response(aggregate);
  await assert.rejects(() => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }), /unknown shard/);
  manifest.aggregate = descriptor(aggregate, 'https://evil.test/aggregate.json');
  await assert.rejects(() => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }), /same-origin/);
});

test('spatial cell calculation rejects out-of-world coordinates and uneven grids', () => {
  assert.throws(() => spatialCellForCoordinates(181, 0), /invalid spatial cell/);
  assert.throws(() => spatialCellForCoordinates(0, 0, 7), /invalid spatial cell/);
});


async function hierarchyFixture(identifier = 'debian') {
  const record = compactRecord(identifier);
  const key = await shardKeyForIdentity(identifier, webcrypto, 3);
  const indexKey = key.slice(0, 1);
  const shard = { kind: 'commonworld.catalog_shard', version: '1.0', key, records: [record] };
  const leafDescriptor = { key, entry_count: 1, ...descriptor(shard, `catalog/runtime/shards/${key}.v1.json`) };
  const shardIndex = {
    kind: 'commonworld.catalog_shard_index',
    version: '2.0',
    generation,
    source_catalog_sha256: sourceHash,
    index_key: indexKey,
    index_prefix_length: 1,
    leaf_prefix_length: 3,
    entry_count: 1,
    shard_count: 1,
    entries: [leafDescriptor],
  };
  const shardIndexDescriptor = { key: indexKey, entry_count: 1, shard_count: 1, ...descriptor(shardIndex, `catalog/runtime/shard-indexes/${indexKey}.v2.json`) };
  const themeSegment = {
    kind: 'commonworld.catalog_aggregate_segment',
    version: '2.0',
    generation,
    source_catalog_sha256: sourceHash,
    dimension: 'themes',
    key: 'so',
    entry_count: 1,
    value_count: 1,
    shard_reference_count: 1,
    index: { software: [key] },
  };
  const themeDescriptor = { dimension: 'themes', key: 'so', value_count: 1, shard_reference_count: 1, ...descriptor(themeSegment, 'catalog/runtime/aggregate-segments/themes/so.v2.json') };
  const digitalSegment = {
    kind: 'commonworld.catalog_aggregate_segment',
    version: '2.0',
    generation,
    source_catalog_sha256: sourceHash,
    dimension: 'digital',
    key: 'all',
    entry_count: 1,
    value_count: 2,
    shard_reference_count: 1,
    index: { available: [key], unavailable: [] },
  };
  const digitalDescriptor = { dimension: 'digital', key: 'all', value_count: 2, shard_reference_count: 1, ...descriptor(digitalSegment, 'catalog/runtime/aggregate-segments/digital/all.v2.json') };
  const aggregate = {
    kind: 'commonworld.catalog_aggregate',
    version: '2.0',
    generation,
    entry_count: 1,
    source_catalog_sha256: sourceHash,
    spatial_cell_degrees: 10,
    segments: { themes: [themeDescriptor], spatial_cells: [], digital: [digitalDescriptor] },
  };
  const manifest = {
    kind: 'commonworld.catalog_runtime_manifest',
    version: '2.0',
    generation,
    entry_count: 1,
    source_catalog_sha256: sourceHash,
    world_index: worldDescriptor,
    aggregate: descriptor(aggregate, 'catalog/runtime/aggregate.v2.json'),
    details: detailsManifest,
    shards: { strategy: 'sha256-prefix-hierarchy', index_prefix_length: 1, leaf_prefix_length: 3, indexes: [shardIndexDescriptor] },
    migration_guard: {
      default_manifest_version: '1.0',
      default_shard_prefix_length: 2,
      candidate_manifest_version: '2.0',
      cutover_authorized: false,
      rollback_manifest_url: 'catalog/runtime/manifest.v1.json',
      required_gates: ['deterministic-fixtures', 'browser-transfer-budget', 'physical-device'],
    },
  };
  return { manifest, aggregate, themeSegment, digitalSegment, shardIndex, shard, key, indexKey };
}

test('manifest v2 aggregate root loads without eagerly fetching segments', async () => {
  const fixture = await hierarchyFixture();
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(String(url));
    return calls.length === 1 ? response(fixture.manifest) : response(fixture.aggregate);
  };
  const platform = await loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v2.json', fetchImpl, cryptoImpl: webcrypto });
  assert.equal(platform.manifest.version, '2.0');
  assert.deepEqual(calls, [
    'https://commonworld.test/catalog/runtime/manifest.v2.json',
    'https://commonworld.test/catalog/runtime/aggregate.v2.json',
  ]);
});

test('manifest v2 selection fetches only the required aggregate segment', async () => {
  const fixture = await hierarchyFixture();
  const platform = { manifest: fixture.manifest, aggregate: fixture.aggregate, documentRoot: 'https://commonworld.test/' };
  const calls = [];
  const selected = await selectCatalogShardKeys(platform, { themes: ['software'] }, {
    cryptoImpl: webcrypto,
    fetchImpl: async (url) => { calls.push(String(url)); return response(fixture.themeSegment); },
  });
  assert.deepEqual(selected, [fixture.key]);
  assert.deepEqual(calls, ['https://commonworld.test/catalog/runtime/aggregate-segments/themes/so.v2.json']);
});

test('manifest v2 segment loader rejects undeclared buckets before fetching', async () => {
  const fixture = await hierarchyFixture();
  const platform = { manifest: fixture.manifest, aggregate: fixture.aggregate, documentRoot: 'https://commonworld.test/' };
  let calls = 0;
  await assert.rejects(
    () => loadCatalogAggregateSegment(platform, { dimension: 'themes', key: 'x' }, { fetchImpl: async () => { calls += 1; return response({}); }, cryptoImpl: webcrypto }),
    /not declared/,
  );
  assert.equal(calls, 0);
});

test('manifest v2 shard load fetches one bounded directory and one leaf shard', async () => {
  const fixture = await hierarchyFixture();
  const platform = { manifest: fixture.manifest, aggregate: fixture.aggregate, documentRoot: 'https://commonworld.test/' };
  const calls = [];
  const loaded = await loadCatalogShard(platform, fixture.key, {
    cryptoImpl: webcrypto,
    fetchImpl: async (url) => {
      calls.push(String(url));
      return calls.length === 1 ? response(fixture.shardIndex) : response(fixture.shard);
    },
  });
  assert.equal(loaded.records[0].id, 'debian');
  assert.deepEqual(calls, [
    `https://commonworld.test/catalog/runtime/shard-indexes/${fixture.indexKey}.v2.json`,
    `https://commonworld.test/catalog/runtime/shards/${fixture.key}.v1.json`,
  ]);
});

test('manifest v2 shard load fails closed on corrupt directory bytes', async () => {
  const fixture = await hierarchyFixture();
  const platform = { manifest: fixture.manifest, aggregate: fixture.aggregate, documentRoot: 'https://commonworld.test/' };
  const corrupted = { ...fixture.shardIndex, entry_count: 2 };
  await assert.rejects(
    () => loadCatalogShard(platform, fixture.key, { fetchImpl: async () => response(corrupted), cryptoImpl: webcrypto }),
    /byte length mismatch|SHA-256 mismatch/,
  );
});

test('manifest v2 cutover guard and unknown versions fail closed', async () => {
  const fixture = await hierarchyFixture();
  const enabled = structuredClone(fixture.manifest);
  enabled.migration_guard.cutover_authorized = true;
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v2.json', fetchImpl: async () => response(enabled), cryptoImpl: webcrypto }),
    /cutover must remain unauthorized/,
  );
  const unknown = { ...fixture.manifest, version: '3.0' };
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v3.json', fetchImpl: async () => response(unknown), cryptoImpl: webcrypto }),
    /unsupported catalog manifest/,
  );
});

test('identity shard key supports explicit v2 leaf prefix without changing v1 default', async () => {
  const v1 = await shardKeyForIdentity('debian', webcrypto);
  const v2 = await shardKeyForIdentity('debian', webcrypto, 3);
  assert.equal(v1.length, 2);
  assert.equal(v2.length, 3);
  assert.equal(v2.slice(0, 2), v1);
  await assert.rejects(() => shardKeyForIdentity('debian', webcrypto, 9), /prefix length/);
});


test('manifest v2 rejects unbounded roots, prefix drift and unexpected schema fields', async () => {
  const fixture = await hierarchyFixture();
  const unbounded = structuredClone(fixture.manifest);
  unbounded.shards.indexes = Array.from({ length: 17 }, () => structuredClone(unbounded.shards.indexes[0]));
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v2.json', fetchImpl: async () => response(unbounded), cryptoImpl: webcrypto }),
    /bounded shard indexes/,
  );
  const prefixDrift = structuredClone(fixture.manifest);
  prefixDrift.shards.leaf_prefix_length = 4;
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v2.json', fetchImpl: async () => response(prefixDrift), cryptoImpl: webcrypto }),
    /prefix contract mismatch/,
  );
  const unexpected = structuredClone(fixture.manifest);
  unexpected.unexpected = true;
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v2.json', fetchImpl: async () => response(unexpected), cryptoImpl: webcrypto }),
    /unexpected field/,
  );
});
