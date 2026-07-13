import {
  DEFAULT_CAMERA,
  LAYERS,
  binaryFragment,
  deriveLayer,
  mapCamera,
  searchFromState,
  sphereOpacityForZoom,
  sphereStartOffset,
  stateFromSearch,
} from './commonworld-core.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const elements = {
  stage: document.querySelector('.globe-stage'),
  map: document.querySelector('#map'),
  mapStatus: document.querySelector('#map-status'),
  sphere: document.querySelector('#digital-sphere'),
  sphereStreams: document.querySelector('#sphere-streams'),
  sphereEdge: document.querySelector('#sphere-edge-control'),
  layerToggle: document.querySelector('#layer-view-button'),
  layerPanel: document.querySelector('#layer-panel'),
  layerClose: document.querySelector('#layer-close'),
  layerButtons: document.querySelector('#layer-buttons'),
  layerProjects: document.querySelector('#layer-projects'),
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
  state: { camera: { ...DEFAULT_CAMERA }, project: null, layer: null, view: 'globe' },
  previousGlobeCamera: null,
  applyingHistory: false,
  mapReady: false,
  mapRenderCount: 0,
  overlayRenderCount: 0,
  historyTimer: null,
  focusReturnTarget: null,
};

function setStatus(message, state = 'loading') {
  elements.stage.dataset.runtimeState = state;
  elements.mapStatus.textContent = message;
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

function layerForRecord(record) {
  return LAYERS.find(({ id }) => id === deriveLayer(record));
}

function renderLayerPanel() {
  elements.layerButtons.replaceChildren();
  elements.layerProjects.replaceChildren();
  for (const layer of LAYERS) {
    const count = runtime.records.filter((record) => deriveLayer(record) === layer.id).length;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'layer-filter';
    button.dataset.layerId = layer.id;
    button.setAttribute('aria-pressed', String(runtime.state.layer === layer.id));
    button.textContent = `${layer.label} · ${count}`;
    button.addEventListener('click', () => setLayer(runtime.state.layer === layer.id ? null : layer.id));
    elements.layerButtons.append(button);
  }
  const visible = runtime.records.filter((record) => !runtime.state.layer || deriveLayer(record) === runtime.state.layer);
  for (const record of visible) {
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
  updateSelectionMarks();
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
  renderLayerPanel();
  updateSelectionMarks();
  if (historyMode) writeHistory(historyMode);
  if (focus) elements.focus.focus({ preventScroll: true });
}

function clearProject({ historyMode = 'push', restoreFocus = true } = {}) {
  const closingIdentifier = runtime.state.project;
  runtime.state.project = null;
  updateSelectionMarks();
  if (historyMode) writeHistory(historyMode);
  if (restoreFocus && closingIdentifier) {
    const fallback = document.querySelector(`.catalog-select[data-commonproject-id="${CSS.escape(closingIdentifier)}"]`);
    const target = runtime.focusReturnTarget?.isConnected ? runtime.focusReturnTarget : fallback;
    target?.focus({ preventScroll: true });
    runtime.focusReturnTarget = null;
  }
}

function setLayer(layer, { historyMode = 'push' } = {}) {
  runtime.state.layer = LAYERS.some(({ id }) => id === layer) ? layer : null;
  renderLayerPanel();
  if (historyMode) writeHistory(historyMode);
}

function setSphereOpacity() {
  const opacity = runtime.mapReady ? sphereOpacityForZoom(runtime.map.getZoom()) : 1;
  elements.sphere.style.setProperty('--sphere-opacity', String(opacity));
  elements.sphere.toggleAttribute('data-hidden-local', opacity === 0);
}

function layerCamera() {
  const current = mapCamera(runtime.map);
  return {
    center: [current.lng, current.lat],
    zoom: Math.max(current.zoom, 1.55),
    bearing: 22,
    pitch: 34,
    padding: { top: 36, bottom: 36, left: 36, right: Math.min(420, Math.max(260, elements.stage.clientWidth * 0.42)) },
  };
}

function applyCamera(camera, { instant = false } = {}) {
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

function openLayerView({ historyMode = 'push', cameraState = null } = {}) {
  if (runtime.state.view !== 'layers') runtime.previousGlobeCamera = runtime.mapReady ? mapCamera(runtime.map) : runtime.state.camera;
  runtime.state.view = 'layers';
  elements.stage.classList.add('layer-view-open');
  elements.layerPanel.hidden = false;
  elements.layerToggle.setAttribute('aria-expanded', 'true');
  renderLayerPanel();
  if (runtime.mapReady) {
    const target = cameraState ? { ...cameraState, padding: layerCamera().padding } : layerCamera();
    applyCamera(target, { instant: Boolean(cameraState) });
  }
  if (historyMode) writeHistory(historyMode);
}

function closeLayerView({ historyMode = 'push', cameraState = null } = {}) {
  runtime.state.view = 'globe';
  runtime.state.layer = null;
  elements.stage.classList.remove('layer-view-open');
  elements.layerPanel.hidden = true;
  elements.layerToggle.setAttribute('aria-expanded', 'false');
  if (runtime.mapReady) applyCamera(cameraState ?? runtime.previousGlobeCamera ?? runtime.state.camera, { instant: reducedMotion.matches });
  if (historyMode) writeHistory(historyMode);
}

function applyDeepLink(search, { initial = false } = {}) {
  const next = stateFromSearch(search, runtime.records.map(({ id }) => id));
  runtime.applyingHistory = true;
  runtime.state.project = next.project;
  runtime.state.layer = next.layer;
  runtime.state.camera = next.camera;
  if (runtime.mapReady) applyCamera(next.camera, { instant: true });
  if (next.view === 'layers') openLayerView({ historyMode: null, cameraState: next.camera });
  else closeLayerView({ historyMode: null, cameraState: next.camera });
  renderLayerPanel();
  updateSelectionMarks();
  runtime.applyingHistory = false;
  if (initial) writeHistory('replace');
}

function wireControls() {
  elements.layerToggle.addEventListener('click', () => openLayerView());
  elements.layerClose.addEventListener('click', () => closeLayerView());
  elements.sphereEdge.addEventListener('click', () => openLayerView());
  elements.sphereEdge.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openLayerView();
    }
  });
  elements.focusClose.addEventListener('click', () => clearProject());
  document.querySelectorAll('.catalog-select').forEach((button) => {
    button.addEventListener('click', () => selectProject(button.dataset.commonprojectId));
  });
  window.addEventListener('popstate', () => applyDeepLink(location.search));
}

