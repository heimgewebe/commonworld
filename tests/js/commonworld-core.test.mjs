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
  publicProjectNavigationTarget,
  evidencedRelations,
  geodesicDistanceMeters,
  prepareCatalogProjection,
  PUBLIC_MAP_COLLECTION_CACHE_LIMIT,
  recordLocationSummaries,
  recordPresentationLabel,
  ribbonRepeatCount,
  RING_ORBIT_MIN_DURATION_S,
  RING_ORBIT_MAX_DURATION_S,
  ringOrbitDirection,
  ringOrbitDuration,
  ringOrbitStartAngle,
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


test('ring orbit duration is deterministic, monotonic and bounded', () => {
  assert.equal(ringOrbitDuration(3), ringOrbitDuration(3), 'same entry count must yield the same duration');
  assert.ok(ringOrbitDuration(1) < ringOrbitDuration(3), '1 < 3');
  assert.ok(ringOrbitDuration(3) < ringOrbitDuration(10), '3 < 10');
  for (let count = 1; count < 48; count += 1) {
    assert.ok(ringOrbitDuration(count) <= ringOrbitDuration(count + 1), `monotonic at ${count}`);
  }
  assert.equal(ringOrbitDuration(1), RING_ORBIT_MIN_DURATION_S, 'one entry receives the exact minimum duration');
  assert.equal(RING_ORBIT_MIN_DURATION_S, 24);
  assert.equal(RING_ORBIT_MAX_DURATION_S, 96);
  assert.equal(ringOrbitDuration(10000), RING_ORBIT_MAX_DURATION_S, 'large counts saturate at the cap');
  assert.equal(ringOrbitDuration(100000), ringOrbitDuration(10000), 'cap is flat beyond saturation');
  assert.equal(ringOrbitDuration(0), ringOrbitDuration(1), 'empty rings fall back to the slowest small-ring pace');
  assert.equal(ringOrbitDuration('nonsense'), ringOrbitDuration(1), 'invalid input fails closed to the fallback');
});

test('ring orbit direction and start angle are deterministic presentation parameters', () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5].map(ringOrbitDirection), [1, -1, 1, -1, 1, -1]);
  const angles = [0, 1, 2, 3, 4, 5].map(ringOrbitStartAngle);
  assert.deepEqual(angles, [0, 1, 2, 3, 4, 5].map(ringOrbitStartAngle), 'start angles are deterministic');
  assert.equal(new Set(angles).size, 6, 'start angles stay distinct across the six rings');
  assert.ok(angles.every((value) => value >= 0 && value < 360));
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

