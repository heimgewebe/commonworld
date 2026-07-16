import {
  DEFAULT_CAMERA,
  MAX_MAP_ZOOM,
  binaryName,
  DIGITAL_LAYER_TRANSITION_MS,
  LAYERS,
  deriveLayer,
  digitalLayerCamera,
  filterRecords,
  globeHorizonCoordinates,
  mapCamera,
  mapFailurePolicy,
  normalizeQuery,
  prepareCatalogProjection,
  prepareIntentSearchIndex,
  recordLocationSummaries,
  recordPresentationLabel,
  projectedGlobeCircle,
  publicProjectNavigationTarget,
  ribbonRepeatCount,
  searchFromState,
  semanticLocationLine,
  sphereDetailLevel,
  sphereLayout,
  sphereOpacityForGlobeRatio,
  stateFromSearch,
} from './commonworld-core.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const LOCAL_FALLBACK_STYLE = Object.freeze({ version: 8, sources: {}, layers: [{ id: 'commonworld-fallback', type: 'background', paint: { 'background-color': '#0d2426' } }] });
const PRESENTATION_STORAGE_KEY = 'commonworld.presentation';
const PUBLIC_MAP_SOURCE_ID = 'commonworld-public-representations';
const PUBLIC_MAP_LAYER_IDS = Object.freeze(['commonworld-public-extents', 'commonworld-approximate-zones', 'commonworld-exact-anchors']);
const ACTION_LINK_TYPES = new Set(['visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate']);
const INTENT_FILTER_NAMES = Object.freeze(['presence', 'action', 'language', 'access', 'freshness', 'curation']);
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const elements = {
  body: document.body,
  skipLink: document.querySelector('.skip-link'),
  bootstrap: document.querySelector('#catalog-bootstrap'),
  globeSurface: document.querySelector('#globe-surface'),
  textView: document.querySelector('#text-view'),
  textCount: document.querySelector('#text-count'),
  textEmpty: document.querySelector('#text-empty'),
  textLayerButtons: document.querySelector('#text-layer-buttons'),
  stage: document.querySelector('.globe-stage'),
  map: document.querySelector('#map'),
  mapStatus: document.querySelector('#map-status'),
  globeResults: document.querySelector('#globe-results'),
  semanticLevel: document.querySelector('#semantic-level'),
  semanticSummary: document.querySelector('#semantic-summary'),
  sphere: document.querySelector('#digital-sphere'),
  sphereStreams: document.querySelector('#sphere-streams'),
  sphereRings: document.querySelector('#sphere-rings'),
  sphereEdge: document.querySelector('#sphere-edge-control'),
  layerStack: document.querySelector('#layer-stack-visual'),
  layerToggle: document.querySelector('#layer-view-button'),
  layerPanel: document.querySelector('#layer-panel'),
  layerClose: document.querySelector('#layer-close'),
  layerSearchToggle: document.querySelector('#layer-search-toggle'),
  layerDiscovery: document.querySelector('#layer-discovery'),
  layerSearch: document.querySelector('#layer-search'),
  layerButtons: document.querySelector('#layer-buttons'),
  layerProjects: document.querySelector('#layer-projects'),
  layerDeck: document.querySelector('#layer-track-deck'),
  globeReset: document.querySelector('#globe-reset'),
  search: document.querySelector('#commons-search'),
  searchClear: document.querySelector('#search-clear'),
  filterToggle: document.querySelector('#filter-toggle'),
  discoveryPanel: document.querySelector('#discovery-panel'),
  discoveryClose: document.querySelector('#discovery-close'),
  discoveryCount: document.querySelector('#discovery-count'),
  discoveryEmpty: document.querySelector('#discovery-empty'),
  discoveryList: document.querySelector('#discovery-list'),
  filterClear: document.querySelector('#filter-clear'),
  filterSelects: [...document.querySelectorAll('[data-intent-filter]')],
  discoveryOpenButtons: [...document.querySelectorAll('[data-open-discovery]')],
  settingsToggle: document.querySelector('#settings-toggle'),
  settingsPanel: document.querySelector('#settings-panel'),
  settingsClose: document.querySelector('#settings-close'),
  presentationButtons: [...document.querySelectorAll('[data-presentation-choice]')],
  focus: document.querySelector('#project-focus'),
  focusClose: document.querySelector('#focus-close'),
  focusTitle: document.querySelector('#focus-title'),
  focusSummary: document.querySelector('#focus-summary'),
  focusKind: document.querySelector('#focus-kind'),
  focusThemes: document.querySelector('#focus-themes'),
  focusActions: document.querySelector('#focus-actions'),
  focusLocations: document.querySelector('#focus-locations'),
  focusDigital: document.querySelector('#focus-digital'),
  focusRelations: document.querySelector('#focus-relations'),
  focusLinks: document.querySelector('#focus-links'),
  focusSources: document.querySelector('#focus-sources'),
  focusCuration: document.querySelector('#focus-curation'),
};

const runtime = {
  map: null,
  records: [],
  recordsById: new Map(),
  catalogProjection: null,
  searchIndex: null,
  visibleRecordsCache: null,
  lastPublicMapData: null,
  publicMapUpdateCount: 0,
  state: {
    camera: { ...DEFAULT_CAMERA },
    project: null,
    layer: null,
    view: 'globe',
    surface: 'globe',
    query: '',
    presence: null,
    action: null,
    language: null,
    access: null,
    freshness: null,
    curation: null,
  },
  previousGlobeCamera: null,
  viewPhase: 'overview',
  viewTransitionTimer: null,
  viewTransitionCleanup: null,
  layerPanelRevealTimer: null,
  layerPanelReady: false,
  layerReturnTarget: null,
  spherePointerStart: null,
  lastSpherePointerActivation: 0,
  applyingHistory: false,
  mapReady: false,
  mapRenderCount: 0,
  overlayRenderCount: 0,
  historyTimer: null,
  searchTimer: null,
  focusReturnTarget: null,
  settingsReturnTarget: null,
  discoveryReturnTarget: null,
  pendingSpatialProject: null,
  resizeObserver: null,
  catalogDegraded: false,
  mapDegraded: false,
  providerFallbackApplied: false,
  providerErrorLogged: false,
  laneResizeObserver: null,
  mapInteractionsBound: false,
};

function setStatus(message, state = 'loading') {
  elements.stage.dataset.runtimeState = state;
  elements.mapStatus.textContent = message;
}

function refreshStatus() {
  const failures = [];
  if (runtime.catalogDegraded) failures.push('Der Netzabruf des Katalogs ist fehlgeschlagen; die eingebettete, buildgebundene Fassung bleibt bedienbar.');
  if (runtime.mapDegraded) failures.push('Die Basiskarte ist vorübergehend nicht erreichbar; Globuszustand und Textansicht bleiben verfügbar.');
  if (failures.length) {
    setStatus(failures.join(' '), 'degraded');
  } else if (runtime.mapReady) {
    setStatus('Globus bereit. Ziehen zum Drehen, Pinch oder Tasten zum Zoomen.', 'ready');
  } else {
    setStatus('Globus wird geladen. Die Textansicht bleibt verfügbar.', 'loading');
  }
}

function storedPresentation() {
  try {
    return localStorage.getItem(PRESENTATION_STORAGE_KEY) === 'text' ? 'text' : 'globe';
  } catch {
    return 'globe';
  }
}

function persistPresentation(surface) {
  try {
    localStorage.setItem(PRESENTATION_STORAGE_KEY, surface);
  } catch {
    // Private browsing or a storage policy may reject local persistence.
  }
}

async function fetchJson(url, timeoutMs = 5000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  } finally {
    window.clearTimeout(timeout);
  }
}

