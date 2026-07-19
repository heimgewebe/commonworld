import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  COMMONS_TYPE_LABELS,
  COMMONS_TYPE_VALUES,
  DEFAULT_CAMERA,
  MAX_MAP_ZOOM,
  DIGITAL_LAYER_TRANSITION_MS,
  DIGITAL_RING_FIELDS,
  DIGITAL_ROOT_PATH,
  DIGITAL_TAXONOMY,
  LAYERS,
  ORBIT_PROFILES,
  binaryFragment,
  binaryName,
  buildDigitalPresentationTree,
  cameraFromSearch,
  commonsTypeLabel,
  deriveCommonsType,
  deriveDigitalProjectPath,
  deriveLayer,
  digitalPresentationTreeConstructionCount,
  digitalPathFromLegacyLayer,
  digitalLayerCamera,
  filterRecords,
  globeHorizonCoordinates,
  hasDigitalPresence,
  mapFailurePolicy,
  projectedGlobeCircle,
  publicGeographicLocations,
  publicGeographicRepresentationKind,
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
  normalizeDigitalPath,
  ringOrbitDirection,
  ringOrbitDuration,
  ringOrbitStartAngle,
  safeExternalHttpsUrl,
  searchFromState,
  serializeDigitalPath,
  semanticLocationLine,
  semanticZoomLevel,
  sphereDetailLevel,
  sphereLayout,
  sphereOpacityForGlobeRatio,
  stateFromSearch,
  validateDigitalTaxonomy,
  visibleDigitalNodes,
} from '../../assets/commonworld-core.mjs';

function loadPublicCatalogRecords() {
  const manifest = JSON.parse(readFileSync(new URL('../../catalog/catalog.json', import.meta.url), 'utf8'));
  return manifest.project_files.map((relative) => JSON.parse(readFileSync(new URL(`../../catalog/${relative}`, import.meta.url), 'utf8')));
}

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

test('Commons types follow the proposal vocabulary and derive from explicit theme rules', () => {
  assert.deepEqual(COMMONS_TYPE_LABELS, {
    knowledge: 'Wissen und Daten',
    software: 'Software und Infrastruktur',
    culture: 'Kultur und Medien',
    'food-seeds': 'Saatgut und Ernährung',
    water: 'Wasser und Bewässerung',
    energy: 'Energie',
    'housing-land': 'Boden und Wohnen',
    'health-care': 'Pflege und Gesundheit',
    'tools-repair': 'Werkzeuge, Reparatur und Fertigung',
    'community-network': 'Gemeinschaftsnetz',
    other: 'Andere',
  });
  assert.deepEqual(COMMONS_TYPE_VALUES, [
    'knowledge', 'software', 'culture', 'food-seeds', 'water', 'energy',
    'housing-land', 'health-care', 'tools-repair', 'community-network', 'other',
  ]);
  const cases = [
    [['open-data', 'infrastructure'], 'knowledge'],
    [['open-source', 'open-data'], 'software'],
    [['open-media', 'creative-commons'], 'culture'],
    [['food', 'platform', 'open-source'], 'food-seeds'],
    [['water', 'food'], 'water'],
    [['energy', 'network'], 'energy'],
    [['housing', 'shared-space'], 'housing-land'],
    [['health', 'open-source'], 'health-care'],
    [['open-hardware', 'education'], 'tools-repair'],
    [['communication', 'community-network'], 'community-network'],
    [['commons-governance', 'cooperative-economy'], 'other'],
  ];
  for (const [themes, expected] of cases) assert.equal(deriveCommonsType({ themes }), expected, themes.join(','));
  assert.equal(deriveCommonsType({ commons_type: 'water', themes: ['health'] }), 'water', 'an explicit valid catalog value must win');
  assert.equal(deriveCommonsType({ commons_type: 'invalid', themes: ['health'] }), 'other', 'invalid explicit values fail closed instead of falling back to themes');
  assert.equal(deriveCommonsType({ commons_type: null, themes: ['health'] }), 'other', 'null explicit values fail closed instead of falling back to themes');
  assert.equal(commonsTypeLabel('community-network'), 'Gemeinschaftsnetz');
  assert.equal(commonsTypeLabel({ themes: ['repair'] }), 'Werkzeuge, Reparatur und Fertigung');
});