function createMap() {
  if (!window.maplibregl?.Map) throw new Error('MapLibre konnte nicht aus der lokalen Laufzeit geladen werden.');
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
  });
  runtime.map.on('zoom', setSphereOpacity);
  runtime.map.on('moveend', scheduleCameraHistory);
  runtime.map.on('error', (event) => {
    console.warn('Commonworld map provider error', event?.error ?? event);
    setStatus('Die Basiskarte ist vorübergehend nicht erreichbar. Der Globus und alle Commons bleiben über die lineare Ansicht nutzbar.', 'degraded');
  });
  runtime.map.on('load', () => {
    runtime.mapReady = true;
    runtime.map.setProjection({ type: 'globe' });
    setSphereOpacity();
    setStatus('Interaktiver Globus bereit. Ziehen zum Drehen, scrollen oder die Tasten der Kartensteuerung zum Zoomen verwenden.', 'ready');
    applyDeepLink(location.search, { initial: true });
  });
}

async function boot() {
  try {
    runtime.records = await loadRecords();
    runtime.recordsById = new Map(runtime.records.map((record) => [record.id, record]));
    runtime.state = stateFromSearch(location.search, runtime.records.map(({ id }) => id));
    renderSphere();
    renderLayerPanel();
    wireControls();
    createMap();
    document.documentElement.classList.add('runtime-ready');
  } catch (error) {
    console.error(error);
    setStatus('Der interaktive Globus konnte nicht geladen werden. Die zehn geprüften Commons bleiben unten vollständig erreichbar.', 'failed');
    document.documentElement.classList.add('runtime-failed');
  }
}

boot();