function validateRecords(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error('Der Katalog enthält keine Einträge.');
  const ids = new Set();
  for (const record of records) {
    if (!record || typeof record.id !== 'string' || ids.has(record.id)) throw new Error('Ungültige oder doppelte CommonProject-ID.');
    if (!['geographic', 'digital', 'hybrid'].includes(record.kind)) throw new Error(`CommonProject ${record.id} besitzt eine unbekannte Präsenzart.`);
    const locations = record?.presence?.geographic;
    if (!Array.isArray(locations)) throw new Error(`CommonProject ${record.id} besitzt keine gültige Ortsliste.`);
    for (const location of locations) {
      if (!location || !['exact', 'approximate', 'hidden'].includes(location.mode)) throw new Error(`CommonProject ${record.id} besitzt einen ungültigen Ortsmodus.`);
      if (location.mode === 'hidden') {
        if ('geometry' in location || 'uncertainty_meters_min' in location) throw new Error(`Verborgener Ort ${location.id} darf keine Geometrie oder Ersatzgenauigkeit enthalten.`);
        continue;
      }
      if (!location.geometry || !['Point', 'Polygon', 'MultiPolygon'].includes(location.geometry.type)) throw new Error(`Öffentlicher Ort ${location.id} besitzt keine unterstützte Geometrie.`);
      if (location.mode === 'approximate' && !(Number(location.uncertainty_meters_min) > 0)) throw new Error(`Ungefährer Ort ${location.id} muss seine Mindestunschärfe nennen.`);
    }
    ids.add(record.id);
  }
  return records;
}

function bootstrapRecords() {
  const text = elements.bootstrap?.content?.textContent ?? '';
  return validateRecords(JSON.parse(text));
}

async function loadRecords() {
  const manifest = await fetchJson('./catalog/catalog.json');
  if (!Array.isArray(manifest.project_files) || manifest.project_files.length !== manifest.entry_count) {
    throw new Error('Katalogmanifest und Eintragszahl stimmen nicht überein.');
  }
  return validateRecords(await Promise.all(manifest.project_files.map((path) => fetchJson(`./catalog/${path}`))));
}

function installRecords(records) {
  runtime.records = records;
  runtime.catalogProjection = prepareCatalogProjection(records);
  runtime.searchIndex = prepareIntentSearchIndex(records);
  runtime.recordsById = runtime.catalogProjection.recordsById;
  elements.stage.dataset.searchIndexedRecords = String(runtime.searchIndex.indexedRecordCount);
  elements.stage.dataset.searchIndexedTerms = String(runtime.searchIndex.indexedTermCount);
  runtime.visibleRecordsCache = null;
  runtime.lastPublicMapData = null;
  runtime.publicMapUpdateCount = 0;
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function groupedDigitalRecords(records = runtime.records) {
  const grouped = new Map(LAYERS.map((layer) => [layer.id, []]));
  for (const record of records) {
    if (record?.presence?.digital?.available === true) grouped.get(deriveLayer(record))?.push(record);
  }
  return grouped;
}

function appendRingSequence(textPath, records, repeatCount) {
  for (let copy = 0; copy < repeatCount; copy += 1) {
    for (const record of records) {
      const name = createSvgElement('tspan', { class: 'sphere-ring-name' });
      name.textContent = `  ${record.title}  `;
      const binary = createSvgElement('tspan', { class: 'sphere-ring-binary' });
      binary.textContent = `${binaryName(record.title)}   `;
      textPath.append(name, binary);
    }
  }
}

function renderSphereRibbons(records = runtime.records) {
  elements.sphereStreams.replaceChildren();
  const grouped = groupedDigitalRecords(records);
  LAYERS.forEach((layer, layerIndex) => {
    const source = grouped.get(layer.id) ?? [];
    const displayRecords = source.length ? source : [{ title: layer.trackLabel }];
    const text = createSvgElement('text', {
      class: 'sphere-ring-text',
      'data-layer-id': layer.id,
    });
    const textPath = createSvgElement('textPath', {
      href: `#sphere-path-${layerIndex + 1}`,
      startOffset: `${(layerIndex * 11 + 3) % 100}%`,
    });
    appendRingSequence(textPath, displayRecords, ribbonRepeatCount(displayRecords.length, 10));
    text.append(textPath);
    text.toggleAttribute('data-empty', source.length === 0);
    elements.sphereStreams.append(text);
  });
  runtime.overlayRenderCount += 1;
  elements.stage.dataset.overlayRenders = String(runtime.overlayRenderCount);
}

function selectLayerTrack(layerId) {
  const nextLayer = runtime.state.layer === layerId ? null : layerId;
  if (runtime.state.project && nextLayer && deriveLayer(runtime.recordsById.get(runtime.state.project)) !== nextLayer) {
    runtime.state.project = null;
  }
  setLayer(nextLayer);
}

function createRibbonSegment(record, copyIndex) {
  const segment = document.createElement('button');
  segment.type = 'button';
  segment.className = 'digital-ribbon-item';
  segment.dataset.commonprojectId = record.id;
  segment.dataset.ribbonCopy = String(copyIndex);
  segment.setAttribute('aria-label', `${record.title} öffnen`);
  if (copyIndex > 0) segment.setAttribute('tabindex', '-1');
  const name = document.createElement('span');
  name.className = 'digital-ribbon-name';
  name.textContent = record.title;
  const binary = document.createElement('span');
  binary.className = 'digital-ribbon-binary';
  binary.textContent = binaryName(record.title);
  segment.append(name, binary);
  segment.addEventListener('click', () => selectProject(record.id, { trigger: segment }));
  return segment;
}

function updateLaneOverflow() {
  elements.layerDeck.querySelectorAll('.digital-lane-scroll').forEach((scroller) => {
    scroller.toggleAttribute('data-overflowing', scroller.scrollWidth > scroller.clientWidth + 2);
  });
}

function renderLayerDeck() {
  elements.layerDeck.replaceChildren();
  const grouped = groupedDigitalRecords();
  for (const layer of LAYERS) {
    const records = grouped.get(layer.id) ?? [];
    const lane = document.createElement('section');
    lane.className = 'digital-lane';
    lane.dataset.layerId = layer.id;
    lane.setAttribute('aria-label', layer.label);

    const focus = document.createElement('button');
    focus.type = 'button';
    focus.className = 'digital-lane-focus';
    focus.dataset.layerId = layer.id;
    focus.setAttribute('aria-pressed', 'false');
    focus.innerHTML = `<span>${layer.trackLabel}</span><small>${records.length} Commons</small>`;
    focus.addEventListener('click', () => selectLayerTrack(layer.id));

    const scroller = document.createElement('div');
    scroller.className = 'digital-lane-scroll';
    scroller.dataset.layerId = layer.id;
    scroller.tabIndex = 0;
    scroller.setAttribute('role', 'region');
    scroller.setAttribute('aria-label', `${layer.label} horizontal durchblättern`);
    const content = document.createElement('div');
    content.className = 'digital-lane-content';
    const repeats = ribbonRepeatCount(records.length, 10);
    for (let copy = 0; copy < repeats; copy += 1) {
      for (const record of records) content.append(createRibbonSegment(record, copy));
    }
    scroller.append(content);
    lane.append(focus, scroller);
    elements.layerDeck.append(lane);
  }
  runtime.laneResizeObserver?.disconnect();
  if ('ResizeObserver' in window) {
    runtime.laneResizeObserver = new ResizeObserver(updateLaneOverflow);
    elements.layerDeck.querySelectorAll('.digital-lane-scroll').forEach((scroller) => runtime.laneResizeObserver.observe(scroller));
  }
  window.requestAnimationFrame(updateLaneOverflow);
}

function renderSphere() {
  renderSphereRibbons(runtime.records);
  renderLayerDeck();
}

function renderLayerStack() {
  elements.layerStack.replaceChildren();
}

function layerForRecord(record) {
  return LAYERS.find(({ id }) => id === deriveLayer(record));
}

function discoveryCacheKey() {
  return [runtime.state.layer, runtime.state.query, ...INTENT_FILTER_NAMES.map((name) => runtime.state[name])]
    .map((value) => value ?? '')
    .join('\u001f');
}

function visibleRecords() {
  const key = discoveryCacheKey();
  if (runtime.visibleRecordsCache?.key === key) return runtime.visibleRecordsCache.records;
  const records = filterRecords(runtime.records, { ...runtime.state, searchIndex: runtime.searchIndex });
  runtime.visibleRecordsCache = { key, records };
  return records;
}

function recordsMatchingQuery() {
  return filterRecords(runtime.records, { ...runtime.state, layer: null, searchIndex: runtime.searchIndex });
}

function hasIntentFilters() {
  return INTENT_FILTER_NAMES.some((name) => Boolean(runtime.state[name]));
}

function currentPublicMapData() {
  if (!runtime.catalogProjection) return Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) });
  const filtering = Boolean(runtime.state.layer || normalizeQuery(runtime.state.query) || hasIntentFilters());
  const visibleProjectIds = filtering ? visibleRecords().map(({ id }) => id) : null;
  return runtime.catalogProjection.publicMapFeatureCollection(visibleProjectIds);
}

