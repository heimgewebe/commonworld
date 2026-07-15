import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_CAMERA,
  MAX_MAP_ZOOM,
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
  publicMapFeatureCollection,
  evidencedRelations,
  recordLocationSummaries,
  recordPresentationLabel,
  ribbonRepeatCount,
  searchFromState,
  semanticLocationLine,
  semanticZoomLevel,
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
  assert.equal(MAX_MAP_ZOOM, 18);
  assert.deepEqual(state.camera, { lng: 180, lat: -85, zoom: MAX_MAP_ZOOM, bearing: 0, pitch: 70 });
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
  assert.equal(digitalLayerCamera({ zoom: MAX_MAP_ZOOM }).zoom, 8, 'digital layer journey must remain bounded after geographic close-up');
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


const geographicHybridRecords = [
  {
    id: 'cltb-le-nid',
    title: 'Le Nid',
    kind: 'geographic',
    themes: ['housing', 'shared-space'],
    presence: {
      geographic: [
        { id: 'entrance', label: 'Rue Verheyden 121', mode: 'exact', geometry: { type: 'Point', coordinates: [4.3152961, 50.8452417] }, source_ids: ['official', 'registry-point'] },
        { id: 'building', label: 'Gebäude Le Nid', mode: 'exact', geometry: { type: 'Polygon', coordinates: [[[4.31, 50.84], [4.32, 50.84], [4.32, 50.85], [4.31, 50.84]]] }, source_ids: ['official', 'registry-polygon'] },
      ],
      digital: { available: false, source_ids: ['official'] },
    },
    relations: [],
  },
  {
    id: 'freifunk',
    title: 'Freifunk',
    kind: 'digital',
    themes: ['communication', 'community-network'],
    presence: { geographic: [], digital: { available: true, reach: 'network', label: 'Community-Netze', source_ids: ['overview'] } },
    relations: [],
  },
  {
    id: 'freifunk-hamburg',
    title: 'Freifunk Hamburg',
    kind: 'hybrid',
    themes: ['communication', 'community-network'],
    presence: {
      geographic: [
        { id: 'community-area', label: 'Community Hamburg', mode: 'approximate', geometry: { type: 'Point', coordinates: [9.9445, 53.5583] }, uncertainty_meters_min: 5000, source_ids: ['api'] },
        { id: 'private-routers', label: 'Private Heimrouter', mode: 'hidden', privacy_note: 'Private Routerstandorte werden nicht veröffentlicht.', source_ids: ['directory'] },
      ],
      digital: { available: true, reach: 'regional', label: 'Hamburger Community-Netz', source_ids: ['api'] },
    },
    relations: [{ type: 'chapter-of', target_id: 'freifunk', source_ids: ['api'], note: 'Lokale Freifunk-Community.' }],
  },
];

test('public map derivation preserves CommonProject identity and excludes hidden geometry', () => {
  const collection = publicMapFeatureCollection(geographicHybridRecords);
  assert.equal(collection.type, 'FeatureCollection');
  assert.equal(collection.features.length, 3);
  assert.deepEqual(collection.features.map(({ properties }) => properties.project_id), ['cltb-le-nid', 'cltb-le-nid', 'freifunk-hamburg']);
  assert.deepEqual(collection.features.map(({ properties }) => properties.representation_kind), ['exact_anchor', 'public_extent', 'approximate_anchor']);
  assert.equal(collection.features.some(({ properties }) => properties.location_id === 'private-routers'), false);
  const approximate = collection.features.find(({ properties }) => properties.representation_kind === 'approximate_anchor');
  assert.equal(approximate.properties.uncertainty_meters_min, 5000);
  assert.deepEqual(approximate.geometry.coordinates, [9.9445, 53.5583]);
});

test('map filtering uses the same visible identity set without multiplying hybrid identities', () => {
  const collection = publicMapFeatureCollection(geographicHybridRecords, new Set(['freifunk-hamburg']));
  assert.equal(collection.features.length, 1);
  assert.equal(collection.features[0].properties.project_id, 'freifunk-hamburg');
  assert.equal(new Set(collection.features.map(({ properties }) => properties.project_id)).size, 1);
});


test('digital layer filtering excludes geographic-only identities but retains hybrid identities', () => {
  assert.deepEqual(
    filterRecords(geographicHybridRecords, { layer: 'communication_networks' }).map(({ id }) => id),
    ['freifunk', 'freifunk-hamburg'],
  );
  assert.deepEqual(
    filterRecords(geographicHybridRecords, { layer: 'mixed_other' }).map(({ id }) => id),
    [],
  );
});

test('only evidenced relations to known identities are projected', () => {
  const records = structuredClone(geographicHybridRecords);
  records[2].relations.push({ type: 'cooperates-with', target_id: 'missing', source_ids: ['api'] });
  assert.deepEqual(evidencedRelations(records), [{
    source_project_id: 'freifunk-hamburg',
    source_title: 'Freifunk Hamburg',
    target_project_id: 'freifunk',
    target_title: 'Freifunk',
    relation_type: 'chapter-of',
    source_ids: ['api'],
    note: 'Lokale Freifunk-Community.',
  }]);
});

test('semantic zoom remains presentation logic from planet to focus', () => {
  assert.equal(semanticZoomLevel(1.15), 'planet');
  assert.equal(semanticZoomLevel(2.2), 'macroregion');
  assert.equal(semanticZoomLevel(4.2), 'region');
  assert.equal(semanticZoomLevel(6.2), 'local');
  assert.equal(semanticZoomLevel(1.15, 'freifunk-hamburg'), 'focus');
  assert.deepEqual(semanticLocationLine({ zoom: 4.2, records: geographicHybridRecords }), {
    level: 'region',
    crumbs: ['Erde', 'Region'],
    summary: '2 räumlich belegte Commons · öffentliche Flächen und ungefähre Orte',
  });
  assert.deepEqual(semanticLocationLine({ zoom: 1.15, records: geographicHybridRecords, selectedProjectId: 'freifunk' }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk'],
    summary: 'Digital · Ortsunabhängige digitale Präsenz',
  });
  assert.deepEqual(semanticLocationLine({ zoom: 1.15, records: geographicHybridRecords, selectedProjectId: 'freifunk-hamburg' }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk Hamburg'],
    summary: 'Hybrid · 1 öffentlicher Ort · 1 verborgener Ort',
  });
  assert.deepEqual(semanticLocationLine({
    zoom: 1.15,
    records: [geographicHybridRecords[0]],
    selectedProjectId: 'freifunk-hamburg',
    selectedRecord: geographicHybridRecords[2],
  }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk Hamburg'],
    summary: 'Hybrid · 1 öffentlicher Ort · 1 verborgener Ort',
  });
});

test('presentation and location labels explain geographic, digital and hybrid truth', () => {
  assert.equal(recordPresentationLabel(geographicHybridRecords[0]), 'Geografisch');
  assert.equal(recordPresentationLabel(geographicHybridRecords[1]), 'Digital · Kommunikation und Netze');
  assert.equal(recordPresentationLabel(geographicHybridRecords[2]), 'Hybrid · Kommunikation und Netze');
  assert.deepEqual(recordLocationSummaries(geographicHybridRecords[0]), [
    'Rue Verheyden 121 · exakter öffentlicher Punkt',
    'Gebäude Le Nid · öffentliche Fläche',
  ]);
  assert.deepEqual(recordLocationSummaries(geographicHybridRecords[2]), [
    'Community Hamburg · ungefähr, mindestens 5 km Unschärfe',
    'Private Heimrouter · Ort verborgen',
  ]);
});
