import {
  DEFAULT_CAMERA,
  DIGITAL_LAYER_TRANSITION_MS,
  LAYERS,
  deriveLayer,
  digitalLayerCamera,
  filterRecords,
  globeHorizonCoordinates,
  mapCamera,
  mapFailurePolicy,
  normalizeQuery,
  projectedGlobeCircle,
  searchFromState,
  sphereDetailLevel,
  sphereLabelLayout,
  sphereLayout,
  sphereProjectScale,
  sphereOpacityForGlobeRatio,
  stateFromSearch,
} from './commonworld-core.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const LOCAL_FALLBACK_STYLE = Object.freeze({ version: 8, sources: {}, layers: [{ id: 'commonworld-fallback', type: 'background', paint: { 'background-color': '#0d2426' } }] });
const PRESENTATION_STORAGE_KEY = 'commonworld.presentation';
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
  sphere: document.querySelector('#digital-sphere'),
  sphereStreams: document.querySelector('#sphere-streams'),
  sphereEdge: document.querySelector('#sphere-edge-control'),
  layerStack: document.querySelector('#layer-stack-visual'),
  layerToggle: document.querySelector('#layer-view-button'),
  layerPanel: document.querySelector('#layer-panel'),
  layerClose: document.querySelector('#layer-close'),
  layerButtons: document.querySelector('#layer-buttons'),
  layerProjects: document.querySelector('#layer-projects'),
  globeReset: document.querySelector('#globe-reset'),
  search: document.querySelector('#commons-search'),
  searchClear: document.querySelector('#search-clear'),
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
  focusDigital: document.querySelector('#focus-digital'),
  focusLinks: document.querySelector('#focus-links'),
  focusSources: document.querySelector('#focus-sources'),
  focusCuration: document.querySelector('#focus-curation'),
};