function publishPublicMapDiagnostics(data) {
  elements.stage.dataset.publicMapFeatures = String(data.features.length);
  elements.stage.dataset.publicMapProjectIds = String(new Set(data.features.map(({ properties }) => properties.project_id)).size);
  elements.stage.dataset.publicMapFeatureIds = data.features.map(({ id }) => id).join(',');
  elements.stage.dataset.publicMapLocationIds = data.features.map(({ properties }) => properties.location_id).join(',');
  elements.stage.dataset.publicMapUpdates = String(runtime.publicMapUpdateCount);
}

function updatePublicMapData() {
  if (!runtime.mapReady || !runtime.map) return;
  const source = runtime.map.getSource(PUBLIC_MAP_SOURCE_ID);
  if (!source || typeof source.setData !== 'function') return;
  const data = currentPublicMapData();
  if (runtime.lastPublicMapData !== data) {
    source.setData(data);
    runtime.lastPublicMapData = data;
    runtime.publicMapUpdateCount += 1;
  }
  publishPublicMapDiagnostics(data);
}

function ensurePublicMapLayers() {
  if (!runtime.map || !runtime.map.isStyleLoaded()) return;
  if (!runtime.map.getSource(PUBLIC_MAP_SOURCE_ID)) {
    const data = currentPublicMapData();
    runtime.map.addSource(PUBLIC_MAP_SOURCE_ID, { type: 'geojson', data });
    runtime.lastPublicMapData = data;
    publishPublicMapDiagnostics(data);
  }
  if (!runtime.map.getLayer('commonworld-public-extents')) {
    runtime.map.addLayer({
      id: 'commonworld-public-extents',
      type: 'fill',
      source: PUBLIC_MAP_SOURCE_ID,
      minzoom: 3.4,
      filter: ['==', ['get', 'representation_kind'], 'public_extent'],
      paint: {
        'fill-color': '#76c7a4',
        'fill-opacity': 0.32,
        'fill-outline-color': '#d7f4e8',
      },
    });
  }
  if (!runtime.map.getLayer('commonworld-approximate-zones')) {
    runtime.map.addLayer({
      id: 'commonworld-approximate-zones',
      type: 'fill',
      source: PUBLIC_MAP_SOURCE_ID,
      minzoom: 3.4,
      filter: ['==', ['get', 'representation_kind'], 'approximate_zone'],
      paint: {
        'fill-color': '#e8b96d',
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3.4, 0.2, 5.5, 0.24, 12, 0.15, 18, 0.1],
        'fill-outline-color': 'rgba(255, 242, 212, 0.48)',
      },
    });
  }
  if (!runtime.map.getLayer('commonworld-exact-anchors')) {
    runtime.map.addLayer({
      id: 'commonworld-exact-anchors',
      type: 'circle',
      source: PUBLIC_MAP_SOURCE_ID,
      minzoom: 5.5,
      filter: ['==', ['get', 'representation_kind'], 'exact_anchor'],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 5.5, 6, 8, 10],
        'circle-color': '#8bd9f5',
        'circle-opacity': 0.94,
        'circle-stroke-color': '#e5f8ff',
        'circle-stroke-width': 1.5,
      },
    });
  }
  updatePublicMapData();
}

function updateSemanticLocationLine() {
  const zoom = runtime.mapReady ? runtime.map.getZoom() : runtime.state.camera.zoom;
  const line = semanticLocationLine({
    zoom,
    records: visibleRecords(),
    selectedProjectId: runtime.state.project,
    selectedRecord: runtime.state.project ? runtime.recordsById.get(runtime.state.project) ?? null : null,
  });
  elements.stage.dataset.semanticLevel = line.level;
  elements.semanticLevel.textContent = line.crumbs.at(-1) ?? 'Gesamtansicht';
  elements.semanticSummary.textContent = line.summary;
  elements.semanticSummary.setAttribute('aria-label', line.crumbs.join(' nach '));
}

function renderLayerButtons(container) {
  container.replaceChildren();
  const queryMatches = recordsMatchingQuery();
  for (const layer of LAYERS) {
    const count = queryMatches.filter((record) => deriveLayer(record) === layer.id).length;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'layer-filter';
    button.dataset.layerId = layer.id;
    button.setAttribute('aria-pressed', String(runtime.state.layer === layer.id));
    button.textContent = `${layer.label} · ${count}`;
    button.addEventListener('click', () => setLayer(runtime.state.layer === layer.id ? null : layer.id));
    container.append(button);
  }
}

function renderLayerPanel() {
  renderLayerButtons(elements.layerButtons);
  elements.layerProjects.replaceChildren();
  elements.layerSearch.value = runtime.state.query;
}

function openDiscovery({ trigger = document.activeElement, focusFirst = false } = {}) {
  if (trigger instanceof Element && !elements.discoveryPanel.contains(trigger)) runtime.discoveryReturnTarget = trigger;
  elements.discoveryPanel.hidden = false;
  elements.filterToggle.setAttribute('aria-expanded', 'true');
  elements.search.setAttribute('aria-expanded', 'true');
  if (focusFirst) elements.discoveryList.querySelector('.discovery-result-main')?.focus({ preventScroll: true });
}

function closeDiscovery({ restoreFocus = false } = {}) {
  elements.discoveryPanel.hidden = true;
  elements.filterToggle.setAttribute('aria-expanded', 'false');
  elements.search.setAttribute('aria-expanded', 'false');
  if (restoreFocus && runtime.discoveryReturnTarget instanceof Element && runtime.discoveryReturnTarget.isConnected) {
    runtime.discoveryReturnTarget.focus({ preventScroll: true });
  }
  runtime.discoveryReturnTarget = null;
}

function syncIntentFilterControls() {
  for (const select of elements.filterSelects) {
    select.value = runtime.state[select.dataset.intentFilter] ?? '';
  }
  elements.filterClear.disabled = !hasIntentFilters();
}

function setIntentFilter(name, value, { historyMode = 'push' } = {}) {
  const select = elements.filterSelects.find((candidate) => candidate.dataset.intentFilter === name);
  if (!select) return;
  const allowed = [...select.options].some((option) => option.value === value);
  runtime.state[name] = allowed && value ? value : null;
  renderDiscoveryState();
  if (historyMode) writeHistory(historyMode);
}

function clearIntentFilters({ historyMode = 'push' } = {}) {
  for (const name of INTENT_FILTER_NAMES) runtime.state[name] = null;
  renderDiscoveryState();
  if (historyMode) writeHistory(historyMode);
}

function directActionLinks(record) {
  const actions = new Set(Array.isArray(record?.actions) ? record.actions : []);
  return (Array.isArray(record?.links) ? record.links : []).filter((link) => (
    link && ACTION_LINK_TYPES.has(link.type) && actions.has(link.type) && typeof link.url === 'string' && link.url.startsWith('https://')
  ));
}

function resultLocationLabel(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  const publicCount = locations.filter((location) => location?.mode !== 'hidden' && location?.geometry).length;
  if (publicCount > 0) return publicCount === 1 ? '1 öffentlicher Ort' : String(publicCount) + ' öffentliche Orte';
  return record?.presence?.digital?.available ? 'Ortsunabhängige digitale Präsenz' : 'Keine öffentliche Geometrie';
}

