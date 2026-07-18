import { BOOTSTRAP_RECORDS } from './commonworld-bootstrap-catalog.mjs';
import {
  DEFAULT_CAMERA,
  MAX_MAP_ZOOM,
  binaryName,
  buildDigitalPresentationTree,
  deriveLayer,
  digitalPathContainsRecord,
  digitalPresentationTreeConstructionCount,
  DIGITAL_LAYER_TRANSITION_MS,
  DIGITAL_ROOT_PATH,
  digitalLayerCamera,
  filterRecords,
  globeHorizonCoordinates,
  hasDigitalPresence,
  mapCamera,
  mapFailurePolicy,
  normalizeDigitalPath,
  normalizeQuery,
  prepareCatalogProjection,
  prepareIntentSearchIndex,
  recordLocationSummaries,
  recordPresentationLabel,
  projectedGlobeCircle,
  publicGeographicLocations,
  publicGeographicRepresentationKind,
  publicProjectNavigationTarget,
  ribbonRepeatCount,
  ringOrbitDirection,
  ringOrbitDuration,
  ringOrbitStartAngle,
  safeExternalHttpsUrl,
  searchFromState,
  serializeDigitalPath,
  semanticLocationLine,
  sphereDetailLevel,
  sphereLayout,
  sphereOpacityForGlobeRatio,
  stateFromSearch,
  visibleDigitalNodes,
} from './commonworld-core.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const LOCAL_FALLBACK_STYLE = Object.freeze({ version: 8, sources: {}, layers: [{ id: 'commonworld-fallback', type: 'background', paint: { 'background-color': '#0d2426' } }] });
const PRESENTATION_STORAGE_KEY = 'commonworld.presentation';
const PUBLIC_MAP_SOURCE_ID = 'commonworld-public-representations';
const PUBLIC_MAP_LAYER_IDS = Object.freeze(['commonworld-public-extents', 'commonworld-approximate-zones', 'commonworld-exact-anchors']);
const ACTION_LINK_TYPES = new Set(['visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate']);
const INTENT_FILTER_NAMES = Object.freeze(['presence', 'action', 'language', 'access', 'freshness', 'curation']);
const DIGITAL_IDENTITY_DOM_LIMIT = 48;
const TEXT_IDENTITY_DOM_LIMIT = 48;
const DISCOVERY_RESULT_PREVIEW_LIMIT = 50;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const elements = {
  body: document.body,
  skipLink: document.querySelector('.skip-link'),
  topbar: document.querySelector('.topbar'),
  globeSurface: document.querySelector('#globe-surface'),
  textView: document.querySelector('#text-view'),
  textCount: document.querySelector('#text-count'),
  textEmpty: document.querySelector('#text-empty'),
  textLayerBreadcrumb: document.querySelector('#text-layer-breadcrumb'),
  textLayerCurrent: document.querySelector('#text-layer-current'),
  textLayerButtons: document.querySelector('#text-layer-buttons'),
  textShowMore: document.querySelector('#text-show-more'),
  stage: document.querySelector('.globe-stage'),
  map: document.querySelector('#map'),
  mapStatus: document.querySelector('#map-status'),
  globeResults: document.querySelector('#globe-results'),
  semanticLevel: document.querySelector('#semantic-level'),
  semanticSummary: document.querySelector('#semantic-summary'),
  sphere: document.querySelector('#digital-sphere'),
  sphereRings: document.querySelector('#sphere-rings'),
  sphereEdge: document.querySelector('#sphere-edge-control'),
  sphereFocus: document.querySelector('.sphere-edge-focus'),
  layerStack: document.querySelector('#layer-stack-visual'),
  layerToggle: document.querySelector('#layer-view-button'),
  layerPanel: document.querySelector('#layer-panel'),
  layerClose: document.querySelector('#layer-close'),
  layerSearchToggle: document.querySelector('#layer-search-toggle'),
  layerDiscovery: document.querySelector('#layer-discovery'),
  layerSearch: document.querySelector('#layer-search'),
  layerBreadcrumb: document.querySelector('#layer-breadcrumb'),
  layerCurrent: document.querySelector('#layer-current'),
  layerButtons: document.querySelector('#layer-buttons'),
  layerProjects: document.querySelector('#layer-projects'),
  layerDeck: document.querySelector('#layer-track-deck'),
  orientationBar: document.querySelector('.orientation-bar'),
  globeReset: document.querySelector('#globe-reset'),
  search: document.querySelector('#commons-search'),
  searchClear: document.querySelector('#search-clear'),
  filterToggle: document.querySelector('#filter-toggle'),
  discoveryPanel: document.querySelector('#discovery-panel'),
  discoveryClose: document.querySelector('#discovery-close'),
  discoveryCount: document.querySelector('#discovery-count'),
  discoveryEmpty: document.querySelector('#discovery-empty'),
  discoveryList: document.querySelector('#discovery-list'),
  discoveryShowText: document.querySelector('#discovery-show-text'),
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
  focusPresence: document.querySelector('#focus-presence'),
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
  digitalTree: null,
  searchIndex: null,
  visibleRecordsCache: null,
  unfilteredPathRecordsCache: null,
  lastPublicMapData: null,
  publicMapUpdateCount: 0,
  state: {
    camera: { ...DEFAULT_CAMERA },
    project: null,
    layer: null,
    digitalPath: DIGITAL_ROOT_PATH,
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
  cameraFlightGeneration: 0,
  cameraFlightCleanup: null,
  viewTransitionCleanup: null,
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
  activeOverlay: null,
  settingsReturnTarget: null,
  discoveryReturnTarget: null,
  pendingSpatialProject: null,
  resizeObserver: null,
  orientationResizeObserver: null,
  catalogDegraded: false,
  mapDegraded: false,
  providerFallbackApplied: false,
  providerErrorLogged: false,
  laneResizeObserver: null,
  mapInteractionsBound: false,
  stageSize: null,
  sphereGeometryCommitCount: 0,
  publicMapInteractiveLayerIds: null,
  pointerHitTestFrame: null,
  pointerHitTestPoint: null,
  inputModality: null,
  pendingHierarchyFocusPath: null,
  hierarchyFocusTimer: null,
  presentationKey: null,
  identityPresentationLimit: DIGITAL_IDENTITY_DOM_LIMIT,
  textPresentationLimit: TEXT_IDENTITY_DOM_LIMIT,
};

function setStylePropertyIfChanged(element, name, value) {
  if (element.style.getPropertyValue(name) === value) return false;
  element.style.setProperty(name, value);
  return true;
}

function updateOrientationBarClearance() {
  const height = Math.ceil(elements.orientationBar?.getBoundingClientRect().height ?? 0);
  if (height > 0) setStylePropertyIfChanged(elements.stage, '--orientation-bar-height', `${height}px`);
}

function installOrientationBarClearanceTracking() {
  updateOrientationBarClearance();
  if (!('ResizeObserver' in window)) return;
  runtime.orientationResizeObserver?.disconnect();
  runtime.orientationResizeObserver = new ResizeObserver(updateOrientationBarClearance);
  runtime.orientationResizeObserver.observe(elements.orientationBar);
}

function setDatasetIfChanged(element, name, value) {
  const serialized = String(value);
  if (element.dataset[name] === serialized) return false;
  element.dataset[name] = serialized;
  return true;
}

function setAttributePresenceIfChanged(element, name, present) {
  if (element.hasAttribute(name) === present) return false;
  element.toggleAttribute(name, present);
  return true;
}

function currentStageSize() {
  if (runtime.stageSize?.width > 0 && runtime.stageSize?.height > 0) return runtime.stageSize;
  return {
    width: Math.max(1, elements.stage.clientWidth),
    height: Math.max(1, elements.stage.clientHeight),
  };
}

function setStageSizeIfChanged(width, height) {
  const next = { width: Math.max(1, width), height: Math.max(1, height) };
  const current = runtime.stageSize;
  if (current && Math.abs(current.width - next.width) < 0.25 && Math.abs(current.height - next.height) < 0.25) return false;
  runtime.stageSize = next;
  return true;
}

function setInputModality(modality) {
  const next = modality === 'keyboard' ? 'keyboard' : 'pointer';
  if (runtime.inputModality === next) return;
  runtime.inputModality = next;
  document.documentElement.dataset.inputModality = next;
  syncSphereKeyboardFocus();
}

function installInputModalityTracking() {
  const usePointerModality = () => setInputModality('pointer');
  const useKeyboardModality = (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    setInputModality('keyboard');
  };
  document.addEventListener('pointerdown', usePointerModality, { capture: true, passive: true });
  document.addEventListener('touchstart', usePointerModality, { capture: true, passive: true });
  document.addEventListener('mousedown', usePointerModality, { capture: true, passive: true });
  document.addEventListener('keydown', useKeyboardModality, true);
  setInputModality(window.matchMedia('(pointer: coarse)').matches ? 'pointer' : 'keyboard');
}

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
    if (record.schema_version !== 4) throw new Error(`CommonProject ${record.id} verwendet nicht Schema v4.`);
    if (Object.prototype.hasOwnProperty.call(record, 'kind')) throw new Error(`CommonProject ${record.id} enthält das entfernte Feld kind.`);
    const locations = record?.presence?.geographic;
    if (!Array.isArray(locations)) throw new Error(`CommonProject ${record.id} besitzt keine gültige Ortsliste.`);
    const isDigital = hasDigitalPresence(record);
    const hasClaimedPresence = locations.length > 0 || isDigital;
    if (!hasClaimedPresence) throw new Error(`CommonProject ${record.id} besitzt keine belegte Präsenz.`);
    for (const location of locations) {
      if (!location || !['exact', 'approximate', 'hidden'].includes(location.mode)) throw new Error(`CommonProject ${record.id} besitzt einen ungültigen Ortsmodus.`);
      if (location.mode === 'hidden') {
        if ('geometry' in location || 'uncertainty_meters_min' in location) throw new Error(`Verborgener Ort ${location.id} darf keine Geometrie oder Ersatzgenauigkeit enthalten.`);
        continue;
      }
      if (!publicGeographicRepresentationKind(location)) throw new Error(`Öffentlicher Ort ${location.id} besitzt keine gültige kartierbare Geometrie.`);
    }
    ids.add(record.id);
  }
  return records;
}