test('external catalogue links require canonical credential-free HTTPS URLs', () => {
  assert.equal(safeExternalHttpsUrl('https://example.org/path?q=commons'), 'https://example.org/path?q=commons');
  assert.equal(safeExternalHttpsUrl('https://EXAMPLE.org:443/a/../b'), 'https://example.org/b');
  assert.equal(safeExternalHttpsUrl('https://xn--bcher-kva.example.com'), 'https://xn--bcher-kva.example.com/');
  assert.equal(safeExternalHttpsUrl('https://example.org:8443/path'), 'https://example.org:8443/path');
  for (const value of [
    null,
    42,
    '',
    ' https://example.org',
    'https://example.org ',
    '/relative',
    'http://example.org',
    'javascript:alert(1)',
    'data:text/html,<h1>x</h1>',
    'https://user@example.org',
    'https://user:secret@example.org',
    'https://%',
  ]) {
    assert.equal(safeExternalHttpsUrl(value), null, String(value));
  }
});

test('digital ring taxonomy exposes five fields and validates its legacy aliases', () => {
  assert.deepEqual(validateDigitalTaxonomy(), []);
  assert.deepEqual(DIGITAL_RING_FIELDS.map(({ id }) => id), [
    'knowledge_learning_culture',
    'software_tools_production',
    'communication_networks',
    'provision_land_ecology',
    'cooperation_self_organization',
  ]);
  assert.equal(DIGITAL_RING_FIELDS.length, 5);
  assert.deepEqual(digitalPathFromLegacyLayer('knowledge_data'), ['sphere', 'knowledge_learning_culture', 'open_knowledge_data']);
  assert.deepEqual(digitalPathFromLegacyLayer('software_infrastructure'), ['sphere', 'software_tools_production', 'free_software']);
  assert.deepEqual(digitalPathFromLegacyLayer('media_culture'), ['sphere', 'knowledge_learning_culture', 'media_culture']);
  assert.deepEqual(digitalPathFromLegacyLayer('learning_education'), ['sphere', 'knowledge_learning_culture', 'learning_education']);
  assert.deepEqual(digitalPathFromLegacyLayer('communication_networks'), ['sphere', 'communication_networks', 'community_networks']);
  assert.deepEqual(digitalPathFromLegacyLayer('mixed_other'), ['sphere']);
  assert.equal(DIGITAL_TAXONOMY.version, 'digital-ring-bundles-v1');
});

test('digital taxonomy validation rejects duplicate and semantically broadened legacy aliases', () => {
  const duplicate = structuredClone(DIGITAL_TAXONOMY);
  duplicate.legacy_layer_aliases.push(structuredClone(duplicate.legacy_layer_aliases[0]));
  assert(validateDigitalTaxonomy(duplicate).includes('digital taxonomy legacy aliases must be unique'));

  const broadenedMixed = structuredClone(DIGITAL_TAXONOMY);
  broadenedMixed.legacy_layer_aliases.find(({ alias }) => alias === 'mixed_other').target_path = ['sphere', 'knowledge_learning_culture'];
  assert(validateDigitalTaxonomy(broadenedMixed).includes('digital taxonomy legacy mixed_other alias must orient to the unfiltered root'));
});