function createDiscoveryResult(record, position) {
  const item = document.createElement('li');
  item.className = 'discovery-result';
  item.dataset.commonprojectId = record.id;

  const main = document.createElement('button');
  main.type = 'button';
  main.className = 'discovery-result-main';
  main.dataset.commonprojectId = record.id;
  main.setAttribute('aria-label', String(position + 1) + '. ' + record.title + ' öffnen');

  const rank = document.createElement('span');
  rank.className = 'discovery-result-rank';
  rank.textContent = String(position + 1);
  const copy = document.createElement('span');
  copy.className = 'discovery-result-copy';
  const title = document.createElement('strong');
  title.textContent = record.title;
  const meta = document.createElement('span');
  meta.className = 'discovery-result-meta';
  meta.textContent = recordPresentationLabel(record) + ' · ' + resultLocationLabel(record);
  const summary = document.createElement('span');
  summary.className = 'discovery-result-summary';
  summary.textContent = record.summary;
  copy.append(title, meta, summary);
  main.append(rank, copy);
  main.addEventListener('click', () => selectProject(record.id, { trigger: main, navigateSpatial: true }));
  item.append(main);

  const actions = directActionLinks(record);
  if (actions.length) {
    const links = document.createElement('div');
    links.className = 'discovery-result-actions';
    for (const link of actions) {
      const anchor = document.createElement('a');
      anchor.href = link.url;
      anchor.rel = 'external noreferrer';
      anchor.dataset.actionType = link.type;
      anchor.textContent = link.label;
      links.append(anchor);
    }
    item.append(links);
  }
  return item;
}

function renderDiscoveryResults() {
  const records = visibleRecords();
  elements.discoveryList.replaceChildren(...records.map(createDiscoveryResult));
  const count = records.length;
  elements.discoveryCount.textContent = String(count) + ' Commons';
  elements.discoveryEmpty.hidden = count !== 0;
  elements.discoveryList.hidden = count === 0;
}

function renderTextView() {
  const visible = visibleRecords();
  const visibleIds = new Set(visible.map(({ id }) => id));
  const catalog = document.querySelector('#catalog');
  document.querySelectorAll('.catalog-card[data-commonproject-id]').forEach((card) => {
    card.hidden = !visibleIds.has(card.dataset.commonprojectId);
  });
  for (const record of visible) {
    const card = catalog?.querySelector('.catalog-card[data-commonproject-id="' + CSS.escape(record.id) + '"]');
    if (card) catalog.append(card);
  }
  renderLayerButtons(elements.textLayerButtons);
  const count = visibleIds.size;
  elements.textCount.textContent = String(count) + ' Commons';
  elements.textEmpty.hidden = count !== 0;
}

function updateSphereResultVisibility() {
  const visible = visibleRecords();
  const visibleIds = new Set(visible.map(({ id }) => id));
  const focusedLayer = runtime.state.view === 'layers' ? runtime.state.layer : null;
  if (focusedLayer) elements.stage.dataset.focusedLayer = focusedLayer;
  else delete elements.stage.dataset.focusedLayer;
  renderSphereRibbons(visible);
  elements.layerDeck.querySelectorAll('.digital-ribbon-item[data-commonproject-id]').forEach((segment) => {
    segment.hidden = !visibleIds.has(segment.dataset.commonprojectId);
  });
  elements.layerDeck.querySelectorAll('.digital-lane[data-layer-id]').forEach((lane) => {
    const selected = focusedLayer === lane.dataset.layerId;
    const primaryVisible = [...lane.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]')].filter((segment) => !segment.hidden).length;
    lane.classList.toggle('is-focused', selected);
    lane.toggleAttribute('data-layer-hidden', Boolean(focusedLayer && !selected));
    lane.toggleAttribute('data-empty', primaryVisible === 0);
    lane.querySelector('.digital-lane-focus')?.setAttribute('aria-pressed', String(selected));
  });
  window.requestAnimationFrame(updateLaneOverflow);
}

function replaceList(container, values) {
  container.replaceChildren();
  for (const value of values) {
    const item = document.createElement('li');
    item.textContent = value;
    container.append(item);
  }
}

function replaceLinks(container, links) {
  container.replaceChildren();
  for (const link of links) {
    if (!link || typeof link.url !== 'string' || !link.url.startsWith('https://')) continue;
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = link.url;
    anchor.rel = 'external noreferrer';
    anchor.textContent = link.label || link.url;
    item.append(anchor);
    container.append(item);
  }
}

function updateFocusPanel() {
  const record = runtime.state.project ? runtime.recordsById.get(runtime.state.project) : null;
  elements.focus.hidden = !record;
  if (!record) return;
  elements.focusTitle.textContent = record.title;
  elements.focusSummary.textContent = record.summary;
  elements.focusKind.textContent = recordPresentationLabel(record);
  replaceList(elements.focusThemes, record.themes ?? []);
  replaceList(elements.focusActions, record.actions ?? []);
  replaceList(elements.focusLocations, recordLocationSummaries(record));
  const digital = record?.presence?.digital;
  elements.focusDigital.textContent = digital?.available
    ? (digital.label ?? 'Digitale Präsenz veröffentlicht')
    : 'Keine digitale Präsenz veröffentlicht.';
  const relationLabels = (runtime.catalogProjection?.relations ?? [])
    .filter(({ source_project_id }) => source_project_id === record.id)
    .map(({ relation_type, target_title }) => relation_type === 'chapter-of'
      ? `Teil von ${target_title}`
      : `${relation_type} · ${target_title}`);
  replaceList(elements.focusRelations, relationLabels.length ? relationLabels : ['Keine belegte Beziehung veröffentlicht.']);
  replaceLinks(elements.focusLinks, record.links ?? []);
  replaceLinks(elements.focusSources, record?.provenance?.sources ?? []);
  elements.focusCuration.textContent = `Redaktionell geprüft am ${record?.curation?.reviewed_at ?? 'unbekannt'}; nächste Prüfung ${record?.curation?.next_review_at ?? 'offen'}.`;
}

function updateSelectionMarks() {
  document.querySelectorAll('[data-commonproject-id]').forEach((element) => {
    const selected = element.dataset.commonprojectId === runtime.state.project;
    element.classList.toggle('is-selected', selected);
    if (element.matches('button') || element.getAttribute('role') === 'button') element.setAttribute('aria-pressed', String(selected));
    if (element.matches('.catalog-card')) element.toggleAttribute('data-selected', selected);
  });
  updateFocusPanel();
  updateSemanticLocationLine();
}

function renderDiscoveryState() {
  renderLayerPanel();
  renderTextView();
  renderDiscoveryResults();
  syncIntentFilterControls();
  updateSphereResultVisibility();
  updatePublicMapData();
  updateSelectionMarks();
  const count = visibleRecords().length;
  elements.globeResults.textContent = count === 0
    ? 'Keine Commons entsprechen dieser Suche oder Filterauswahl.'
    : String(count) + ' Commons in der aktuellen Auswahl.';
  elements.globeResults.toggleAttribute('data-empty', count === 0);
  elements.search.value = runtime.state.query;
  elements.layerSearch.value = runtime.state.query;
  elements.searchClear.hidden = runtime.state.query.length === 0;
}

function currentUrlState() {
  const preserveOverviewCamera = (runtime.state.view === 'layers' || runtime.viewPhase === 'leaving-layers') && runtime.previousGlobeCamera;
  const camera = preserveOverviewCamera
    ? runtime.previousGlobeCamera
    : (runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera);
  return { ...runtime.state, camera };
}

function writeHistory(mode = 'replace') {
  if (runtime.applyingHistory) return;
  const state = currentUrlState();
  const url = `${location.pathname}${searchFromState(state)}${location.hash}`;
  history[mode === 'push' ? 'pushState' : 'replaceState']({ commonworld: state }, '', url);
}

function scheduleCameraHistory() {
  window.clearTimeout(runtime.historyTimer);
  runtime.historyTimer = window.setTimeout(() => writeHistory('replace'), 180);
}

