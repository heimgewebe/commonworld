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
  globeHorizonCoordinates,
  mapFailurePolicy,
  projectedGlobeCircle,
  searchFromState,
  sphereLabelLayout,
  sphereLayout,
  sphereOpacityForGlobeRatio,
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

test('sphere labels keep one identity between overview rings and tangent tracks', () => {
  const first = sphereLabelLayout(0, 0, 2);
  const second = sphereLabelLayout(0, 1, 2);
  const lower = sphereLabelLayout(5, 0, 1);
  assert.notEqual(first.overviewX, second.overviewX);
  assert.notEqual(first.overviewY, second.overviewY);
  assert.equal(first.sideY, 9);
  assert.equal(lower.sideY, 64);
  assert(first.sideX < second.sideX);
  assert.equal(lower.sideX, 320);
  for (const layout of [first, second, lower]) {
    for (const value of Object.values(layout)) assert(Number.isFinite(value));
  }
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

test('globe horizon coordinates stay ninety degrees from the current map center', () => {
  const horizon = globeHorizonCoordinates({ lng: 8, lat: 24 });
  assert.equal(horizon.length, 8);
  const radians = Math.PI / 180;
  const center = { lng: 8 * radians, lat: 24 * radians };
  for (const point of horizon) {
    const longitude = point.lng * radians;
    const latitude = point.lat * radians;
    const cosineDistance = Math.sin(center.lat) * Math.sin(latitude)
      + Math.cos(center.lat) * Math.cos(latitude) * Math.cos(longitude - center.lng);
    const distance = Math.acos(Math.max(-1, Math.min(1, cosineDistance))) / radians;
    assert.ok(Math.abs(distance - 89.994) < 0.001);
  }
});

test('projected globe circle uses the rendered horizon rather than MapLibre zoom numbers', () => {
  const center = { x: 195, y: 422 };
  const horizon = [
    { x: 195, y: 250.82 }, { x: 316.04, y: 300.96 }, { x: 366.18, y: 422 }, { x: 316.04, y: 543.04 },
    { x: 195, y: 593.18 }, { x: 73.96, y: 543.04 }, { x: 23.82, y: 422 }, { x: 73.96, y: 300.96 },
  ];
  assert.deepEqual(projectedGlobeCircle({ center, horizon }), { x: 195, y: 422, diameter: 342.36 });
  assert.equal(projectedGlobeCircle({ center, horizon: horizon.slice(0, 3) }), null);
});

test('sphere layout follows measured globe geometry and crops a tangent side-view patch', () => {
  const normal = sphereLayout({ width: 1000, height: 700, globe: { x: 500, y: 350, diameter: 600 } });
  const rotatedEquivalent = sphereLayout({ width: 1000, height: 700, globe: { x: 498.2, y: 351.4, diameter: 600 } });
  const zoomed = sphereLayout({ width: 1000, height: 700, globe: { x: 500, y: 350, diameter: 900 } });
  const side = sphereLayout({ width: 1000, height: 700, padding: { left: 36, right: 420, top: 36, bottom: 36 }, sideView: true });
  assert.deepEqual(normal, { x: 500, y: 350, diameter: 708, globeDiameter: 600 });
  assert.equal(rotatedEquivalent.diameter, normal.diameter);
  assert(zoomed.diameter > normal.diameter * 1.4);
  assert(normal.diameter * (276 / 320) > normal.globeDiameter, 'innermost digital layer must remain outside the globe');
  assert.equal(side.x, 500);
  assert.equal(side.y, 1289.63);
  assert.equal(side.diameter, 2300);
  assert.equal(side.globeDiameter, 2300);
  assert(side.diameter > 1000 * 2, 'side-view sphere must extend beyond both horizontal viewport edges');
  assert(side.y - side.diameter / 2 < 700 * 0.25, 'outer tangent must enter near the upper viewport quarter');
  assert(side.y > 700, 'sphere center must remain below the visible viewport');
  const projected = sphereLayout({ width: 1000, height: 700, padding: { right: 400 }, globe: { x: 301.25, y: 348.5, diameter: 588 } });
  assert.equal(projected.x, 301.25);
  assert.equal(projected.y, 348.5);
  assert.equal(projected.diameter, 693.84);
  assert.equal(projected.globeDiameter, 588);
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

test('digital sphere fade follows visible globe scale instead of MapLibre zoom normalization', () => {
  assert.equal(sphereOpacityForGlobeRatio(1.05), 1);
  assert.equal(sphereOpacityForGlobeRatio(1.575), 0.5);
  assert.equal(sphereOpacityForGlobeRatio(2.1), 0);
  assert.ok(sphereOpacityForGlobeRatio(1.4) > sphereOpacityForGlobeRatio(1.8));
});