test('digital ring path derivation is deterministic and handles ambiguity explicitly', () => {
  const digital = (themes, available = true) => ({
    id: 'case',
    title: 'Case',
    themes,
    presence: { digital: { available } },
  });
  assert.equal(deriveDigitalProjectPath(digital(['free-software']))?.pathKey, 'sphere/software_tools_production/free_software');
  assert.equal(deriveDigitalProjectPath(digital(['knowledge', 'education']))?.pathKey, 'sphere/knowledge_learning_culture/knowledge_learning_bridge');
  assert.equal(deriveDigitalProjectPath(digital(['open-data', 'open-source']))?.pathKey, 'sphere/software_tools_production/knowledge_software_bridge');
  const unknown = deriveDigitalProjectPath(digital(['future-theme']));
  assert.equal(unknown?.status, 'unclassified');
  assert.equal(unknown?.pathKey, 'sphere/unclassified_future_theme');
  assert.deepEqual(unknown?.unknownThemes, ['future-theme']);
  assert.equal(deriveDigitalProjectPath(digital(['education'], false)), null);
  assert.equal(deriveDigitalProjectPath(digital(['open-source', 'open-data']))?.pathKey, deriveDigitalProjectPath(digital(['open-data', 'open-source']))?.pathKey);
});

test('current digital catalog identities derive exactly once without a public rest bucket', () => {
  const records = loadPublicCatalogRecords();
  const digitalRecords = records.filter(hasDigitalPresence);
  assert.ok(digitalRecords.length > 0);
  const derived = new Map(digitalRecords.map((record) => [record.id, deriveDigitalProjectPath(record)]));
  assert.equal(derived.size, digitalRecords.length);
  for (const [identifier, path] of derived) {
    assert.equal(path.status, 'classified', identifier);
    assert.notEqual(path.pathKey, 'sphere', identifier);
    assert.equal(path.pathKey.includes('mixed_other'), false, identifier);
    assert.equal(path.pathKey.includes('unclassified_future_theme'), false, identifier);
  }
  const reversedRecords = [...digitalRecords].reverse();
  const reversedThemes = digitalRecords.map((record) => ({ ...record, themes: [...record.themes].reverse() }));
  const permutedRecords = [...digitalRecords.slice(9), ...digitalRecords.slice(0, 9)];
  const baseline = Object.fromEntries([...derived].map(([identifier, path]) => [identifier, path.pathKey]));
  for (const variant of [reversedRecords, reversedThemes, permutedRecords]) {
    assert.deepEqual(
      Object.fromEntries(variant.map((record) => [record.id, deriveDigitalProjectPath(record).pathKey])),
      baseline,
    );
  }
});

test('digital presentation tree aggregates parent sets as exact disjoint child unions', () => {
  const records = loadPublicCatalogRecords();
  const digitalRecords = records.filter(hasDigitalPresence);
  const tree = buildDigitalPresentationTree(records);
  assert.equal(tree.identityIds.length, digitalRecords.length);
  const rootView = visibleDigitalNodes(tree, DIGITAL_ROOT_PATH);
  assert.equal(rootView.children.length, 5);
  assert.deepEqual(rootView.children.map(({ id }) => id), DIGITAL_RING_FIELDS.map(({ id }) => id));
  const rootUnion = new Set(rootView.children.flatMap(({ identityIds }) => identityIds));
  assert.equal(rootUnion.size, digitalRecords.length);
  assert.deepEqual([...rootUnion].sort(), tree.identityIds);
  for (const node of tree.nodesByPath.values()) {
    const union = new Set();
    for (const child of node.children) {
      for (const identifier of child.identityIds) {
        assert.equal(union.has(identifier), false, `${node.pathKey} duplicates ${identifier}`);
        union.add(identifier);
      }
    }
    if (!node.children.length) {
      for (const identifier of node.directIdentityIds) union.add(identifier);
    }
    assert.deepEqual([...union].sort(), node.identityIds, node.pathKey);
  }
  const knowledgePath = ['sphere', 'knowledge_learning_culture'];
  const knowledgeView = visibleDigitalNodes(tree, knowledgePath);
  assert.deepEqual(knowledgeView.breadcrumb.map(({ id }) => id), ['sphere', 'knowledge_learning_culture']);
  assert(knowledgeView.children.every((node) => node.parentPathKey === serializeDigitalPath(knowledgePath)));
  assert(knowledgeView.children.length < tree.nodesByPath.size, 'progressive disclosure must not return the full recursive tree');
});