const runtime = {
  map: null,
  records: [],
  recordsById: new Map(),
  state: {
    camera: { ...DEFAULT_CAMERA },
    project: null,
    layer: null,
    view: 'globe',
    surface: 'globe',
    query: '',
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
  resizeObserver: null,
  catalogDegraded: false,
  mapDegraded: false,
  providerFallbackApplied: false,
  providerErrorLogged: false,
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
    if (record?.presence?.geographic?.length) throw new Error(`Digitale Katalogidentität ${record.id} enthält unerlaubte Geodaten.`);
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
  runtime.recordsById = new Map(records.map((record) => [record.id, record]));
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function sphereTextAnchor(directionX) {
  if (directionX > 0.28) return 'start';
  if (directionX < -0.28) return 'end';
  return 'middle';
}

function configureSphereProject(project, sideView = false) {
  const mode = sideView ? 'side' : 'overview';
  const directionX = Number(project.dataset[`${mode}Dx`] ?? 0);
  const directionY = Number(project.dataset[`${mode}Dy`] ?? -1);
  const leaderLength = sideView ? 22 : 18;
  const labelDistance = sideView ? 30 : 26;
  const leader = project.querySelector('.sphere-project-leader');
  const text = project.querySelector('.sphere-project-text');
  leader?.setAttribute('x2', String(Number((directionX * leaderLength).toFixed(2))));
  leader?.setAttribute('y2', String(Number((directionY * leaderLength).toFixed(2))));
  text?.setAttribute('x', String(Number((directionX * labelDistance).toFixed(2))));
  text?.setAttribute('y', String(Number((directionY * labelDistance).toFixed(2))));
  text?.setAttribute('text-anchor', sphereTextAnchor(directionX));
}

function renderSphere() {
  elements.sphereStreams.replaceChildren();
  const grouped = new Map(LAYERS.map((layer) => [layer.id, []]));
  for (const record of runtime.records) grouped.get(deriveLayer(record))?.push(record);
  LAYERS.forEach((layer, layerIndex) => {
    const records = grouped.get(layer.id) ?? [];
    records.forEach((record, recordIndex) => {
      const project = createSvgElement('g', {
        class: 'sphere-project sphere-label',
        'data-commonproject-id': record.id,
        'data-layer-id': layer.id,
        'data-priority': String(recordIndex === 0),
        role: 'button',
        tabindex: '-1',
        focusable: 'true',
        'aria-label': `${record.title} öffnen`,
      });
      const layout = sphereLabelLayout(layerIndex, recordIndex, records.length);
      project.style.setProperty('--project-overview-x', `${layout.overviewX}px`);
      project.style.setProperty('--project-overview-y', `${layout.overviewY}px`);
      project.style.setProperty('--project-side-x', `${layout.sideX}px`);
      project.style.setProperty('--project-side-y', `${layout.sideY}px`);
      project.dataset.overviewDx = String(layout.overviewDx);
      project.dataset.overviewDy = String(layout.overviewDy);
      project.dataset.sideDx = String(layout.sideDx);
      project.dataset.sideDy = String(layout.sideDy);
      const hit = createSvgElement('circle', {
        class: 'sphere-project-hit',
        cx: '0',
        cy: '0',
        r: '13',
        'aria-hidden': 'true',
      });
      const leader = createSvgElement('line', {
        class: 'sphere-project-leader',
        x1: '0',
        y1: '0',
        x2: '0',
        y2: '-18',
        'aria-hidden': 'true',
      });
      const node = createSvgElement('circle', {
        class: 'sphere-project-node',
        cx: '0',
        cy: '0',
        r: '3.4',
        'aria-hidden': 'true',
      });
      const text = createSvgElement('text', {
        class: 'sphere-project-text sphere-name',
        x: '0',
        y: '-26',
      });
      text.textContent = record.title;
      project.append(hit, leader, node, text);
      configureSphereProject(project, false);
      project.addEventListener('click', () => {
        if (runtime.viewPhase === 'layers') selectProject(record.id, { trigger: project });
      });
      project.addEventListener('keydown', (event) => {
        if (runtime.viewPhase !== 'layers' || !['Enter', ' '].includes(event.key)) return;
        event.preventDefault();
        selectProject(record.id, { trigger: project });
      });
      elements.sphereStreams.append(project);
    });
  });
  elements.sphere.dataset.projectMode = 'overview';
  runtime.overlayRenderCount += 1;
  elements.stage.dataset.overlayRenders = String(runtime.overlayRenderCount);
}

function renderLayerStack() {
  elements.layerStack.replaceChildren();
}

function layerForRecord(record) {
  return LAYERS.find(({ id }) => id === deriveLayer(record));
}

function visibleRecords() {
  return filterRecords(runtime.records, runtime.state);
}

function recordsMatchingQuery() {
  return filterRecords(runtime.records, { query: runtime.state.query });
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
  elements.layerButtons.replaceChildren();
  elements.layerProjects.replaceChildren();
}

function renderTextView() {
  const visibleIds = new Set(visibleRecords().map(({ id }) => id));
  document.querySelectorAll('.catalog-card[data-commonproject-id]').forEach((card) => {
    card.hidden = !visibleIds.has(card.dataset.commonprojectId);
  });
  renderLayerButtons(elements.textLayerButtons);
  const count = visibleIds.size;
  elements.textCount.textContent = `${count} ${count === 1 ? 'Commons' : 'Commons'}`;
  elements.textEmpty.hidden = count !== 0;
}

function updateSphereResultVisibility() {
  const visibleIds = new Set(visibleRecords().map(({ id }) => id));
  const queryIds = runtime.state.query
    ? new Set(recordsMatchingQuery().map(({ id }) => id))
    : new Set();
  elements.sphere.querySelectorAll('.sphere-project[data-commonproject-id]').forEach((project) => {
    project.toggleAttribute('data-filtered-out', !visibleIds.has(project.dataset.commonprojectId));
    project.toggleAttribute('data-query-match', queryIds.has(project.dataset.commonprojectId));
  });
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
  elements.focusKind.textContent = `Digital · ${layerForRecord(record)?.label ?? 'Weitere Commons'}`;
  replaceList(elements.focusThemes, record.themes ?? []);
  replaceList(elements.focusActions, record.actions ?? []);
  elements.focusDigital.textContent = record?.presence?.digital?.label ?? 'Digitale Präsenz';
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
}

function renderDiscoveryState() {
  renderLayerPanel();
  renderTextView();
  updateSphereResultVisibility();
  updateSelectionMarks();
  const count = visibleRecords().length;
  elements.globeResults.textContent = count === 0
    ? 'Keine Commons entsprechen dieser Suche oder Schichtauswahl.'
    : `${count} ${count === 1 ? 'Commons' : 'Commons'} in der aktuellen Auswahl.`;
  elements.globeResults.toggleAttribute('data-empty', count === 0);
  elements.search.value = runtime.state.query;
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

function selectProject(identifier, { historyMode = 'push', focus = true, trigger = document.activeElement } = {}) {
  if (!runtime.recordsById.has(identifier)) return;
  if (trigger instanceof Element && !elements.focus.contains(trigger)) runtime.focusReturnTarget = trigger;
  runtime.state.project = identifier;
  runtime.state.layer = deriveLayer(runtime.recordsById.get(identifier));
  renderDiscoveryState();
  if (historyMode) writeHistory(historyMode);
  if (focus) elements.focus.focus({ preventScroll: true });
}

function isVisibleFocusTarget(target) {
  return target instanceof Element && typeof target.focus === 'function' && target.isConnected && target.getClientRects().length > 0 && !target.closest('[hidden]');
}


function visibleProjectTrigger(identifier) {
  const escaped = CSS.escape(identifier);
  const candidates = [
    ...document.querySelectorAll(`.sphere-label[data-commonproject-id="${escaped}"], .catalog-select[data-commonproject-id="${escaped}"]`),
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
  runtime.state.layer = LAYERS.some(({ id }) => id === layer) ? layer : null;
  renderDiscoveryState();
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
  const projectScale = sphereProjectScale(geometry.diameter, detailLevel);
  elements.sphere.dataset.detailLevel = detailLevel;
  elements.sphere.style.setProperty('--project-scale', String(projectScale));
  const projectMode = sideView ? 'side' : 'overview';
  if (elements.sphere.dataset.projectMode !== projectMode) {
    elements.sphere.querySelectorAll('.sphere-project[data-commonproject-id]').forEach((project) => configureSphereProject(project, sideView));
    elements.sphere.dataset.projectMode = projectMode;
  }
  elements.stage.dataset.sphereDetailLevel = detailLevel;
  elements.stage.dataset.sphereProjectScale = String(projectScale);
  elements.stage.dataset.mapZoom = String(Number(runtime.map.getZoom().toFixed(4)));
  setSphereOpacity({ globeDiameter: geometry.globeDiameter, rect });
}

function layerCamera(camera = null) {
  const current = camera ?? (runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera);
  return digitalLayerCamera(current);
}

function applyCamera(camera, { instant = false, duration = 260 } = {}) {
  if (!runtime.map) return;
  const options = {
    center: camera.center ?? [camera.lng, camera.lat],
    zoom: camera.zoom,
    bearing: camera.bearing,
    pitch: camera.pitch,
    padding: camera.padding ?? { top: 0, right: 0, bottom: 0, left: 0 },
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
  elements.sphere.querySelectorAll('.sphere-label[data-commonproject-id]').forEach((label) => {
    const interactive = runtime.viewPhase === 'layers';
    label.setAttribute('tabindex', interactive ? '0' : '-1');
    label.toggleAttribute('aria-hidden', !interactive);
  });
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
    }, 520);
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
  elements.search.addEventListener('input', () => setQuery(elements.search.value));
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
    button.addEventListener('click', () => selectProject(button.dataset.commonprojectId));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (runtime.viewPhase !== 'overview' || runtime.state.view === 'layers') closeLayerView();
    else if (!elements.settingsPanel.hidden) closeSettings();
    else if (!elements.focus.hidden) clearProject();
  });
  window.addEventListener('popstate', () => applyDeepLink(location.search));
  window.addEventListener('resize', () => {
    runtime.map?.resize();
    updateSphereGeometry();
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
  runtime.map = new window.maplibregl.Map({
    container: elements.map,
    style: './assets/map/openfreemap-liberty.json',
    center: [runtime.state.camera.lng, runtime.state.camera.lat],
    zoom: runtime.state.camera.zoom,
    bearing: runtime.state.camera.bearing,
    pitch: runtime.state.camera.pitch,
    minZoom: 0.35,
    maxZoom: 8,
    attributionControl: true,
    renderWorldCopies: false,
    fadeDuration: reducedMotion.matches ? 0 : 120,
  });
  runtime.map.addControl(new window.maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }), 'bottom-right');
  runtime.map.on('render', () => {
    runtime.mapRenderCount += 1;
    elements.stage.dataset.mapRenders = String(runtime.mapRenderCount);
    updateSphereGeometry();
  });
  runtime.map.on('moveend', scheduleCameraHistory);
  runtime.map.on('error', (event) => {
    const policy = mapFailurePolicy({ providerReadbackFailed: false });
    degradeMap(event?.error ?? event, { replaceStyle: policy.replaceStyle });
  });
  runtime.map.on('load', () => {
    runtime.mapReady = true;
    runtime.map.setProjection({ type: 'globe' });
    updateSphereGeometry();
    refreshStatus();
    if (runtime.state.view === 'layers') openLayerView({ historyMode: null, cameraState: runtime.state.camera, instant: true });
    else applyCamera(runtime.state.camera, { instant: true });
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
