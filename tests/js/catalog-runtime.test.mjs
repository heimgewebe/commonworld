import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import test from 'node:test';
import {
  loadCatalogAggregate,
  loadCatalogShard,
  selectAggregateShardKeys,
  shardKeyForIdentity,
  spatialCellForCoordinates,
  verifyCatalogPayload,
} from '../../assets/commonworld-catalog-runtime.mjs';

const bytes = (value) => new TextEncoder().encode(JSON.stringify(value));
const descriptor = (value, url = 'catalog/runtime/aggregate.v1.json') => ({ bytes: bytes(value).byteLength, sha256: createHash('sha256').update(bytes(value)).digest('hex'), url });
const sourceHash = 'a'.repeat(64);
const aggregateStub = { kind: 'commonworld.catalog_aggregate', version: '1.0', entry_count: 1, source_catalog_sha256: sourceHash, spatial_cell_degrees: 10, themes: {}, spatial_cells: {}, digital: { available: [], unavailable: [] } };
const shardDescriptor = { key: '01', entry_count: 1, ...descriptor({ records: [] }, 'catalog/runtime/shards/01.v1.json') };

function response(value) {
  const payload = bytes(value);
  return { ok: true, status: 200, json: async () => value, arrayBuffer: async () => payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength) };
}

function compactRecord(identifier = 'debian') {
  return {
    id: identifier,
    title: identifier === 'debian' ? 'Debian' : `Project ${identifier}`,
    themes: ['software'],
    actions: ['use'],
    languages: ['en'],
    access: null,
    presence: { geographic: [], digital: true },
    activity: 'active',
    detail: `catalog/projects/${identifier}.json`,
  };
}

function platformForShard(shard, { entryCount = shard.records.length, descriptorKey = shard.key, url = `catalog/runtime/shards/${descriptorKey}.v1.json`, documentRoot = 'https://commonworld.test/' } = {}) {
  const shardEntry = { key: descriptorKey, entry_count: entryCount, ...descriptor(shard, url) };
  return {
    manifest: {
      kind: 'commonworld.catalog_runtime_manifest',
      version: '1.0',
      generation: 'b'.repeat(64),
      entry_count: entryCount,
      source_catalog_sha256: sourceHash,
      aggregate: descriptor(aggregateStub),
      shards: { strategy: 'sha256-prefix', prefix_length: 2, entries: [shardEntry] },
    },
    documentRoot,
  };
}

test('integrity verification rejects changed catalog bytes', async () => {
  const payload = bytes({ ok: true });
  await verifyCatalogPayload(payload, { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex'), url: 'catalog/runtime/test.json' }, webcrypto);
  await assert.rejects(() => verifyCatalogPayload(bytes({ ok: false }), { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex'), url: 'catalog/runtime/test.json' }, webcrypto));
});

test('aggregate loader binds manifest descriptor and payload', async () => {
  const aggregate = { ...aggregateStub, digital: { available: ['01'], unavailable: [] } };
  const manifest = { kind: 'commonworld.catalog_runtime_manifest', version: '1.0', generation: 'b'.repeat(64), entry_count: 1, source_catalog_sha256: sourceHash, aggregate: descriptor(aggregate), shards: { strategy: 'sha256-prefix', prefix_length: 2, entries: [shardDescriptor] } };
  const calls = [];
  const fetchImpl = async (url) => { calls.push(String(url)); return calls.length === 1 ? response(manifest) : response(aggregate); };
  const loaded = await loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto });
  assert.equal(loaded.aggregate.kind, aggregate.kind);
  assert.equal(loaded.documentRoot, 'https://commonworld.test/');
  assert(Object.isFrozen(loaded) && Object.isFrozen(loaded.manifest) && Object.isFrozen(loaded.manifest.shards.entries));
  assert(Object.isFrozen(loaded.aggregate) && Object.isFrozen(loaded.aggregate.digital.available));
  assert.deepEqual(calls, ['https://commonworld.test/catalog/runtime/manifest.v1.json', 'https://commonworld.test/catalog/runtime/aggregate.v1.json']);
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
  assert(Object.isFrozen(loaded.records[0].presence) && Object.isFrozen(loaded.records[0].themes));
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
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, detail: '../escape.json' }] }, {}, /detail reference/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, languages: ['en', 'en'] }] }, {}, /duplicate value/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, presence: { geographic: [{ mode: 'exact', geometry: { type: 'Point', coordinates: [null, 10] } }], digital: false } }] }, {}, /longitude/],
    [{ kind: 'commonworld.catalog_shard', version: '1.0', key, records: [{ ...record, id: 'Bad-ID', detail: 'catalog/projects/Bad-ID.json' }] }, {}, /invalid format/],
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
  const record = { ...compactRecord(), languages: [], presence: { geographic: [], digital: false } };
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

test('spatial cell calculation is bounded at world edges', () => {
  assert.equal(spatialCellForCoordinates(-180, -90), '00:00');
  assert.equal(spatialCellForCoordinates(180, 90), '35:17');
  assert.equal(spatialCellForCoordinates(0, 0), '18:09');
});

test('aggregate loader rejects inconsistent shard sums and duplicate aggregate shard references', async () => {
  const aggregate = { ...aggregateStub, themes: { software: ['01', '01'] } };
  const sumMismatchManifest = {
    kind: 'commonworld.catalog_runtime_manifest',
    version: '1.0',
    generation: 'b'.repeat(64),
    entry_count: 2,
    source_catalog_sha256: sourceHash,
    aggregate: descriptor({ ...aggregate, entry_count: 2 }),
    shards: { strategy: 'sha256-prefix', prefix_length: 2, entries: [shardDescriptor] },
  };
  let calls = 0;
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl: async () => { calls += 1; return response(sumMismatchManifest); }, cryptoImpl: webcrypto }),
    /entry count sum mismatch/,
  );
  assert.equal(calls, 1);

  const duplicateManifest = {
    ...sumMismatchManifest,
    entry_count: 1,
    aggregate: descriptor(aggregate),
  };
  const fetchImpl = async (url) => String(url).includes('manifest') ? response(duplicateManifest) : response(aggregate);
  await assert.rejects(
    () => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }),
    /duplicate shard/,
  );
});

test('aggregate loader rejects cross-origin descriptors and unknown shards', async () => {
  const aggregate = { ...aggregateStub, themes: { water: ['ff'] } };
  const manifest = { kind: 'commonworld.catalog_runtime_manifest', version: '1.0', generation: 'b'.repeat(64), entry_count: 1, source_catalog_sha256: sourceHash, aggregate: descriptor(aggregate), shards: { strategy: 'sha256-prefix', prefix_length: 2, entries: [shardDescriptor] } };
  const fetchImpl = async (_url) => _url.toString().includes('manifest') ? response(manifest) : response(aggregate);
  await assert.rejects(() => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }), /unknown shard/);
  manifest.aggregate = descriptor(aggregate, 'https://evil.test/aggregate.json');
  await assert.rejects(() => loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto }), /same-origin/);
});

test('spatial cell calculation rejects out-of-world coordinates and uneven grids', () => {
  assert.throws(() => spatialCellForCoordinates(181, 0), /invalid spatial cell/);
  assert.throws(() => spatialCellForCoordinates(0, 0, 7), /invalid spatial cell/);
});