test('digital path normalization roundtrips canonical paths and fails closed on traversal', () => {
  const path = ['sphere', 'communication_networks', 'community_networks'];
  const key = serializeDigitalPath(path);
  assert.equal(key, 'sphere/communication_networks/community_networks');
  assert.deepEqual(normalizeDigitalPath(key).path, path);
  assert.deepEqual(normalizeDigitalPath('').path, DIGITAL_ROOT_PATH);
  assert.deepEqual(normalizeDigitalPath('sphere/../catalog').path, DIGITAL_ROOT_PATH);
  assert.equal(normalizeDigitalPath('sphere/../catalog').valid, false);
  assert.equal(normalizeDigitalPath('sphere/communication_networks/../../catalog').valid, false);
  assert.equal(normalizeDigitalPath('sphere/nope').valid, false);
});

test('digital path normalization matches the shared fail-closed parity fixtures', () => {
  const fixtures = JSON.parse(readFileSync(new URL('../fixtures/digital-path-parity.json', import.meta.url), 'utf8'));
  for (const fixture of fixtures) {
    const normalized = normalizeDigitalPath(fixture.value);
    assert.equal(normalized.valid, fixture.valid, fixture.name);
    assert.deepEqual(normalized.path, fixture.path, fixture.name);
  }
  for (const encodedSegment of ['%20', '%09', '%0A']) {
    const encodedWhitespace = stateFromSearch(`?layer=communication_networks&digital_path=sphere/${encodedSegment}/communication_networks`);
    assert.equal(encodedWhitespace.layer, null, encodedSegment);
    assert.deepEqual(encodedWhitespace.digitalPath, DIGITAL_ROOT_PATH, encodedSegment);
  }
});

test('digital tree keeps full identity truth behind repeatable 48-item presentation windows', () => {
  for (const size of [500, 5000, 50000]) {
    const records = Array.from({ length: size }, (_, index) => ({
      id: `synthetic-digital-${String(index).padStart(4, '0')}`,
      title: `Synthetic Digital ${index}`,
      themes: index % 2 === 0 ? ['communication', 'community-network'] : ['open-data', 'infrastructure'],
      presence: { geographic: [], digital: { available: true } },
    }));
    const constructionsBefore = digitalPresentationTreeConstructionCount();
    const tree = buildDigitalPresentationTree(records);
    assert.strictEqual(buildDigitalPresentationTree(records), tree);
    assert(Object.isFrozen(tree));
    assert.equal(digitalPresentationTreeConstructionCount() - constructionsBefore, 1);
    assert.notStrictEqual(buildDigitalPresentationTree([...records]), tree);
    const root = visibleDigitalNodes(tree, DIGITAL_ROOT_PATH);
    const communication = visibleDigitalNodes(tree, ['sphere', 'communication_networks']);
    const community = visibleDigitalNodes(tree, ['sphere', 'communication_networks', 'community_networks']);
    const boundedCommunity = visibleDigitalNodes(tree, ['sphere', 'communication_networks', 'community_networks'], { identityLimit: 48 });
    assert.equal(root.children.length, 2);
    assert(communication.children.length <= 3);
    assert.equal(community.children.length, Math.ceil(size / 2));
    assert.equal(boundedCommunity.children.length, 48);
    assert.equal(tree.nodesByPath.get('sphere/communication_networks/community_networks').identityCount, Math.ceil(size / 2));
    let presented = 0;
    while (presented < Math.ceil(size / 2)) {
      presented = Math.min(presented + 48, Math.ceil(size / 2));
      const continued = visibleDigitalNodes(tree, ['sphere', 'communication_networks', 'community_networks'], { identityLimit: presented });
      assert.equal(continued.children.length, presented);
      assert.equal(new Set(continued.children.map(({ projectId }) => projectId)).size, presented);
    }
    assert.equal(root.children.length < tree.nodesByPath.size, true);
    assert.equal(communication.children.length < tree.nodesByPath.size, true);
  }
});

