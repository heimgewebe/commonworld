import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_CAMERA,
  DIGITAL_LAYER_TRANSITION_MS,
  LAYERS,
  binaryFragment,
  cameraFromSearch,
  deriveLayer,
  digitalLayerCamera,
  filterRecords,
  mapFailurePolicy,
  searchFromState,
  sphereLayout,
  sphereOpacityForZoom,
  sphereStartOffset,
  stateFromSearch,
} from '../../assets/commonworld-core.mjs';

test('all six digital presentation layers remain ordered', () => {
  assert.deepEqual(LAYERS.map(({ id }) => id), [
    'knowledge_data',
    'software_infrastructure',
    'media_culture',
    'learning_education',
    'communication_networks',
    'mixed_other',
  ]);
});

test('layer derivation uses catalog themes without overrides', () => {
  assert.equal(deriveLayer({ themes: ['knowledge', 'open-data'], presence: { digital: { available: true } } }), 'knowledge_data');
  assert.equal(deriveLayer({ themes: ['open-data', 'infrastructure'], presence: { digital: { available: true } } }), 'mixed_other');
  assert.equal(deriveLayer({ themes: ['education'], presence: { digital: { available: false } } }), null);
});

test('binary fragments are stable visual encodings', () => {
  assert.equal(binaryFragment('wikipedia'), binaryFragment('wikipedia'));
  assert.notEqual(binaryFragment('wikipedia'), binaryFragment('wikidata'));
  assert.match(binaryFragment('debian'), /^[01]{12}$/);
});

test('digital sphere offsets wrap all catalog labels into the visible path band', () => {
  const recordsPerLayer = [2, 2, 1, 2, 2, 1];
  const offsets = recordsPerLayer.flatMap((count, layerIndex) =>
    Array.from({ length: count }, (_, recordIndex) => sphereStartOffset(layerIndex, recordIndex, count)),
  );
  assert.equal(offsets.length, 10);
  assert.ok(offsets.every((offset) => offset >= 8 && offset < 80));
  assert.ok(Math.abs(sphereStartOffset(3, 1, 2) - 64.88) < 0.0001);
  assert.ok(Math.abs(sphereStartOffset(5, 0, 1) - 18.8) < 0.0001);
  assert.equal(sphereStartOffset(-1, -1, 0), 8);
});

test('deep-link state accepts surface, search, identity and clamped camera', () => {
  const state = stateFromSearch('?surface=text&q=open%20data&project=debian&view=layers&layer=software_infrastructure&lng=999&lat=-999&z=99&p=99', ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'open data');
  assert.equal(state.layer, 'software_infrastructure');
  assert.deepEqual(state.camera, { lng: 180, lat: -85, zoom: 8, bearing: 0, pitch: 70 });
});

test('unknown identities and malformed numbers fail closed', () => {
  const state = stateFromSearch('?project=unknown&layer=unknown&lng=nope', ['debian']);
  assert.equal(state.project, null);
  assert.equal(state.layer, null);
  assert.equal(state.surface, 'globe');
  assert.equal(state.camera.lng, DEFAULT_CAMERA.lng);
  assert.deepEqual(cameraFromSearch(''), DEFAULT_CAMERA);
});

test('serialized state roundtrips selection, view, surface and query', () => {
  const search = searchFromState({
    camera: { lng: 13.4049, lat: 52.52, zoom: 3.456, bearing: 4.2, pitch: 25 },
    project: 'debian',
    layer: 'software_infrastructure',
    view: 'layers',
    surface: 'text',
    query: 'freie Software',
  });
  const state = stateFromSearch(search, ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.layer, 'software_infrastructure');
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'freie Software');
  assert.equal(state.camera.zoom, 3.46);
});

test('record filtering keeps one shared search and layer truth', () => {
  const records = [
    { id: 'a', title: 'Offene Karte', summary: 'Weltweite Daten', themes: ['open-data'], actions: ['use'], presence: { digital: { available: true } } },
    { id: 'b', title: 'Freie Schule', summary: 'Lernen', themes: ['education'], actions: ['learn'], presence: { digital: { available: true } } },
  ];
  assert.deepEqual(filterRecords(records, { query: 'karte' }).map(({ id }) => id), ['a']);
  assert.deepEqual(filterRecords(records, { layer: 'learning_education' }).map(({ id }) => id), ['b']);
  assert.deepEqual(filterRecords(records, { query: 'daten', layer: 'knowledge_data' }).map(({ id }) => id), ['a']);
});

test('sphere layout keeps one stable overview extent and centers the full-screen side view', () => {
  const normal = sphereLayout({ width: 1000, height: 700, padding: {} });
  const rotatedEquivalent = sphereLayout({ width: 1000, height: 700, padding: {}, center: { x: 498.2, y: 351.4 } });
  const side = sphereLayout({ width: 1000, height: 700, padding: { left: 36, right: 420, top: 36, bottom: 36 }, center: { x: 308, y: 350 }, sideView: true });
  assert.deepEqual(normal, { x: 500, y: 350, diameter: 686 });
  assert.equal(rotatedEquivalent.diameter, normal.diameter);
  assert.equal(side.x, 500);
  assert.equal(side.y, 350);
  assert.equal(side.diameter, 616);
  const projected = sphereLayout({ width: 1000, height: 700, padding: { right: 400 }, center: { x: 301.25, y: 348.5 } });
  assert.equal(projected.x, 301.25);
  assert.equal(projected.y, 348.5);
  assert.equal(projected.diameter, normal.diameter);
});

test('digital layer camera performs a bounded journey without changing identity', () => {
  assert.equal(DIGITAL_LAYER_TRANSITION_MS, 760);
  assert.deepEqual(digitalLayerCamera({ lng: 13.4, lat: 52.5, zoom: 1.2, bearing: 170, pitch: 0 }), {
    center: [13.4, 52.5],
    zoom: 1.95,
    bearing: -172,
    pitch: 52,
    padding: { top: 0, right: 0, bottom: 0, left: 0 },
  });
});

test('map failure policy preserves the style for isolated errors and replaces it only after provider readback failure', () => {
  assert.deepEqual(mapFailurePolicy(), { degraded: true, replaceStyle: false });
  assert.deepEqual(mapFailurePolicy({ providerReadbackFailed: false }), { degraded: true, replaceStyle: false });
  assert.deepEqual(mapFailurePolicy({ providerReadbackFailed: true }), { degraded: true, replaceStyle: true });
});

test('digital sphere fade is monotonic and bounded', () => {
  assert.equal(sphereOpacityForZoom(1.8), 1);
  assert.equal(sphereOpacityForZoom(2.2), 0.5);
  assert.equal(sphereOpacityForZoom(2.6), 0);
  assert.ok(sphereOpacityForZoom(2.1) > sphereOpacityForZoom(2.4));
});