function performSpatialNavigation(identifier) {
  const publicMapData = runtime.catalogProjection?.publicMapFeatureCollection() ?? { type: 'FeatureCollection', features: [] };
  const target = publicProjectNavigationTarget(publicMapData, identifier);
  runtime.pendingSpatialProject = null;
  if (!target) {
    elements.stage.dataset.lastSpatialResult = 'coordinate-free:' + identifier;
    return false;
  }

  closeDiscovery({ restoreFocus: false });
  if (runtime.state.surface !== 'globe') setPresentation('globe', { historyMode: null });
  if (runtime.state.view === 'layers' || runtime.viewPhase !== 'overview') {
    closeLayerView({ historyMode: null, instant: true, restoreFocus: false });
  }
  ensureMap();
  if (!runtime.mapReady) {
    runtime.pendingSpatialProject = identifier;
    elements.stage.dataset.lastSpatialResult = 'pending:' + identifier;
    return true;
  }

  const duration = reducedMotion.matches ? 0 : 520;
  if (target.kind === 'point') {
    applyCamera({
      center: target.center,
      zoom: target.zoom,
      bearing: 0,
      pitch: 0,
      padding: { top: 96, right: 56, bottom: 72, left: 56 },
    }, { instant: duration === 0, duration });
  } else {
    elements.stage.dataset.lastCameraCommand = duration === 0 ? 'fitBounds-instant' : 'fitBounds';
    elements.stage.dataset.lastCameraDuration = String(duration);
    runtime.map.fitBounds(target.bounds, {
      padding: { top: 112, right: 72, bottom: 88, left: 72 },
      maxZoom: 15,
      duration,
      essential: false,
    });
  }
  elements.stage.dataset.lastSpatialResult = target.kind + ':' + identifier;
  return true;
}

function selectProject(identifier, { historyMode = 'push', focus = true, trigger = document.activeElement, navigateSpatial = false } = {}) {
  if (!runtime.recordsById.has(identifier)) return;
  if (trigger instanceof Element && !elements.focus.contains(trigger)) runtime.focusReturnTarget = trigger;
  if (!elements.discoveryPanel.hidden) closeDiscovery({ restoreFocus: false });
  runtime.state.project = identifier;
  renderDiscoveryState();
  if (navigateSpatial) performSpatialNavigation(identifier);
  if (historyMode) writeHistory(historyMode);
  if (focus) elements.focus.focus({ preventScroll: true });
}

function isVisibleFocusTarget(target) {
  return target instanceof Element && typeof target.focus === 'function' && target.isConnected && target.getClientRects().length > 0 && !target.closest('[hidden]');
}


function visibleProjectTrigger(identifier) {
  const escaped = CSS.escape(identifier);
  const candidates = [
    ...document.querySelectorAll(`.digital-ribbon-item[data-commonproject-id="${escaped}"], .catalog-select[data-commonproject-id="${escaped}"]`),
  ];
  return candidates.find(isVisibleFocusTarget) ?? null;
}

function clearProject({ historyMode = 'push', restoreFocus = true } = {}) {
  const closingIdentifier = runtime.state.project;
  runtime.state.project = null;
  updateSelectionMarks();
  if (historyMode) writeHistory(historyMode);
  if (restoreFocus && closingIdentifier) {
    const remembered = isVisibleFocusTarget(runtime.focusReturnTarget) ? runtime.focusReturnTarget : null;
    const surfaceFallback = runtime.state.surface === 'text' ? elements.search : elements.globeReset;
    const target = remembered ?? visibleProjectTrigger(closingIdentifier) ?? surfaceFallback;
    target?.focus({ preventScroll: true });
    runtime.focusReturnTarget = null;
  }
}

function setLayer(layer, { historyMode = 'push' } = {}) {
  const nextLayer = LAYERS.some(({ id }) => id === layer) ? layer : null;
  if (runtime.state.project && nextLayer && deriveLayer(runtime.recordsById.get(runtime.state.project)) !== nextLayer) runtime.state.project = null;
  runtime.state.layer = nextLayer;
  renderDiscoveryState();
  if (runtime.state.view === 'layers' && nextLayer) {
    window.requestAnimationFrame(() => elements.layerDeck.querySelector(`.digital-lane[data-layer-id="${CSS.escape(nextLayer)}"] .digital-lane-scroll`)?.focus({ preventScroll: true }));
  }
  if (historyMode) writeHistory(historyMode);
}

function setQuery(value, { historyMode = 'replace' } = {}) {
  runtime.state.query = normalizeQuery(value);
  renderDiscoveryState();
  window.clearTimeout(runtime.searchTimer);
  if (historyMode) runtime.searchTimer = window.setTimeout(() => writeHistory(historyMode), 150);
}

function setSphereOpacity({ globeDiameter = null, rect = null } = {}) {
  const immersive = runtime.state.view === 'layers' || runtime.viewPhase !== 'overview';
  let globeViewportRatio = 0;
  let opacity = 1;
  if (!immersive && runtime.mapReady) {
    const bounds = rect ?? elements.stage.getBoundingClientRect();
    const suppliedDiameter = globeDiameter !== null && globeDiameter !== undefined
      ? Number(globeDiameter)
      : Number.NaN;
    const measuredDiameter = Number.isFinite(suppliedDiameter)
      ? suppliedDiameter
      : Number(elements.stage.dataset.globeDiameter ?? 0);
    globeViewportRatio = measuredDiameter / Math.max(1, Math.min(bounds.width, bounds.height));
    opacity = sphereOpacityForGlobeRatio(globeViewportRatio);
  }
  elements.sphere.style.setProperty('--sphere-opacity', String(opacity));
  elements.sphere.toggleAttribute('data-hidden-local', opacity === 0);
  elements.stage.dataset.globeViewportRatio = String(Number(globeViewportRatio.toFixed(4)));
}

function projectedGlobeGeometry(center, projectedCenter) {
  const horizon = globeHorizonCoordinates(center).map(({ lng, lat }) => runtime.map.project([lng, lat]));
  return projectedGlobeCircle({ center: projectedCenter, horizon });
}

function updateSphereGeometry() {
  if (!runtime.mapReady || elements.globeSurface.hidden) return;
  const rect = elements.stage.getBoundingClientRect();
  const padding = typeof runtime.map.getPadding === 'function' ? runtime.map.getPadding() : {};
  const sideView = runtime.state.view === 'layers' || runtime.viewPhase !== 'overview';
  const center = runtime.map.getCenter();
  const projectedCenter = runtime.map.project(center);
  const globe = sideView ? null : projectedGlobeGeometry(center, projectedCenter);
  const geometry = sphereLayout({
    width: rect.width,
    height: rect.height,
    padding,
    globe,
    sideView,
  });
  elements.stage.style.setProperty('--sphere-x', `${geometry.x}px`);
  elements.stage.style.setProperty('--sphere-y', `${geometry.y}px`);
  elements.stage.style.setProperty('--sphere-size', `${geometry.diameter}px`);
  elements.sphere.style.setProperty('--sphere-x', `${geometry.x}px`);
  elements.sphere.style.setProperty('--sphere-y', `${geometry.y}px`);
  elements.sphere.style.setProperty('--sphere-size', `${geometry.diameter}px`);
  elements.stage.dataset.mapProjectedCenterX = String(Number(projectedCenter.x.toFixed(2)));
  elements.stage.dataset.mapProjectedCenterY = String(Number(projectedCenter.y.toFixed(2)));
  elements.stage.dataset.sphereX = String(geometry.x);
  elements.stage.dataset.sphereY = String(geometry.y);
  elements.stage.dataset.sphereSize = String(geometry.diameter);
  elements.stage.dataset.globeDiameter = String(geometry.globeDiameter);
  elements.stage.dataset.globeGeometrySource = sideView ? 'side-view-layout' : 'maplibre-projected-horizon';
  const detailLevel = sphereDetailLevel({ diameter: geometry.diameter, sideView });
  elements.sphere.dataset.detailLevel = detailLevel;
  elements.stage.dataset.sphereDetailLevel = detailLevel;
  elements.stage.dataset.mapZoom = String(Number(runtime.map.getZoom().toFixed(4)));
  setSphereOpacity({ globeDiameter: geometry.globeDiameter, rect });
}

function layerCamera(camera = null) {
  const current = camera ?? (runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera);
  return {
    ...digitalLayerCamera(current),
    offset: [-Math.min(240, window.innerWidth * 0.18), 0],
  };
}