test('digital presence is derived from the explicit availability flag only', () => {
  assert.equal(hasDigitalPresence({ presence: { digital: { available: true } } }), true);
  assert.equal(hasDigitalPresence({ presence: { digital: { available: false } } }), false);
  assert.equal(hasDigitalPresence({ presence: { digital: { label: 'Nur Beschreibung' } } }), false);
  assert.equal(hasDigitalPresence(null), false);
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
  assert.ok(ORBIT_PROFILES.length >= DIGITAL_RING_FIELDS.length);
  assert.equal(new Set(ORBIT_PROFILES.map(({ rotation }) => rotation)).size, ORBIT_PROFILES.length);
  assert(ORBIT_PROFILES.every(({ rx, ry }) => rx !== ry));
  assert(ORBIT_PROFILES.every(({ rx, ry }) => rx >= 274 && ry >= 262));
});

test('sphere detail levels remain stable for overview and close-up rendering', () => {
  assert.equal(sphereDetailLevel({ diameter: 300 }), 'micro');
  assert.equal(sphereDetailLevel({ diameter: 500 }), 'compact');
  assert.equal(sphereDetailLevel({ diameter: 800 }), 'names');
  assert.equal(sphereDetailLevel({ diameter: 300, sideView: true }), 'close');
  assert(LAYERS.every(({ trackLabel }) => typeof trackLabel === 'string' && trackLabel.length > 0));
  assert(DIGITAL_RING_FIELDS.every(({ trackLabel }) => typeof trackLabel === 'string' && trackLabel.length > 0));
});

test('deep-link state accepts surface, search, identity, filters and clamped camera', () => {
  const state = stateFromSearch('?surface=text&q=open%20data&project=debian&view=layers&layer=software_infrastructure&commons_type=software&presence=digital&action=contribute&language=de&access=public&freshness=current&curation=listed&lng=999&lat=-999&z=99&p=99', ['debian']);
  assert.equal(state.project, 'debian');
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'open data');
  assert.equal(state.layer, 'software_infrastructure');
  assert.deepEqual(state.digitalPath, ['sphere', 'software_tools_production', 'free_software']);
  assert.deepEqual(
    { commons_type: state.commons_type, presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { commons_type: 'software', presence: ['digital'], action: 'contribute', language: 'de', access: 'public', freshness: 'current', curation: 'listed' },
  );
  assert.equal(MAX_MAP_ZOOM, 18);
  assert.deepEqual(state.camera, { lng: 180, lat: -85, zoom: MAX_MAP_ZOOM, bearing: 0, pitch: 70 });
});

test('legacy layer links preserve their exact six-layer filter and URL until explicit path selection', () => {
  const records = loadPublicCatalogRecords();
  for (const { id: layer } of LAYERS) {
    const parsed = stateFromSearch(`?view=layers&layer=${layer}`);
    const expectedIds = records.filter((record) => deriveLayer(record) === layer).map(({ id }) => id);
    assert.equal(parsed.layer, layer);
    assert.deepEqual(filterRecords(records, parsed).map(({ id }) => id), expectedIds, layer);
    const parameters = new URLSearchParams(searchFromState(parsed).slice(1));
    assert.equal(parameters.get('layer'), layer);
    assert.equal(parameters.has('digital_path'), false);
  }

  const communication = filterRecords(records, stateFromSearch('?layer=communication_networks')).map(({ id }) => id);
  assert(communication.includes('mastodon'));
  const software = filterRecords(records, stateFromSearch('?layer=software_infrastructure')).map(({ id }) => id);
  assert(software.includes('openmrs'));
  assert(software.includes('open-food-network-australia'));

  const explicit = stateFromSearch('?layer=communication_networks&digital_path=sphere/software_tools_production/free_software');
  assert.equal(explicit.layer, null);
  assert.deepEqual(explicit.digitalPath, ['sphere', 'software_tools_production', 'free_software']);
  const explicitParameters = new URLSearchParams(searchFromState(explicit).slice(1));
  assert.equal(explicitParameters.has('layer'), false);
  assert.equal(explicitParameters.get('digital_path'), 'sphere/software_tools_production/free_software');

  const invalidExplicit = stateFromSearch('?layer=communication_networks&digital_path=sphere/../catalog');
  assert.equal(invalidExplicit.layer, null);
  assert.deepEqual(invalidExplicit.digitalPath, DIGITAL_ROOT_PATH);
});

