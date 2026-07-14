import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_CAMERA,
  DIGITAL_LAYER_TRANSITION_MS,
  LAYERS,
  ORBIT_PROFILES,
  binaryFragment,
  binaryName,
  cameraFromSearch,
  deriveLayer,
  digitalLayerCamera,
  filterRecords,
  globeHorizonCoordinates,
  mapFailurePolicy,
  projectedGlobeCircle,
  ribbonRepeatCount,
  searchFromState,
  sphereDetailLevel,
  sphereLayout,
  sphereOpacityForGlobeRatio,
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

test('digital ribbons encode the actual UTF-8 Commons names', () => {
  assert.equal(binaryName('A'), '01000001');
  assert.equal(binaryName('ä'), '11000011 10100100');
  assert.equal(binaryName('Debian').split(' ').length, 6);
  assert.equal(ribbonRepeatCount(1), 6);
  assert.equal(ribbonRepeatCount(2), 6);
  assert.equal(ribbonRepeatCount(10), 2);
});


test('orbital profiles remain distinct semantic paths rather than copied circles', () => {
  assert.equal(ORBIT_PROFILES.length, LAYERS.length);
  assert.equal(new Set(ORBIT_PROFILES.map(({ rotation }) => rotation)).size, LAYERS.length);
  assert(ORBIT_PROFILES.every(({ rx, ry }) => rx !== ry));
  assert(ORBIT_PROFILES.every(({ rx, ry }) => rx >= 286 && ry >= 268));
});

test('sphere detail levels remain stable for overview and close-up rendering', () => {
  assert.equal(sphereDetailLevel({ diameter: 300 }), 'micro');
  assert.equal(sphereDetailLevel({ diameter: 500 }), 'compact');
  assert.equal(sphereDetailLevel({ diameter: 800 }), 'names');
  assert.equal(sphereDetailLevel({ diameter: 300, sideView: true }), 'close');
  assert(LAYERS.every(({ trackLabel }) => typeof trackLabel === 'string' && trackLabel.length > 0));
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

test('sphere layout follows measured globe geometry and keeps stacked side tracks cropped', () => {
  const normal = sphereLayout({ width: 1000, height: 700, globe: { x: 500, y: 350, diameter: 600 } });
  const rotatedEquivalent = sphereLayout({ width: 1000, height: 700, globe: { x: 498.2, y: 351.4, diameter: 600 } });
  const zoomed = sphereLayout({ width: 1000, height: 700, globe: { x: 500, y: 350, diameter: 900 } });
  const side = sphereLayout({ width: 1000, height: 700, padding: { left: 36, right: 420, top: 36, bottom: 36 }, sideView: true });
  assert.deepEqual(normal, { x: 500, y: 350, diameter: 792, globeDiameter: 600 });
  assert.equal(rotatedEquivalent.diameter, normal.diameter);
  assert(zoomed.diameter > normal.diameter * 1.4);
  assert(normal.diameter * (276 / 320) > normal.globeDiameter, 'innermost digital layer must remain outside the globe');
  assert.deepEqual(side, { x: 80, y: 406, diameter: 2050, globeDiameter: 2050 });
  assert(side.diameter > 1000 * 2, 'side journey must move through a cropped enlargement of the text sphere');
  assert(side.x < 1000 * 0.1 && side.y > 700 * 0.55, 'side journey must approach the enlarged sphere from the left');
  const projected = sphereLayout({ width: 1000, height: 700, padding: { right: 400 }, globe: { x: 301.25, y: 348.5, diameter: 588 } });
  assert.equal(projected.x, 301.25);
  assert.equal(projected.y, 348.5);
  assert.equal(projected.diameter, 776.16);
  assert.equal(projected.globeDiameter, 588);
});

test('digital layer camera performs a bounded journey without changing identity', () => {
  assert.equal(DIGITAL_LAYER_TRANSITION_MS, 1080);
  assert.deepEqual(digitalLayerCamera({ lng: 13.4, lat: 52.5, zoom: 1.2, bearing: 170, pitch: 0 }), {
    center: [13.4, 52.5],
    zoom: 2.25,
    bearing: -162,
    pitch: 58,
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