function applyCamera(camera, { instant = false, duration = 260 } = {}) {
  if (!runtime.map) return;
  const options = {
    center: camera.center ?? [camera.lng, camera.lat],
    zoom: camera.zoom,
    bearing: camera.bearing,
    pitch: camera.pitch,
    padding: camera.padding ?? { top: 0, right: 0, bottom: 0, left: 0 },
    offset: camera.offset ?? [0, 0],
  };
  const useJump = instant || reducedMotion.matches;
  elements.stage.dataset.lastCameraCommand = useJump ? 'jumpTo' : 'easeTo';
  elements.stage.dataset.lastCameraDuration = useJump ? '0' : String(duration);
  if (useJump) runtime.map.jumpTo(options);
  else runtime.map.easeTo({ ...options, duration, essential: false });
}

function clearViewTransition() {
  window.clearTimeout(runtime.viewTransitionTimer);
  runtime.viewTransitionTimer = null;
  window.clearTimeout(runtime.layerPanelRevealTimer);
  runtime.layerPanelRevealTimer = null;
  runtime.viewTransitionCleanup?.();
  runtime.viewTransitionCleanup = null;
}

function scheduleViewTransition(phase, duration, options = {}) {
  let completed = false;
  const expectedOpacity = phase === 'overview' ? 1 : 0;
  const visualTargetReached = () => Math.abs(Number.parseFloat(getComputedStyle(elements.map).opacity) - expectedOpacity) <= 0.02;
  const complete = () => {
    if (completed) return;
    completed = true;
    finishViewTransition(phase, options);
  };
  const completeIfReady = () => {
    if (!visualTargetReached()) return false;
    complete();
    return true;
  };
  const onTransitionEnd = (event) => {
    if (event.target === elements.map && event.propertyName === 'opacity') completeIfReady();
  };
  elements.map.addEventListener('transitionend', onTransitionEnd);
  runtime.viewTransitionCleanup = () => elements.map.removeEventListener('transitionend', onTransitionEnd);
  runtime.viewTransitionTimer = window.setTimeout(() => {
    if (completed) return;
    const animations = typeof elements.map.getAnimations === 'function' ? elements.map.getAnimations() : [];
    for (const animation of animations) {
      try {
        animation.finish();
      } catch {
        // A cancelled transition is settled by the no-transition fallback below.
      }
    }
    if (completeIfReady()) return;
    const previousTransition = elements.map.style.transition;
    const previousOpacity = elements.map.style.opacity;
    elements.map.style.transition = 'none';
    elements.map.style.opacity = String(expectedOpacity);
    void elements.map.offsetWidth;
    complete();
    elements.map.style.opacity = previousOpacity;
    elements.map.style.transition = previousTransition;
  }, Math.max(2000, duration * 3));
}

function setViewPhase(phase) {
  const allowed = new Set(['overview', 'entering-layers', 'layers-preview', 'layers', 'leaving-layers']);
  runtime.viewPhase = allowed.has(phase) ? phase : 'overview';
  elements.stage.dataset.viewPhase = runtime.viewPhase;
  elements.stage.dataset.viewPhaseStartedAt = String(performance.now());
  if (runtime.viewPhase === 'layers-preview') {
    elements.stage.dataset.layerPreviewStartedAt = elements.stage.dataset.viewPhaseStartedAt;
    delete elements.stage.dataset.layerPanelVisibleAt;
  }
  if (runtime.viewPhase === 'leaving-layers') {
    elements.stage.dataset.layerReturnStartedAt = elements.stage.dataset.viewPhaseStartedAt;
  }
  updateSphereGeometry();
  if (!runtime.mapReady) setSphereOpacity();
}

function showLayerState() {
  const journeyActive = runtime.state.surface === 'globe' && (runtime.state.view === 'layers' || runtime.viewPhase !== 'overview');
  const panelMounted = runtime.state.surface === 'globe' && runtime.viewPhase === 'layers';
  const panelVisible = panelMounted && runtime.layerPanelReady;
  const transformed = runtime.state.surface === 'globe' && runtime.state.view === 'layers';
  elements.stage.classList.toggle('layer-view-open', transformed);
  elements.stage.classList.toggle('layer-view-settled', runtime.viewPhase === 'layers-preview' || runtime.viewPhase === 'layers');
  elements.layerPanel.hidden = !panelMounted;
  elements.layerPanel.toggleAttribute('data-visible', panelVisible);
  elements.layerPanel.toggleAttribute('inert', !panelVisible);
  elements.layerToggle.setAttribute('aria-expanded', String(runtime.state.view === 'layers'));
  elements.layerDeck.toggleAttribute('inert', !panelVisible);
  elements.layerDeck.setAttribute('aria-hidden', String(!panelVisible));
  elements.sphere.setAttribute('aria-hidden', String(runtime.viewPhase === 'layers'));
  elements.map.toggleAttribute('inert', journeyActive);
  elements.layerToggle.toggleAttribute('inert', journeyActive);
  if (journeyActive) {
    elements.map.setAttribute('aria-hidden', 'true');
    elements.layerToggle.setAttribute('aria-hidden', 'true');
    elements.sphereEdge.setAttribute('aria-hidden', 'true');
    elements.sphereEdge.setAttribute('tabindex', '-1');
  } else {
    elements.map.removeAttribute('aria-hidden');
    elements.layerToggle.removeAttribute('aria-hidden');
    elements.sphereEdge.removeAttribute('aria-hidden');
    elements.sphereEdge.setAttribute('tabindex', '0');
    elements.layerPanel.removeAttribute('data-closing');
  }
}

function finishViewTransition(phase, { restoreFocus = false, revealImmediately = false } = {}) {
  clearViewTransition();
  runtime.layerPanelReady = false;
  setViewPhase(phase);
  showLayerState();
  if (phase === 'layers-preview') {
    runtime.layerPanelRevealTimer = window.setTimeout(() => {
      runtime.layerPanelRevealTimer = null;
      if (runtime.viewPhase !== 'layers-preview' || runtime.state.view !== 'layers') return;
      setViewPhase('layers');
      showLayerState();
      window.requestAnimationFrame(() => {
        if (runtime.viewPhase !== 'layers' || runtime.state.view !== 'layers') return;
        runtime.layerPanelReady = true;
        elements.stage.dataset.layerPanelVisibleAt = String(performance.now());
        showLayerState();
        elements.layerClose.focus({ preventScroll: true });
      });
    }, 280);
  } else if (phase === 'layers' && revealImmediately) {
    runtime.layerPanelReady = true;
    showLayerState();
    elements.layerClose.focus({ preventScroll: true });
  }
  if (phase === 'overview' && restoreFocus) {
    (runtime.layerReturnTarget ?? elements.layerToggle).focus({ preventScroll: true });
    runtime.layerReturnTarget = null;
  }
}

function openLayerView({ historyMode = 'push', cameraState = null, instant = false, trigger = document.activeElement } = {}) {
  if (cameraState) runtime.previousGlobeCamera = { ...cameraState };
  else if (runtime.state.view !== 'layers') runtime.previousGlobeCamera = runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera;
  if (runtime.state.view !== 'layers') {
    runtime.layerReturnTarget = trigger === elements.sphereEdge
      ? elements.sphereEdge
      : (trigger instanceof HTMLElement ? trigger : elements.layerToggle);
  }
  runtime.state.view = 'layers';
  clearViewTransition();
  const duration = instant || cameraState || reducedMotion.matches ? 0 : DIGITAL_LAYER_TRANSITION_MS;
  setViewPhase(duration ? 'entering-layers' : 'layers');
  elements.layerPanel.removeAttribute('data-closing');
  closeLayerDiscovery();
  showLayerState();
  renderLayerPanel();
  if (runtime.mapReady) applyCamera(layerCamera(cameraState), { instant: duration === 0, duration });
  if (duration) scheduleViewTransition('layers-preview', duration);
  else finishViewTransition('layers', { revealImmediately: true });
  if (historyMode) writeHistory(historyMode);
}

