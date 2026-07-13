import {
  DEFAULT_CAMERA,
  LAYERS,
  binaryFragment,
  deriveLayer,
  filterRecords,
  mapCamera,
  normalizeQuery,
  searchFromState,
  sphereLayout,
  sphereOpacityForZoom,
  sphereStartOffset,
  stateFromSearch,
} from './commonworld-core.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const PRESENTATION_STORAGE_KEY = 'commonworld.presentation';
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const elements = {
  body: document.body,
  globeSurface: document.querySelector('#globe-surface'),
  textView: document.querySelector('#text-view'),
  textCount: document.querySelector('#text-count'),
  textEmpty: document.querySelector('#text-empty'),
  textLayerButtons: document.querySelector('#text-layer-buttons'),
  stage: document.querySelector('.globe-stage'),
  map: document.querySelector('#map'),
  mapStatus: document.querySelector('#map-status'),
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
  applyingHistory: false,
  mapReady: false,
  mapRenderCount: 0,
  overlayRenderCount: 0,
  historyTimer: null,
  searchTimer: null,
  focusReturnTarget: null,
  settingsReturnTarget: null,
  resizeObserver: null,
};

function setStatus(message, state = 'loading') {
  elements.stage.dataset.runtimeState = state;
  elements.mapStatus.textContent = message;
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

async function fetchJson(url) {
  const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}

async function loadRecords() {
  const manifest = await fetchJson('./catalog/catalog.json');
  if (!Array.isArray(manifest.project_files) || manifest.project_files.length !== manifest.entry_count) {
    throw new Error('Katalogmanifest und Eintragszahl stimmen nicht überein.');
  }
  const records = await Promise.all(manifest.project_files.map((path) => fetchJson(`./catalog/${path}`)));
  const ids = new Set();
  for (const record of records) {
    if (!record || typeof record.id !== 'string' || ids.has(record.id)) throw new Error('Ungültige oder doppelte CommonProject-ID.');
    if (record?.presence?.geographic?.length) throw new Error(`Digitale Katalogidentität ${record.id} enthält unerlaubte Geodaten.`);
    ids.add(record.id);
  }
  return records;
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function renderSphere() {
  elements.sphereStreams.replaceChildren();
  const grouped = new Map(LAYERS.map((layer) => [layer.id, []]));
  for (const record of runtime.records) grouped.get(deriveLayer(record))?.push(record);
  LAYERS.forEach((layer, layerIndex) => {
    const records = grouped.get(layer.id) ?? [];
    records.forEach((record, recordIndex) => {
      const text = createSvgElement('text', {
        class: 'sphere-label',
        'data-commonproject-id': record.id,
        'data-layer-id': layer.id,
      });
      const path = createSvgElement('textPath', {
        href: `#sphere-path-${layerIndex + 1}`,
        startOffset: `${sphereStartOffset(layerIndex, recordIndex, records.length)}%`,
      });
      const name = createSvgElement('tspan', { class: 'sphere-name' });
      name.textContent = record.title;
      const binary = createSvgElement('tspan', { class: 'sphere-binary', dx: '8' });
      binary.textContent = binaryFragment(record.id);
      path.append(name, binary);
      text.append(path);
      elements.sphereStreams.append(text);
    });
  });
  runtime.overlayRenderCount += 1;
  elements.stage.dataset.overlayRenders = String(runtime.overlayRenderCount);
}

function renderLayerStack() {
  elements.layerStack.replaceChildren();
  for (const layer of LAYERS) {
    const item = document.createElement('div');
    item.className = 'layer-stack-item';
    item.dataset.layerId = layer.id;
    const label = document.createElement('span');
    label.textContent = layer.label;
    const count = document.createElement('small');
    count.textContent = String(runtime.records.filter((record) => deriveLayer(record) === layer.id).length);
    item.append(label, count);
    elements.layerStack.append(item);
  }
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
  renderLayerButtons(elements.layerButtons);
  elements.layerProjects.replaceChildren();
  for (const record of visibleRecords()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'layer-project';
    button.dataset.commonprojectId = record.id;
    const name = document.createElement('span');
    name.textContent = record.title;
    const layerName = document.createElement('small');
    layerName.textContent = layerForRecord(record)?.label ?? 'Digital';
    button.append(name, layerName);
    button.addEventListener('click', () => selectProject(record.id));
    elements.layerProjects.append(button);
  }
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
  elements.sphere.querySelectorAll('.sphere-label[data-commonproject-id]').forEach((label) => {
    label.toggleAttribute('data-filtered-out', !visibleIds.has(label.dataset.commonprojectId));
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
    if (element.matches('button')) element.setAttribute('aria-pressed', String(selected));
    if (element.matches('.catalog-card')) element.toggleAttribute('data-selected', selected);
  });
  updateFocusPanel();
}

function renderDiscoveryState() {
  renderLayerPanel();
  renderTextView();
  updateSphereResultVisibility();
  updateSelectionMarks();
  elements.search.value = runtime.state.query;
  elements.searchClear.hidden = runtime.state.query.length === 0;
}

function currentUrlState() {
  return {
    ...runtime.state,
    camera: runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera,
  };
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
  if (trigger instanceof HTMLElement && !elements.focus.contains(trigger)) runtime.focusReturnTarget = trigger;
  runtime.state.project = identifier;
  runtime.state.layer = deriveLayer(runtime.recordsById.get(identifier));
  renderDiscoveryState();
  if (historyMode) writeHistory(historyMode);
  if (focus) elements.focus.focus({ preventScroll: true });
}

function isVisibleFocusTarget(target) {
  return target instanceof HTMLElement && target.isConnected && target.getClientRects().length > 0 && !target.closest('[hidden]');
}

function visibleProjectTrigger(identifier) {
  const escaped = CSS.escape(identifier);
  const candidates = [
    ...document.querySelectorAll(`.layer-project[data-commonproject-id="${escaped}"], .catalog-select[data-commonproject-id="${escaped}"]`),
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

function setSphereOpacity() {
  const opacity = runtime.mapReady ? sphereOpacityForZoom(runtime.map.getZoom()) : 1;
  elements.sphere.style.setProperty('--sphere-opacity', String(opacity));
  elements.sphere.toggleAttribute('data-hidden-local', opacity === 0);
}

function updateSphereGeometry() {
  if (!runtime.mapReady || elements.globeSurface.hidden) return;
  const rect = elements.stage.getBoundingClientRect();
  const projected = runtime.map.project(runtime.map.getCenter());
  const padding = typeof runtime.map.getPadding === 'function' ? runtime.map.getPadding() : {};
  const geometry = sphereLayout({
    width: rect.width,
    height: rect.height,
    zoom: runtime.map.getZoom(),
    padding,
    center: projected,
    sideView: runtime.state.view === 'layers',
  });
  elements.stage.style.setProperty('--sphere-x', `${geometry.x}px`);
  elements.stage.style.setProperty('--sphere-y', `${geometry.y}px`);
  elements.stage.style.setProperty('--sphere-size', `${geometry.diameter}px`);
  elements.sphere.style.setProperty('--sphere-x', `${geometry.x}px`);
  elements.sphere.style.setProperty('--sphere-y', `${geometry.y}px`);
  elements.sphere.style.setProperty('--sphere-size', `${geometry.diameter}px`);
  elements.stage.dataset.mapProjectedCenterX = String(Number(projected.x.toFixed(2)));
  elements.stage.dataset.mapProjectedCenterY = String(Number(projected.y.toFixed(2)));
  elements.stage.dataset.sphereX = String(geometry.x);
  elements.stage.dataset.sphereY = String(geometry.y);
  elements.stage.dataset.sphereSize = String(geometry.diameter);
}

function layerCamera() {
  const current = mapCamera(runtime.map);
  const panelRect = elements.layerPanel.getBoundingClientRect();
  const mobileSheet = window.matchMedia('(max-width: 48rem)').matches;
  const padding = mobileSheet
    ? {
        top: 36,
        right: 36,
        bottom: Math.min(Math.max(220, panelRect.height + 24), elements.stage.clientHeight * 0.62),
        left: 36,
      }
    : {
        top: 36,
        right: Math.min(Math.max(260, panelRect.width) + 24, elements.stage.clientWidth * 0.58),
        bottom: 36,
        left: 36,
      };
  return {
    center: [current.lng, current.lat],
    zoom: Math.max(current.zoom, 1.55),
    bearing: 22,
    pitch: 34,
    padding,
  };
}

function applyCamera(camera, { instant = false } = {}) {
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
  elements.stage.dataset.lastCameraDuration = useJump ? '0' : '260';
  if (useJump) runtime.map.jumpTo(options);
  else runtime.map.easeTo({ ...options, duration: 260, essential: false });
}

function showLayerState() {
  const open = runtime.state.view === 'layers' && runtime.state.surface === 'globe';
  elements.stage.classList.toggle('layer-view-open', open);
  elements.layerPanel.hidden = !open;
  elements.layerToggle.setAttribute('aria-expanded', String(open));
}

function openLayerView({ historyMode = 'push', cameraState = null } = {}) {
  if (runtime.state.view !== 'layers') runtime.previousGlobeCamera = runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera;
  runtime.state.view = 'layers';
  showLayerState();
  renderLayerPanel();
  updateSphereGeometry();
  if (runtime.mapReady) {
    const target = cameraState ? { ...cameraState, padding: layerCamera().padding } : layerCamera();
    applyCamera(target, { instant: Boolean(cameraState) });
  }
  if (historyMode) writeHistory(historyMode);
}

function closeLayerView({ historyMode = 'push', cameraState = null, preserveLayer = false } = {}) {
  runtime.state.view = 'globe';
  if (!preserveLayer) runtime.state.layer = null;
  showLayerState();
  renderDiscoveryState();
  if (runtime.mapReady) applyCamera(cameraState ?? runtime.previousGlobeCamera ?? runtime.state.camera, { instant: reducedMotion.matches });
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
  runtime.previousGlobeCamera = null;
  runtime.state.view = 'globe';
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
    if (next.view === 'layers') openLayerView({ historyMode: null, cameraState: next.camera });
    else closeLayerView({ historyMode: null, cameraState: next.camera, preserveLayer: true });
  } else {
    showLayerState();
  }
  renderDiscoveryState();
  runtime.applyingHistory = false;
  if (initial) writeHistory('replace');
}

function wireControls() {
  elements.layerToggle.addEventListener('click', () => (runtime.state.view === 'layers' ? closeLayerView() : openLayerView()));
  elements.layerClose.addEventListener('click', () => closeLayerView());
  elements.sphereEdge.addEventListener('click', () => openLayerView());
  elements.sphereEdge.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openLayerView();
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
    if (!elements.settingsPanel.hidden) closeSettings();
    else if (!elements.focus.hidden) clearProject();
    else if (runtime.state.view === 'layers') closeLayerView();
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
    setStatus('Der Globus ist gerade nicht verfügbar. Die Textansicht bleibt vollständig nutzbar.', 'failed');
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
    setSphereOpacity();
    updateSphereGeometry();
  });
  runtime.map.on('moveend', scheduleCameraHistory);
  runtime.map.on('error', (event) => {
    console.warn('Commonworld map provider error', event?.error ?? event);
    setStatus('Die Basiskarte ist vorübergehend nicht erreichbar. Globuszustand und Textansicht bleiben verfügbar.', 'degraded');
  });
  runtime.map.on('load', () => {
    runtime.mapReady = true;
    runtime.map.setProjection({ type: 'globe' });
    setSphereOpacity();
    updateSphereGeometry();
    setStatus('Globus bereit. Ziehen zum Drehen, Pinch oder Tasten zum Zoomen.', 'ready');
    if (runtime.state.view === 'layers') openLayerView({ historyMode: null, cameraState: runtime.state.camera });
    else applyCamera(runtime.state.camera, { instant: true });
  });
  if ('ResizeObserver' in window) {
    runtime.resizeObserver = new ResizeObserver(() => {
      runtime.map?.resize();
      updateSphereGeometry();
    });
    runtime.resizeObserver.observe(elements.stage);
  }
}

function ensureMap() {
  if (!runtime.map) createMap();
}

async function boot() {
  try {
    runtime.records = await loadRecords();
    runtime.recordsById = new Map(runtime.records.map((record) => [record.id, record]));
    renderSphere();
    renderLayerStack();
    wireControls();
    applyDeepLink(location.search, { initial: true });
    renderDiscoveryState();
    document.documentElement.classList.add('runtime-ready');
  } catch (error) {
    console.error(error);
    setStatus('Commonworld konnte den öffentlichen Katalog nicht laden.', 'failed');
    elements.body.dataset.presentation = 'text';
    elements.globeSurface.hidden = true;
    elements.textView.hidden = false;
    document.documentElement.classList.add('runtime-failed');
  }
}

boot();