function bootstrapRecords() {
  return validateRecords(BOOTSTRAP_RECORDS);
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
  runtime.digitalTree = buildDigitalPresentationTree(records);
  runtime.searchIndex = prepareIntentSearchIndex(records);
  runtime.recordsById = runtime.catalogProjection.recordsById;
  elements.stage.dataset.searchIndexedRecords = String(runtime.searchIndex.indexedRecordCount);
  elements.stage.dataset.searchIndexedTerms = String(runtime.searchIndex.indexedTermCount);
  runtime.visibleRecordsCache = null;
  runtime.unfilteredPathRecordsCache = null;
  runtime.lastPublicMapData = null;
  runtime.publicMapUpdateCount = 0;
  runtime.presentationKey = null;
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function recordsForNode(node) {
  return (node?.identityIds ?? []).map((identifier) => runtime.recordsById.get(identifier)).filter(Boolean);
}

function currentDigitalPath() {
  return runtime.state.digitalPath ?? DIGITAL_ROOT_PATH;
}

function setCurrentDigitalPathDataset() {
  elements.stage.dataset.digitalPath = serializeDigitalPath(currentDigitalPath());
}

function digitalPathFiltered() {
  return serializeDigitalPath(currentDigitalPath()) !== serializeDigitalPath(DIGITAL_ROOT_PATH);
}

function treeForRecords(records = runtime.records) {
  if (records === runtime.records && runtime.digitalTree) return runtime.digitalTree;
  return buildDigitalPresentationTree(records);
}

function unfilteredPathRecords() {
  const key = discoveryCacheKey();
  if (runtime.unfilteredPathRecordsCache?.key === key) return runtime.unfilteredPathRecordsCache.records;
  const records = filterRecords(runtime.records, {
    ...runtime.state,
    layer: null,
    digitalPath: DIGITAL_ROOT_PATH,
    searchIndex: runtime.searchIndex,
  });
  runtime.unfilteredPathRecordsCache = { key, records };
  return records;
}

function syncPresentationBudgets() {
  const key = discoveryCacheKey();
  if (runtime.presentationKey === key) return;
  runtime.presentationKey = key;
  runtime.identityPresentationLimit = DIGITAL_IDENTITY_DOM_LIMIT;
  runtime.textPresentationLimit = TEXT_IDENTITY_DOM_LIMIT;
}

function visibleDigitalView(records = visibleRecords()) {
  syncPresentationBudgets();
  return visibleDigitalNodes(treeForRecords(records), currentDigitalPath(), { identityLimit: runtime.identityPresentationLimit });
}

function appendRingSequence(textPath, records, { prefix = '' } = {}) {
  if (prefix) {
    const label = createSvgElement('tspan', { class: 'sphere-ring-label' });
    label.textContent = `  ${prefix}  `;
    textPath.append(label);
  }
  for (const record of records) {
    const name = createSvgElement('tspan', { class: 'sphere-ring-name', 'data-commonproject-id': record.id });
    name.textContent = `  ${record.title}  `;
    const binary = createSvgElement('tspan', { class: 'sphere-ring-binary' });
    binary.textContent = `${binaryName(record.title)}   `;
    textPath.append(name, binary);
  }
}

function renderSphereRibbons(records = runtime.records) {
  const view = visibleDigitalView(records);
  const childBundles = view.children.filter((node) => node.type !== 'identity');
  const visibleNodes = (childBundles.length ? childBundles : (view.current ? [view.current] : []))
    .filter((node) => node.type !== 'diagnostic' || node.identityCount > 0)
    .slice(0, 8);
  elements.sphereRings.replaceChildren();
  visibleNodes.forEach((node, layerIndex) => {
    const source = recordsForNode(node).slice(0, node.type === 'field' ? 2 : 3);
    const plane = createSvgElement('g', {
      class: 'sphere-ring-plane',
      'data-node-id': node.id,
      'data-layer-id': node.id,
      'data-digital-path': node.pathKey,
      'data-ring-index': String(layerIndex),
    });
    const guide = createSvgElement('use', {
      href: `#sphere-path-${layerIndex + 1}`,
      class: 'sphere-layer-guide',
      'data-node-id': node.id,
      'data-layer-id': node.id,
    });
    plane.append(guide);
    const orbitDuration = ringOrbitDuration(node.identityCount);
    plane.dataset.entryCount = String(node.identityCount);
    plane.dataset.identityCount = String(node.identityCount);
    plane.dataset.orbitDuration = String(orbitDuration);
    plane.style.setProperty('--ring-orbit-duration', `${orbitDuration}s`);
    plane.style.setProperty('--ring-orbit-direction', String(ringOrbitDirection(layerIndex)));
    plane.style.setProperty('--ring-orbit-start-angle', `${ringOrbitStartAngle(layerIndex)}deg`);
    const text = createSvgElement('text', {
      class: 'sphere-ring-text',
      'data-layer-id': node.id,
      'data-node-id': node.id,
      'data-digital-path': node.pathKey,
      'data-entry-count': String(source.length),
    });
    const textPath = createSvgElement('textPath', {
      href: `#sphere-path-${layerIndex + 1}`,
      startOffset: `${(layerIndex * 11 + 3) % 100}%`,
    });
    if (source.length) {
      appendRingSequence(textPath, source, { prefix: `${node.label} · ${node.identityCount}` });
    } else {
      const placeholder = createSvgElement('tspan', { class: 'sphere-ring-placeholder' });
      placeholder.textContent = `  ${node.label} · keine sichtbaren Einträge  `;
      textPath.append(placeholder);
    }
    text.append(textPath);
    text.toggleAttribute('data-empty', source.length === 0);
    plane.append(text);
    elements.sphereRings.append(plane);
  });
  runtime.overlayRenderCount += 1;
  elements.stage.dataset.overlayRenders = String(runtime.overlayRenderCount);
}

function selectDigitalBundle(path) {
  setDigitalPath(path);
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
  const view = visibleDigitalView();
  if (!view.current) return;
  const identityLevel = view.children.length > 0 && view.children.every((node) => node.type === 'identity');
  const laneNodes = identityLevel ? [view.current] : view.children.filter((node) => node.identityCount > 0 || node.type === 'identity');
  elements.layerDeck.style.setProperty('--lane-count', String(Math.max(1, laneNodes.length)));
  const visibleIdentityRecords = identityLevel
    ? view.children.map((node) => runtime.recordsById.get(node.projectId)).filter(Boolean)
    : null;
  for (const [index, node] of laneNodes.entries()) {
    const allRecords = visibleIdentityRecords ?? recordsForNode(node);
    const records = identityLevel || node.type === 'identity' ? allRecords : allRecords.slice(0, 4);
    const lane = document.createElement('section');
    lane.className = 'digital-lane';
    lane.dataset.layerId = node.id;
    lane.dataset.nodeId = node.id;
    lane.dataset.digitalPath = node.pathKey;
    lane.style.setProperty('--lane-index', String(index));
    lane.setAttribute('aria-label', `${node.label}, ${node.identityCount} Commons`);

    const focus = document.createElement('button');
    focus.type = 'button';
    focus.className = 'digital-lane-focus';
    focus.dataset.layerId = node.id;
    focus.dataset.nodeId = node.id;
    focus.dataset.digitalPath = node.pathKey;
    focus.setAttribute('aria-pressed', 'false');
    focus.setAttribute('aria-expanded', String(!identityLevel && serializeDigitalPath(currentDigitalPath()) === node.pathKey));
    if (serializeDigitalPath(currentDigitalPath()) === node.pathKey) focus.setAttribute('aria-current', 'page');
    const focusLabel = document.createElement('span');
    focusLabel.textContent = node.label;
    const count = document.createElement('small');
    count.textContent = `${node.identityCount} Commons`;
    focus.append(focusLabel, count);
    focus.addEventListener('click', () => {
      if (identityLevel) return;
      selectDigitalBundle(node.path);
    });

    const scroller = document.createElement('div');
    scroller.className = 'digital-lane-scroll';
    scroller.dataset.layerId = node.id;
    scroller.dataset.nodeId = node.id;
    scroller.dataset.digitalPath = node.pathKey;
    scroller.tabIndex = 0;
    scroller.setAttribute('role', 'region');
    scroller.setAttribute('aria-label', `${node.label} horizontal durchblättern`);
    const content = document.createElement('div');
    content.className = 'digital-lane-content';
    const repeats = identityLevel ? 1 : ribbonRepeatCount(records.length, 10);
    for (let copy = 0; copy < repeats; copy += 1) {
      for (const record of records) content.append(createRibbonSegment(record, copy));
    }
    scroller.append(content);
    lane.append(focus, scroller);
    if (identityLevel) {
      const shown = records.length;
      const status = document.createElement('p');
      status.className = 'identity-presentation-status';
      status.setAttribute('role', 'status');
      status.textContent = `${shown} von ${node.identityCount} Commons angezeigt`;
      lane.append(status);
      if (shown < node.identityCount) {
        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'quiet-button identity-show-more';
        more.dataset.digitalPath = node.pathKey;
        const increment = Math.min(DIGITAL_IDENTITY_DOM_LIMIT, node.identityCount - shown);
        more.textContent = `Weitere ${increment} anzeigen`;
        more.setAttribute('aria-label', `Weitere ${increment} Commons in ${node.label} anzeigen`);
        more.addEventListener('click', () => {
          runtime.identityPresentationLimit += DIGITAL_IDENTITY_DOM_LIMIT;
          renderDiscoveryState();
          queueMicrotask(() => {
            document.querySelector(`.identity-show-more[data-digital-path="${CSS.escape(node.pathKey)}"]`)?.focus({ preventScroll: true });
          });
        });
        lane.append(more);
      }
    }
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

function discoveryCacheKey() {
  return [runtime.state.layer, serializeDigitalPath(currentDigitalPath()), runtime.state.query, ...INTENT_FILTER_NAMES.map((name) => runtime.state[name])]
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
  return filterRecords(runtime.records, { ...runtime.state, layer: null, digitalPath: DIGITAL_ROOT_PATH, searchIndex: runtime.searchIndex });
}

function hasIntentFilters() {
  return INTENT_FILTER_NAMES.some((name) => {
    const value = runtime.state[name];
    return Array.isArray(value) ? value.length > 0 : Boolean(value);
  });
}

function currentPublicMapData() {
  if (!runtime.catalogProjection) return Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) });
  const filtering = Boolean(digitalPathFiltered() || normalizeQuery(runtime.state.query) || hasIntentFilters());
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
  runtime.publicMapInteractiveLayerIds = PUBLIC_MAP_LAYER_IDS.filter((identifier) => runtime.map.getLayer(identifier));
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
  const tree = treeForRecords(unfilteredPathRecords());
  const view = visibleDigitalNodes(tree, currentDigitalPath());
  const currentKey = view.current?.pathKey ?? serializeDigitalPath(DIGITAL_ROOT_PATH);
  for (const node of view.children.filter((child) => child.type !== 'identity' && child.identityCount > 0)) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'layer-filter';
    button.dataset.layerId = node.id;
    button.dataset.nodeId = node.id;
    button.dataset.digitalPath = node.pathKey;
    button.setAttribute('aria-pressed', String(currentKey === node.pathKey));
    button.setAttribute('aria-expanded', 'false');
    button.textContent = `${node.label} · ${node.identityCount}`;
    button.addEventListener('click', () => setDigitalPath(node.path));
    container.append(button);
  }
}

