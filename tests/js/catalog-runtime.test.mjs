import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import test from 'node:test';
import { loadCatalogAggregate, selectAggregateShardKeys, spatialCellForCoordinates, verifyCatalogPayload } from '../../assets/commonworld-catalog-runtime.mjs';

const bytes = (value) => new TextEncoder().encode(JSON.stringify(value));
const descriptor = (value) => ({ bytes: bytes(value).byteLength, sha256: createHash('sha256').update(bytes(value)).digest('hex'), url: 'catalog/runtime/aggregate.v1.json' });

function response(value) {
  const payload = bytes(value);
  return { ok: true, status: 200, json: async () => value, arrayBuffer: async () => payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength) };
}

test('integrity verification rejects changed catalog bytes', async () => {
  const payload = bytes({ ok: true });
  await verifyCatalogPayload(payload, { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex') }, webcrypto);
  await assert.rejects(() => verifyCatalogPayload(bytes({ ok: false }), { bytes: payload.byteLength, sha256: createHash('sha256').update(payload).digest('hex') }, webcrypto));
});

test('aggregate loader binds manifest descriptor and payload', async () => {
  const aggregate = { kind: 'commonworld.catalog_aggregate', version: '1.0', themes: {}, spatial_cells: {}, digital: { available: [], unavailable: [] } };
  const manifest = { kind: 'commonworld.catalog_runtime_manifest', version: '1.0', aggregate: descriptor(aggregate) };
  const calls = [];
  const fetchImpl = async (url) => { calls.push(String(url)); return calls.length === 1 ? response(manifest) : response(aggregate); };
  const loaded = await loadCatalogAggregate({ manifestUrl: 'https://commonworld.test/catalog/runtime/manifest.v1.json', fetchImpl, cryptoImpl: webcrypto });
  assert.equal(loaded.aggregate.kind, aggregate.kind);
  assert.deepEqual(calls, ['https://commonworld.test/catalog/runtime/manifest.v1.json', 'https://commonworld.test/catalog/runtime/aggregate.v1.json']);
});

test('aggregate selection intersects active dimensions', () => {
  const aggregate = { themes: { water: ['01', '02'], food: ['02'] }, spatial_cells: { '10:08': ['02', '03'] }, digital: { available: ['02', '04'], unavailable: ['01', '03'] } };
  assert.deepEqual(selectAggregateShardKeys(aggregate, { themes: ['water'], spatialCells: ['10:08'], digital: true }), ['02']);
  assert.deepEqual(selectAggregateShardKeys(aggregate, { themes: ['food'] }), ['02']);
  assert.deepEqual(selectAggregateShardKeys(aggregate), []);
});

test('spatial cell calculation is bounded at world edges', () => {
  assert.equal(spatialCellForCoordinates(-180, -90), '00:00');
  assert.equal(spatialCellForCoordinates(180, 90), '35:17');
  assert.equal(spatialCellForCoordinates(0, 0), '18:09');
});