test('deep-link state accepts surface, search, identity, filters and clamped camera', () => {
  const state = stateFromSearch('?surface=text&q=open%20data&project=debian&view=layers&layer=software_infrastructure&presence=digital&action=contribute&language=de&access=public&freshness=current&curation=listed&lng=999&lat=-999&z=99&p=99', ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'open data');
  assert.equal(state.layer, 'software_infrastructure');
  assert.deepEqual(
    { presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { presence: 'digital', action: 'contribute', language: 'de', access: 'public', freshness: 'current', curation: 'listed' },
  );
  assert.equal(MAX_MAP_ZOOM, 18);
  assert.deepEqual(state.camera, { lng: 180, lat: -85, zoom: MAX_MAP_ZOOM, bearing: 0, pitch: 70 });
});

test('unknown identities, filters and malformed numbers fail closed', () => {
  const state = stateFromSearch('?project=unknown&layer=unknown&presence=space&action=hack&language=../../private&access=secret&freshness=future&curation=hidden&lng=nope', ['debian']);
  assert.equal(state.project, null);
  assert.equal(state.layer, null);
  assert.equal(state.surface, 'globe');
  assert.deepEqual(
    { presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { presence: null, action: null, language: null, access: null, freshness: null, curation: null },
  );
  assert.equal(state.camera.lng, DEFAULT_CAMERA.lng);
  assert.deepEqual(cameraFromSearch(''), DEFAULT_CAMERA);
});

test('serialized state roundtrips selection, view, surface, query and filters', () => {
  const search = searchFromState({
    camera: { lng: 13.4049, lat: 52.52, zoom: 3.456, bearing: 4.2, pitch: 25 },
    project: 'debian',
    layer: 'software_infrastructure',
    view: 'layers',
    surface: 'text',
    query: 'freie Software',
    presence: 'digital',
    action: 'learn',
    language: 'unknown',
    access: 'unknown',
    freshness: 'stale',
    curation: 'verified',
  });
  const state = stateFromSearch(search, ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.layer, 'software_infrastructure');
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'freie Software');
  assert.deepEqual(
    { presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { presence: 'digital', action: 'learn', language: 'unknown', access: 'unknown', freshness: 'stale', curation: 'verified' },
  );
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
  assert.deepEqual(collection.features.map(({ properties }) => properties.representation_kind), ['exact_anchor', 'public_extent', 'approximate_zone']);
  assert.equal(collection.features.some(({ properties }) => properties.location_id === 'private-routers'), false);
  const approximate = collection.features.find(({ properties }) => properties.representation_kind === 'approximate_zone');
  assert.equal(approximate.properties.uncertainty_meters_min, 5000);
  assert.equal(approximate.geometry.type, 'Polygon');
  const uncertaintyRing = approximate.geometry.coordinates[0];
  assert.equal(uncertaintyRing.length, 65);
  assert.deepEqual(uncertaintyRing[0], uncertaintyRing.at(-1));
  const center = [9.9445, 53.5583];
  for (const coordinate of uncertaintyRing.slice(0, -1)) {
    const distance = geodesicDistanceMeters(center, coordinate);
    assert(Math.abs(distance - 5000) <= 1, 'uncertainty zone radius drifted: ' + distance);
  }
});

test('public project navigation targets use only published geometry and keep digital Commons coordinate-free', () => {
  const collection = publicMapFeatureCollection(geographicHybridRecords);
  const leNid = publicProjectNavigationTarget(collection, 'cltb-le-nid');
  assert.equal(leNid.kind, 'bounds');
  assert.deepEqual(leNid.bounds, [[4.31, 50.84], [4.32, 50.85]]);
  const hamburg = publicProjectNavigationTarget(collection, 'freifunk-hamburg');
  assert.equal(hamburg.kind, 'bounds');
  assert(hamburg.bounds[0][0] < 9.9445);
  assert(hamburg.bounds[1][0] > 9.9445);
  assert.equal(publicProjectNavigationTarget(collection, 'freifunk'), null);
  assert.equal(publicProjectNavigationTarget(collection, 'private-routers'), null);
  assert(Object.isFrozen(leNid));
  assert(Object.isFrozen(leNid.bounds));
});

test('map filtering uses the same visible identity set without multiplying hybrid identities', () => {
  const visible = new Set(['freifunk-hamburg']);
  const collection = publicMapFeatureCollection(geographicHybridRecords, visible);
  assert.strictEqual(collection, publicMapFeatureCollection(geographicHybridRecords, ['freifunk-hamburg']));
  assert.equal(collection.features.length, 1);
  assert.equal(collection.features[0].properties.project_id, 'freifunk-hamburg');
  assert.equal(new Set(collection.features.map(({ properties }) => properties.project_id)).size, 1);
});

test('catalog projection precomputes 250 approximate Commons and keeps its filter cache bounded', () => {
  assert.equal(PUBLIC_MAP_COLLECTION_CACHE_LIMIT, 64);
  const records = Array.from({ length: 250 }, (_, index) => ({
    id: 'regional-common-' + String(index).padStart(4, '0'),
    title: 'Regional Common ' + index,
    kind: 'hybrid',
    presence: {
      geographic: [{
        id: 'area-' + index,
        label: 'Region ' + index,
        mode: 'approximate',
        geometry: { type: 'Point', coordinates: [8 + index / 1000, 50 + index / 1000] },
        uncertainty_meters_min: 5000,
      }],
      digital: { available: true },
    },
    relations: [],
  }));
  const projection = prepareCatalogProjection(records);
  const all = projection.publicMapFeatureCollection();
  assert.equal(all.features.length, 250);
  assert(Object.isFrozen(records));
  assert(Object.isFrozen(records[0].presence.geographic[0].geometry.coordinates));
  assert(Object.isFrozen(all));
  assert(Object.isFrozen(all.features));
  assert(Object.isFrozen(all.features[0].geometry.coordinates[0]));
  assert.strictEqual(all, projection.publicMapFeatureCollection());
  assert.strictEqual(all, publicMapFeatureCollection(records));

  const visibleIds = records.filter((_, index) => index % 5 === 0).map(({ id }) => id);
  const subset = projection.publicMapFeatureCollection(visibleIds);
  assert.equal(subset.features.length, 50);
  assert.strictEqual(subset, projection.publicMapFeatureCollection([...visibleIds].reverse()));

  const firstFiltered = projection.publicMapFeatureCollection([records[0].id]);
  for (let index = 1; index <= PUBLIC_MAP_COLLECTION_CACHE_LIMIT; index += 1) {
    projection.publicMapFeatureCollection([records[index].id]);
  }
  assert.notStrictEqual(firstFiltered, projection.publicMapFeatureCollection([records[0].id]));
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
  const relations = evidencedRelations(records);
  assert.strictEqual(relations, prepareCatalogProjection(records).relations);
  assert.deepEqual(relations, [{
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