function renderLayerPanel() {
  renderLayerButtons(elements.layerButtons);
  elements.layerProjects.replaceChildren();
  elements.layerSearch.value = runtime.state.query;
  setCurrentDigitalPathDataset();
  renderDigitalBreadcrumb(elements.layerBreadcrumb, elements.layerCurrent);
}

function renderDigitalBreadcrumb(breadcrumbElement, currentElement) {
  const tree = treeForRecords(unfilteredPathRecords());
  const view = visibleDigitalNodes(tree, currentDigitalPath());
  if (currentElement) {
    currentElement.textContent = view.current
      ? `${view.current.label} · ${view.current.identityCount} Commons`
      : 'Digitale Commons-Sphäre';
  }
  if (breadcrumbElement) {
    breadcrumbElement.replaceChildren();
    for (const [index, crumb] of view.breadcrumb.entries()) {
      if (index > 0) {
        const separator = document.createElement('span');
        separator.textContent = '›';
        separator.setAttribute('aria-hidden', 'true');
        breadcrumbElement.append(separator);
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'digital-breadcrumb-item';
      button.dataset.digitalPath = crumb.pathKey;
      button.textContent = crumb.type === 'sphere' ? 'Sphäre' : crumb.label;
      if (index === view.breadcrumb.length - 1) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', () => setDigitalPath(crumb.path));
      breadcrumbElement.append(button);
    }
  }
}

function selectedProjectRecord() {
  return runtime.state.project ? runtime.recordsById.get(runtime.state.project) ?? null : null;
}

function syncPrimaryOverlayInteractivity({ discoveryOpen, settingsOpen, focusVisible }) {
  elements.skipLink.toggleAttribute('inert', settingsOpen);
  elements.topbar.toggleAttribute('inert', settingsOpen);
  elements.discoveryPanel.toggleAttribute('inert', settingsOpen);
  elements.globeSurface.toggleAttribute('inert', settingsOpen || discoveryOpen);
  elements.textView.toggleAttribute('inert', settingsOpen || discoveryOpen);
  elements.focus.toggleAttribute('inert', settingsOpen || discoveryOpen || !focusVisible);
}

function renderPrimaryOverlayState(record = selectedProjectRecord()) {
  const discoveryOpen = runtime.activeOverlay === 'discovery';
  const settingsOpen = runtime.activeOverlay === 'settings';
  const focusVisible = Boolean(record) && runtime.activeOverlay === null;

  elements.discoveryPanel.hidden = !discoveryOpen;
  elements.settingsPanel.hidden = !settingsOpen;
  elements.filterToggle.setAttribute('aria-expanded', String(discoveryOpen));
  elements.search.setAttribute('aria-expanded', String(discoveryOpen));
  elements.settingsToggle.setAttribute('aria-expanded', String(settingsOpen));
  elements.focus.hidden = !focusVisible;
  syncPrimaryOverlayInteractivity({ discoveryOpen, settingsOpen, focusVisible });
  if (focusVisible) elements.focus.removeAttribute('aria-hidden');
  else elements.focus.setAttribute('aria-hidden', 'true');
}

function setActiveOverlay(nextOverlay) {
  runtime.activeOverlay = nextOverlay === 'discovery' || nextOverlay === 'settings' ? nextOverlay : null;
  renderPrimaryOverlayState();
}

function openDiscovery({ trigger = document.activeElement, focusFirst = false } = {}) {
  if (runtime.activeOverlay === 'settings') runtime.settingsReturnTarget = null;
  if (trigger instanceof Element && !elements.discoveryPanel.contains(trigger)) runtime.discoveryReturnTarget = trigger;
  setActiveOverlay('discovery');
  if (focusFirst) elements.discoveryList.querySelector('.discovery-result-main')?.focus({ preventScroll: true });
}

function closeDiscovery({ restoreFocus = false } = {}) {
  const wasOpen = runtime.activeOverlay === 'discovery';
  if (wasOpen) setActiveOverlay(null);
  if (restoreFocus && wasOpen && runtime.discoveryReturnTarget instanceof Element && runtime.discoveryReturnTarget.isConnected) {
    runtime.discoveryReturnTarget.focus({ preventScroll: true });
  }
  runtime.discoveryReturnTarget = null;
}

function syncIntentFilterControls() {
  for (const control of elements.filterSelects) {
    const value = runtime.state[control.dataset.intentFilter];
    if (control.type === 'checkbox') {
      control.checked = Array.isArray(value) && value.includes(control.value);
    } else {
      control.value = value ?? '';
    }
  }
  elements.filterClear.disabled = !hasIntentFilters();
}

function setIntentFilter(name, value, { historyMode = 'push' } = {}) {
  if (name === 'presence') {
    const checkboxes = elements.filterSelects.filter(c => c.dataset.intentFilter === name);
    const checkedValues = checkboxes.filter(c => c.checked).map(c => c.value);
    runtime.state[name] = checkedValues.length > 0 ? Object.freeze(checkedValues) : null;
  } else {
    const select = elements.filterSelects.find((candidate) => candidate.dataset.intentFilter === name);
    if (!select) return;
    const allowed = [...select.options].some((option) => option.value === value);
    runtime.state[name] = allowed && value ? value : null;
  }
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
  return (Array.isArray(record?.links) ? record.links : []).flatMap((link) => {
    if (!link || !ACTION_LINK_TYPES.has(link.type) || !actions.has(link.type)) return [];
    const url = safeExternalHttpsUrl(link.url);
    return url ? [{ ...link, url }] : [];
  });
}

function resultLocationLabel(record) {
  const publicCount = publicGeographicLocations(record).length;
  if (publicCount > 0) return publicCount === 1 ? '1 öffentlicher Ort' : String(publicCount) + ' öffentliche Orte';
  const isDigital = hasDigitalPresence(record);
  return isDigital ? 'Ortsunabhängige digitale Präsenz' : 'Keine öffentliche Geometrie';
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
  const preview = records.slice(0, DISCOVERY_RESULT_PREVIEW_LIMIT);
  elements.discoveryList.replaceChildren(...preview.map(createDiscoveryResult));
  const total = records.length;
  elements.discoveryCount.textContent = total > preview.length
    ? `${preview.length} von ${total} Commons als Vorschau`
    : String(total) + ' Commons';
  elements.discoveryEmpty.hidden = total !== 0;
  elements.discoveryList.hidden = total === 0;
  elements.discoveryShowText.hidden = total <= preview.length;
  elements.discoveryShowText.textContent = total > preview.length ? `Alle ${total} Treffer in der Textansicht anzeigen` : '';
}

function createRuntimeCatalogCard(record) {
  const card = document.createElement('article');
  card.className = 'catalog-card';
  card.id = `project-${record.id}`;
  card.dataset.commonprojectId = record.id;
  const kind = document.createElement('p');
  kind.className = 'catalog-kind';
  kind.textContent = recordPresentationLabel(record);
  const title = document.createElement('h2');
  title.textContent = record.title;
  const summary = document.createElement('p');
  summary.textContent = record.summary;
  const location = document.createElement('p');
  location.className = 'catalog-location';
  location.textContent = resultLocationLabel(record);
  const actions = document.createElement('div');
  actions.className = 'catalog-actions';
  const open = document.createElement('button');
  open.className = 'catalog-select';
  open.type = 'button';
  open.dataset.commonprojectId = record.id;
  open.setAttribute('aria-pressed', 'false');
  open.textContent = 'Öffnen';
  open.addEventListener('click', () => selectProject(record.id, { trigger: open, navigateSpatial: true }));
  actions.append(open);
  for (const link of directActionLinks(record)) {
    const href = link.url;
    if (!href.startsWith('https://')) continue;
    const anchor = document.createElement('a');
    anchor.className = 'catalog-action-link';
    anchor.dataset.actionType = link.type;
    anchor.href = href;
    anchor.rel = 'external noreferrer';
    anchor.textContent = link.label;
    actions.append(anchor);
  }
  card.append(kind, title, summary, location, actions);
  return card;
}

function renderTextView() {
  const visible = visibleRecords();
  syncPresentationBudgets();
  const presented = visible.slice(0, runtime.textPresentationLimit);
  const visibleIds = new Set(presented.map(({ id }) => id));
  const catalog = document.querySelector('#catalog');
  for (const record of presented) {
    if (!catalog?.querySelector(`.catalog-card[data-commonproject-id="${CSS.escape(record.id)}"]`)) catalog?.append(createRuntimeCatalogCard(record));
  }
  document.querySelectorAll('.catalog-card[data-commonproject-id]').forEach((card) => {
    card.hidden = !visibleIds.has(card.dataset.commonprojectId);
  });
  for (const record of presented) {
    const card = catalog?.querySelector('.catalog-card[data-commonproject-id="' + CSS.escape(record.id) + '"]');
    if (card) catalog.append(card);
  }
  renderLayerButtons(elements.textLayerButtons);
  renderDigitalBreadcrumb(elements.textLayerBreadcrumb, elements.textLayerCurrent);
  const total = visible.length;
  elements.textCount.textContent = presented.length < total
    ? `${presented.length} von ${total} Commons angezeigt`
    : String(total) + ' Commons';
  elements.textEmpty.hidden = total !== 0;
  elements.textShowMore.hidden = presented.length >= total;
  if (presented.length < total) {
    const increment = Math.min(TEXT_IDENTITY_DOM_LIMIT, total - presented.length);
    elements.textShowMore.textContent = `Weitere ${increment} Commons anzeigen`;
    elements.textShowMore.setAttribute('aria-label', `Weitere ${increment} von insgesamt ${total} Commons anzeigen`);
  }
}

function updateSphereResultVisibility() {
  const visible = visibleRecords();
  const visibleIds = new Set(visible.map(({ id }) => id));
  const digitalView = visibleDigitalView();
  const identityLevel = digitalView.children.length > 0 && digitalView.children.every((node) => node.type === 'identity');
  const focusedPath = runtime.state.view === 'layers' && identityLevel ? serializeDigitalPath(currentDigitalPath()) : null;
  if (focusedPath && focusedPath !== serializeDigitalPath(DIGITAL_ROOT_PATH)) elements.stage.dataset.focusedPath = focusedPath;
  else delete elements.stage.dataset.focusedPath;
  renderSphereRibbons(visible);
  elements.layerDeck.querySelectorAll('.digital-ribbon-item[data-commonproject-id]').forEach((segment) => {
    segment.hidden = !visibleIds.has(segment.dataset.commonprojectId);
  });
  elements.layerDeck.querySelectorAll('.digital-lane[data-layer-id]').forEach((lane) => {
    const selected = focusedPath === lane.dataset.digitalPath;
    const primaryVisible = [...lane.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]')].filter((segment) => !segment.hidden).length;
    lane.classList.toggle('is-focused', selected);
    lane.toggleAttribute('data-layer-hidden', false);
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
    const url = safeExternalHttpsUrl(link?.url);
    if (!url || !url.startsWith('https://')) continue;
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.rel = 'external noreferrer';
    anchor.textContent = link.label || url;
    item.append(anchor);
    container.append(item);
  }
}

function updateFocusPanel() {
  const record = selectedProjectRecord();
  renderPrimaryOverlayState(record);
  if (!record) return;
  elements.focusTitle.textContent = record.title;
  elements.focusSummary.textContent = record.summary;
  elements.focusPresence.textContent = recordPresentationLabel(record);
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
  renderLayerDeck();
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
  elements.stage.dataset.digitalTreeConstructions = String(digitalPresentationTreeConstructionCount());
}

function currentUrlState() {
  const preserveOverviewCamera = (
    runtime.state.view === 'layers'
    || runtime.viewPhase === 'preparing-overview'
    || runtime.viewPhase === 'leaving-layers'
  ) && runtime.previousGlobeCamera;
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
  return target instanceof Element
    && typeof target.focus === 'function'
    && target.isConnected
    && target.getClientRects().length > 0
    && !target.matches(':disabled, input[type="hidden"]')
    && !target.closest('[hidden], [inert], [aria-hidden="true"]');
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

function projectMatchesDigitalState(identifier, state = runtime.state) {
  const record = identifier ? runtime.recordsById.get(identifier) : null;
  if (!record) return false;
  if (state.layer) return deriveLayer(record) === state.layer;
  return digitalPathContainsRecord(state.digitalPath ?? DIGITAL_ROOT_PATH, record);
}

function hierarchyFocusSurfaceReady() {
  if (runtime.state.surface === 'text') return !elements.textView.hidden;
  return runtime.state.view === 'layers'
    && runtime.viewPhase === 'layers'
    && elements.layerPanel.hasAttribute('data-visible')
    && !elements.layerPanel.hidden
    && !elements.layerPanel.hasAttribute('inert');
}

function focusVisibleHierarchyControl(pathKey) {
  const textSelectors = [
    '#text-layer-breadcrumb .digital-breadcrumb-item[aria-current="page"]',
    `#text-layer-buttons .layer-filter[data-digital-path="${CSS.escape(pathKey)}"]`,
    '#text-layer-buttons .layer-filter',
  ];
  const globeSelectors = [
    `.digital-lane[data-digital-path="${CSS.escape(pathKey)}"] .digital-lane-focus`,
    `.digital-lane[data-digital-path="${CSS.escape(pathKey)}"] .digital-lane-scroll`,
    '#layer-breadcrumb .digital-breadcrumb-item[aria-current="page"]',
    '#layer-close',
  ];
  const fallbackSelectors = runtime.state.surface === 'text'
    ? ['[data-open-discovery]', '#text-view']
    : ['#globe-reset'];
  const selectors = runtime.state.surface === 'text'
    ? [...textSelectors, ...globeSelectors, ...fallbackSelectors]
    : [...globeSelectors, ...textSelectors, ...fallbackSelectors];
  const target = selectors
    .map((selector) => document.querySelector(selector))
    .find(isVisibleFocusTarget);
  target?.focus({ preventScroll: true });
  return target ?? null;
}

function flushPendingHierarchyFocus() {
  const pathKey = runtime.pendingHierarchyFocusPath;
  if (!pathKey || !hierarchyFocusSurfaceReady()) return null;
  const target = focusVisibleHierarchyControl(pathKey);
  if (!target) return null;
  runtime.pendingHierarchyFocusPath = null;
  window.clearTimeout(runtime.hierarchyFocusTimer);
  runtime.hierarchyFocusTimer = null;
  return target;
}

const HIERARCHY_FOCUS_RETRY_DELAYS_MS = [0, 50, 150, 400, 900, 1800];

function isVisibleHierarchyFocusTarget(target = document.activeElement) {
  return isVisibleFocusTarget(target)
    && target.matches('.digital-lane-focus, .digital-lane-scroll, .digital-breadcrumb-item, .layer-filter, #layer-close');
}

function scheduleHierarchyFocus(pathKey, verificationAttempt = 0) {
  runtime.pendingHierarchyFocusPath = pathKey;
  window.clearTimeout(runtime.hierarchyFocusTimer);
  let attempt = 0;
  const tryFocus = () => {
    runtime.hierarchyFocusTimer = null;
    if (runtime.pendingHierarchyFocusPath !== pathKey) return;
    const target = flushPendingHierarchyFocus();
    if (target) {
      window.setTimeout(() => {
        if (runtime.state.project || serializeDigitalPath(currentDigitalPath()) !== pathKey) return;
        if (isVisibleHierarchyFocusTarget()) return;
        const active = document.activeElement;
        if (active && active !== document.body && isVisibleFocusTarget(active)) return;
        if (verificationAttempt >= 2) return;
        scheduleHierarchyFocus(pathKey, verificationAttempt + 1);
      }, 50);
      return;
    }
    attempt += 1;
    if (attempt >= HIERARCHY_FOCUS_RETRY_DELAYS_MS.length) return;
    runtime.hierarchyFocusTimer = window.setTimeout(tryFocus, HIERARCHY_FOCUS_RETRY_DELAYS_MS[attempt]);
  };
  runtime.hierarchyFocusTimer = window.setTimeout(tryFocus, HIERARCHY_FOCUS_RETRY_DELAYS_MS[attempt]);
}

function setDigitalPath(path, { historyMode = 'push' } = {}) {
  const normalized = normalizeDigitalPathForApp(path);
  const closesProject = Boolean(runtime.state.project) && !projectMatchesDigitalState(runtime.state.project, {
    ...runtime.state,
    layer: null,
    digitalPath: normalized.path,
  });
  runtime.state.digitalPath = normalized.path;
  runtime.state.layer = null;
  if (closesProject) {
    runtime.state.project = null;
    runtime.focusReturnTarget = null;
  }
  runtime.visibleRecordsCache = null;
  renderDiscoveryState();
  if (closesProject || runtime.state.view === 'layers' || runtime.state.surface === 'text') {
    scheduleHierarchyFocus(normalized.pathKey);
  }
  if (historyMode) writeHistory(historyMode);
}

function normalizeDigitalPathForApp(path) {
  const normalized = normalizeDigitalPath(path);
  if (!normalized.valid) return { path: DIGITAL_ROOT_PATH, pathKey: serializeDigitalPath(DIGITAL_ROOT_PATH) };
  const tree = runtime.digitalTree ?? treeForRecords(runtime.records);
  const current = tree.nodesByPath.get(normalized.pathKey);
  if (!current) {
    return { path: DIGITAL_ROOT_PATH, pathKey: serializeDigitalPath(DIGITAL_ROOT_PATH) };
  }
  return normalized;
}

function setQuery(value, { historyMode = 'replace' } = {}) {
  runtime.state.query = normalizeQuery(value);
  renderDiscoveryState();
  window.clearTimeout(runtime.searchTimer);
  if (historyMode) runtime.searchTimer = window.setTimeout(() => writeHistory(historyMode), 150);
}

function setSphereOpacity({ globeDiameter = null, size = null } = {}) {
  const immersive = runtime.state.view === 'layers' || runtime.viewPhase !== 'overview';
  let globeViewportRatio = 0;
  let opacity = 1;
  if (!immersive && runtime.mapReady) {
    const bounds = size ?? currentStageSize();
    const suppliedDiameter = globeDiameter !== null && globeDiameter !== undefined
      ? Number(globeDiameter)
      : Number.NaN;
    const measuredDiameter = Number.isFinite(suppliedDiameter)
      ? suppliedDiameter
      : Number(elements.stage.dataset.globeDiameter ?? 0);
    globeViewportRatio = measuredDiameter / Math.max(1, Math.min(bounds.width, bounds.height));
    opacity = sphereOpacityForGlobeRatio(globeViewportRatio);
  }
  let visualChanged = setStylePropertyIfChanged(elements.sphere, '--sphere-opacity', String(opacity));
  visualChanged = setAttributePresenceIfChanged(elements.sphere, 'data-hidden-local', opacity === 0) || visualChanged;
  setDatasetIfChanged(elements.stage, 'globeViewportRatio', Number(globeViewportRatio.toFixed(4)));
  return visualChanged;
}

function projectedGlobeGeometry(center, projectedCenter) {
  const horizon = globeHorizonCoordinates(center).map(({ lng, lat }) => runtime.map.project([lng, lat]));
  return projectedGlobeCircle({ center: projectedCenter, horizon });
}

function updateSphereGeometry() {
  if (!runtime.mapReady || elements.globeSurface.hidden) return;
  const size = currentStageSize();
  const padding = typeof runtime.map.getPadding === 'function' ? runtime.map.getPadding() : {};
  // Camera flights keep the MapLibre-projected overview geometry; side layout is
  // used only after entry has settled and during invisible return preparation.
  const sideView = runtime.viewPhase === 'layers' || runtime.viewPhase === 'preparing-overview';
  const center = runtime.map.getCenter();
  const projectedCenter = runtime.map.project(center);
  const globe = sideView ? null : projectedGlobeGeometry(center, projectedCenter);
  const geometry = sphereLayout({
    width: size.width,
    height: size.height,
    padding,
    globe,
    sideView,
  });
  const x = String(geometry.x) + 'px';
  const y = String(geometry.y) + 'px';
  const diameter = String(geometry.diameter) + 'px';
  let visualChanged = false;
  visualChanged = setStylePropertyIfChanged(elements.stage, '--sphere-x', x) || visualChanged;
  visualChanged = setStylePropertyIfChanged(elements.stage, '--sphere-y', y) || visualChanged;
  visualChanged = setStylePropertyIfChanged(elements.stage, '--sphere-size', diameter) || visualChanged;
  visualChanged = setStylePropertyIfChanged(elements.sphere, '--sphere-x', x) || visualChanged;
  visualChanged = setStylePropertyIfChanged(elements.sphere, '--sphere-y', y) || visualChanged;
  visualChanged = setStylePropertyIfChanged(elements.sphere, '--sphere-size', diameter) || visualChanged;
  setDatasetIfChanged(elements.stage, 'mapProjectedCenterX', Number(projectedCenter.x.toFixed(2)));
  setDatasetIfChanged(elements.stage, 'mapProjectedCenterY', Number(projectedCenter.y.toFixed(2)));
  setDatasetIfChanged(elements.stage, 'sphereX', geometry.x);
  setDatasetIfChanged(elements.stage, 'sphereY', geometry.y);
  setDatasetIfChanged(elements.stage, 'sphereSize', geometry.diameter);
  setDatasetIfChanged(elements.stage, 'globeDiameter', geometry.globeDiameter);
  setDatasetIfChanged(elements.stage, 'globeGeometrySource', sideView ? 'side-view-layout' : 'maplibre-projected-horizon');
  const detailLevel = sphereDetailLevel({ diameter: geometry.diameter, sideView });
  visualChanged = setDatasetIfChanged(elements.sphere, 'detailLevel', detailLevel) || visualChanged;
  setDatasetIfChanged(elements.stage, 'sphereDetailLevel', detailLevel);
  setDatasetIfChanged(elements.stage, 'mapZoom', Number(runtime.map.getZoom().toFixed(4)));
  visualChanged = setSphereOpacity({ globeDiameter: geometry.globeDiameter, size }) || visualChanged;
  if (visualChanged) {
    runtime.sphereGeometryCommitCount += 1;
    setDatasetIfChanged(elements.stage, 'sphereGeometryCommits', runtime.sphereGeometryCommitCount);
  }
}

function layerCamera(camera = null) {
  const current = camera ?? (runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera);
  return {
    ...digitalLayerCamera(current),
    offset: [-Math.min(240, window.innerWidth * 0.18), 0],
  };
}

function smoothCameraEasing(progress) {
  const remaining = 1 - Math.min(1, Math.max(0, progress));
  return 1 - remaining * remaining * remaining * remaining;
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
  else runtime.map.easeTo({ ...options, duration, easing: smoothCameraEasing, essential: false });
}

function clearViewTransition() {
  runtime.cameraFlightGeneration += 1;
  runtime.cameraFlightCleanup?.();
  runtime.cameraFlightCleanup = null;
  runtime.viewTransitionCleanup?.();
  runtime.viewTransitionCleanup = null;
}

function startCameraFlight(camera, { instant = false, duration = 260, onSettled = () => {} } = {}) {
  clearViewTransition();
  const generation = runtime.cameraFlightGeneration;
  const map = runtime.map;
  if (!map) {
    if (generation === runtime.cameraFlightGeneration) onSettled();
    return;
  }
  let completed = false;
  const complete = () => {
    if (completed || generation !== runtime.cameraFlightGeneration) return;
    completed = true;
    runtime.cameraFlightCleanup?.();
    runtime.cameraFlightCleanup = null;
    onSettled();
  };
  const onMoveEnd = () => complete();
  map.once('moveend', onMoveEnd);
  // Fallback only for a MapLibre moveend that never arrives.
  const fallbackTimer = window.setTimeout(complete, Math.max(2000, duration * 3));
  runtime.cameraFlightCleanup = () => {
    map.off('moveend', onMoveEnd);
    window.clearTimeout(fallbackTimer);
  };
  applyCamera(camera, { instant, duration });
  if (typeof map.isMoving === 'function' && !map.isMoving()) complete();
}

function sphereVisualOpacity() {
  const value = Number.parseFloat(getComputedStyle(elements.sphere).opacity);
  return Number.isFinite(value) ? value : 0;
}

function forceSphereOpacity(visible) {
  const previousTransition = elements.sphere.style.transition;
  const previousOpacity = elements.sphere.style.opacity;
  elements.sphere.style.transition = 'none';
  elements.sphere.style.opacity = visible ? '1' : '0';
  void elements.sphere.offsetWidth;
  window.setTimeout(() => {
    elements.sphere.style.transition = previousTransition;
    elements.sphere.style.opacity = previousOpacity;
  }, 0);
}

function waitForSphereOpacity({ visible = false, hiddenOpacity = 0.08, fallbackMs = 720, onSettled = () => {} } = {}) {
  const generation = runtime.cameraFlightGeneration;
  let completed = false;
  const targetReached = () => (visible ? sphereVisualOpacity() >= 0.98 : sphereVisualOpacity() <= hiddenOpacity);
  const complete = () => {
    if (completed || generation !== runtime.cameraFlightGeneration) return;
    completed = true;
    runtime.viewTransitionCleanup?.();
    runtime.viewTransitionCleanup = null;
    onSettled();
  };
  const onTransitionEnd = (event) => {
    if (event.target === elements.sphere && event.propertyName === 'opacity' && targetReached()) complete();
  };
  elements.sphere.addEventListener('transitionend', onTransitionEnd);
  const fallbackTimer = window.setTimeout(() => {
    if (!targetReached()) forceSphereOpacity(visible);
    complete();
  }, fallbackMs);
  runtime.viewTransitionCleanup = () => {
    elements.sphere.removeEventListener('transitionend', onTransitionEnd);
    window.clearTimeout(fallbackTimer);
  };
  window.setTimeout(() => {
    if (targetReached()) complete();
  }, 0);
}

function settleLayerViewAfterCamera() {
  waitForSphereOpacity({
    hiddenOpacity: 0.08,
    onSettled: () => finishViewTransition('layers'),
  });
  setViewPhase('settling-layers');
  showLayerState();
}

function startOverviewReturnCamera(targetCamera, duration, restoreFocus) {
  setViewPhase('leaving-layers');
  showLayerState();
  startCameraFlight(targetCamera, {
    duration,
    onSettled: () => finishViewTransition('overview', { restoreFocus }),
  });
}

function prepareOverviewReturn(targetCamera, duration, restoreFocus) {
  waitForSphereOpacity({
    hiddenOpacity: 0.02,
    onSettled: () => startOverviewReturnCamera(targetCamera, duration, restoreFocus),
  });
  setViewPhase('preparing-overview');
  showLayerState();
}

function setViewPhase(phase) {
  const allowed = new Set(['overview', 'entering-layers', 'settling-layers', 'layers', 'preparing-overview', 'leaving-layers']);
  runtime.viewPhase = allowed.has(phase) ? phase : 'overview';
  elements.stage.dataset.viewPhase = runtime.viewPhase;
  elements.stage.dataset.viewPhaseStartedAt = String(performance.now());
  if (runtime.viewPhase === 'entering-layers') {
    delete elements.stage.dataset.layerPanelVisibleAt;
    delete elements.stage.dataset.layerSettlingStartedAt;
  }
  if (runtime.viewPhase === 'settling-layers') {
    elements.stage.dataset.layerSettlingStartedAt = elements.stage.dataset.viewPhaseStartedAt;
  }
  if (runtime.viewPhase === 'preparing-overview' || runtime.viewPhase === 'leaving-layers') {
    elements.stage.dataset.layerReturnStartedAt = elements.stage.dataset.viewPhaseStartedAt;
  }
  updateSphereGeometry();
  if (!runtime.mapReady) setSphereOpacity();
}

function showLayerState() {
  const journeyActive = runtime.state.surface === 'globe' && (runtime.state.view === 'layers' || runtime.viewPhase !== 'overview');
  const panelMounted = runtime.state.surface === 'globe' && runtime.viewPhase === 'layers';
  const panelVisible = panelMounted && runtime.layerPanelReady;
  elements.stage.classList.toggle('layer-view-open', journeyActive);
  elements.stage.classList.toggle('layer-view-settled', runtime.viewPhase === 'layers');
  elements.layerPanel.hidden = !panelMounted;
  elements.layerPanel.toggleAttribute('data-visible', panelVisible);
  elements.layerPanel.toggleAttribute('inert', !panelVisible);
  elements.layerToggle.setAttribute('aria-expanded', String(runtime.state.view === 'layers'));
  elements.layerDeck.toggleAttribute('inert', !panelVisible);
  elements.layerDeck.setAttribute('aria-hidden', String(!panelVisible));
  elements.sphere.setAttribute('aria-hidden', String(runtime.viewPhase === 'layers'));
  elements.map.toggleAttribute('inert', journeyActive);
  elements.layerToggle.toggleAttribute('inert', journeyActive);
  elements.orientationBar.toggleAttribute('inert', journeyActive);
  if (journeyActive) {
    elements.map.setAttribute('aria-hidden', 'true');
    elements.layerToggle.setAttribute('aria-hidden', 'true');
    elements.sphereEdge.setAttribute('aria-hidden', 'true');
    elements.sphereEdge.setAttribute('tabindex', '-1');
    elements.orientationBar.setAttribute('aria-hidden', 'true');
  } else {
    elements.map.removeAttribute('aria-hidden');
    elements.layerToggle.removeAttribute('aria-hidden');
    elements.sphereEdge.removeAttribute('aria-hidden');
    elements.sphereEdge.setAttribute('tabindex', '0');
    elements.orientationBar.removeAttribute('aria-hidden');
    elements.layerPanel.removeAttribute('data-closing');
  }
}

function finishViewTransition(phase, { restoreFocus = false } = {}) {
  clearViewTransition();
  runtime.layerPanelReady = false;
  setViewPhase(phase);
  showLayerState();
  if (phase === 'layers') {
    window.requestAnimationFrame(() => {
      if (runtime.viewPhase !== 'layers' || runtime.state.view !== 'layers') return;
      runtime.layerPanelReady = true;
      elements.stage.dataset.layerPanelVisibleAt = String(performance.now());
      showLayerState();
      if (!flushPendingHierarchyFocus()) elements.layerClose.focus({ preventScroll: true });
    });
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
  const duration = instant || cameraState || reducedMotion.matches || !runtime.mapReady ? 0 : DIGITAL_LAYER_TRANSITION_MS;
  elements.layerPanel.removeAttribute('data-closing');
  closeLayerDiscovery();
  renderLayerPanel();
  if (runtime.mapReady) {
    const targetCamera = layerCamera(cameraState);
    if (duration) {
      setViewPhase('entering-layers');
      showLayerState();
      startCameraFlight(targetCamera, {
        duration,
        onSettled: settleLayerViewAfterCamera,
      });
    } else {
      startCameraFlight(targetCamera, {
        instant: true,
        duration: 0,
        onSettled: () => finishViewTransition('layers'),
      });
    }
  } else if (duration) {
    setViewPhase('entering-layers');
    showLayerState();
  } else {
    finishViewTransition('layers');
  }
  if (historyMode) writeHistory(historyMode);
}

function closeLayerView({ historyMode = 'push', cameraState = null, preserveLayer = false, instant = false, restoreFocus = true } = {}) {
  const wasOpen = runtime.state.view === 'layers' || runtime.viewPhase !== 'overview';
  const currentPhase = runtime.viewPhase;
  runtime.layerPanelReady = false;
  closeLayerDiscovery();
  runtime.state.view = 'globe';
  runtime.state.layer = null;
  clearViewTransition();
  const duration = instant || reducedMotion.matches || !runtime.mapReady ? 0 : DIGITAL_LAYER_TRANSITION_MS;
  renderDiscoveryState();
  const targetCamera = cameraState ?? runtime.previousGlobeCamera ?? runtime.state.camera;
  if (wasOpen && runtime.mapReady && duration) {
    elements.layerPanel.dataset.closing = 'true';
    if (currentPhase === 'layers' || currentPhase === 'preparing-overview') {
      prepareOverviewReturn(targetCamera, duration, restoreFocus);
    } else {
      startOverviewReturnCamera(targetCamera, duration, restoreFocus);
    }
  } else if (runtime.mapReady) {
    startCameraFlight(targetCamera, {
      instant: true,
      duration: 0,
      onSettled: () => finishViewTransition('overview', { restoreFocus: wasOpen && restoreFocus }),
    });
  } else {
    finishViewTransition('overview', { restoreFocus: wasOpen && restoreFocus });
  }
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

const SETTINGS_FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]):not([type=\"hidden\"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex=\"-1\"])';

function trapSettingsFocus(event) {
  if (event.key !== 'Tab' || runtime.activeOverlay !== 'settings') return false;
  const targets = [...elements.settingsPanel.querySelectorAll(SETTINGS_FOCUSABLE_SELECTOR)].filter(isVisibleFocusTarget);
  if (!targets.length) return false;
  const first = targets[0];
  const last = targets.at(-1);
  const active = document.activeElement;
  if (event.shiftKey && (active === first || !elements.settingsPanel.contains(active))) {
    event.preventDefault();
    last.focus({ preventScroll: true });
    return true;
  }
  if (!event.shiftKey && (active === last || !elements.settingsPanel.contains(active))) {
    event.preventDefault();
    first.focus({ preventScroll: true });
    return true;
  }
  return false;
}

function closeSettings({ restoreFocus = true } = {}) {
  const wasOpen = runtime.activeOverlay === 'settings';
  if (wasOpen) setActiveOverlay(null);
  if (restoreFocus && wasOpen) (runtime.settingsReturnTarget ?? elements.settingsToggle).focus({ preventScroll: true });
  runtime.settingsReturnTarget = null;
}

function openSettings({ trigger = elements.settingsToggle } = {}) {
  runtime.settingsReturnTarget = trigger instanceof HTMLElement && trigger.isConnected ? trigger : elements.settingsToggle;
  runtime.discoveryReturnTarget = null;
  setActiveOverlay('settings');
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
  runtime.state.digitalPath = DIGITAL_ROOT_PATH;
  runtime.state.camera = { ...DEFAULT_CAMERA };
  showLayerState();
  renderDiscoveryState();
  if (runtime.mapReady) applyCamera(DEFAULT_CAMERA);
  writeHistory('push');
}

function applyDeepLink(search, { initial = false } = {}) {
  const previousFocus = document.activeElement;
  const next = stateFromSearch(search, runtime.records.map(({ id }) => id));
  if (initial && !new URLSearchParams(search).has('surface')) next.surface = storedPresentation();
  runtime.applyingHistory = true;
  runtime.state = next;
  runtime.state.digitalPath = normalizeDigitalPathForApp(next.digitalPath).path;
  if (runtime.state.project && !projectMatchesDigitalState(runtime.state.project, runtime.state)) {
    runtime.state.project = null;
    runtime.focusReturnTarget = null;
  }
  runtime.visibleRecordsCache = null;
  runtime.unfilteredPathRecordsCache = null;
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
  if ((next.query || hasIntentFilters()) && !runtime.state.project) openDiscovery({ trigger: elements.search });
  else closeDiscovery({ restoreFocus: false });
  runtime.applyingHistory = false;
  if (initial) writeHistory('replace');
  else if (runtime.state.project) elements.focus.focus({ preventScroll: true });
  else if (!isVisibleFocusTarget(previousFocus)) {
    scheduleHierarchyFocus(serializeDigitalPath(runtime.state.digitalPath));
  }
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

function syncSphereKeyboardFocus() {
  const visible = runtime.inputModality === 'keyboard' && document.activeElement === elements.sphereEdge;
  elements.sphereFocus.style.display = visible ? 'inline' : 'none';
}

function beginSpherePointer(event) {
  if (event.button !== undefined && event.button !== 0) return;
  elements.sphereFocus.style.display = 'none';
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
  elements.sphereEdge.addEventListener('focus', syncSphereKeyboardFocus);
  elements.sphereEdge.addEventListener('blur', () => { elements.sphereFocus.style.display = 'none'; });
  elements.sphereEdge.addEventListener('keydown', (event) => {
    syncSphereKeyboardFocus();
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openLayerView({ trigger: elements.sphereEdge });
    }
  });
  elements.globeReset.addEventListener('click', resetGlobe);
  elements.focusClose.addEventListener('click', () => clearProject());
  elements.filterToggle.addEventListener('click', () => {
    if (runtime.activeOverlay === 'discovery') closeDiscovery({ restoreFocus: true });
    else openDiscovery({ trigger: elements.filterToggle });
  });
  elements.discoveryClose.addEventListener('click', () => closeDiscovery({ restoreFocus: true }));
  elements.discoveryShowText.addEventListener('click', () => {
    closeDiscovery({ restoreFocus: false });
    setPresentation('text');
    elements.textView.focus({ preventScroll: true });
  });
  elements.textShowMore.addEventListener('click', () => {
    const firstNewIndex = runtime.textPresentationLimit;
    runtime.textPresentationLimit += TEXT_IDENTITY_DOM_LIMIT;
    renderDiscoveryState();
    queueMicrotask(() => {
      if (isVisibleFocusTarget(elements.textShowMore)) elements.textShowMore.focus({ preventScroll: true });
      else document.querySelectorAll('.catalog-card:not([hidden]) .catalog-select')[firstNewIndex]?.focus({ preventScroll: true });
    });
  });
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
    if (runtime.activeOverlay === 'settings') closeSettings();
    else openSettings({ trigger: elements.settingsToggle });
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
    if (event.key === 'Tab' && runtime.activeOverlay === 'settings') {
      trapSettingsFocus(event);
      return;
    }
    if (event.key !== 'Escape') return;
    if (runtime.activeOverlay === 'settings') closeSettings();
    else if (runtime.activeOverlay === 'discovery') closeDiscovery({ restoreFocus: true });
    else if (!elements.focus.hidden) clearProject();
    else if (!elements.layerDiscovery.hidden) closeLayerDiscovery({ restoreFocus: true });
    else if ((runtime.viewPhase !== 'overview' || runtime.state.view === 'layers') && digitalPathFiltered()) {
      const view = visibleDigitalNodes(runtime.digitalTree ?? treeForRecords(runtime.records), currentDigitalPath());
      setDigitalPath(view.parent?.path ?? DIGITAL_ROOT_PATH);
    }
    else if (runtime.viewPhase !== 'overview' || runtime.state.view === 'layers') closeLayerView();
  });
  window.addEventListener('popstate', () => applyDeepLink(location.search));
  window.addEventListener('resize', () => {
    updateOrientationBarClearance();
    if (runtime.resizeObserver) return;
    runtime.stageSize = null;
    runtime.map?.resize();
    updateSphereGeometry();
  });
}

function interactivePublicMapLayers() {
  if (runtime.publicMapInteractiveLayerIds !== null) return runtime.publicMapInteractiveLayerIds;
  runtime.publicMapInteractiveLayerIds = PUBLIC_MAP_LAYER_IDS.filter((identifier) => runtime.map.getLayer(identifier));
  return runtime.publicMapInteractiveLayerIds;
}

function updateMapPointerCursor() {
  runtime.pointerHitTestFrame = null;
  const point = runtime.pointerHitTestPoint;
  runtime.pointerHitTestPoint = null;
  if (!point || !runtime.map) return;
  const layers = interactivePublicMapLayers();
  const interactive = layers.length > 0 && runtime.map.queryRenderedFeatures(point, { layers }).length > 0;
  const cursor = interactive ? 'pointer' : '';
  const canvas = runtime.map.getCanvas();
  if (canvas.style.cursor !== cursor) canvas.style.cursor = cursor;
}

function bindPublicMapInteractions() {
  if (!runtime.map || runtime.mapInteractionsBound) return;
  runtime.mapInteractionsBound = true;
  runtime.map.on('click', (event) => {
    const layers = interactivePublicMapLayers();
    if (!layers.length) return;
    const feature = runtime.map.queryRenderedFeatures(event.point, { layers })[0];
    const identifier = feature?.properties?.project_id;
    if (typeof identifier === 'string') selectProject(identifier, { trigger: runtime.map.getCanvas() });
  });
  runtime.map.on('mousemove', (event) => {
    runtime.pointerHitTestPoint = { x: event.point.x, y: event.point.y };
    if (runtime.pointerHitTestFrame === null) {
      runtime.pointerHitTestFrame = window.requestAnimationFrame(updateMapPointerCursor);
    }
  });
  runtime.map.on('mouseleave', () => {
    if (runtime.pointerHitTestFrame !== null) window.cancelAnimationFrame(runtime.pointerHitTestFrame);
    runtime.pointerHitTestFrame = null;
    runtime.pointerHitTestPoint = null;
    runtime.map.getCanvas().style.cursor = '';
  });
}

function createMap() {
  if (runtime.map) return;
  if (!window.maplibregl?.Map) {
    runtime.mapDegraded = true;
    refreshStatus();
    setPresentation('text', { historyMode: 'replace', persist: false });
    return;
  }
  const initialStageBounds = elements.stage.getBoundingClientRect();
  setStageSizeIfChanged(initialStageBounds.width, initialStageBounds.height);
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
    projection: { type: 'globe' },
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
    runtime.publicMapInteractiveLayerIds = null;
    if (runtime.mapReady) ensurePublicMapLayers();
  });
  runtime.map.on('idle', () => {
    if (runtime.mapReady && !runtime.map.getSource(PUBLIC_MAP_SOURCE_ID)) ensurePublicMapLayers();
    if (runtime.mapReady && elements.stage.dataset.visualReady !== 'true') {
      updateSphereGeometry();
      elements.stage.dataset.visualReady = 'true';
    }
  });
  runtime.map.on('load', () => {
    runtime.mapReady = true;
    runtime.map.setProjection({ type: 'globe' });
    ensurePublicMapLayers();
    if (runtime.state.view === 'layers') openLayerView({ historyMode: null, cameraState: runtime.state.camera, instant: true });
    else applyCamera(runtime.state.camera, { instant: true });
    updateSphereGeometry();
    updateSemanticLocationLine();
    refreshStatus();
    window.setTimeout(() => {
      if (!runtime.mapReady || elements.stage.dataset.visualReady === 'true') return;
      updateSphereGeometry();
      elements.stage.dataset.visualReady = 'true';
    }, 1200);
    if (runtime.pendingSpatialProject) performSpatialNavigation(runtime.pendingSpatialProject);
  });
  void verifyMapProvider();
  if ('ResizeObserver' in window) {
    runtime.resizeObserver = new ResizeObserver(([entry]) => {
      const box = entry?.contentRect;
      if (!box || !setStageSizeIfChanged(box.width, box.height)) return;
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
  installInputModalityTracking();
  try {
    const embedded = bootstrapRecords();
    installRecords(embedded);
    renderSphere();
    renderLayerStack();
    wireControls();
    installOrientationBarClearanceTracking();
    if (navigator.webdriver && ['127.0.0.1', 'localhost'].includes(location.hostname)) {
      window.__commonworldInstallSyntheticRecordsForTest = (records) => {
        installRecords(validateRecords(records));
        runtime.state.project = null;
        runtime.state.layer = null;
        runtime.state.digitalPath = DIGITAL_ROOT_PATH;
        runtime.state.query = '';
        for (const name of INTENT_FILTER_NAMES) runtime.state[name] = null;
        renderDiscoveryState();
        return Object.freeze({ records: runtime.records.length, treeIdentities: runtime.digitalTree.identityIds.length });
      };
    }
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