test('unknown identities, filters and malformed numbers fail closed', () => {
  const state = stateFromSearch('?project=unknown&layer=unknown&commons_type=imaginary&presence=space&action=hack&language=../../private&access=secret&freshness=future&curation=hidden&lng=nope', ['debian']);
  assert.equal(state.project, null);
  assert.equal(state.layer, null);
  assert.deepEqual(state.digitalPath, DIGITAL_ROOT_PATH);
  assert.equal(state.surface, 'globe');
  assert.deepEqual(
    { commons_type: state.commons_type, presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { commons_type: null, presence: [], action: null, language: null, access: null, freshness: null, curation: null },
  );
  assert.equal(state.camera.lng, DEFAULT_CAMERA.lng);
  assert.deepEqual(cameraFromSearch(''), DEFAULT_CAMERA);
});

test('presence URL state discards unknown values and serializes both axes once in canonical order', () => {
  const parsed = stateFromSearch('?presence=digital&presence=hybrid&presence=geographic&presence=digital');
  assert.deepEqual(parsed.presence, ['geographic', 'digital']);

  const search = searchFromState({
    camera: DEFAULT_CAMERA,
    presence: ['digital', 'geographic', 'digital', 'hybrid'],
  });
  const parameters = new URLSearchParams(search.slice(1));
  assert.deepEqual(parameters.getAll('presence'), ['geographic', 'digital']);
});

test('serialized state roundtrips selection, view, surface, query and filters', () => {
  const search = searchFromState({
    camera: { lng: 13.4049, lat: 52.52, zoom: 3.456, bearing: 4.2, pitch: 25 },
    project: 'debian',
    digitalPath: ['sphere', 'software_tools_production', 'free_software'],
    view: 'layers',
    surface: 'text',
    query: 'freie Software',
    commons_type: 'software',
    presence: ['digital'],
    action: 'learn',
    language: 'unknown',
    access: 'unknown',
    freshness: 'stale',
    curation: 'verified',
  });
  const state = stateFromSearch(search, ['debian']);
  const parameters = new URLSearchParams(search.slice(1));
  assert.equal(parameters.get('digital_path'), 'sphere/software_tools_production/free_software');
  assert.equal(parameters.has('layer'), false);
  assert.equal(state.project, 'debian');
  assert.equal(state.layer, null);
  assert.deepEqual(state.digitalPath, ['sphere', 'software_tools_production', 'free_software']);
  assert.equal(state.view, 'layers');
  assert.equal(state.surface, 'text');
  assert.equal(state.query, 'freie Software');
  assert.deepEqual(
    { commons_type: state.commons_type, presence: state.presence, action: state.action, language: state.language, access: state.access, freshness: state.freshness, curation: state.curation },
    { commons_type: 'software', presence: ['digital'], action: 'learn', language: 'unknown', access: 'unknown', freshness: 'stale', curation: 'verified' },
  );
  assert.equal(state.camera.zoom, 3.46);
});

test('record filtering keeps one shared search and layer truth', () => {
  const records = [
    { id: 'a', title: 'Offene Karte', summary: 'Weltweite Daten', themes: ['open-data'], actions: ['use'], presence: { digital: { available: true } } },
    { id: 'b', title: 'Freie Schule', summary: 'Lernen', themes: ['education'], actions: ['learn'], presence: { digital: { available: true } } },
    { id: 'c', title: 'Werkstatt vor Ort', summary: 'Stadtteil', themes: ['repair'], actions: ['visit'], presence: { geographic: [{ mode: 'approximate' }] } },
  ];
  assert.deepEqual(filterRecords(records, { query: 'karte' }).map(({ id }) => id), ['a']);
  assert.deepEqual(filterRecords(records, { commons_type: 'knowledge' }).map(({ id }) => id), ['a', 'b']);
  assert.deepEqual(filterRecords(records, { commons_type: 'tools-repair' }).map(({ id }) => id), ['c']);
  assert.deepEqual(filterRecords(records, { digitalPath: DIGITAL_ROOT_PATH }).map(({ id }) => id), ['a', 'b', 'c']);
  assert.deepEqual(filterRecords(records, { digitalPath: ['sphere', 'knowledge_learning_culture', 'learning_education'] }).map(({ id }) => id), ['b']);
  assert.deepEqual(filterRecords(records, { query: 'daten', digitalPath: ['sphere', 'knowledge_learning_culture', 'open_knowledge_data'] }).map(({ id }) => id), ['a']);
  assert.deepEqual(filterRecords(records, {
    query: 'lernen',
    digitalPath: ['sphere', 'knowledge_learning_culture', 'learning_education'],
    presence: ['digital'],
    action: 'learn',
  }).map(({ id }) => id), ['b']);
  assert.deepEqual(filterRecords(records, { layer: 'learning_education' }).map(({ id }) => id), ['b']);
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


const presenceAxisRecords = [
  {
    id: 'cltb-le-nid',
    title: 'Le Nid',

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

    themes: ['communication', 'community-network'],
    presence: { geographic: [], digital: { available: true, reach: 'network', label: 'Community-Netze', source_ids: ['overview'] } },
    relations: [],
  },
  {
    id: 'freifunk-hamburg',
    title: 'Freifunk Hamburg',

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

test('public geographic truth rejects malformed, hidden and privacy-breaking geometry', () => {
  const validExact = { mode: 'exact', geometry: { type: 'Point', coordinates: [8, 50] } };
  const validApproximate = { mode: 'approximate', geometry: { type: 'Point', coordinates: [8, 50] }, uncertainty_meters_min: 1000 };
  assert.equal(publicGeographicRepresentationKind(validExact), 'exact_anchor');
  assert.equal(publicGeographicRepresentationKind(validApproximate), 'approximate_zone');
  assert.equal(publicGeographicRepresentationKind({ mode: 'hidden', geometry: validExact.geometry }), null);
  assert.equal(publicGeographicRepresentationKind({ mode: 'exact', geometry: { type: 'Point', coordinates: [181, 50] } }), null);
  assert.equal(publicGeographicRepresentationKind({ mode: 'exact', geometry: { type: 'Point', coordinates: ['8', 50] } }), null);
  assert.equal(publicGeographicRepresentationKind({ mode: 'approximate', geometry: { type: 'Point', coordinates: [8, 50] }, uncertainty_meters_min: 0 }), null);
  assert.equal(publicGeographicRepresentationKind({ mode: 'approximate', geometry: { type: 'Polygon', coordinates: [[[8, 50], [9, 50], [9, 51], [8, 50]]] }, uncertainty_meters_min: 1000 }), null);

  const hiddenOnly = {
    id: 'hidden-only',
    title: 'Hidden only',
    themes: [],
    presence: {
      geographic: [{ id: 'private', mode: 'hidden', label: 'Private place' }],
      digital: { available: false },
    },
  };
  assert.deepEqual(publicGeographicLocations(hiddenOnly), []);
  assert.deepEqual(publicMapFeatureCollection([hiddenOnly]).features, []);
  assert.deepEqual(filterRecords([hiddenOnly], { presence: ['geographic'] }), []);
  assert.equal(recordPresentationLabel(hiddenOnly), 'Commons');
});

test('public map derivation preserves CommonProject identity and excludes hidden geometry', () => {
  const collection = publicMapFeatureCollection(presenceAxisRecords);
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
  const collection = publicMapFeatureCollection(presenceAxisRecords);
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

test('map filtering uses the same visible identity set without multiplying dual presence identities', () => {
  const visible = new Set(['freifunk-hamburg']);
  const collection = publicMapFeatureCollection(presenceAxisRecords, visible);
  assert.strictEqual(collection, publicMapFeatureCollection(presenceAxisRecords, ['freifunk-hamburg']));
  assert.equal(collection.features.length, 1);
  assert.equal(collection.features[0].properties.project_id, 'freifunk-hamburg');
  assert.equal(new Set(collection.features.map(({ properties }) => properties.project_id)).size, 1);
});

test('catalog projection precomputes 250 approximate Commons and keeps its filter cache bounded', () => {
  assert.equal(PUBLIC_MAP_COLLECTION_CACHE_LIMIT, 64);
  const records = Array.from({ length: 250 }, (_, index) => ({
    id: 'regional-common-' + String(index).padStart(4, '0'),
    title: 'Regional Common ' + index,

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

test('digital layer filtering excludes geographic-only identities but retains dual presence identities', () => {
  assert.deepEqual(
    filterRecords(presenceAxisRecords, { digitalPath: ['sphere', 'communication_networks', 'community_networks'] }).map(({ id }) => id),
    ['freifunk', 'freifunk-hamburg'],
  );
  assert.deepEqual(
    filterRecords(presenceAxisRecords, { layer: 'communication_networks' }).map(({ id }) => id),
    ['freifunk', 'freifunk-hamburg'],
  );
  assert.deepEqual(
    filterRecords(presenceAxisRecords, { digitalPath: ['sphere', 'software_tools_production'] }).map(({ id }) => id),
    [],
  );
});

test('only evidenced relations to known identities are projected', () => {
  const records = structuredClone(presenceAxisRecords);
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
  const recordsWithMalformedGeometry = [...presenceAxisRecords, {
    id: 'malformed-location',
    presence: {
      geographic: [{ mode: 'exact', geometry: { type: 'Point', coordinates: [true, false] } }],
      digital: { available: false },
    },
  }];
  assert.deepEqual(semanticLocationLine({ zoom: 4.2, records: recordsWithMalformedGeometry }), {
    level: 'region',
    crumbs: ['Erde', 'Region'],
    summary: '2 räumlich belegte Commons · öffentliche Flächen und ungefähre Orte',
  });
  assert.deepEqual(semanticLocationLine({ zoom: 1.15, records: presenceAxisRecords, selectedProjectId: 'freifunk' }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk'],
    summary: 'Digital · Ortsunabhängige digitale Präsenz',
  });
  assert.deepEqual(semanticLocationLine({ zoom: 1.15, records: presenceAxisRecords, selectedProjectId: 'freifunk-hamburg' }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk Hamburg'],
    summary: 'Vor Ort · Digital · 1 öffentlicher Ort · 1 verborgener Ort',
  });
  assert.deepEqual(semanticLocationLine({
    zoom: 1.15,
    records: [presenceAxisRecords[0]],
    selectedProjectId: 'freifunk-hamburg',
    selectedRecord: presenceAxisRecords[2],
  }), {
    level: 'focus',
    crumbs: ['Erde', 'Commons', 'Freifunk Hamburg'],
    summary: 'Vor Ort · Digital · 1 öffentlicher Ort · 1 verborgener Ort',
  });
});

test('presentation and location labels explain geographic, digital and dual presence truth', () => {
  assert.equal(recordPresentationLabel(presenceAxisRecords[0]), 'Vor Ort');
  assert.equal(recordPresentationLabel(presenceAxisRecords[1]), 'Digital · Kommunikation und Netze › Gemeinschaftsnetze');
  assert.equal(recordPresentationLabel(presenceAxisRecords[2]), 'Vor Ort · Digital · Kommunikation und Netze › Gemeinschaftsnetze');
  assert.deepEqual(recordLocationSummaries(presenceAxisRecords[0]), [
    'Rue Verheyden 121 · exakter öffentlicher Punkt',
    'Gebäude Le Nid · öffentliche Fläche',
  ]);
  assert.deepEqual(recordLocationSummaries(presenceAxisRecords[2]), [
    'Community Hamburg · ungefähr, mindestens 5 km Unschärfe',
    'Private Heimrouter · Ort verborgen',
  ]);
});