function closeLayerView({ historyMode = 'push', cameraState = null, preserveLayer = false, instant = false, restoreFocus = true } = {}) {
  const wasOpen = runtime.state.view === 'layers' || runtime.viewPhase !== 'overview';
  runtime.layerPanelReady = false;
  closeLayerDiscovery();
  runtime.state.view = 'globe';
  if (!preserveLayer) runtime.state.layer = null;
  clearViewTransition();
  const duration = instant || reducedMotion.matches ? 0 : DIGITAL_LAYER_TRANSITION_MS;
  if (wasOpen && duration) {
    elements.layerPanel.dataset.closing = 'true';
    setViewPhase('leaving-layers');
    showLayerState();
  }
  renderDiscoveryState();
  if (runtime.mapReady) applyCamera(cameraState ?? runtime.previousGlobeCamera ?? runtime.state.camera, { instant: duration === 0, duration });
  if (wasOpen && duration) scheduleViewTransition('overview', duration, { restoreFocus });
  else finishViewTransition('overview', { restoreFocus: wasOpen && restoreFocus });
  if (historyMode) writeHistory(historyMode);
}

function closeLayerDiscovery({ restoreFocus = false } = {}) {
  elements.layerDiscovery.hidden = true;
  elements.layerSearchToggle.setAttribute('aria-expanded', 'false');
  if (restoreFocus) elements.layerSearchToggle.focus({ preventScroll: true });
}

function toggleLayerDiscovery() {
  const opening = elements.layerDiscovery.hidden;
  elements.layerDiscovery.hidden = !opening;
  elements.layerSearchToggle.setAttribute('aria-expanded', String(opening));
  if (opening) {
    renderLayerPanel();
    elements.layerSearch.focus({ preventScroll: true });
  }
}

function closeSettings({ restoreFocus = true } = {}) {
  elements.settingsPanel.hidden = true;
  elements.settingsToggle.setAttribute('aria-expanded', 'false');
  if (restoreFocus) (runtime.settingsReturnTarget ?? elements.settingsToggle).focus({ preventScroll: true });
  runtime.settingsReturnTarget = null;
}

function openSettings() {
  runtime.settingsReturnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : elements.settingsToggle;
  elements.settingsPanel.hidden = false;
  elements.settingsToggle.setAttribute('aria-expanded', 'true');
  elements.settingsClose.focus({ preventScroll: true });
}

function updatePresentationControls() {
  for (const button of elements.presentationButtons) {
    const selected = button.dataset.presentationChoice === runtime.state.surface;
    button.setAttribute('aria-checked', String(selected));
    button.classList.toggle('is-selected', selected);
  }
}

function setPresentation(surface, { historyMode = 'push', persist = true } = {}) {
  runtime.state.surface = surface === 'text' ? 'text' : 'globe';
  elements.body.dataset.presentation = runtime.state.surface;
  elements.globeSurface.hidden = runtime.state.surface !== 'globe';
  elements.textView.hidden = runtime.state.surface !== 'text';
  clearViewTransition();
  if (runtime.state.surface === 'text') setViewPhase('overview');
  else if (runtime.state.view === 'layers') setViewPhase('layers');
  showLayerState();
  updatePresentationControls();
  if (persist) persistPresentation(runtime.state.surface);
  if (runtime.state.surface === 'globe') {
    ensureMap();
    window.setTimeout(() => {
      runtime.map?.resize();
      updateSphereGeometry();
    }, 0);
  }
  if (historyMode) writeHistory(historyMode);
}

function resetGlobe() {
  clearViewTransition();
  runtime.previousGlobeCamera = null;
  runtime.layerReturnTarget = null;
  runtime.state.view = 'globe';
  setViewPhase('overview');
  runtime.state.layer = null;
  runtime.state.camera = { ...DEFAULT_CAMERA };
  showLayerState();
  renderDiscoveryState();
  if (runtime.mapReady) applyCamera(DEFAULT_CAMERA);
  writeHistory('push');
}

function applyDeepLink(search, { initial = false } = {}) {
  const next = stateFromSearch(search, runtime.records.map(({ id }) => id));
  if (initial && !new URLSearchParams(search).has('surface')) next.surface = storedPresentation();
  runtime.applyingHistory = true;
  runtime.state = next;
  elements.search.value = next.query;
  setPresentation(next.surface, { historyMode: null, persist: false });
  if (runtime.mapReady) {
    applyCamera(next.camera, { instant: true });
    if (next.view === 'layers') openLayerView({ historyMode: null, cameraState: next.camera, instant: true });
    else closeLayerView({ historyMode: null, cameraState: next.camera, preserveLayer: true, instant: true, restoreFocus: false });
  } else {
    showLayerState();
  }
  renderDiscoveryState();
  if (next.query || hasIntentFilters()) openDiscovery({ trigger: elements.search });
  else closeDiscovery({ restoreFocus: false });
  runtime.applyingHistory = false;
  if (initial) writeHistory('replace');
}


function activateSphereEdge(event) {
  if (Number.isFinite(event?.clientX) && Number.isFinite(event?.clientY)) {
    const mapControl = [...document.querySelectorAll('.maplibregl-ctrl button')].find((button) => {
      const rect = button.getBoundingClientRect();
      return event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
    });
    if (mapControl) {
      event.preventDefault();
      event.stopPropagation();
      elements.stage.dataset.forwardedMapControl = mapControl.getAttribute('aria-label') ?? mapControl.getAttribute('title') ?? 'unknown';
      mapControl.click();
      return;
    }
  }
  delete elements.stage.dataset.forwardedMapControl;
  openLayerView({ trigger: elements.sphereEdge });
}

function beginSpherePointer(event) {
  if (event.button !== undefined && event.button !== 0) return;
  runtime.spherePointerStart = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    at: performance.now(),
  };
  event.currentTarget.setPointerCapture?.(event.pointerId);
}

function endSpherePointer(event) {
  const start = runtime.spherePointerStart;
  runtime.spherePointerStart = null;
  if (!start || start.pointerId !== event.pointerId) return;
  const distance = Math.hypot(event.clientX - start.x, event.clientY - start.y);
  const elapsed = performance.now() - start.at;
  if (distance > 12 || elapsed > 700) return;
  runtime.lastSpherePointerActivation = performance.now();
  activateSphereEdge(event);
}

function cancelSpherePointer() {
  runtime.spherePointerStart = null;
}

function activateSphereFallbackClick(event) {
  if (runtime.state.view === 'layers' || runtime.viewPhase !== 'overview') return;
  if (performance.now() - runtime.lastSpherePointerActivation < 500) return;
  activateSphereEdge(event);
}

