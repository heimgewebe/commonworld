import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_CAMERA,
  LAYERS,
  binaryFragment,
  cameraFromSearch,
  deriveLayer,
  searchFromState,
  sphereOpacityForZoom,
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

test('deep-link state accepts known identities and clamps camera', () => {
  const state = stateFromSearch('?project=debian&view=layers&layer=software_infrastructure&lng=999&lat=-999&z=99&p=99', ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.view, 'layers');
  assert.equal(state.layer, 'software_infrastructure');
  assert.deepEqual(state.camera, { lng: 180, lat: -85, zoom: 8, bearing: 0, pitch: 70 });
});

test('unknown identities and malformed numbers fail closed', () => {
  const state = stateFromSearch('?project=unknown&layer=unknown&lng=nope', ['debian']);
  assert.equal(state.project, null);
  assert.equal(state.layer, null);
  assert.equal(state.camera.lng, DEFAULT_CAMERA.lng);
  assert.deepEqual(cameraFromSearch(''), DEFAULT_CAMERA);
});

test('serialized state roundtrips selection and view', () => {
  const search = searchFromState({
    camera: { lng: 13.4049, lat: 52.52, zoom: 3.456, bearing: 4.2, pitch: 25 },
    project: 'debian',
    layer: 'software_infrastructure',
    view: 'layers',
  });
  const state = stateFromSearch(search, ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.layer, 'software_infrastructure');
  assert.equal(state.view, 'layers');
  assert.equal(state.camera.zoom, 3.46);
});

test('digital sphere fade is monotonic and bounded', () => {
  assert.equal(sphereOpacityForZoom(1.8), 1);
  assert.equal(sphereOpacityForZoom(2.2), 0.5);
  assert.equal(sphereOpacityForZoom(2.6), 0);
  assert.ok(sphereOpacityForZoom(2.1) > sphereOpacityForZoom(2.4));
});