function wireControls() {
  elements.skipLink.addEventListener('click', (event) => {
    event.preventDefault();
    setPresentation('text');
    elements.textView.focus({ preventScroll: true });
  });
  elements.layerToggle.addEventListener('click', () => (runtime.state.view === 'layers' ? closeLayerView() : openLayerView({ trigger: elements.layerToggle })));
  elements.layerClose.addEventListener('click', () => closeLayerView());
  elements.layerSearchToggle.addEventListener('click', toggleLayerDiscovery);
  elements.layerSearch.addEventListener('input', () => setQuery(elements.layerSearch.value));
  elements.sphereEdge.addEventListener('pointerdown', beginSpherePointer);
  elements.sphereEdge.addEventListener('pointerup', endSpherePointer);
  elements.sphereEdge.addEventListener('pointercancel', cancelSpherePointer);
  elements.sphereEdge.addEventListener('click', activateSphereFallbackClick);
  elements.sphereEdge.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openLayerView({ trigger: elements.sphereEdge });
    }
  });
  elements.globeReset.addEventListener('click', resetGlobe);
  elements.focusClose.addEventListener('click', () => clearProject());
  elements.filterToggle.addEventListener('click', () => {
    if (elements.discoveryPanel.hidden) openDiscovery({ trigger: elements.filterToggle });
    else closeDiscovery({ restoreFocus: true });
  });
  elements.discoveryClose.addEventListener('click', () => closeDiscovery({ restoreFocus: true }));
  for (const button of elements.discoveryOpenButtons) {
    button.addEventListener('click', () => openDiscovery({ trigger: button }));
  }
  for (const select of elements.filterSelects) {
    select.addEventListener('change', () => setIntentFilter(select.dataset.intentFilter, select.value));
  }
  elements.filterClear.addEventListener('click', () => clearIntentFilters());
  elements.search.addEventListener('input', () => {
    openDiscovery({ trigger: elements.search });
    setQuery(elements.search.value);
  });
  elements.search.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowDown') return;
    event.preventDefault();
    openDiscovery({ trigger: elements.search, focusFirst: true });
  });
  elements.discoveryList.addEventListener('keydown', (event) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const results = [...elements.discoveryList.querySelectorAll('.discovery-result-main')];
    if (!results.length) return;
    const current = results.indexOf(document.activeElement);
    let next = current;
    if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = results.length - 1;
    else if (event.key === 'ArrowDown') next = Math.min(results.length - 1, Math.max(0, current + 1));
    else next = Math.max(0, current <= 0 ? 0 : current - 1);
    event.preventDefault();
    results[next].focus({ preventScroll: true });
  });
  elements.searchClear.addEventListener('click', () => {
    setQuery('', { historyMode: 'push' });
    elements.search.focus();
  });
  elements.settingsToggle.addEventListener('click', () => {
    if (elements.settingsPanel.hidden) openSettings();
    else closeSettings();
  });
  elements.settingsClose.addEventListener('click', () => closeSettings());
  for (const button of elements.presentationButtons) {
    button.addEventListener('click', () => {
      setPresentation(button.dataset.presentationChoice);
      closeSettings({ restoreFocus: false });
      if (runtime.state.surface === 'text') elements.textView.focus({ preventScroll: true });
      else elements.globeReset.focus({ preventScroll: true });
    });
  }
  document.querySelectorAll('.catalog-select').forEach((button) => {
    button.addEventListener('click', () => selectProject(button.dataset.commonprojectId, { trigger: button, navigateSpatial: true }));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!elements.discoveryPanel.hidden) closeDiscovery({ restoreFocus: true });
    else if (!elements.layerDiscovery.hidden) closeLayerDiscovery({ restoreFocus: true });
    else if (runtime.viewPhase !== 'overview' || runtime.state.view === 'layers') closeLayerView();
    else if (!elements.settingsPanel.hidden) closeSettings();
    else if (!elements.focus.hidden) clearProject();
  });
  window.addEventListener('popstate', () => applyDeepLink(location.search));
  window.addEventListener('resize', () => {
    runtime.map?.resize();
    updateSphereGeometry();
  });
}

function bindPublicMapInteractions() {
  if (!runtime.map || runtime.mapInteractionsBound) return;
  runtime.mapInteractionsBound = true;
  runtime.map.on('click', (event) => {
    const layers = PUBLIC_MAP_LAYER_IDS.filter((identifier) => runtime.map.getLayer(identifier));
    if (!layers.length) return;
    const feature = runtime.map.queryRenderedFeatures(event.point, { layers })[0];
    const identifier = feature?.properties?.project_id;
    if (typeof identifier === 'string') selectProject(identifier, { trigger: runtime.map.getCanvas() });
  });
  runtime.map.on('mousemove', (event) => {
    const layers = PUBLIC_MAP_LAYER_IDS.filter((identifier) => runtime.map.getLayer(identifier));
    const interactive = layers.length > 0 && runtime.map.queryRenderedFeatures(event.point, { layers }).length > 0;
    runtime.map.getCanvas().style.cursor = interactive ? 'pointer' : '';
  });
  runtime.map.on('mouseleave', () => { runtime.map.getCanvas().style.cursor = ''; });
}

function createMap() {
  if (runtime.map) return;
  if (!window.maplibregl?.Map) {
    runtime.mapDegraded = true;
    refreshStatus();
    setPresentation('text', { historyMode: 'replace', persist: false });
    return;
  }
  runtime.map = new window.maplibregl.Map({
    container: elements.map,
    style: './assets/map/openfreemap-liberty.json',
    center: [runtime.state.camera.lng, runtime.state.camera.lat],
    zoom: runtime.state.camera.zoom,
    bearing: runtime.state.camera.bearing,
    pitch: runtime.state.camera.pitch,
    minZoom: 0.35,
    maxZoom: MAX_MAP_ZOOM,
    attributionControl: true,
    renderWorldCopies: false,
    fadeDuration: reducedMotion.matches ? 0 : 120,
  });
  runtime.map.addControl(new window.maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }), 'bottom-right');
  bindPublicMapInteractions();
  runtime.map.on('render', () => {
    runtime.mapRenderCount += 1;
    elements.stage.dataset.mapRenders = String(runtime.mapRenderCount);
    updateSphereGeometry();
  });
  runtime.map.on('movestart', () => { elements.stage.dataset.mapMoving = 'true'; });
  runtime.map.on('moveend', () => {
    delete elements.stage.dataset.mapMoving;
    updateSphereGeometry();
    updateSemanticLocationLine();
    scheduleCameraHistory();
  });
  runtime.map.on('error', (event) => {
    const policy = mapFailurePolicy({ providerReadbackFailed: false });
    degradeMap(event?.error ?? event, { replaceStyle: policy.replaceStyle });
  });
  runtime.map.on('styledata', () => {
    if (runtime.mapReady) ensurePublicMapLayers();
  });
  runtime.map.on('idle', () => {
    if (runtime.mapReady && !runtime.map.getSource(PUBLIC_MAP_SOURCE_ID)) ensurePublicMapLayers();
  });
  runtime.map.on('load', () => {
    runtime.mapReady = true;
    runtime.map.setProjection({ type: 'globe' });
    ensurePublicMapLayers();
    updateSphereGeometry();
    updateSemanticLocationLine();
    refreshStatus();
    if (runtime.state.view === 'layers') openLayerView({ historyMode: null, cameraState: runtime.state.camera, instant: true });
    else applyCamera(runtime.state.camera, { instant: true });
    if (runtime.pendingSpatialProject) performSpatialNavigation(runtime.pendingSpatialProject);
  });
  void verifyMapProvider();
  if ('ResizeObserver' in window) {
    runtime.resizeObserver = new ResizeObserver(() => {
      runtime.map?.resize();
      updateSphereGeometry();
    });
    runtime.resizeObserver.observe(elements.stage);
  }
}

function degradeMap(error, { replaceStyle = true } = {}) {
  runtime.mapDegraded = true;
  if (!runtime.providerErrorLogged) {
    runtime.providerErrorLogged = true;
    console.warn('Commonworld map provider degraded', error);
  }
  if (replaceStyle && runtime.map && !runtime.providerFallbackApplied) {
    runtime.providerFallbackApplied = true;
    elements.stage.dataset.providerFallback = 'true';
    try { runtime.map.setStyle(LOCAL_FALLBACK_STYLE); } catch { /* The text surface remains available. */ }
  }
  refreshStatus();
}

async function verifyMapProvider(timeoutMs = 4000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch('https://tiles.openfreemap.org/planet', { signal: controller.signal, headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`OpenFreeMap HTTP ${response.status}`);
  } catch (error) {
    const policy = mapFailurePolicy({ providerReadbackFailed: true });
    degradeMap(error, { replaceStyle: policy.replaceStyle });
  } finally {
    window.clearTimeout(timeout);
  }
}

function ensureMap() {
  if (!runtime.map) createMap();
}

async function boot() {
  try {
    const embedded = bootstrapRecords();
    installRecords(embedded);
    renderSphere();
    renderLayerStack();
    wireControls();
    applyDeepLink(location.search, { initial: true });
    renderDiscoveryState();
    document.documentElement.classList.add('runtime-ready');

    try {
      const fetched = await loadRecords();
      if (JSON.stringify(fetched) !== JSON.stringify(embedded)) {
        throw new Error('Netzkatalog und buildgebundener Katalog unterscheiden sich.');
      }
    } catch (error) {
      runtime.catalogDegraded = true;
      console.warn('Commonworld catalogue verification degraded; using build-bound bootstrap', error);
      refreshStatus();
    }
  } catch (error) {
    console.error(error);
    setStatus('Commonworld konnte auch den buildgebundenen Katalog nicht lesen.', 'failed');
    elements.body.dataset.presentation = 'text';
    elements.globeSurface.hidden = true;
    elements.textView.hidden = false;
    document.documentElement.classList.add('runtime-failed');
  }
}

boot();
