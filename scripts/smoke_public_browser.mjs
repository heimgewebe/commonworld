import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile, rename, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import {
  buildDigitalPresentationTree,
  deriveCommonsType,
  deriveDigitalProjectPath,
  deriveLayer,
  DIGITAL_LAYER_TRANSITION_MS,
  MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL,
  MAP_GEOMETRY_SAMPLE_INTERVAL_MS,
  DIGITAL_RING_FIELDS,
  DIGITAL_ROOT_PATH,
  globeHorizonCoordinates,
  publicMapFeatureCollection,
  ringOrbitDuration,
  serializeDigitalPath,
  sphereOpacityForGlobeRatio,
  visibleDigitalNodes,
} from '../assets/commonworld-core.mjs';

const ROOT = process.cwd();
// Allow half a CSS pixel for browser-dependent subpixel rounding of the nominal 48 px lane.
const MIN_RENDERED_LANE_HEIGHT_PX = 47.5;
const resultArgumentIndex = process.argv.indexOf('--result');
const resultPath = resultArgumentIndex >= 0 ? process.argv[resultArgumentIndex + 1] : null;
if (resultArgumentIndex >= 0 && !resultPath) throw new Error('--result requires a path');

async function writeResult(result) {
  if (!resultPath) return;
  const target = path.resolve(resultPath);
  const temporary = `${target}.tmp-${process.pid}`;
  await writeFile(temporary, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  await rename(temporary, target);
}
const MIME = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
  ['.png', 'image/png'],
  ['.pbf', 'application/x-protobuf'],
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function hierarchyFocusDiagnostic(page) {
  return page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    const panel = document.querySelector('#layer-panel');
    const active = document.activeElement;
    return {
      url: location.href,
      parameters: Object.fromEntries(new URL(location.href).searchParams),
      stage: {
        phase: stage?.dataset.viewPhase ?? null,
        digitalPath: stage?.dataset.digitalPath ?? null,
        pendingHierarchyFocusPath: stage?.dataset.pendingHierarchyFocusPath ?? null,
        hierarchyFocusAttempt: stage?.dataset.hierarchyFocusAttempt ?? null,
      },
      panel: {
        dataVisible: panel?.hasAttribute('data-visible') ?? false,
        hidden: panel?.hidden ?? null,
        inert: panel?.hasAttribute('inert') ?? false,
        ariaHidden: panel?.getAttribute('aria-hidden') ?? null,
      },
      active: {
        tag: active?.tagName ?? null,
        id: active?.id ?? null,
        className: active?.getAttribute?.('class') ?? null,
        connected: active?.isConnected ?? false,
        visible: Boolean(active?.getClientRects?.().length),
        hidden: Boolean(active?.closest?.('[hidden]')),
        inert: Boolean(active?.closest?.('[inert]')),
        ariaHidden: Boolean(active?.closest?.('[aria-hidden="true"]')),
      },
    };
  });
}

async function waitForAtomicHierarchyFocus(page, {
  label,
  expectedPath,
  activeSelector,
  requirePanel = true,
  timeout = 30_000,
}) {
  try {
    await page.waitForFunction(({ pathKey, selector, panelRequired }) => {
      const url = new URL(location.href);
      const stage = document.querySelector('.globe-stage');
      const panel = document.querySelector('#layer-panel');
      const active = document.activeElement;
      const serializedPath = url.searchParams.get('digital_path');
      const urlPathReady = pathKey === 'sphere' ? serializedPath === null : serializedPath === pathKey;
      const urlReady = urlPathReady && !url.searchParams.has('project');
      const stageReady = stage?.dataset.digitalPath === pathKey && !stage.dataset.pendingHierarchyFocusPath;
      const panelReady = !panelRequired || (
        panel?.hasAttribute('data-visible')
        && !panel.hidden
        && !panel.hasAttribute('inert')
      );
      const focusReady = active?.matches(selector)
        && active.isConnected
        && active.getClientRects().length > 0
        && !active.closest('[hidden], [inert], [aria-hidden="true"]');
      return urlReady && stageReady && panelReady && focusReady;
    }, { pathKey: expectedPath, selector: activeSelector, panelRequired: requirePanel }, { timeout });
  } catch (error) {
    const diagnostic = await hierarchyFocusDiagnostic(page);
    throw new Error(`${label}: timed out waiting for atomic URL, panel and focus state (${JSON.stringify(diagnostic)})`, { cause: error });
  }
  return hierarchyFocusDiagnostic(page);
}

function safePath(url) {
  const pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname);
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const target = path.resolve(ROOT, relative);
  if (target !== ROOT && !target.startsWith(`${ROOT}${path.sep}`)) return null;
  return target;
}

const server = createServer(async (request, response) => {
  try {
    const target = safePath(request.url ?? '/');
    if (!target || !(await stat(target)).isFile()) {
      response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end('not found');
      return;
    }
    response.writeHead(200, {
      'Content-Type': MIME.get(path.extname(target)) ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    response.end(await readFile(target));
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('not found');
  }
});

await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
const address = server.address();
if (!address || typeof address === 'string') throw new Error('browser smoke server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || (existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);
const browser = await chromium.launch({ headless: true, executablePath });
const results = [];

function sortedIds(values) {
  return [...values].sort((left, right) => left.localeCompare(right));
}

function assertSameIds(actual, expected, label) {
  const actualSorted = sortedIds(actual);
  const expectedSorted = sortedIds(expected);
  assert(JSON.stringify(actualSorted) === JSON.stringify(expectedSorted), `${label}: expected ${JSON.stringify(expectedSorted)} but found ${JSON.stringify(actualSorted)}`);
}

async function loadExpectedDigitalProjection() {
  const manifest = JSON.parse(await readFile(path.join(ROOT, 'catalog/catalog.json'), 'utf8'));
  assert(Array.isArray(manifest.project_files), 'catalog projection: manifest project_files missing');
  assert(manifest.project_files.length === manifest.entry_count, 'catalog projection: manifest entry_count does not match project_files');
  const allIds = [];
  const records = [];
  const catalogIds = [];
  const contributionIds = [];
  const communityNetworkIds = [];
  const dualPresenceIds = [];
  const dualPresenceVolunteerIds = [];
  for (const projectFile of manifest.project_files) {
    const record = JSON.parse(await readFile(path.join(ROOT, 'catalog', projectFile), 'utf8'));
    records.push(record);
    catalogIds.push(record.id);
    if (record.actions?.includes('contribute')) contributionIds.push(record.id);
    if (deriveCommonsType(record) === 'community-network') communityNetworkIds.push(record.id);
    const hasPublicGeographicPresence = (record.presence?.geographic ?? []).some((location) => location?.mode !== 'hidden' && Boolean(location?.geometry));
    const hasPublicDigitalPresence = record.presence?.digital?.available === true;
    if (hasPublicGeographicPresence && hasPublicDigitalPresence) dualPresenceIds.push(record.id);
    if (hasPublicGeographicPresence && hasPublicDigitalPresence && record.actions?.includes('volunteer')) dualPresenceVolunteerIds.push(record.id);
    if (record?.presence?.digital?.available !== true) continue;
    const derived = deriveDigitalProjectPath(record);
    assert(derived?.status === 'classified', `catalog projection: ${record.id} did not derive a classified digital path ${JSON.stringify(derived)}`);
    allIds.push(record.id);
  }
  assert(new Set(allIds).size === allIds.length, `catalog projection: duplicate digital IDs in catalog ${JSON.stringify(allIds)}`);
  const publicCollection = publicMapFeatureCollection(records);
  const publicFeatureCount = publicCollection.features.length;
  const publicIdentityCount = new Set(
    publicCollection.features.map(({ properties }) => properties.project_id).filter(Boolean),
  ).size;
  const aggregateImpressionCount = publicCollection.features.filter(
    ({ properties }) => properties.representation_kind === 'aggregate_impression',
  ).length;
  const privacyNoticeCount = publicCollection.features.filter(
    ({ properties }) => properties.representation_kind === 'aggregate_privacy_notice',
  ).length;
  const geographicSemanticLevels = sortedIds(new Set(
    publicCollection.features.map(({ properties }) => properties.semantic_level).filter(Boolean),
  ));
  const publicFeatureCountsByIdentity = Object.fromEntries(catalogIds.map((identifier) => [
    identifier,
    publicMapFeatureCollection(records, new Set([identifier])).features.length,
  ]));
  const tree = buildDigitalPresentationTree(records);
  const legacyLayerIds = Object.fromEntries([
    ...new Set(records.map(deriveLayer).filter(Boolean)),
  ].map((layer) => [layer, records.filter((record) => deriveLayer(record) === layer).map(({ id }) => id)]));
  const rootView = visibleDigitalNodes(tree, DIGITAL_ROOT_PATH);
  const nodes = Object.fromEntries([...tree.nodesByPath].map(([pathKey, node]) => [pathKey, {
    id: node.id,
    label: node.label,
    type: node.type,
    path: node.path,
    pathKey: node.pathKey,
    identityIds: [...node.identityIds],
    identityCount: node.identityCount,
  }]));
  const titleById = Object.fromEntries(records.map(({ id, title }) => [id, title]));
  const fields = DIGITAL_RING_FIELDS.map((field) => {
    const pathKey = serializeDigitalPath(field.path);
    const node = tree.nodesByPath.get(pathKey);
    assert(node, `catalog projection: missing field node ${pathKey}`);
    return {
      id: field.id,
      label: field.label,
      path: field.path,
      pathKey,
      ids: [...node.identityIds],
      previewIds: [...node.identityIds].slice(0, 4),
      ringPreviewIds: [...node.identityIds].slice(0, 2),
      count: node.identityCount,
    };
  });
  return {
    allIds,
    titleById,
    catalogIds,
    contributionIds,
    communityNetworkIds,
    dualPresenceIds,
    dualPresenceVolunteerIds,
    publicFeatureCount,
    publicIdentityCount,
    aggregateImpressionCount,
    privacyNoticeCount,
    geographicSemanticLevels,
    publicFeatureCountsByIdentity,
    totalCount: allIds.length,
    catalogEntryCount: manifest.entry_count,
    fields,
    nodes,
    rootChildIds: rootView.children.map((node) => node.id),
    legacyLayerIds,
  };
}

const expectedDigitalProjection = await loadExpectedDigitalProjection();

async function newPage({
  mobile = false,
  viewportOverride = null,
  touch = mobile,
  reducedMotion = 'reduce',
  geolocation = null,
  permissions = [],
} = {}) {
  const context = await browser.newContext({
    viewport: viewportOverride ?? (mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 }),
    isMobile: mobile,
    hasTouch: touch,
    deviceScaleFactor: 1,
    reducedMotion,
    ...(geolocation ? { geolocation } : {}),
  });
  if (permissions.length) await context.grantPermissions(permissions, { origin: baseUrl });
  await context.route('https://tiles.openfreemap.org/fonts/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/x-protobuf',
    body: Buffer.alloc(0),
  }));
  await context.addInitScript(() => {
    let maplibreValue;
    Object.defineProperty(window, 'maplibregl', {
      configurable: true,
      get() { return maplibreValue; },
      set(value) {
        if (value?.Map && !value.Map.__commonworldCaptured) {
          const OriginalMap = value.Map;
          class CapturedMap extends OriginalMap {
            constructor(...arguments_) {
              if (window.__commonworldStartupCalibrationHarness) {
                arguments_[0] = {
                  ...arguments_[0],
                  style: {
                    version: 8,
                    sources: {},
                    layers: [
                      {
                        id: 'commonworld-fallback',
                        type: 'background',
                        paint: { 'background-color': '#0d2426' },
                      },
                    ],
                  },
                };
              }
              window.__commonworldTestMapOptions = arguments_[0];
              window.__commonworldCameraCommands = [];
              super(...arguments_);
              if (window.__commonworldStartupCalibrationHarness) {
                const originalOn = this.on.bind(this);
                let delayedLoadListenerRegistered = false;
                this.on = (type, listener) => {
                  if (type === 'load' && !delayedLoadListenerRegistered) {
                    delayedLoadListenerRegistered = true;
                    return originalOn(type, (...eventArguments) => {
                      window.setTimeout(() => listener(...eventArguments), 650);
                    });
                  }
                  return originalOn(type, listener);
                };
              }
              window.__commonworldTestMap = this;
            }

            easeTo(options) {
              window.__commonworldCameraCommands ??= [];
              window.__commonworldCameraCommands.push({ command: 'easeTo', duration: options?.duration ?? null, at: performance.now() });
              return super.easeTo(options);
            }

            jumpTo(options) {
              window.__commonworldCameraCommands ??= [];
              window.__commonworldCameraCommands.push({ command: 'jumpTo', duration: 0, at: performance.now() });
              return super.jumpTo(options);
            }
          }
          CapturedMap.__commonworldCaptured = true;
          value.Map = CapturedMap;
        }
        maplibreValue = value;
      },
    });
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const consoleWarnings = [];
  const pageErrors = [];
  const httpErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
    if (message.type() === 'warning') consoleWarnings.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 400) httpErrors.push(response.status() + ' ' + response.url());
  });
  return { context, page, consoleErrors, consoleWarnings, pageErrors, httpErrors };
}


async function primaryOverlayState(page) {
  return page.evaluate(() => {
    const discovery = document.querySelector('#discovery-panel');
    const settings = document.querySelector('#settings-panel');
    const focus = document.querySelector('#project-focus');
    return {
      discoveryVisible: !discovery.hidden,
      settingsVisible: !settings.hidden,
      focusVisible: !focus.hidden,
      focusInert: focus.hasAttribute('inert'),
      focusAriaHidden: focus.getAttribute('aria-hidden'),
      skipInert: document.querySelector('.skip-link').hasAttribute('inert'),
      topbarInert: document.querySelector('.topbar').hasAttribute('inert'),
      globeInert: document.querySelector('#globe-surface').hasAttribute('inert'),
      textInert: document.querySelector('#text-view').hasAttribute('inert'),
      discoveryInert: discovery.hasAttribute('inert'),
      settingsModal: settings.getAttribute('aria-modal'),
    };
  });
}

async function waitForSphereOpacitySettled(page) {
  await page.waitForFunction(() => {
    const sphere = document.querySelector('#digital-sphere');
    if (!sphere) return false;
    const style = getComputedStyle(sphere);
    const visible = Number(style.opacity);
    const target = Number(style.getPropertyValue('--sphere-opacity'));
    return Number.isFinite(visible) && Number.isFinite(target) && Math.abs(visible - target) <= 0.01;
  });
}

async function waitForSphereGeometrySettled(page) {
  await page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    const stage = document.querySelector('.globe-stage');
    const sphere = document.querySelector('#digital-sphere');
    if (!map || !stage || !sphere || stage.dataset.viewPhase !== 'overview') return false;
    const globeDiameter = Number(stage.dataset.globeDiameter);
    const sphereWidth = sphere.getBoundingClientRect().width;
    return !map.isMoving() && Number.isFinite(globeDiameter) && globeDiameter > 0 && Math.abs(sphereWidth - globeDiameter * 1.32) <= 2;
  });
}

async function independentProjectedGlobeDiameter(page) {
  const center = await page.evaluate(() => {
    const map = window.__commonworldTestMap;
    if (!map) return null;
    const value = map.getCenter();
    return { lng: value.lng, lat: value.lat };
  });
  assert(center, 'browser proof: captured MapLibre instance missing');
  const horizon = globeHorizonCoordinates(center);
  return page.evaluate((coordinates) => {
    const map = window.__commonworldTestMap;
    const projectedCenter = map.project(map.getCenter());
    const radii = coordinates
      .map(({ lng, lat }) => map.project([lng, lat]))
      .map((point) => Math.hypot(point.x - projectedCenter.x, point.y - projectedCenter.y))
      .sort((left, right) => left - right);
    const middle = Math.floor(radii.length / 2);
    const radius = (radii[middle - 1] + radii[middle]) / 2;
    return radius * 2;
  }, horizon);
}

async function startupAndRingOrbitScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'startup-and-ring-orbits' })}\n`);
  const run = await newPage({ viewportOverride: { width: 1280, height: 800 }, reducedMotion: 'no-preference' });
  await run.page.addInitScript(() => {
    window.__commonworldStartupCalibrationHarness = true;
  });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Boolean(window.__commonworldTestMap));

  const loadingVisual = await run.page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    const sphere = document.querySelector('#digital-sphere');
    const canvas = document.querySelector('.maplibregl-canvas');
    return {
      visualReady: stage?.dataset.visualReady,
      sphereOpacity: Number(getComputedStyle(sphere).opacity),
      spherePointerEvents: getComputedStyle(sphere).pointerEvents,
      canvasOpacity: canvas ? Number(getComputedStyle(canvas).opacity) : null,
      projection: window.__commonworldTestMapOptions?.projection?.type ?? null,
    };
  });
  assert(loadingVisual.visualReady === 'false', 'startup: visual became ready before map calibration ' + JSON.stringify(loadingVisual));
  assert(loadingVisual.sphereOpacity === 0 && loadingVisual.spherePointerEvents === 'none', 'startup: uncalibrated digital sphere was exposed ' + JSON.stringify(loadingVisual));
  assert(loadingVisual.canvasOpacity === 0, 'startup: uncalibrated globe canvas was exposed ' + JSON.stringify(loadingVisual));
  assert(loadingVisual.projection === 'globe', 'startup: map did not start directly in globe projection ' + JSON.stringify(loadingVisual));

  try {
    await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.visualReady === 'true');
  } catch (error) {
    const diagnostic = await run.page.evaluate(() => {
      const stage = document.querySelector('.globe-stage');
      return {
        htmlClass: document.documentElement.className,
        stageDataset: { ...stage?.dataset },
        mapReady: Boolean(window.__commonworldTestMap),
        mapMoving: window.__commonworldTestMap?.isMoving?.() ?? null,
        mapLoaded: window.__commonworldTestMap?.loaded?.() ?? null,
      };
    });
    throw new Error('startup: map calibration timed out ' + JSON.stringify({ diagnostic, consoleErrors: run.consoleErrors, pageErrors: run.pageErrors, cause: error.message }));
  }
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  assert((await run.page.evaluate(() => window.__commonworldTestMap?.getProjection?.()?.type)) === 'globe', 'startup: active projection changed after map calibration');
  await waitForSphereOpacitySettled(run.page);

  const geometryBeforeRepaint = await run.page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    window.__commonworldIdleRepaintRenderCount = 0;
    window.__commonworldIdleRepaintRenderHandler = () => {
      window.__commonworldIdleRepaintRenderCount += 1;
    };
    window.__commonworldTestMap.on('render', window.__commonworldIdleRepaintRenderHandler);
    return {
      geometryCommits: Number(stage?.dataset.sphereGeometryCommits ?? 0),
      geometryEvaluations: Number(stage?.dataset.sphereGeometryEvaluations ?? 0),
      diagnosticPublishes: Number(stage?.dataset.sphereGeometryDiagnosticPublishes ?? 0),
    };
  });
  await run.page.evaluate(async () => {
    const map = window.__commonworldTestMap;
    for (let index = 0; index < 6; index += 1) {
      map.triggerRepaint();
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
  });
  await run.page.waitForFunction(() => window.__commonworldIdleRepaintRenderCount > 0);
  await run.page.waitForTimeout(120);
  const geometryAfterRepaint = await run.page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    const renderCount = window.__commonworldIdleRepaintRenderCount;
    window.__commonworldTestMap.off('render', window.__commonworldIdleRepaintRenderHandler);
    delete window.__commonworldIdleRepaintRenderHandler;
    return {
      idleRepaintRenderCount: renderCount,
      geometryCommits: Number(stage?.dataset.sphereGeometryCommits ?? 0),
      geometryEvaluations: Number(stage?.dataset.sphereGeometryEvaluations ?? 0),
      diagnosticPublishes: Number(stage?.dataset.sphereGeometryDiagnosticPublishes ?? 0),
    };
  });
  const repaintEvaluationDelta = geometryAfterRepaint.geometryEvaluations - geometryBeforeRepaint.geometryEvaluations;
  const repaintDiagnosticPublishDelta = geometryAfterRepaint.diagnosticPublishes - geometryBeforeRepaint.diagnosticPublishes;
  assert(geometryAfterRepaint.idleRepaintRenderCount > 0, 'geometry cache: test repaints did not reach MapLibre');
  assert(repaintEvaluationDelta === 0, 'geometry sampler: idle MapLibre repaints still trigger sphere projection work ' + JSON.stringify({ geometryBeforeRepaint, geometryAfterRepaint }));
  assert(repaintDiagnosticPublishDelta === 0, 'geometry diagnostics: idle MapLibre repaints still publish DOM metadata ' + JSON.stringify({ geometryBeforeRepaint, geometryAfterRepaint }));
  assert(geometryAfterRepaint.geometryCommits === geometryBeforeRepaint.geometryCommits, 'geometry cache: unchanged repaints rewrote sphere geometry ' + JSON.stringify({ geometryBeforeRepaint, geometryAfterRepaint }));

  const removedHint = await run.page.evaluate(() => ({
    actionPath: document.querySelector('#sphere-action-path') !== null,
    actionGuide: document.querySelector('.sphere-action-guide') !== null,
    actionText: document.querySelector('.sphere-action-text') !== null,
    affordanceAttribute: document.querySelector('#digital-sphere')?.hasAttribute('data-affordance-active') ?? false,
    hintText: document.querySelector('#digital-sphere')?.textContent?.includes('DIGITALE EBENEN ÖFFNEN') ?? false,
  }));
  assert(Object.values(removedHint).every((value) => value === false), 'outer hint: removed affordance markup is still present ' + JSON.stringify(removedHint));

  const edgeControl = await run.page.evaluate(() => {
    const control = document.querySelector('#sphere-edge-control');
    return {
      ariaLabel: control?.getAttribute('aria-label') ?? '',
      tabindex: control?.getAttribute('tabindex') ?? '',
      hitWidth: Number(control?.getAttribute('stroke-width')),
    };
  });
  assert(edgeControl.ariaLabel.includes('Antippen') && edgeControl.ariaLabel.includes('Eingabetaste'), 'edge control: accessible instruction is incomplete ' + JSON.stringify(edgeControl));
  assert(edgeControl.tabindex === '0' && edgeControl.hitWidth >= 34, 'edge control: keyboard path or hit target was lost ' + JSON.stringify(edgeControl));

  const rings = await run.page.evaluate(() => {
    return [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
      const style = getComputedStyle(plane);
      const names = [...plane.querySelectorAll('.sphere-ring-name[data-commonproject-id]')].map((node) => node.dataset.commonprojectId);
      return {
        layer: plane.dataset.layerId,
        entryCount: Number(plane.dataset.entryCount),
        orbitDuration: Number(plane.dataset.orbitDuration),
        directionVariable: plane.style.getPropertyValue('--ring-orbit-direction').trim(),
        startAngleVariable: plane.style.getPropertyValue('--ring-orbit-start-angle').trim(),
        animationName: style.animationName,
        animationDurationSeconds: Number.parseFloat(style.animationDuration),
        animationIterationCount: style.animationIterationCount,
        animationPlayState: style.animationPlayState,
        hasGuide: plane.querySelector('use.sphere-layer-guide') !== null,
        placeholderCount: plane.querySelectorAll('.sphere-ring-placeholder').length,
        placeholderIds: [...plane.querySelectorAll('.sphere-ring-placeholder')].filter((node) => node.dataset.commonprojectId).length,
        ids: names,
      };
    });
  });
  assert(rings.length === expectedDigitalProjection.fields.length, `ring orbits: expected canonical ring planes (${rings.length})`);
  const aggregateCount = rings.reduce((total, ring) => total + ring.entryCount, 0);
  assert(aggregateCount === expectedDigitalProjection.totalCount, `ring orbits: aggregate count differs from catalog (${aggregateCount})`);
  for (const ring of rings) {
    const expectedLayer = expectedDigitalProjection.fields.find(({ id }) => id === ring.layer);
    assert(expectedLayer, `ring orbits: rendered unknown layer ${ring.layer}`);
    assert(ring.hasGuide, `ring orbits: ${ring.layer} lost its orbit guide`);
    assert(Number.isFinite(ring.entryCount) && ring.entryCount === expectedLayer.count, `ring orbits: ${ring.layer} entry count diverges from catalog identities ${JSON.stringify({ ring, expectedLayer })}`);
    assertSameIds(ring.ids, expectedLayer.ringPreviewIds, `ring orbits: ${ring.layer} preview identity set`);
    assert(new Set(ring.ids).size === ring.ids.length, `ring orbits: ${ring.layer} repeats an identity ${JSON.stringify(ring.ids)}`);
    if (ring.entryCount === 0) {
      assert(ring.placeholderCount === 1 && ring.placeholderIds === 0, `ring orbits: empty ${ring.layer} needs a non-identity placeholder ${JSON.stringify(ring)}`);
    } else {
      assert(ring.placeholderCount === 0, `ring orbits: populated ${ring.layer} must not show a placeholder`);
    }
    assert(Math.abs(ring.orbitDuration - ringOrbitDuration(ring.entryCount)) <= 0.01, `ring orbits: ${ring.layer} duration diverges from ringOrbitDuration ${JSON.stringify(ring)}`);
    assert(ring.animationName === 'sphere-ring-orbit', `ring orbits: ${ring.layer} is not driven by the shared CSS orbit animation ${JSON.stringify(ring)}`);
    assert(Math.abs(ring.animationDurationSeconds - ring.orbitDuration) <= 0.5, `ring orbits: ${ring.layer} CSS duration diverges from its declared duration ${JSON.stringify(ring)}`);
    assert(ring.animationIterationCount === 'infinite' && ring.animationPlayState === 'running', `ring orbits: ${ring.layer} does not orbit continuously ${JSON.stringify(ring)}`);
  }
  const directions = rings.map(({ directionVariable }) => directionVariable);
  assert(directions.every((value) => value === '1' || value === '-1'), `ring orbits: directions must be deterministic units (${JSON.stringify(directions)})`);
  assert(new Set(directions).size === 2, `ring orbits: directions must alternate (${JSON.stringify(directions)})`);
  assert(new Set(rings.map(({ startAngleVariable }) => startAngleVariable)).size === rings.length, 'ring orbits: start angles must stay distinct');

  const ringMatricesBefore = await run.page.evaluate(() => [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
    const matrix = plane.getCTM?.();
    return {
      layer: plane.dataset.layerId,
      transform: getComputedStyle(plane).transform,
      ctm: matrix ? [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f].map((value) => value.toFixed(5)).join(',') : null,
    };
  }));
  await run.page.waitForTimeout(520);
  const ringMatricesAfter = await run.page.evaluate(() => [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
    const matrix = plane.getCTM?.();
    return {
      layer: plane.dataset.layerId,
      transform: getComputedStyle(plane).transform,
      ctm: matrix ? [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f].map((value) => value.toFixed(5)).join(',') : null,
    };
  }));
  const movedRing = ringMatricesBefore.some((before, index) => before.transform !== ringMatricesAfter[index]?.transform);
  assert(movedRing, `ring orbits: no ring transform matrix changed under normal motion (${JSON.stringify({ before: ringMatricesBefore, after: ringMatricesAfter })})`);
  const idleBefore = Number(await run.page.locator('.globe-stage').getAttribute('data-overlay-renders'));
  await run.page.waitForTimeout(650);
  const idleAfter = Number(await run.page.locator('.globe-stage').getAttribute('data-overlay-renders'));
  assert(idleAfter - idleBefore === 0, `ring orbits: idle overlay render delta is not zero (${idleBefore} -> ${idleAfter})`);

  assert(run.consoleErrors.length === 0, 'startup: console errors: ' + run.consoleErrors.join(' | ') + '; HTTP: ' + run.httpErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'startup: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'startup-and-ring-orbits', verdict: 'PASS', directGlobeProjection: true, hiddenUntilCalibrated: true, outerHintRemoved: true, aggregateRingIdentities: aggregateCount, movingRingMatrix: movedRing, unchangedGeometryRepaintSkipped: true });
  await run.context.close();
}

async function syntheticDigitalPerformanceScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'synthetic-digital-performance' })}\n`);
  const run = await newPage({ viewportOverride: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  const metrics = await run.page.evaluate(async () => {
    const core = await import('/assets/commonworld-core.mjs');
    const measure = (size) => {
      const records = Array.from({ length: size }, (_, index) => ({
        id: `synthetic-digital-${String(index).padStart(5, '0')}`,
        title: `Synthetic Digital ${index}`,
        summary: 'Synthetic browser performance identity.',
        themes: index % 2 === 0 ? ['communication', 'community-network'] : ['open-data', 'infrastructure'],
        presence: { geographic: [], digital: { available: true } },
      }));
      const constructionsBefore = core.digitalPresentationTreeConstructionCount();
      const tree = core.buildDigitalPresentationTree(records);
      core.buildDigitalPresentationTree(records);
      core.buildDigitalPresentationTree(records);
      core.buildDigitalPresentationTree(records);
      const root = core.visibleDigitalNodes(tree, core.DIGITAL_ROOT_PATH);
      const communication = core.visibleDigitalNodes(tree, ['sphere', 'communication_networks']);
      const community = core.visibleDigitalNodes(tree, ['sphere', 'communication_networks', 'community_networks'], { identityLimit: 48 });
      const fullCommunity = core.visibleDigitalNodes(tree, ['sphere', 'communication_networks', 'community_networks']);
      return {
        size,
        treeNodeCount: tree.nodesByPath.size,
        rootVisible: root.children.length,
        communicationVisible: communication.children.length,
        boundedIdentityVisible: community.children.length,
        fullIdentityCount: fullCommunity.current.identityCount,
        syntheticDomBudget: root.children.length + communication.children.length + community.children.length,
        treeConstructionDelta: core.digitalPresentationTreeConstructionCount() - constructionsBefore,
      };
    };
    const stage = document.querySelector('.globe-stage');
    const overlayBefore = Number(stage?.dataset.overlayRenders ?? 0);
    await new Promise((resolve) => setTimeout(resolve, 650));
    const overlayAfter = Number(stage?.dataset.overlayRenders ?? 0);
    return {
      cases: [measure(500), measure(5000)],
      liveRibbonDom: document.querySelectorAll('#sphere-rings .sphere-ring-plane, .digital-lane, .digital-ribbon-item').length,
      overlayDelta: overlayAfter - overlayBefore,
    };
  });
  for (const item of metrics.cases) {
    assert(item.rootVisible <= 5, `synthetic ${item.size}: root rendered too many visible nodes (${JSON.stringify(item)})`);
    assert(item.communicationVisible <= 3, `synthetic ${item.size}: field rendered too many child bundles (${JSON.stringify(item)})`);
    assert(item.boundedIdentityVisible <= 48, `synthetic ${item.size}: identity level exceeded the DOM budget (${JSON.stringify(item)})`);
    assert(item.fullIdentityCount === Math.ceil(item.size / 2), `synthetic ${item.size}: aggregate identity count was lost (${JSON.stringify(item)})`);
    assert(item.syntheticDomBudget <= 56, `synthetic ${item.size}: visible node budget is unbounded (${JSON.stringify(item)})`);
    assert(item.treeConstructionDelta === 1, `synthetic ${item.size}: stable record identity rebuilt the full tree (${JSON.stringify(item)})`);
  }
  assert(metrics.liveRibbonDom < 140, `synthetic performance: live DOM budget unexpectedly high (${JSON.stringify(metrics)})`);
  assert(metrics.overlayDelta === 0, `synthetic performance: idle overlay render delta is not zero (${JSON.stringify(metrics)})`);
  const queryTreeBuildsBefore = await run.page.evaluate(async () => (await import('/assets/commonworld-core.mjs')).digitalPresentationTreeConstructionCount());
  await run.page.locator('#commons-search').fill('Wikipedia');
  await run.page.waitForTimeout(220);
  const queryTreeBuildsAfter = await run.page.evaluate(async () => (await import('/assets/commonworld-core.mjs')).digitalPresentationTreeConstructionCount());
  assert(queryTreeBuildsAfter - queryTreeBuildsBefore < 4, `synthetic performance: one query action built four full trees (${queryTreeBuildsBefore} -> ${queryTreeBuildsAfter})`);
  assert(run.consoleErrors.length === 0, `synthetic performance: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `synthetic performance: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'synthetic-digital-performance', verdict: 'PASS', cases: metrics.cases, idleOverlayRenderDelta: metrics.overlayDelta });
  await run.context.close();
}

async function reducedMotionRingScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'ring-orbits-reduced-motion' })}\n`);
  const run = await newPage({ reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  const rings = await run.page.evaluate(() => (
    [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
      const style = getComputedStyle(plane);
      return {
        layer: plane.dataset.layerId,
        entryCount: plane.dataset.entryCount,
        animationName: style.animationName,
        animationDurationSeconds: Number.parseFloat(style.animationDuration),
      };
    })
  ));
  assert(rings.length === expectedDigitalProjection.fields.length, `reduced motion rings: expected canonical ring planes (${rings.length})`);
  for (const ring of rings) {
    assert(ring.entryCount !== undefined, `reduced motion rings: ${ring.layer} lost its entry count`);
    const stopped = ring.animationName === 'none' || ring.animationDurationSeconds <= 0.001;
    assert(stopped, `reduced motion rings: ${ring.layer} keeps orbiting (${JSON.stringify(ring)})`);
  }
  const matricesBefore = await run.page.evaluate(() => [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
    const matrix = plane.getCTM?.();
    return {
      layer: plane.dataset.layerId,
      transform: getComputedStyle(plane).transform,
      ctm: matrix ? [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f].map((value) => value.toFixed(5)).join(',') : null,
    };
  }));
  await run.page.waitForTimeout(520);
  const matricesAfter = await run.page.evaluate(() => [...document.querySelectorAll('#sphere-rings .sphere-ring-plane')].map((plane) => {
    const matrix = plane.getCTM?.();
    return {
      layer: plane.dataset.layerId,
      transform: getComputedStyle(plane).transform,
      ctm: matrix ? [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f].map((value) => value.toFixed(5)).join(',') : null,
    };
  }));
  const moved = matricesBefore.some((before, index) => before.transform !== matricesAfter[index]?.transform);
  assert(!moved, `reduced motion rings: ring transform changed despite disabled animation (${JSON.stringify({ before: matricesBefore, after: matricesAfter })})`);
  await run.page.locator('#sphere-edge-control').focus();
  await run.page.keyboard.press('Enter');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  assert(run.pageErrors.length === 0, `reduced motion rings: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'ring-orbits-reduced-motion', verdict: 'PASS' });
  await run.context.close();
}


async function normalScenario() {
  const run = await newPage();
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  assert(await run.page.locator('#globe-surface').isVisible(), 'normal: globe is not visible');
  assert((await run.page.locator('#globe-results').textContent())?.includes(`${expectedDigitalProjection.catalogEntryCount} Commons`), 'normal: result count missing');
  const declutterGeometry = await run.page.evaluate(() => {
    const box = (selector) => {
      const rect = document.querySelector(selector).getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    };
    return {
      results: box('#globe-results'),
      semanticSummary: box('#semantic-summary'),
      orientation: box('.orientation-bar'),
      legend: box('.map-legend'),
    };
  });
  assert(declutterGeometry.results.width <= 2 && declutterGeometry.results.height <= 2, `normal: result description still obscures the globe (${JSON.stringify(declutterGeometry)})`);
  assert(declutterGeometry.semanticSummary.width <= 2 && declutterGeometry.semanticSummary.height <= 2, `normal: semantic description still expands the orientation bar (${JSON.stringify(declutterGeometry)})`);
  assert(declutterGeometry.orientation.width < 320, `normal: compact orientation bar regressed (${JSON.stringify(declutterGeometry)})`);
  assert(declutterGeometry.legend.width < 240, `normal: collapsed map legend is not compact (${JSON.stringify(declutterGeometry)})`);
  const topbarGeometry = await run.page.evaluate(() => {
    const topbar = document.querySelector('.topbar');
    const bar = topbar.getBoundingClientRect();
    return {
      bar: { top: bar.top, bottom: bar.bottom },
      children: [...topbar.children].map((node) => {
        const rect = node.getBoundingClientRect();
        return { className: node.className, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
      }),
    };
  });
  assert(topbarGeometry.children.every(({ top, bottom }) => top >= topbarGeometry.bar.top - 1 && bottom <= topbarGeometry.bar.bottom + 1), `normal: topbar child escaped into a second row (${JSON.stringify(topbarGeometry)})`);
  const proposalGeometry = topbarGeometry.children.find(({ className }) => className === 'proposal-link');
  assert(proposalGeometry?.width >= 44 && proposalGeometry?.height >= 44, `normal: proposal link is not a full touch target (${JSON.stringify(proposalGeometry)})`);

  await run.page.locator('.skip-link').focus();
  await run.page.keyboard.press('Enter');
  assert(await run.page.locator('#text-view').isVisible(), 'normal: skip link did not switch to text');
  assert((await run.page.locator('body').getAttribute('data-presentation')) === 'text', 'normal: presentation did not become text');

  await run.page.keyboard.press('Tab');
  await run.page.locator('#settings-toggle').focus();
  const keyboardFocusAppearance = await run.page.locator('#settings-toggle').evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      modality: document.documentElement.dataset.inputModality,
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth),
    };
  });
  assert(keyboardFocusAppearance.modality === 'keyboard' && keyboardFocusAppearance.outlineStyle !== 'none' && keyboardFocusAppearance.outlineWidth > 0, 'normal: keyboard focus indicator was removed ' + JSON.stringify(keyboardFocusAppearance));
  await run.page.locator('#filter-toggle').click();
  assert(await run.page.locator('#discovery-panel').isVisible(), 'normal: discovery panel did not open before settings');
  await run.page.locator('#settings-toggle').click();
  assert(await run.page.locator('#discovery-panel').isHidden(), 'normal: opening settings left discovery stacked underneath');
  assert(await run.page.locator('#settings-panel').isVisible(), 'normal: settings panel did not open');
  const settingsOnlyState = await primaryOverlayState(run.page);
  assert(settingsOnlyState.settingsVisible && !settingsOnlyState.discoveryVisible && !settingsOnlyState.focusVisible, 'normal: primary overlay invariant failed while settings opened ' + JSON.stringify(settingsOnlyState));
  assert(settingsOnlyState.settingsModal === 'true', 'normal: settings are not exposed as a modal dialog');
  assert(settingsOnlyState.skipInert && settingsOnlyState.topbarInert && settingsOnlyState.globeInert && settingsOnlyState.textInert, 'normal: settings left background surfaces interactive ' + JSON.stringify(settingsOnlyState));
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'settings-close', 'normal: settings did not establish an initial focus target');
  const settingsAccessibility = await run.page.evaluate(() => {
    const panel = document.querySelector('#settings-panel');
    const describedBy = panel.getAttribute('aria-describedby');
    const selector = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const controls = [...panel.querySelectorAll(selector)].map((node) => ({
      label: node.id || node.getAttribute('aria-label') || node.textContent.trim().slice(0, 40),
      height: node.getBoundingClientRect().height,
    }));
    const background = [...document.querySelectorAll(selector)]
      .filter((node) => !panel.contains(node) && node.getClientRects().length > 0)
      .map((node) => ({
        label: node.id || node.getAttribute('aria-label') || node.textContent.trim().slice(0, 40),
        inertAncestor: Boolean(node.closest('[inert]')),
      }));
    return {
      controls,
      background,
      describedBy,
      description: describedBy ? document.getElementById(describedBy)?.textContent.trim() ?? '' : '',
    };
  });
  assert(settingsAccessibility.controls.length > 0 && settingsAccessibility.controls.every(({ height }) => height >= 44), `normal: settings contain undersized focus targets (${JSON.stringify(settingsAccessibility.controls)})`);
  assert(settingsAccessibility.background.length > 0 && settingsAccessibility.background.every(({ inertAncestor }) => inertAncestor), `normal: visible background focus target lacks an inert ancestor (${JSON.stringify(settingsAccessibility.background)})`);
  assert(settingsAccessibility.describedBy === 'settings-description' && settingsAccessibility.description.length > 0, `normal: settings dialog lacks a usable description (${JSON.stringify(settingsAccessibility)})`);
  const lastSettingsLink = run.page.locator('#settings-panel a').last();
  await lastSettingsLink.focus();
  await run.page.keyboard.press('Tab');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'settings-close', 'normal: settings focus escaped after the last control');
  await run.page.keyboard.press('Shift+Tab');
  assert(await lastSettingsLink.evaluate((node) => document.activeElement === node), 'normal: reverse settings focus did not wrap to the final control');
  await run.page.evaluate(() => {
    const probe = document.createElement('button');
    probe.id = 'settings-focus-escape-probe';
    probe.textContent = 'probe';
    document.body.append(probe);
    probe.focus();
  });
  await run.page.keyboard.press('Tab');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'settings-close', 'normal: settings did not recover focus from an injected outside target');
  await run.page.evaluate(() => document.querySelector('#settings-focus-escape-probe')?.remove());
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#settings-panel').isHidden(), 'normal: settings panel did not close with Escape');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'settings-toggle', 'normal: settings focus was not restored');
  const settingsClosedState = await primaryOverlayState(run.page);
  assert(!settingsClosedState.skipInert && !settingsClosedState.topbarInert && !settingsClosedState.globeInert && !settingsClosedState.textInert, 'normal: settings left background surfaces inert after close ' + JSON.stringify(settingsClosedState));

  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForTimeout(220);
  const debianTrigger = run.page.locator('#project-debian .catalog-select');
  const debianResult = run.page.locator('.discovery-result-main[data-commonproject-id="debian"]');
  await debianResult.click();
  assert(await run.page.locator('#project-focus').isVisible(), 'normal: project focus did not open');
  const focusOnlyState = await primaryOverlayState(run.page);
  assert(focusOnlyState.focusVisible && !focusOnlyState.discoveryVisible && !focusOnlyState.settingsVisible && !focusOnlyState.focusInert && focusOnlyState.focusAriaHidden === null, 'normal: visible project focus kept suppressed accessibility state ' + JSON.stringify(focusOnlyState));
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'project-focus', 'normal: project focus did not receive focus');
  assert(((await run.page.locator('#semantic-summary').textContent()) ?? '') === 'Digital · Ortsunabhängige digitale Präsenz', 'normal: digital-only focus lost its location-independent truth');
  await run.page.locator('#filter-toggle').click();
  assert(await run.page.locator('#discovery-panel').isVisible(), 'normal: discovery did not open over a selected project');
  assert(await run.page.locator('#project-focus').isHidden(), 'normal: selected project obscured discovery results');
  const discoveryOnlyState = await primaryOverlayState(run.page);
  assert(discoveryOnlyState.discoveryVisible && !discoveryOnlyState.settingsVisible && !discoveryOnlyState.focusVisible && discoveryOnlyState.focusInert && discoveryOnlyState.focusAriaHidden === 'true', 'normal: discovery did not exclusively suppress project focus ' + JSON.stringify(discoveryOnlyState));
  assert(discoveryOnlyState.globeInert && discoveryOnlyState.textInert, 'normal: discovery left obscured content interactive ' + JSON.stringify(discoveryOnlyState));
  assert(new URL(run.page.url()).searchParams.get('project') === 'debian', 'normal: hiding focus for discovery cleared the selected project context');
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#discovery-panel').isHidden(), 'normal: Escape did not close discovery before the preserved project focus');
  assert(await run.page.locator('#project-focus').isVisible(), 'normal: preserved project focus did not return after discovery closed');
  await run.page.locator('#settings-toggle').click();
  assert(await run.page.locator('#settings-panel').isVisible(), 'normal: settings did not open over a selected project');
  assert(await run.page.locator('#project-focus').isHidden(), 'normal: selected project obscured settings');
  const selectedSettingsOnlyState = await primaryOverlayState(run.page);
  assert(selectedSettingsOnlyState.settingsVisible && !selectedSettingsOnlyState.discoveryVisible && !selectedSettingsOnlyState.focusVisible && selectedSettingsOnlyState.focusInert && selectedSettingsOnlyState.focusAriaHidden === 'true', 'normal: settings did not exclusively suppress project focus ' + JSON.stringify(selectedSettingsOnlyState));
  assert(new URL(run.page.url()).searchParams.get('project') === 'debian', 'normal: hiding focus for settings cleared the selected project context');
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#settings-panel').isHidden(), 'normal: Escape did not close settings before the preserved project focus');
  assert(await run.page.locator('#project-focus').isVisible(), 'normal: preserved project focus did not return after settings closed');
  await run.page.locator('#commons-search').focus();
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'commons-search', 'normal: project focus incorrectly blocks background navigation');
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#project-focus').isHidden(), 'normal: project focus did not close with Escape');
  assert(await debianTrigger.evaluate((node) => document.activeElement === node), 'normal: project focus did not restore its trigger');

  await run.page.locator('#commons-search').fill('quantenbanane-xyz');
  await run.page.waitForTimeout(220);
  await run.page.locator('#settings-toggle').click();
  await run.page.getByRole('radio', { name: /Globus/ }).click();
  assert(await run.page.locator('#globe-results').getAttribute('data-empty') !== null, 'normal: globe empty state marker missing');
  assert((await run.page.locator('#globe-results').textContent())?.includes('Keine Commons'), 'normal: globe empty-state text missing');
  assert(run.consoleErrors.length === 0, `normal: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `normal: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'normal', verdict: 'PASS' });
  await run.context.close();
}


async function layerJourneyScenario({ mobile = false, viewportOverride = null, touch = mobile, scenarioId = null } = {}) {
  const activeScenarioId = scenarioId ?? (mobile ? 'layer-journey-mobile' : 'layer-journey-desktop');
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: activeScenarioId })}\n`);
  const run = await newPage({ mobile, viewportOverride, touch, reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  await run.page.waitForTimeout(820);

  const before = await run.page.locator('#digital-sphere').boundingBox();
  assert(before, 'layer journey: sphere has no initial geometry');
  const stage = run.page.locator('.globe-stage');
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'maplibre-projected-horizon', 'layer journey: sphere does not use MapLibre horizon geometry');
  const projectedBefore = await independentProjectedGlobeDiameter(run.page);
  const declaredBefore = Number(await stage.getAttribute('data-globe-diameter'));
  assert(Math.abs(declaredBefore - projectedBefore) <= 1, `layer journey: declared globe diameter diverges from MapLibre horizon (${declaredBefore} vs ${projectedBefore})`);
  assert(Math.abs(before.width - declaredBefore * 1.32) <= 2, `layer journey: outer shell ratio is wrong (${before.width} vs ${declaredBefore})`);
  const overviewRibbons = await run.page.evaluate(() => ({
    rings: document.querySelectorAll('.sphere-ring-text').length,
    names: [...document.querySelectorAll('.sphere-ring-name')].map((node) => node.textContent.trim()).filter(Boolean),
    binaries: [...document.querySelectorAll('.sphere-ring-binary')].map((node) => node.textContent.trim()).filter(Boolean),
  }));
  assert(overviewRibbons.rings === expectedDigitalProjection.fields.length, `layer journey: overview does not contain all text rings (${JSON.stringify(overviewRibbons)})`);
  const expectedOverviewNames = expectedDigitalProjection.fields.flatMap(({ ringPreviewIds }) =>
    ringPreviewIds.map((identifier) => expectedDigitalProjection.titleById[identifier]),
  );
  assertSameIds(overviewRibbons.names, expectedOverviewNames, 'layer journey: preview ring Commons name set');
  assert(overviewRibbons.binaries.some((value) => /^(?:[01]{8})(?: [01]{8})*$/.test(value)), 'layer journey: real bytewise binary names are missing from the rings');
  await waitForSphereOpacitySettled(run.page);
  const opacityBefore = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioBefore = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacityBefore - sphereOpacityForGlobeRatio(ratioBefore)) <= 0.01, `layer journey: initial opacity does not follow visible globe ratio (${opacityBefore} at ${ratioBefore})`);

  const zoomInBox = await run.page.locator('.maplibregl-ctrl-zoom-in').boundingBox();
  assert(zoomInBox, 'layer journey: zoom-in control has no geometry');
  const activateZoomIn = async () => {
    const previousRenderedSize = await run.page.locator('#digital-sphere').evaluate((node) => node.getBoundingClientRect().width);
    if (mobile) await run.page.touchscreen.tap(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
    else await run.page.mouse.click(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
    await run.page.waitForFunction((size) => {
      const sphere = document.querySelector('#digital-sphere');
      return sphere && Math.abs(sphere.getBoundingClientRect().width - size) > 1;
    }, previousRenderedSize);
    const synchronousGeometry = await run.page.evaluate(() => {
      const stage = document.querySelector('.globe-stage');
      const sphere = document.querySelector('#digital-sphere');
      const style = getComputedStyle(sphere);
      return {
        rendered: sphere.getBoundingClientRect().width,
        visualSize: Number.parseFloat(style.getPropertyValue('--sphere-size')),
        diagnosticSize: Number(stage.dataset.sphereSize),
        transitionProperty: style.transitionProperty,
      };
    });
    assert(Number.isFinite(synchronousGeometry.visualSize) && Math.abs(synchronousGeometry.rendered - synchronousGeometry.visualSize) <= 2, 'layer journey: visual sphere geometry trails the moving globe ' + JSON.stringify(synchronousGeometry));
    assert(!synchronousGeometry.transitionProperty.split(',').map((value) => value.trim()).some((value) => ['width', 'height', 'left', 'top'].includes(value)), 'layer journey: overview geometry still animates behind the globe ' + JSON.stringify(synchronousGeometry));
    await waitForSphereGeometrySettled(run.page);
  };
  await activateZoomIn();
  const afterFirstZoom = await run.page.locator('#digital-sphere').boundingBox();
  const projectedFirstZoom = await independentProjectedGlobeDiameter(run.page);
  const declaredFirstZoom = Number(await stage.getAttribute('data-globe-diameter'));
  assert(afterFirstZoom && afterFirstZoom.width > before.width * 1.18, `layer journey: first zoom did not enlarge sphere (${before.width} -> ${afterFirstZoom?.width})`);
  assert(Math.abs(declaredFirstZoom - projectedFirstZoom) <= 1, `layer journey: first zoom lost MapLibre horizon coupling (${declaredFirstZoom} vs ${projectedFirstZoom})`);
  await waitForSphereOpacitySettled(run.page);
  const opacityFirstZoom = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioFirstZoom = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacityFirstZoom - sphereOpacityForGlobeRatio(ratioFirstZoom)) <= 0.01, `layer journey: first zoom opacity does not follow visible globe ratio (${opacityFirstZoom} at ${ratioFirstZoom})`);

  await activateZoomIn();
  const afterSecondZoom = await run.page.locator('#digital-sphere').boundingBox();
  const projectedSecondZoom = await independentProjectedGlobeDiameter(run.page);
  const declaredSecondZoom = Number(await stage.getAttribute('data-globe-diameter'));
  assert(afterSecondZoom && afterSecondZoom.width > afterFirstZoom.width * 1.12, `layer journey: second zoom hit an artificial size ceiling (${afterFirstZoom.width} -> ${afterSecondZoom?.width})`);
  assert(Math.abs(declaredSecondZoom - projectedSecondZoom) <= 1, `layer journey: second zoom lost MapLibre horizon coupling (${declaredSecondZoom} vs ${projectedSecondZoom})`);
  await waitForSphereOpacitySettled(run.page);
  const opacitySecondZoom = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioSecondZoom = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacitySecondZoom - sphereOpacityForGlobeRatio(ratioSecondZoom)) <= 0.01, `layer journey: second zoom opacity does not follow visible globe ratio (${opacitySecondZoom} at ${ratioSecondZoom})`);
  assert(opacitySecondZoom <= opacityFirstZoom, `layer journey: opacity increased while visible globe grew (${opacityFirstZoom} -> ${opacitySecondZoom})`);

  const zoomOutBox = await run.page.locator('.maplibregl-ctrl-zoom-out').boundingBox();
  assert(zoomOutBox, 'layer journey: zoom-out control has no geometry');
  let previousZoomOutWidth = afterSecondZoom.width;
  let restoredScale = null;
  for (let index = 0; index < 2; index += 1) {
    if (mobile) await run.page.touchscreen.tap(zoomOutBox.x + zoomOutBox.width / 2, zoomOutBox.y + zoomOutBox.height / 2);
    else await run.page.mouse.click(zoomOutBox.x + zoomOutBox.width / 2, zoomOutBox.y + zoomOutBox.height / 2);
    await waitForSphereGeometrySettled(run.page);
    restoredScale = await run.page.locator('#digital-sphere').boundingBox();
    const projectedZoomOut = await independentProjectedGlobeDiameter(run.page);
    const declaredZoomOut = Number(await stage.getAttribute('data-globe-diameter'));
    assert(restoredScale && restoredScale.width < previousZoomOutWidth * 0.96, `layer journey: zoom-out did not shrink visible sphere (${previousZoomOutWidth} -> ${restoredScale?.width})`);
    assert(Math.abs(declaredZoomOut - projectedZoomOut) <= 1, `layer journey: zoom-out lost MapLibre horizon coupling (${declaredZoomOut} vs ${projectedZoomOut})`);
    assert(Math.abs(restoredScale.width - declaredZoomOut * 1.32) <= 2, `layer journey: zoom-out lost outer-shell ratio (${restoredScale.width} vs ${declaredZoomOut})`);
    previousZoomOutWidth = restoredScale.width;
  }
  assert((await stage.getAttribute('data-view-phase')) === 'overview', 'layer journey: scaled sphere stole the zoom-out control and opened layers');
  assert(restoredScale, 'layer journey: sphere disappeared after zoom-out');
  await waitForSphereOpacitySettled(run.page);
  const opacityRestored = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioRestored = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacityRestored - sphereOpacityForGlobeRatio(ratioRestored)) <= 0.01, `layer journey: zoom-out opacity does not follow visible globe ratio (${opacityRestored} at ${ratioRestored})`);

  const mapBox = await run.page.locator('#map').boundingBox();
  assert(mapBox, 'layer journey: map has no geometry');
  const zoomNumberBeforeRotation = Number(await stage.getAttribute('data-map-zoom'));
  const projectedBeforeRotation = await independentProjectedGlobeDiameter(run.page);
  await run.page.mouse.move(mapBox.x + mapBox.width * 0.5, mapBox.y + mapBox.height * 0.5);
  await run.page.mouse.down();
  await run.page.mouse.move(mapBox.x + mapBox.width * 0.8, mapBox.y + mapBox.height * 0.35, { steps: 15 });
  await run.page.mouse.up();
  await run.page.waitForFunction(() => window.__commonworldTestMap?.isMoving() === false);
  await run.page.waitForTimeout(240);
  const afterRotation = await run.page.locator('#digital-sphere').boundingBox();
  const zoomNumberAfterRotation = Number(await stage.getAttribute('data-map-zoom'));
  const projectedAfterRotation = await independentProjectedGlobeDiameter(run.page);
  assert(afterRotation, 'layer journey: sphere disappeared after rotation');
  assert(Math.abs(projectedAfterRotation - projectedBeforeRotation) <= 1, `layer journey: MapLibre horizon changed unexpectedly during rotation (${projectedBeforeRotation} -> ${projectedAfterRotation})`);
  assert(Math.abs(afterRotation.width - restoredScale.width) <= 2, `layer journey: sphere followed internal zoom normalization instead of visible globe (${restoredScale.width} -> ${afterRotation.width}; MapLibre zoom ${zoomNumberBeforeRotation} -> ${zoomNumberAfterRotation})`);
  await waitForSphereOpacitySettled(run.page);
  const opacityAfterRotation = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  assert(opacityAfterRotation === opacityRestored, `layer journey: sphere opacity followed internal zoom normalization during rotation (${opacityRestored} -> ${opacityAfterRotation})`);


  const sphereBox = await run.page.locator('#digital-sphere').boundingBox();
  assert(sphereBox, 'layer journey: clickable sphere geometry missing');
  const globeDiameter = Number(await run.page.locator('.globe-stage').getAttribute('data-globe-diameter'));
  const innermostLayerDiameter = sphereBox.width * (276 / 320);
  assert(innermostLayerDiameter > globeDiameter, `layer journey: digital shell intersects globe (${innermostLayerDiameter} <= ${globeDiameter})`);
  const edgeX = sphereBox.x + sphereBox.width * 0.85134;
  const edgeY = sphereBox.y + sphereBox.height * 0.14866;
  if (!touch) {
    const edgeControl = run.page.locator('#sphere-edge-control');
    await run.page.keyboard.press('Tab');
    await edgeControl.focus();
    const keyboardFocusAppearance = await run.page.evaluate(() => {
      const control = document.querySelector('#sphere-edge-control');
      const indicatorStyle = getComputedStyle(document.querySelector('.sphere-edge-focus'));
      return {
        focusVisible: control.matches(':focus-visible'),
        indicatorDisplay: indicatorStyle.display,
        stroke: indicatorStyle.stroke,
        strokeWidth: Number.parseFloat(indicatorStyle.strokeWidth),
        strokeDasharray: indicatorStyle.strokeDasharray,
      };
    });
    assert(keyboardFocusAppearance.focusVisible && keyboardFocusAppearance.indicatorDisplay !== 'none', 'edge control: keyboard focus indicator is not visible on the displayed sphere ' + JSON.stringify(keyboardFocusAppearance));
    assert(keyboardFocusAppearance.stroke !== 'rgba(0, 0, 0, 0)' && keyboardFocusAppearance.strokeWidth <= 2.1 && keyboardFocusAppearance.strokeDasharray !== 'none', 'edge control: keyboard focus indicator is missing or too dominant ' + JSON.stringify(keyboardFocusAppearance));
  }
  const overviewUrlCamera = Object.fromEntries(
    ['lng', 'lat', 'z', 'b', 'p'].map((key) => [key, new URL(run.page.url()).searchParams.get(key)]),
  );
  assert(['lng', 'lat', 'z'].every((key) => overviewUrlCamera[key] !== null), 'layer journey: overview URL lacks required camera parameters ' + JSON.stringify(overviewUrlCamera));
  await run.page.evaluate(() => {
    const stageNode = document.querySelector('.globe-stage');
    const panelNode = document.querySelector('#layer-panel');
    const sphereNode = document.querySelector('#digital-sphere');
    window.__commonworldCameraCommands = [];
    window.__commonworldPhaseLog = [];
    window.__commonworldPhaseObserver?.disconnect?.();
    const snapshot = (reason) => ({
      reason,
      phase: stageNode.dataset.viewPhase,
      source: stageNode.dataset.globeGeometrySource,
      moving: window.__commonworldTestMap?.isMoving() ?? null,
      mapMovingAttribute: stageNode.dataset.mapMoving === 'true',
      sphereOpacity: Number(getComputedStyle(sphereNode).opacity),
      panelVisible: panelNode?.hasAttribute('data-visible') ?? false,
      panelHidden: panelNode?.hidden ?? null,
      ringCount: document.querySelectorAll('.sphere-ring-plane').length,
      ringsPaused: [...document.querySelectorAll('.sphere-ring-plane')].every((ring) => getComputedStyle(ring).animationPlayState === 'paused'),
      commandCount: window.__commonworldCameraCommands?.length ?? 0,
      geometryEvaluations: Number(stageNode.dataset.sphereGeometryEvaluations ?? 0),
      diagnosticPublishes: Number(stageNode.dataset.sphereGeometryDiagnosticPublishes ?? 0),
      at: performance.now(),
    });
    window.__commonworldPhaseLog.push(snapshot('initial'));
    window.__commonworldPhaseObserver = new MutationObserver((mutations) => {
      window.__commonworldPhaseLog.push(snapshot(mutations.map((mutation) => `${mutation.target.id || mutation.target.className}:${mutation.attributeName}`).join('|')));
    });
    window.__commonworldPhaseObserver.observe(stageNode, {
      attributes: true,
      attributeFilter: ['data-view-phase', 'data-globe-geometry-source', 'data-layer-panel-visible-at', 'data-last-camera-command', 'data-last-camera-duration', 'data-map-moving'],
    });
    window.__commonworldPhaseObserver.observe(panelNode, {
      attributes: true,
      attributeFilter: ['data-visible', 'hidden', 'data-closing', 'inert'],
    });
  });
  if (touch) await run.page.touchscreen.tap(edgeX, edgeY);
  else await run.page.mouse.click(edgeX, edgeY);
  if (touch) {
    const touchFocusAppearance = await run.page.evaluate(() => {
      const control = document.querySelector('#sphere-edge-control');
      const controlStyle = getComputedStyle(control);
      const indicatorStyle = getComputedStyle(document.querySelector('.sphere-edge-focus'));
      return {
        active: document.activeElement === control,
        focusVisible: control.matches(':focus-visible'),
        controlStroke: controlStyle.stroke,
        controlStrokeWidth: controlStyle.strokeWidth,
        indicatorDisplay: indicatorStyle.display,
      };
    });
    assert(!touchFocusAppearance.focusVisible, 'edge control: touch focus modality was misclassified ' + JSON.stringify(touchFocusAppearance));
    assert(touchFocusAppearance.controlStroke === 'rgba(0, 0, 0, 0)' && touchFocusAppearance.indicatorDisplay === 'none', 'edge control: touch activation exposed a visible selection ring ' + JSON.stringify(touchFocusAppearance));
  }
  await run.page.waitForFunction(() => window.__commonworldPhaseLog?.some((entry) => entry.phase === 'entering-layers'), null, { timeout: 2000 });
  const enteringLayerState = await run.page.evaluate(() => window.__commonworldPhaseLog.find((entry) => entry.phase === 'entering-layers'));
  assert(enteringLayerState, 'layer journey: animated entry phase missing');
  assert(enteringLayerState.source === 'maplibre-projected-horizon', 'layer journey: entering flight abandoned the MapLibre horizon geometry ' + JSON.stringify(enteringLayerState));
  assert(enteringLayerState.panelHidden === true && enteringLayerState.panelVisible === false, 'layer journey: description panel obscures the camera flight ' + JSON.stringify(enteringLayerState));
  await run.page.waitForFunction(() => window.__commonworldPhaseLog?.some((entry) => (
    entry.mapMovingAttribute && entry.ringCount > 0 && entry.ringsPaused
  )));
  const movingRingState = await run.page.evaluate(() => window.__commonworldPhaseLog.find((entry) => (
    entry.mapMovingAttribute && entry.ringCount > 0 && entry.ringsPaused
  )));
  assert(movingRingState.mapMovingAttribute && movingRingState.ringsPaused, 'layer journey: decorative ring pause was not recorded during camera movement ' + JSON.stringify(movingRingState));
  assert(movingRingState.phase === 'entering-layers' && movingRingState.panelHidden === true, 'layer journey: movement-bound ring pause violated the stable-panel contract ' + JSON.stringify(movingRingState));
  const flightComposition = await run.page.evaluate(() => {
    const map = document.querySelector('#map');
    const style = getComputedStyle(map);
    const stage = document.querySelector('.globe-stage');
    return {
      transform: style.transform,
      transitionProperties: style.transitionProperty.split(',').map((value) => value.trim()),
      duration: Number(stage.dataset.lastCameraDuration),
      command: stage.dataset.lastCameraCommand,
      phase: stage.dataset.viewPhase,
    };
  });
  assert(['none', 'matrix(1, 0, 0, 1, 0, 0)'].includes(flightComposition.transform), 'layer journey: CSS still applies a competing map zoom ' + JSON.stringify(flightComposition));
  assert(!flightComposition.transitionProperties.includes('transform'), 'layer journey: map transform remains part of the camera flight ' + JSON.stringify(flightComposition));
  assert(flightComposition.command === 'easeTo' && flightComposition.duration === DIGITAL_LAYER_TRANSITION_MS, 'layer journey: MapLibre is not the single camera authority for the shortened flight ' + JSON.stringify(flightComposition));
  const openingCommands = await run.page.evaluate(() => window.__commonworldCameraCommands ?? []);
  assert(openingCommands.length === 1 && openingCommands[0].command === 'easeTo', `layer journey: opening issued multiple camera commands (${JSON.stringify(openingCommands)})`);
  const enteringSphere = await run.page.locator('#digital-sphere').boundingBox();
  assert(enteringSphere, 'layer journey: transforming sphere is not visible during camera flight');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  await run.page.evaluate(() => new Promise((resolve) => queueMicrotask(resolve)));
  const phaseLog = await run.page.evaluate(() => window.__commonworldPhaseLog);
  assert(phaseLog.every((entry) => entry.phase !== 'entering-layers' || entry.source === 'maplibre-projected-horizon'), `layer journey: side layout appeared while the camera was still flying (${JSON.stringify(phaseLog)})`);
  assert(phaseLog.some((entry) => entry.phase === 'settling-layers' && entry.source === 'maplibre-projected-horizon' && entry.moving === false), `layer journey: post-move settling phase is missing or still moving (${JSON.stringify(phaseLog)})`);
  const firstSideEntry = phaseLog.find((entry) => entry.source === 'side-view-layout');
  assert(firstSideEntry && firstSideEntry.phase === 'layers' && firstSideEntry.moving === false && firstSideEntry.sphereOpacity <= 0.1, `layer journey: side layout was not entered after moveend with invisible sphere (${JSON.stringify(firstSideEntry)})`);
  const sideIndex = phaseLog.indexOf(firstSideEntry);
  const firstPanelEntry = phaseLog.find((entry) => entry.panelVisible);
  assert(firstPanelEntry && phaseLog.indexOf(firstPanelEntry) > sideIndex && firstPanelEntry.phase === 'layers' && firstPanelEntry.source === 'side-view-layout', `layer journey: panel became visible before the side layout was stable (${JSON.stringify({ firstPanelEntry, phaseLog })})`);
  const flightGeometryEvaluationDelta = firstSideEntry.geometryEvaluations - phaseLog[0].geometryEvaluations;
  const maxFlightGeometryEvaluations = Math.ceil(DIGITAL_LAYER_TRANSITION_MS / MAP_GEOMETRY_SAMPLE_INTERVAL_MS) + 3;
  assert(flightGeometryEvaluationDelta > 0 && flightGeometryEvaluationDelta <= maxFlightGeometryEvaluations, 'layer journey: sphere projection exceeded the sampled camera-flight budget ' + JSON.stringify({ flightGeometryEvaluationDelta, maxFlightGeometryEvaluations, phaseLog }));
  const firstMovingEntry = phaseLog.find((entry) => entry.mapMovingAttribute);
  const settlingEntry = phaseLog.find((entry) => entry.phase === 'settling-layers');
  const movingGeometryEvaluationDelta = settlingEntry.geometryEvaluations - firstMovingEntry.geometryEvaluations;
  const movingDiagnosticPublishDelta = settlingEntry.diagnosticPublishes - firstMovingEntry.diagnosticPublishes;
  const maxMovingDiagnosticPublishes = Math.ceil(movingGeometryEvaluationDelta / MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL) + 2;
  assert(movingDiagnosticPublishDelta > 0 && movingDiagnosticPublishDelta <= maxMovingDiagnosticPublishes, 'layer journey: diagnostic publishing exceeded its movement-window budget ' + JSON.stringify({ movingDiagnosticPublishDelta, maxMovingDiagnosticPublishes, phaseLog }));
  if (movingGeometryEvaluationDelta > 1) {
    assert(movingDiagnosticPublishDelta < movingGeometryEvaluationDelta, 'layer journey: diagnostics still publish on every moving geometry evaluation ' + JSON.stringify({ movingDiagnosticPublishDelta, movingGeometryEvaluationDelta, phaseLog }));
  }
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout', 'layer journey: settled layers view is missing the side layout geometry');
  if (touch) {
    const closeFocusAppearance = await run.page.locator('#layer-close').evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        active: document.activeElement === node,
        modality: document.documentElement.dataset.inputModality,
        outlineStyle: style.outlineStyle,
        outlineWidth: Number.parseFloat(style.outlineWidth),
      };
    });
    assert(closeFocusAppearance.active && closeFocusAppearance.modality === 'pointer', 'layer journey: touch-opened close control lost pointer modality ' + JSON.stringify(closeFocusAppearance));
    assert(closeFocusAppearance.outlineStyle === 'none' || closeFocusAppearance.outlineWidth === 0, 'layer journey: touch-opened close control exposed a focus ring ' + JSON.stringify(closeFocusAppearance));
  }
  await run.page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#digital-sphere')).opacity) <= 0.1);
  assert(await run.page.locator('#layer-panel').isVisible(), 'layer journey: description panel did not appear after the stable end state');
  assert(await run.page.locator('#layer-panel').getAttribute('inert') === null, 'layer journey: revealed description panel remains inert');
  const panelVisibleAt = Number(await run.page.locator('.globe-stage').evaluate((node) => node.dataset.layerPanelVisibleAt));
  assert(Number.isFinite(panelVisibleAt), 'layer journey: panel reveal is not bound to the settled end state');
  await run.page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#map')).opacity) <= 0.02);
  assert(await run.page.locator('#map').getAttribute('inert') !== null, 'layer journey: invisible globe remains keyboard reachable');
  assert((await run.page.locator('#map').getAttribute('aria-hidden')) === 'true', 'layer journey: invisible globe remains in the accessibility tree');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '-1', 'layer journey: old sphere trigger remains reachable inside side view');
  const panelBox = await run.page.locator('#layer-panel').boundingBox();
  const viewport = run.page.viewportSize();
  assert(panelBox && viewport && panelBox.width >= viewport.width - 1, `layer journey: layer surface is not full width (${JSON.stringify(panelBox)})`);
  const ribbonView = await run.page.evaluate(() => {
    const sphere = document.querySelector('#digital-sphere').getBoundingClientRect();
    const lanes = [...document.querySelectorAll('.digital-lane[data-layer-id]')].map((lane) => {
      const scroller = lane.querySelector('.digital-lane-scroll');
      const primary = [...lane.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]')];
      return {
        layer: lane.dataset.layerId,
        displayed: getComputedStyle(lane).display !== 'none',
        clientWidth: scroller.clientWidth,
        scrollWidth: scroller.scrollWidth,
        overflowX: getComputedStyle(scroller).overflowX,
        touchAction: getComputedStyle(scroller).touchAction,
        primary: primary.map((item) => ({
          id: item.dataset.commonprojectId,
          name: item.querySelector('.digital-ribbon-name')?.textContent ?? '',
          binary: item.querySelector('.digital-ribbon-binary')?.textContent ?? '',
          height: item.getBoundingClientRect().height,
          hidden: item.hidden,
        })),
      };
    });
    return {
      viewport: { width: innerWidth, height: innerHeight },
      sphere: { left: sphere.left, right: sphere.right, top: sphere.top, bottom: sphere.bottom, width: sphere.width, height: sphere.height },
      sphereOpacity: Number(getComputedStyle(document.querySelector('#digital-sphere')).opacity),
      ringCount: document.querySelectorAll('.sphere-ring-text').length,
      ringNameCount: document.querySelectorAll('.sphere-ring-name').length,
      ringBinaryCount: document.querySelectorAll('.sphere-ring-binary').length,
      lanes,
      filterChildren: document.querySelector('#layer-buttons').childElementCount,
    };
  });
  assert(ribbonView.sphere.width > ribbonView.viewport.width * 2, `layer journey: camera did not pass through an enlarged text sphere (${JSON.stringify(ribbonView.sphere)})`);
  assert(ribbonView.sphere.left < -ribbonView.viewport.width * 0.7, `layer journey: enlarged sphere did not move into a side approach (${JSON.stringify(ribbonView.sphere)})`);
  assert(ribbonView.sphereOpacity <= 0.1, `layer journey: enlarged sphere obscures the lane surface (${ribbonView.sphereOpacity})`);
  assert(ribbonView.ringCount === expectedDigitalProjection.fields.length && ribbonView.ringNameCount > 0 && ribbonView.ringBinaryCount > 0, `layer journey: text-ring identity was lost during the flight (${JSON.stringify(ribbonView)})`);
  assert(ribbonView.lanes.length === expectedDigitalProjection.fields.length && ribbonView.lanes.every(({ displayed }) => displayed), `layer journey: multi-lane overview does not show all layers (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ scrollWidth, clientWidth }) => scrollWidth > clientWidth + 20), `layer journey: at least one lane is not horizontally scrollable (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ overflowX }) => ['auto', 'scroll'].includes(overflowX)), `layer journey: native horizontal overflow is disabled (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ touchAction }) => touchAction.includes('pan-x')), `layer journey: touch panning is not explicitly horizontal (${JSON.stringify(ribbonView.lanes)})`);
  for (const lane of ribbonView.lanes) {
    const expectedLayer = expectedDigitalProjection.fields.find(({ id }) => id === lane.layer);
    assert(expectedLayer, `layer journey: rendered unknown lane ${lane.layer}`);
    assertSameIds(lane.primary.map(({ id }) => id), expectedLayer.previewIds, `layer journey: ${lane.layer} preview identity set`);
  }
  const primarySegments = ribbonView.lanes.flatMap(({ primary }) => primary);
  const expectedPreviewIds = expectedDigitalProjection.fields.flatMap(({ previewIds }) => previewIds);
  assert(primarySegments.length === expectedPreviewIds.length, `layer journey: primary preview identities were duplicated or lost (${primarySegments.length})`);
  assertSameIds(primarySegments.map(({ id }) => id), expectedPreviewIds, 'layer journey: primary digital preview identity set');
  assert(primarySegments.every(({ name, binary, height }) => name && /^(?:[01]{8})(?: [01]{8})*$/.test(binary) && height >= 44), `layer journey: name/binary pairs or touch heights are invalid (${JSON.stringify(primarySegments)})`);
  assert(ribbonView.filterChildren === expectedDigitalProjection.fields.length, `layer journey: search surface does not contain all layer filters (${ribbonView.filterChildren})`);

  const firstScroller = run.page.locator('.digital-lane-scroll').first();
  const scrollBefore = await firstScroller.evaluate((node) => node.scrollLeft);
  await firstScroller.evaluate((node) => { node.scrollTo({ left: Math.min(node.scrollWidth - node.clientWidth, Math.max(120, node.clientWidth * 0.55)), behavior: 'instant' }); });
  await run.page.waitForTimeout(180);
  const scrollAfter = await firstScroller.evaluate((node) => node.scrollLeft);
  assert(scrollAfter > scrollBefore + 20, `layer journey: multi-lane horizontal scroll did not move (${scrollBefore} -> ${scrollAfter})`);

  const knowledgeFocus = run.page.locator('.digital-lane-focus[data-digital-path="sphere/knowledge_learning_culture"]');
  await knowledgeFocus.click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture');
  assert(new URL(run.page.url()).searchParams.get('digital_path') === 'sphere/knowledge_learning_culture', 'layer journey: field path was not written to the canonical URL');
  let fieldLanes = await run.page.evaluate(() => [...document.querySelectorAll('.digital-lane[data-layer-id]')].map((lane) => ({
    id: lane.dataset.layerId,
    path: lane.dataset.digitalPath,
    count: Number(lane.querySelector('.digital-lane-focus small')?.textContent?.match(/\d+/)?.[0] ?? 0),
  })));
  assert(JSON.stringify(fieldLanes.map(({ id }) => id)) === JSON.stringify(['open_knowledge_data', 'learning_education', 'media_culture']), `layer journey: field did not reveal direct child bundles (${JSON.stringify(fieldLanes)})`);
  await run.page.goBack();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere');
  assert(new URL(run.page.url()).searchParams.get('digital_path') === null, 'layer journey: Back did not restore the sphere root path');
  await run.page.goForward();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture');
  fieldLanes = await run.page.evaluate(() => [...document.querySelectorAll('.digital-lane[data-layer-id]')].map((lane) => lane.dataset.layerId));
  assert(JSON.stringify(fieldLanes) === JSON.stringify(['open_knowledge_data', 'learning_education', 'media_culture']), 'layer journey: Forward did not restore the field child bundles');

  const openKnowledgeFocus = run.page.locator('.digital-lane-focus[data-digital-path="sphere/knowledge_learning_culture/open_knowledge_data"]');
  await openKnowledgeFocus.click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture/open_knowledge_data');
  const focusedLane = await run.page.evaluate(() => {
    const visible = [...document.querySelectorAll('.digital-lane[data-layer-id]')].filter((lane) => getComputedStyle(lane).display !== 'none');
    const scroller = visible[0]?.querySelector('.digital-lane-scroll');
    return {
      visibleLayers: visible.map((lane) => lane.dataset.layerId),
      focusedPath: document.querySelector('.globe-stage')?.dataset.focusedPath ?? null,
      breadcrumb: [...document.querySelectorAll('#layer-breadcrumb .digital-breadcrumb-item')].map((node) => ({ text: node.textContent.trim(), current: node.getAttribute('aria-current') })),
      clientWidth: scroller?.clientWidth ?? 0,
      scrollWidth: scroller?.scrollWidth ?? 0,
      ids: [...document.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]')].map((node) => node.dataset.commonprojectId),
    };
  });
  assert(JSON.stringify(focusedLane.visibleLayers) === JSON.stringify(['open_knowledge_data']), `layer journey: identity-level focus leaves other lanes visible (${JSON.stringify(focusedLane)})`);
  assert(focusedLane.focusedPath === 'sphere/knowledge_learning_culture/open_knowledge_data', `layer journey: focused path data attribute mismatch (${JSON.stringify(focusedLane)})`);
  assert(focusedLane.breadcrumb.at(-1)?.current === 'page' && focusedLane.breadcrumb.map(({ text }) => text).includes('Wissen, Lernen und Kultur'), `layer journey: breadcrumb did not expose parent context (${JSON.stringify(focusedLane.breadcrumb)})`);
  assertSameIds(focusedLane.ids, expectedDigitalProjection.nodes['sphere/knowledge_learning_culture/open_knowledge_data'].identityIds, 'layer journey: identity-level direct Commons');
  assert(focusedLane.scrollWidth > focusedLane.clientWidth + 20, `layer journey: focused lane is not horizontally scrollable (${JSON.stringify(focusedLane)})`);
  const focusedScroller = run.page.locator('.digital-lane[data-layer-id="open_knowledge_data"] .digital-lane-scroll');
  await focusedScroller.evaluate((node) => { node.scrollTo({ left: Math.min(node.scrollWidth - node.clientWidth, Math.max(160, node.clientWidth * 0.7)), behavior: 'instant' }); });
  await run.page.waitForTimeout(180);
  assert((await focusedScroller.evaluate((node) => node.scrollLeft)) > 20, 'layer journey: single-lane horizontal scroll did not move');

  await run.page.locator('#layer-search-toggle').click();
  assert(await run.page.locator('#layer-discovery').isVisible(), 'layer journey: search/filter magnifier did not open');
  assert((await run.page.locator('#layer-buttons .layer-filter').count()) === 0, 'layer journey: identity-level search panel must not expose unrelated bundle filters');
  await run.page.locator('#layer-search').fill('Wikipedia');
  await run.page.waitForTimeout(220);
  assert((await run.page.locator('#commons-search').inputValue()) === 'Wikipedia', 'layer journey: lane search is not synchronized with global search');
  const searchedVisible = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]:not([hidden])').count();
  assert(searchedVisible === 1, `layer journey: focused search did not reduce to one visible identity (${searchedVisible})`);
  await run.page.locator('#layer-search').fill('');
  await run.page.waitForTimeout(220);
  await run.page.locator('#layer-search-toggle').click();
  assert(await run.page.locator('#layer-discovery').isHidden(), 'layer journey: search/filter panel did not close');

  const directContent = run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]:not([hidden])').first();
  const directTitle = (await directContent.locator('.digital-ribbon-name').textContent()) ?? '';
  const directBox = await directContent.boundingBox();
  assert(directBox && directBox.width >= 44 && directBox.height >= 44, `layer journey: Commons ribbon has an undersized touch target (${JSON.stringify(directBox)})`);
  await directContent.click();
  assert(await run.page.locator('#project-focus').isVisible(), 'layer journey: ribbon content did not open its Commons focus');
  assert((await run.page.locator('#focus-title').textContent()) === directTitle, `layer journey: ribbon opened the wrong Commons identity (${directTitle})`);
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#project-focus').isHidden(), 'layer journey: Escape did not close the topmost Commons focus');
  assert(await run.page.locator('#layer-panel').isVisible(), 'layer journey: Escape closed the layer surface behind the visible Commons focus');
  assert(await directContent.evaluate((node) => document.activeElement === node), 'layer journey: focus did not return to the same ribbon identity');
  await run.page.keyboard.press('Escape');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture');
  assert((await stage.getAttribute('data-focused-path')) === null, 'layer journey: Escape did not leave the identity-level focus path');

  const viewportFit = await run.page.evaluate(() => ({
    viewportWidth: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    controls: [...document.querySelectorAll('#layer-panel button')].filter((node) => node.getClientRects().length).map((node) => {
      const rect = node.getBoundingClientRect();
      return { id: node.id || node.textContent.trim(), width: rect.width, height: rect.height };
    }),
  }));
  assert(viewportFit.documentWidth <= viewportFit.viewportWidth + 1, `layer journey: horizontal overflow (${JSON.stringify(viewportFit)})`);
  if (touch) assert(viewportFit.controls.every(({ width, height }) => width >= 44 && height >= 44), `layer journey: undersized mobile layer control (${JSON.stringify(viewportFit.controls)})`);

  await run.page.evaluate((delayReturnFocus) => {
    window.__commonworldCameraCommands = [];
    window.__commonworldPhaseLog = [];
    if (!delayReturnFocus) return;
    const stage = document.querySelector('.globe-stage');
    const edge = document.querySelector('#sphere-edge-control');
    const observer = new MutationObserver(() => {
      if (stage.dataset.viewPhase !== 'overview') return;
      observer.disconnect();
      edge.setAttribute('inert', '');
      window.setTimeout(() => edge.removeAttribute('inert'), 80);
    });
    observer.observe(stage, { attributes: true, attributeFilter: ['data-view-phase'] });
  }, touch);
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="preparing-overview"]');
  const preparingOverviewUrlCamera = Object.fromEntries(
    ['lng', 'lat', 'z', 'b', 'p'].map((key) => [key, new URL(run.page.url()).searchParams.get(key)]),
  );
  assert(JSON.stringify(preparingOverviewUrlCamera) === JSON.stringify(overviewUrlCamera), 'layer journey: return preparation serialized the side camera instead of preserving the overview camera ' + JSON.stringify({ overviewUrlCamera, preparingOverviewUrlCamera }));
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout', 'layer journey: return preparation left side layout too early');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel did not close before return preparation');
  await run.page.waitForFunction(() => ['leaving-layers', 'overview'].includes(document.querySelector('.globe-stage')?.dataset.viewPhase));
  // The transient phase can complete before Playwright observes it; the phase log below remains the strict proof.
  // The phase log below proves that leaving-layers occurred and carried the invisible geometry switch.
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'maplibre-projected-horizon', 'layer journey: return flight did not mirror back to the MapLibre horizon geometry');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the return camera flight');
  const returnCommands = await run.page.evaluate(() => window.__commonworldCameraCommands ?? []);
  assert(returnCommands.length === 1 && returnCommands[0].command === 'easeTo', `layer journey: closing issued multiple camera commands (${JSON.stringify(returnCommands)})`);
  const returnPhaseLog = await run.page.evaluate(() => window.__commonworldPhaseLog);
  const firstReturnOverviewGeometry = returnPhaseLog.find((entry) => entry.source === 'maplibre-projected-horizon');
  assert(firstReturnOverviewGeometry && firstReturnOverviewGeometry.phase === 'leaving-layers' && firstReturnOverviewGeometry.sphereOpacity <= 0.1, `layer journey: return geometry changed while the sphere was visible (${JSON.stringify({ firstReturnOverviewGeometry, returnPhaseLog })})`);
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  await run.page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#map')).opacity) >= 0.98);
  assert(await run.page.locator('#map').getAttribute('inert') === null, 'layer journey: returned globe remains inert');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '0', 'layer journey: sphere trigger was not restored');
  await run.page.waitForFunction(() => document.activeElement?.id === 'sphere-edge-control');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'sphere-edge-control', 'layer journey: focus did not return to the clicked sphere edge');
  assert(run.consoleErrors.length === 0, `layer journey: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `layer journey: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: activeScenarioId, verdict: 'PASS' });
  await run.context.close();
}


async function dualPresenceAxesScenario() {
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: 'dual-presence-axes' }) + '\n');
  const run = await newPage({ viewportOverride: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(({ featureCount, identityCount }) => {
    const stage = document.querySelector('.globe-stage');
    const map = window.__commonworldTestMap;
    return Number(stage?.dataset.publicMapFeatures) === featureCount
      && Number(stage?.dataset.publicMapProjectIds) === identityCount
      && Boolean(map?.getSource('commonworld-public-representations'));
  }, {
    featureCount: expectedDigitalProjection.publicFeatureCount,
    identityCount: expectedDigitalProjection.publicIdentityCount,
  });

  await run.page.waitForFunction(() => {
    const stage = document.querySelector('.globe-stage');
    const map = window.__commonworldTestMap;
    return stage?.dataset.countryMapState === 'ready'
      && Number(stage?.dataset.countryMapFeatures ?? 0) > 0
      && Boolean(map?.getSource('commonworld-country-compositions'));
  });

  const initial = await run.page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    const map = window.__commonworldTestMap;
    const style = map.getStyle();
    return {
      semanticLevel: stage.dataset.semanticLevel,
      semanticText: document.querySelector('#semantic-summary')?.textContent ?? '',
      globeResultsText: document.querySelector('#globe-results')?.textContent ?? '',
      legendSummary: document.querySelector('.map-legend > summary')?.textContent?.trim() ?? '',
      legendAriaHidden: document.querySelector('.map-legend')?.getAttribute('aria-hidden'),
      featureIds: stage.dataset.publicMapFeatureIds?.split(',').filter(Boolean) ?? [],
      locationIds: stage.dataset.publicMapLocationIds?.split(',').filter(Boolean) ?? [],
      mapUpdateCount: Number(stage.dataset.publicMapUpdates ?? -1),
      aggregateImpressions: Number(stage.dataset.publicMapAggregateImpressions ?? -1),
      privacyNotices: Number(stage.dataset.publicMapPrivacyNotices ?? -1),
      geographicSemanticLevels: (stage.dataset.publicMapSemanticLevels ?? '').split(',').filter(Boolean),
      interactiveLayerIds: (stage.dataset.publicMapInteractiveLayers ?? '').split(',').filter(Boolean),
      declaredLayerOrder: (stage.dataset.publicMapLayerOrder ?? '').split(',').filter(Boolean),
      beforeLayerId: stage.dataset.publicMapBeforeLayer ?? null,
      legendSwatchText: [...document.querySelectorAll('#commons-type-legend .legend-color')].map((node) => node.textContent.trim()),
      countryMapState: stage.dataset.countryMapState ?? '',
      countryMapFeatures: Number(stage.dataset.countryMapFeatures ?? -1),
      countrySourceType: style.sources?.['commonworld-country-compositions']?.type ?? null,
      legendLabels: [...document.querySelectorAll('#commons-type-legend .legend-item')].map((node) => node.textContent.trim()),
      sourceType: style.sources?.['commonworld-public-representations']?.type ?? null,
      layers: style.layers
        .filter(({ id }) => id.startsWith('commonworld-'))
        .map(({ id, type, minzoom, maxzoom }) => ({
          id, type, minzoom, maxzoom,
          circleRadius: type === 'circle' ? map.getPaintProperty(id, 'circle-radius') : null,
          fillOpacity: type === 'fill' ? map.getPaintProperty(id, 'fill-opacity') : null,
        })),
      ringNames: [...document.querySelectorAll('.sphere-ring-name')].map((node) => node.textContent.trim()),
    };
  });
  assert(initial.semanticLevel === 'planet', 'dual presence: initial semantic level is not planet');
  assert(initial.semanticText.includes('Katalogabdeckung nicht bewertet'), 'dual presence: semantic coverage boundary is missing: ' + JSON.stringify(initial));
  assert(initial.globeResultsText.includes(`${expectedDigitalProjection.publicIdentityCount} räumlich öffentlich belegte Commons`), 'dual presence: spatial text equivalent is missing: ' + JSON.stringify(initial));
  assert(initial.globeResultsText.includes('keine Dichteaussage'), 'dual presence: spatial text equivalent implies assessed density: ' + JSON.stringify(initial));
  assert(initial.legendSummary === 'Kartenlegende' && initial.legendAriaHidden === null, 'dual presence: accessible map legend is missing or hidden: ' + JSON.stringify(initial));
  assert(initial.aggregateImpressions === expectedDigitalProjection.aggregateImpressionCount, 'dual presence: aggregate impression diagnostics differ from the prepared projection: ' + JSON.stringify(initial));
  assert(initial.privacyNotices === expectedDigitalProjection.privacyNoticeCount, 'dual presence: privacy notice diagnostics differ from the prepared projection: ' + JSON.stringify(initial));
  assertSameIds(initial.geographicSemanticLevels, expectedDigitalProjection.geographicSemanticLevels, 'dual presence: geographic semantic levels');
  assert(initial.legendSwatchText.length === 11 && initial.legendSwatchText.every((value) => value === ''), 'dual presence: far-map legend swatches must not render abbreviations: ' + JSON.stringify(initial));
  assert(initial.legendLabels.length === 11 && initial.legendLabels.some((label) => label.includes('Wissen und Daten')) && initial.legendLabels.some((label) => label.includes('Gemeinschaftsnetz')), 'dual presence: legend labels do not match the Commons type vocabulary: ' + JSON.stringify(initial));
  const reviewedFeatureIds = [
    'cltb-le-nid:cltb-le-nid-entrance',
    'cltb-le-nid:cltb-le-nid-building',
    'freifunk-hamburg:freifunk-hamburg-community-area',
  ];
  assert(initial.featureIds.length === expectedDigitalProjection.publicFeatureCount, 'dual presence: public map feature count differs from the catalog: ' + JSON.stringify(initial));
  assert(reviewedFeatureIds.every((identifier) => initial.featureIds.includes(identifier)), 'dual presence: reviewed public map features are missing: ' + JSON.stringify(initial));
  assert(!initial.locationIds.includes('freifunk-hamburg-private-routers'), 'dual presence: hidden router location leaked into map diagnostics');
  assert(initial.sourceType === 'geojson', 'dual presence: MapLibre source is not a GeoJSON source: ' + JSON.stringify(initial));
  assert(JSON.stringify(initial.layers.map(({ id }) => id)) === JSON.stringify(initial.declaredLayerOrder), 'dual presence: public MapLibre layer order differs from the declared deterministic order: ' + JSON.stringify(initial));
  assert(initial.beforeLayerId === 'road_one_way_arrow', 'dual presence: public layers are not anchored below the base-map labels: ' + JSON.stringify(initial));
  assert(initial.layers.some(({ id, type, minzoom }) => id === 'commonworld-public-extents' && type === 'fill' && minzoom === 3.4), 'dual presence: public extent layer missing');
  assert(initial.layers.some(({ id, type, minzoom, maxzoom }) => id === 'commonworld-approximate-zones' && type === 'fill' && minzoom === 3.4 && maxzoom === undefined), 'dual presence: approximate uncertainty zone must remain visible through local zoom');
  const exactAnchorLayer = initial.layers.find(({ id }) => id === 'commonworld-exact-anchors');
  assert(exactAnchorLayer?.type === 'circle' && exactAnchorLayer.minzoom === 5, 'dual presence: exact anchor layer missing');
  assert(JSON.stringify(exactAnchorLayer.circleRadius).includes('[5,7]') || JSON.stringify(exactAnchorLayer.circleRadius).includes('5,7'), 'dual presence: exact anchors are not visibly enlarged for mobile: ' + JSON.stringify(exactAnchorLayer));
  assert(initial.layers.some(({ id, type, minzoom }) => id === 'commonworld-exact-anchor-hit-targets' && type === 'circle' && minzoom === 5), 'dual presence: exact anchor touch target layer missing');
  assert(initial.countryMapState === 'ready' && initial.countryMapFeatures > 0 && initial.countrySourceType === 'geojson', 'dual presence: country composition source is not ready: ' + JSON.stringify(initial));
  const countryBaseLayer = initial.layers.find(({ id }) => id === 'commonworld-country-compositions-base');
  assert(countryBaseLayer?.type === 'fill' && countryBaseLayer.minzoom === 0 && countryBaseLayer.maxzoom === 5.5, 'dual presence: mobile-safe country base tint layer missing');
  assert(JSON.stringify(countryBaseLayer.fillOpacity).includes('0.78'), 'dual presence: country base tint is too weak or missing at globe overview: ' + JSON.stringify(countryBaseLayer));
  assert(initial.layers.some(({ id, type, minzoom, maxzoom }) => id === 'commonworld-country-compositions' && type === 'fill' && minzoom === 0 && maxzoom === 5.5), 'dual presence: land-first country composition fill layer missing');
  assert(initial.layers.some(({ id, type }) => id === 'commonworld-country-compositions-outline' && type === 'line'), 'dual presence: country composition outline layer missing');
  for (const level of ['macroregion', 'region']) {
    assert(!initial.layers.some((layer) => layer.id === 'commonworld-' + level + '-impressions'), 'dual presence: synthetic aggregate point layer must not be rendered for ' + level + ': ' + JSON.stringify(initial.layers));
    assert(!initial.layers.some((layer) => layer.id === 'commonworld-' + level + '-privacy-withheld'), 'dual presence: aggregate privacy grid center must not be rendered as a location for ' + level);
  }
  assert(!initial.layers.some(({ id, type }) => type === 'symbol' && (id.includes('-semantics') || id.includes('-impression-counts') || id.includes('type-codes'))), 'dual presence: geographic map still renders code/count symbol layers: ' + JSON.stringify(initial.layers));
  assertSameIds(initial.interactiveLayerIds, [
    'commonworld-public-extents',
    'commonworld-approximate-zones',
    'commonworld-exact-anchor-hit-targets',
    'commonworld-exact-anchors',
  ], 'dual presence: only truthful published local geometry and its touch target may be interactive');
  assert(initial.ringNames.includes('Freifunk Hamburg'), 'dual presence: dual presence identity missing from digital sphere');
  assert(!initial.ringNames.includes('Le Nid'), 'dual presence: geographic-only identity leaked into digital sphere');

  await run.page.locator('#sphere-edge-control').focus();
  await run.page.keyboard.press('Enter');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks"]').click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks');
  await run.page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks/community_networks"]').click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks/community_networks');
  const digitalPrimaryIds = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
  const communityNetworkIds = expectedDigitalProjection.nodes['sphere/communication_networks/community_networks'].identityIds;
  assert(digitalPrimaryIds.length === communityNetworkIds.length, 'dual presence: digital lane identity count mismatch: ' + digitalPrimaryIds.length);
  assertSameIds(digitalPrimaryIds, communityNetworkIds, 'dual presence: community-network digital identity set');
  assert(digitalPrimaryIds.includes('freifunk-hamburg'), 'dual presence: dual presence identity missing from digital lanes');
  assert(!digitalPrimaryIds.includes('cltb-le-nid'), 'dual presence: geographic-only identity leaked into digital lanes');
  await run.page.locator('#layer-breadcrumb .digital-breadcrumb-item[data-digital-path="sphere"]').click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere');
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');

  await run.page.locator('#commons-search').fill('Le Nid');
  await run.page.waitForFunction((count) => Number(document.querySelector('.globe-stage')?.dataset.publicMapFeatures) === count, expectedDigitalProjection.publicFeatureCountsByIdentity['cltb-le-nid']);
  assert((await run.page.locator('.globe-stage').getAttribute('data-public-map-project-ids')) === '1', 'dual presence: search did not reduce map identities');
  assert((await run.page.locator('#globe-results').textContent())?.includes('1 Commons'), 'dual presence: shared search count mismatch');
  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction((count) => Number(document.querySelector('.globe-stage')?.dataset.publicMapFeatures) === count, expectedDigitalProjection.publicFeatureCount);
  await run.page.locator('#discovery-close').click();
  assert(await run.page.locator('#discovery-panel').isHidden(), 'dual presence: discovery panel blocked map activation');

  const activateMapIdentity = async ({ coordinates, zoom, layerId, expectedLevel }) => {
    await run.page.evaluate(({ coordinates: target, zoom: targetZoom }) => {
      window.__commonworldTestMap.jumpTo({ center: target, zoom: targetZoom, bearing: 0, pitch: 0 });
    }, { coordinates, zoom });
    await run.page.waitForFunction((level) => document.querySelector('.globe-stage')?.dataset.semanticLevel === level, expectedLevel);
    await run.page.waitForFunction(({ target, layer }) => {
      const map = window.__commonworldTestMap;
      if (!map || map.isMoving() || !map.getLayer(layer)) return false;
      return map.queryRenderedFeatures(map.project(target), { layers: [layer] }).length > 0;
    }, { target: coordinates, layer: layerId });
    const point = await run.page.evaluate((target) => {
      const map = window.__commonworldTestMap;
      const projected = map.project(target);
      const rect = map.getCanvas().getBoundingClientRect();
      return { x: rect.left + projected.x, y: rect.top + projected.y };
    }, coordinates);
    await run.page.mouse.click(point.x, point.y);
    await run.page.waitForSelector('#project-focus:not([hidden])');
  };

  await run.page.evaluate(() => {
    window.__commonworldTestMap.jumpTo({ center: [10.2, 51.1], zoom: 1.2, bearing: 0, pitch: 0 });
  });
  await run.page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    if (!map || map.isMoving() || !map.getLayer('commonworld-country-compositions-base')) return false;
    return map.queryRenderedFeatures(map.project([10.2, 51.1]), { layers: ['commonworld-country-compositions-base'] }).length > 0;
  });

  await run.page.evaluate(() => {
    window.__commonworldTestMap.jumpTo({ center: [10.2, 51.1], zoom: 4.6, bearing: 0, pitch: 0 });
  });
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.semanticLevel === 'region');
  await run.page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    if (!map || map.isMoving() || !map.getLayer('commonworld-country-compositions')) return false;
    return map.queryRenderedFeatures(map.project([10.2, 51.1]), { layers: ['commonworld-country-compositions'] }).length > 0;
  });

  const updatesBeforeSelection = Number(await run.page.locator('.globe-stage').getAttribute('data-public-map-updates'));
  await activateMapIdentity({
    coordinates: [9.944545738399, 53.558314876911],
    zoom: 4.6,
    layerId: 'commonworld-approximate-zones',
    expectedLevel: 'region',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'dual presence: approximate map click selected the wrong identity');
  const updatesAfterSelection = Number(await run.page.locator('.globe-stage').getAttribute('data-public-map-updates'));
  assert(updatesAfterSelection === updatesBeforeSelection, 'dual presence: selecting a project resent unchanged GeoJSON to MapLibre');
  assert((await run.page.locator('#focus-presence').textContent()) === 'Vor Ort · Digital · Kommunikation und Netze › Gemeinschaftsnetze', 'dual presence: dual presence presentation label mismatch');
  const hamburgLocations = (await run.page.locator('#focus-locations').textContent()) ?? '';
  assert(hamburgLocations.includes('mindestens 5 km Unschärfe') && hamburgLocations.includes('Ort verborgen'), 'dual presence: approximate and hidden location truth missing');
  assert(((await run.page.locator('#focus-relations').textContent()) ?? '').includes('Teil von Freifunk'), 'dual presence: evidenced parent relation missing');
  assert((await run.page.locator('.globe-stage').getAttribute('data-semantic-level')) === 'focus', 'dual presence: selected identity did not enter semantic focus');
  await run.page.locator('#commons-search').fill('Le Nid');
  await run.page.waitForFunction((count) => Number(document.querySelector('.globe-stage')?.dataset.publicMapFeatures) === count, expectedDigitalProjection.publicFeatureCountsByIdentity['cltb-le-nid']);
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'dual presence: filtering replaced or cleared the selected identity');
  assert((await run.page.locator('.globe-stage').getAttribute('data-semantic-level')) === 'focus', 'dual presence: filtered selected identity lost semantic focus');
  assert(((await run.page.locator('#semantic-summary').textContent()) ?? '').startsWith('Vor Ort'), 'dual presence: semantic line no longer describes the filtered selected identity');
  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction((count) => Number(document.querySelector('.globe-stage')?.dataset.publicMapFeatures) === count, expectedDigitalProjection.publicFeatureCount);
  await run.page.locator('#discovery-close').click();
  await run.page.locator('#focus-close').click();
  assert(await run.page.evaluate(() => document.activeElement === window.__commonworldTestMap?.getCanvas()), 'dual presence: closing a map-selected focus did not restore focus to the map canvas');
  await activateMapIdentity({
    coordinates: [9.944545738399, 53.558314876911],
    zoom: 6.2,
    layerId: 'commonworld-approximate-zones',
    expectedLevel: 'local',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'dual presence: local uncertainty-zone click lost the dual presence identity');
  assert(((await run.page.locator('#focus-locations').textContent()) ?? '').includes('mindestens 5 km Unschärfe'), 'dual presence: local uncertainty zone lost its minimum-radius truth');
  await run.page.locator('#focus-close').click();
  assert(await run.page.evaluate(() => document.activeElement === window.__commonworldTestMap?.getCanvas()), 'dual presence: local uncertainty-zone focus did not restore map focus');

  await activateMapIdentity({
    coordinates: [4.3152961, 50.8452417],
    zoom: 6.2,
    layerId: 'commonworld-exact-anchors',
    expectedLevel: 'local',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Le Nid', 'dual presence: exact map click selected the wrong identity');
  assert((await run.page.locator('#focus-presence').textContent()) === 'Vor Ort', 'dual presence: geographic presentation label mismatch');
  const leNidLocations = (await run.page.locator('#focus-locations').textContent()) ?? '';
  assert(leNidLocations.includes('exakter öffentlicher Punkt') && leNidLocations.includes('öffentliche Fläche'), 'dual presence: point and extent truth missing from focus');
  const leNidCoordinates = [4.3152961, 50.8452417];
  await run.page.evaluate((target) => {
    window.__commonworldTestMap.jumpTo({ center: target, zoom: 18, bearing: 0, pitch: 0 });
  }, leNidCoordinates);
  await run.page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    if (!map || map.isMoving() || !map.getLayer('commonworld-public-extents')) return false;
    const canvas = map.getCanvas();
    const viewport = [[0, 0], [canvas.clientWidth, canvas.clientHeight]];
    return map.queryRenderedFeatures(viewport, { layers: ['commonworld-public-extents'] })
      .some(({ properties }) => properties?.project_id === 'cltb-le-nid');
  });
  const renderedExtent = await run.page.evaluate(() => {
    const map = window.__commonworldTestMap;
    const canvas = map.getCanvas();
    const viewport = [[0, 0], [canvas.clientWidth, canvas.clientHeight]];
    return map.queryRenderedFeatures(viewport, { layers: ['commonworld-public-extents'] })
      .some(({ properties }) => properties?.project_id === 'cltb-le-nid');
  });
  assert(renderedExtent, 'dual presence: reviewed Le Nid public extent is not rendered through MapLibre at building zoom');

  await run.page.locator('#settings-toggle').click();
  await run.page.getByRole('radio', { name: /Text/ }).click();
  assert(await run.page.locator('#text-view').isVisible(), 'dual presence: text surface did not open');
  assert((await run.page.locator('body').getAttribute('data-presentation')) === 'text', 'dual presence: presentation state did not become text');
  assert(await run.page.locator('#project-cltb-le-nid[data-selected]').isVisible(), 'dual presence: text surface lost the selected CommonProject identity');
  assert(run.consoleErrors.length === 0, 'dual presence: console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'dual presence: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'dual-presence-axes', verdict: 'PASS', publicFeatures: expectedDigitalProjection.publicFeatureCount, publicIdentities: expectedDigitalProjection.publicIdentityCount, digitalIdentities: expectedDigitalProjection.totalCount, unchangedMapUpdatesSkipped: true });
  await run.context.close();
}



async function intentSearchDiscoveryScenario() {
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: 'intent-search-discovery' }) + '\n');
  const run = await newPage({ viewportOverride: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction((catalogEntryCount) => {
    const stage = document.querySelector('.globe-stage');
    return Number(stage?.dataset.searchIndexedRecords) === catalogEntryCount
      && Number(stage?.dataset.searchIndexedTerms ?? 0) > 0
      && stage?.dataset.visualReady === 'true'
      && Boolean(window.__commonworldTestMap);
  }, expectedDigitalProjection.catalogEntryCount);

  const mapCamera = () => run.page.evaluate(() => {
    const map = window.__commonworldTestMap;
    const center = map.getCenter();
    return { lng: center.lng, lat: center.lat, zoom: map.getZoom() };
  });
  const sameCamera = (left, right) => (
    Math.abs(left.lng - right.lng) < 0.0001
    && Math.abs(left.lat - right.lat) < 0.0001
    && Math.abs(left.zoom - right.zoom) < 0.0001
  );
  const stableMapCamera = async () => {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await run.page.waitForFunction(() => Boolean(window.__commonworldTestMap) && !window.__commonworldTestMap.isMoving());
      const before = await mapCamera();
      await run.page.waitForTimeout(120);
      const after = await mapCamera();
      const still = await run.page.evaluate(() => window.__commonworldTestMap?.isMoving() === false);
      if (still && sameCamera(before, after)) return after;
    }
    throw new Error('intent search: map camera did not reach a stable state');
  };
  const resultIds = () => run.page.locator('.discovery-result').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));

  await run.page.locator('#commons-search').fill('ich möchte mitmachen');
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.contributionIds.length);
  assert(await run.page.locator('#discovery-panel').isVisible(), 'intent search: result panel did not open');
  const contributionResultIds = await resultIds();
  assertSameIds(contributionResultIds, expectedDigitalProjection.contributionIds, 'intent search: German contribution identities differ from claimed catalog actions');
  assert((await run.page.locator('#discovery-count').textContent()) === `${expectedDigitalProjection.contributionIds.length} Commons`, 'intent search: ranked count mismatch');

  await run.page.locator('#commons-search').focus();
  await run.page.keyboard.press('ArrowDown');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === contributionResultIds[0], 'intent search: ArrowDown did not focus the first ranked result');
  await run.page.keyboard.press('ArrowDown');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === contributionResultIds[1], 'intent search: result ArrowDown did not advance through the ranked results');
  await run.page.keyboard.press('End');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === contributionResultIds.at(-1), 'intent search: End did not focus the last ranked result');
  await run.page.keyboard.press('Home');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === contributionResultIds[0], 'intent search: Home did not return to the first ranked result');

  const queryCamera = await stableMapCamera();
  await run.page.locator('#commons-search').fill('Anderlecht');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['cltb-le-nid']), 'intent search: public place did not resolve to Le Nid');
  const typedCamera = await stableMapCamera();
  assert(sameCamera(queryCamera, typedCamera), 'intent search: typing a place moved the map before activation ' + JSON.stringify({ queryCamera, typedCamera }));

  await run.page.locator('#commons-search').fill('private heimrouter');
  await run.page.waitForFunction(() => document.querySelector('#discovery-empty')?.hidden === false);
  assert((await resultIds()).length === 0, 'intent search: hidden router information leaked into results');
  await run.page.locator('#commons-search').fill('quantenbanane-xyz');
  await run.page.waitForFunction(() => document.querySelector('#globe-results')?.hasAttribute('data-empty'));
  assert(await run.page.locator('#discovery-empty').isVisible(), 'intent search: empty result state is missing');
  assert(await run.page.locator('#discovery-list').isHidden(), 'intent search: empty result list remains exposed');

  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.catalogEntryCount);
  await run.page.locator('#filter-commons-type').selectOption('community-network');
  await run.page.waitForFunction((count) => new URL(location.href).searchParams.get('commons_type') === 'community-network' && document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.communityNetworkIds.length);
  assertSameIds(await resultIds(), expectedDigitalProjection.communityNetworkIds, 'intent filters: Commons-Art differs from deterministic catalog derivation');
  assert((await run.page.locator('.discovery-result-meta').allTextContents()).every((text) => text.includes('Gemeinschaftsnetz')), 'intent filters: Commons-Art label missing from compact result metadata');
  await run.page.locator('#filter-commons-type').selectOption('');
  await run.page.waitForFunction((count) => !new URL(location.href).searchParams.has('commons_type') && document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.catalogEntryCount);
  await run.page.goBack({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction((count) => document.querySelector('#filter-commons-type')?.value === 'community-network' && document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.communityNetworkIds.length);
  assertSameIds(await resultIds(), expectedDigitalProjection.communityNetworkIds, 'intent history: Back did not restore Commons-Art');
  await run.page.goForward({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction((count) => document.querySelector('#filter-commons-type')?.value === '' && document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.catalogEntryCount);
  if (await run.page.locator('#discovery-panel').isHidden()) await run.page.locator('#filter-toggle').click();
  await run.page.locator('#discovery-panel').waitFor({ state: 'visible' });
  await run.page.waitForFunction(() => Boolean(window.__commonworldTestMap) && !window.__commonworldTestMap.isMoving());
  const filterCamera = await mapCamera();
  await run.page.locator('#filter-presence-geographic').check();
  await run.page.locator('#filter-presence-digital').check();
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.dualPresenceIds.length);
  assert(JSON.stringify(await resultIds()) === JSON.stringify(expectedDigitalProjection.dualPresenceIds), 'intent filters: dual presence differs from the catalog');
  const params = new URL(run.page.url()).searchParams.getAll('presence');
  assert(params.length === 2 && params[0] === 'geographic' && params[1] === 'digital', 'intent filters: presence was not serialized correctly');
  await run.page.locator('#filter-action').selectOption('volunteer');
  await run.page.waitForFunction((count) => new URL(location.href).searchParams.get('action') === 'volunteer' && document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.dualPresenceVolunteerIds.length);
  assert(JSON.stringify(await resultIds()) === JSON.stringify(expectedDigitalProjection.dualPresenceVolunteerIds), 'intent filters: combined dual-presence-volunteer filter differs from claimed catalog actions');
  assert(sameCamera(filterCamera, await mapCamera()), 'intent filters: changing filters moved the map');

  const actionTypes = await run.page.locator('.discovery-result[data-commonproject-id="freifunk-hamburg"] .discovery-result-actions a').evaluateAll((links) => links.map((link) => link.dataset.actionType));
  assert(JSON.stringify(actionTypes) === JSON.stringify(['use', 'learn', 'contribute', 'volunteer', 'contact']), 'intent actions: direct Freifunk Hamburg actions differ from the catalog');
  const actionTargets = await run.page.locator('.discovery-result[data-commonproject-id="freifunk-hamburg"] .discovery-result-actions a').evaluateAll((links) => links.map((link) => link.href));
  assert(actionTargets.every((href) => href.startsWith('https://')), 'intent actions: a direct action target is not HTTPS');

  await run.page.goBack({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction(() => document.querySelector('#filter-presence-geographic')?.checked === true && document.querySelector('#filter-presence-digital')?.checked === true && document.querySelector('#filter-action')?.value === '');
  assert(JSON.stringify(await resultIds()) === JSON.stringify(expectedDigitalProjection.dualPresenceIds), 'intent history: Back did not restore the previous filter context');
  await run.page.goForward({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction(() => document.querySelector('#filter-action')?.value === 'volunteer');
  assert(JSON.stringify(await resultIds()) === JSON.stringify(expectedDigitalProjection.dualPresenceVolunteerIds), 'intent history: Forward did not restore the combined filter context');

  await run.page.locator('#filter-clear').click();
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.catalogEntryCount);
  assert([...new URL(run.page.url()).searchParams.keys()].every((key) => !['commons_type', 'presence', 'action', 'language', 'access', 'freshness', 'curation'].includes(key)), 'intent filters: reset left filter parameters in the URL');

  const digitalCamera = await mapCamera();
  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('q') === 'Debian');
  await run.page.locator('.discovery-result-main').click();
  await run.page.waitForSelector('#project-focus:not([hidden])');
  assert((await run.page.locator('#focus-title').textContent()) === 'Debian', 'intent spatial: digital result did not open Debian');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-spatial-result')) === 'coordinate-free:debian', 'intent spatial: digital result was not kept coordinate-free');
  assert(sameCamera(digitalCamera, await mapCamera()), 'intent spatial: digital result moved the map');

  await run.page.goBack();
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('q') === 'Debian' && !new URL(location.href).searchParams.has('project'));
  assert(await run.page.locator('#discovery-panel').isVisible(), 'intent project history: Back did not restore the search results');
  assert(await run.page.locator('#project-focus').isHidden(), 'intent project history: Back retained the project overlay');

  await run.page.goForward();
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('q') === 'Debian' && new URL(location.href).searchParams.get('project') === 'debian');
  await run.page.waitForFunction(() => (
    document.activeElement === document.querySelector('#project-focus')
    && document.activeElement.getClientRects().length > 0
    && !document.activeElement.closest('[hidden], [inert], [aria-hidden="true"]')
  ));
  assert(await run.page.locator('#discovery-panel').isHidden(), 'intent project history: Forward reopened discovery over the restored project');
  assert(await run.page.locator('#project-focus').isVisible(), 'intent project history: Forward did not restore the project overlay');
  assert((await run.page.locator('#focus-title').textContent()) === 'Debian', 'intent project history: Forward restored the wrong project');
  await run.page.locator('#focus-close').click();

  await run.page.locator('#commons-search').fill('Anderlecht');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  await run.page.locator('.discovery-result-main').click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.lastSpatialResult === 'bounds:cltb-le-nid');
  const spatialCamera = await mapCamera();
  assert(Math.abs(spatialCamera.lng - 4.315) < 0.05 && Math.abs(spatialCamera.lat - 50.845) < 0.05 && spatialCamera.zoom > 10, 'intent spatial: Le Nid did not navigate to its public representation');
  assert((await run.page.locator('#focus-title').textContent()) === 'Le Nid', 'intent spatial: geographic result focus mismatch');
  await run.page.locator('#focus-close').click();

  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.catalogEntryCount);
  await run.page.locator('#filter-presence-geographic').check();
  await run.page.locator('#filter-presence-digital').check();
  await run.page.waitForFunction((count) => document.querySelectorAll('.discovery-result').length === count, expectedDigitalProjection.dualPresenceIds.length);
  await run.page.locator('#discovery-close').click();
  await run.page.locator('#settings-toggle').click();
  await run.page.getByRole('radio', { name: /Text/ }).click();
  const visibleTextIds = await run.page.locator('.catalog-card:not([hidden])').evaluateAll((cards) => cards.map((card) => card.dataset.commonprojectId));
  assert(JSON.stringify(visibleTextIds) === JSON.stringify(expectedDigitalProjection.dualPresenceIds), 'intent parity: text view does not preserve the globe filter context');
  const staticActionTypes = await run.page.locator('#project-freifunk-hamburg .catalog-action-link').evaluateAll((links) => links.map((link) => link.dataset.actionType));
  assert(JSON.stringify(staticActionTypes) === JSON.stringify(['use', 'learn', 'contribute', 'volunteer', 'contact']), 'intent parity: static text actions differ from ranked result actions');

  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), 'intent search: unexpected console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'intent search: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'intent-search-discovery', verdict: 'PASS', indexedRecords: expectedDigitalProjection.catalogEntryCount, rankedGermanIntentResults: expectedDigitalProjection.contributionIds.length, filters: 7, digitalCoordinateFree: true, spatialNavigation: true });
  await run.context.close();
}

async function spatialDiscoveryFiltersScenario() {
  const privateLocation = { latitude: 52.52, longitude: 13.405 };
  const run = await newPage({ geolocation: privateLocation, permissions: ['geolocation'] });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.countryMapState === 'ready');

  await run.page.locator('#filter-toggle').click();
  assert(await run.page.locator('#discovery-panel').isVisible(), 'spatial discovery: discovery panel did not open');
  assert(await run.page.locator('#filter-sections').isVisible(), 'spatial discovery: filter sections were not initially visible');
  await run.page.locator('#filter-sections-toggle').click();
  assert(await run.page.locator('#filter-sections').isHidden(), 'spatial discovery: filter sections did not collapse');
  assert(await run.page.locator('#filter-sections-toggle').getAttribute('aria-expanded') === 'false', 'spatial discovery: collapsed filter aria state is wrong');
  assert(await run.page.locator('#active-filter-chips').evaluate((element) => !element.hidden && !element.closest('#filter-sections')), 'spatial discovery: active filter chip region moved into or disappeared with collapsed controls');
  await run.page.locator('#filter-sections-toggle').click();

  const firstCountry = await run.page.locator('#filter-country option').evaluateAll((options) => {
    const option = options.find((candidate) => candidate.value);
    return option ? { id: option.value, name: option.textContent.trim() } : null;
  });
  assert(firstCountry?.id && firstCountry?.name, 'spatial discovery: country selector has no navigable country');
  await run.page.locator('#spatial-destination-search').fill(firstCountry.name);
  await run.page.waitForFunction(() => document.querySelectorAll('#spatial-destination-results li').length > 0);
  const firstDestination = run.page.locator('#spatial-destination-results li').first();
  await firstDestination.locator('button').first().click();
  await run.page.waitForFunction(() => !document.querySelector('#country-navigation-context')?.hidden);
  assert(!new URL(run.page.url()).searchParams.has('country'), 'spatial discovery: navigating to a country silently activated filtering');
  await run.page.locator('#country-filter-action').click();
  await run.page.waitForFunction((countryId) => new URL(location.href).searchParams.get('country') === countryId, firstCountry.id);
  assert((await run.page.locator('#filter-toggle-count').textContent()) === '1', 'spatial discovery: country filter count badge is wrong');
  assert(await run.page.locator('#active-filter-chips button').count() === 1, 'spatial discovery: country filter chip missing');
  await run.page.locator('#active-filter-chips button').click();
  await run.page.waitForFunction(() => !new URL(location.href).searchParams.has('country'));

  await run.page.locator('#spatial-destination-search').fill('Berlin');
  await run.page.waitForFunction(() => document.querySelectorAll('#spatial-destination-results li').length > 0);
  assert((await run.page.locator('#spatial-destination-results').textContent())?.toLocaleLowerCase('de').includes('berlin'), 'spatial discovery: published Berlin destination is not searchable locally');

  await run.page.locator('#use-current-location').click();
  await run.page.waitForFunction(() => document.querySelector('#geolocation-status')?.textContent.includes('Standort verwendet'));
  const privacyState = await run.page.evaluate(({ latitude, longitude }) => {
    const url = new URL(location.href);
    const serializedLatitude = Number(url.searchParams.get('lat'));
    const serializedLongitude = Number(url.searchParams.get('lng'));
    const state = history.state?.commonworld ?? {};
    return {
      hasNearbyUrlState: [...url.searchParams.keys()].some((key) => key.toLowerCase().includes('nearby')),
      cameraContainsPrivateLocation: Math.abs(serializedLatitude - latitude) < 0.01 && Math.abs(serializedLongitude - longitude) < 0.01,
      historyNearbyOrigin: state.nearbyOrigin ?? null,
      historyNearbyRadiusMeters: state.nearbyRadiusMeters ?? null,
      chipCount: document.querySelectorAll('#active-filter-chips .active-filter-chip').length,
      badge: document.querySelector('#filter-toggle-count')?.textContent,
    };
  }, privateLocation);
  assert(!privacyState.hasNearbyUrlState, `spatial discovery: private nearby state leaked into URL (${JSON.stringify(privacyState)})`);
  assert(!privacyState.cameraContainsPrivateLocation, `spatial discovery: private geolocation leaked through camera URL (${JSON.stringify(privacyState)})`);
  assert(privacyState.historyNearbyOrigin === null && privacyState.historyNearbyRadiusMeters === null, `spatial discovery: private geolocation leaked into history state (${JSON.stringify(privacyState)})`);
  assert(privacyState.chipCount === 1 && privacyState.badge === '1', `spatial discovery: nearby filter chip/badge missing (${JSON.stringify(privacyState)})`);

  const mapCanvas = run.page.locator('.maplibregl-canvas');
  const mapCanvasBox = await mapCanvas.boundingBox();
  assert(mapCanvasBox, 'spatial discovery: map canvas has no interaction bounds');
  await run.page.mouse.move(mapCanvasBox.x + (mapCanvasBox.width / 2), mapCanvasBox.y + (mapCanvasBox.height / 2));
  await run.page.mouse.wheel(0, -120);
  await run.page.waitForTimeout(700);
  const postInteractionPrivacyState = await run.page.evaluate(({ latitude, longitude }) => {
    const url = new URL(location.href);
    const serializedLatitude = Number(url.searchParams.get('lat'));
    const serializedLongitude = Number(url.searchParams.get('lng'));
    return {
      cameraContainsPrivateLocation: Math.abs(serializedLatitude - latitude) < 0.01 && Math.abs(serializedLongitude - longitude) < 0.01,
      historyNearbyOrigin: history.state?.commonworld?.nearbyOrigin ?? null,
      historyNearbyRadiusMeters: history.state?.commonworld?.nearbyRadiusMeters ?? null,
    };
  }, privateLocation);
  assert(!postInteractionPrivacyState.cameraContainsPrivateLocation, `spatial discovery: manual map interaction leaked private geolocation through camera URL (${JSON.stringify(postInteractionPrivacyState)})`);
  assert(postInteractionPrivacyState.historyNearbyOrigin === null && postInteractionPrivacyState.historyNearbyRadiusMeters === null, `spatial discovery: manual map interaction leaked private nearby state into history (${JSON.stringify(postInteractionPrivacyState)})`);
  assert(run.pageErrors.length === 0, `spatial discovery: page errors: ${run.pageErrors.join(' | ')}`);
  assert(run.consoleErrors.length === 0, `spatial discovery: console errors: ${run.consoleErrors.join(' | ')}`);
  results.push({
    id: 'spatial-discovery-filters',
    verdict: 'PASS',
    countryNavigationSeparatedFromFiltering: true,
    localPublishedPlaceSearch: true,
    privateGeolocationNotSerialized: true,
  });
  await run.context.close();
}

async function androidGlobeUiScenario() {
  const scenarioId = 'android-globe-ui-alignment';
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: scenarioId }) + '\n');
  const run = await newPage({ mobile: true, touch: true, reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => document.querySelectorAll('.sphere-ring-text').length > 0);

  const geometry = await run.page.evaluate(() => {
    const button = document.querySelector('#filter-toggle');
    const icon = button.querySelector('.filter-toggle-icon');
    const buttonRect = button.getBoundingClientRect();
    const iconRect = icon.getBoundingClientRect();
    const ring = document.querySelector('.sphere-ring-plane');
    const text = document.querySelector('.sphere-ring-text');
    const textRect = text.getBoundingClientRect();
    const ringStyle = getComputedStyle(ring);
    const textStyle = getComputedStyle(text);
    return {
      filterCenterDeltaX: Math.abs((buttonRect.left + buttonRect.width / 2) - (iconRect.left + iconRect.width / 2)),
      filterCenterDeltaY: Math.abs((buttonRect.top + buttonRect.height / 2) - (iconRect.top + iconRect.height / 2)),
      filterButtonWidth: buttonRect.width,
      filterButtonHeight: buttonRect.height,
      ringAnimationName: ringStyle.animationName,
      ringTransform: ringStyle.transform,
      ringTextWidth: textRect.width,
      ringTextHeight: textRect.height,
      ringTextFontSize: Number.parseFloat(textStyle.fontSize),
    };
  });
  assert(geometry.filterCenterDeltaX <= 1 && geometry.filterCenterDeltaY <= 1, scenarioId + ': filter icon is not centered ' + JSON.stringify(geometry));
  assert(geometry.filterButtonWidth >= 44 && geometry.filterButtonHeight >= 44, scenarioId + ': filter button is below mobile touch target ' + JSON.stringify(geometry));
  assert(geometry.ringAnimationName === 'none', scenarioId + ': mobile ring group still uses CSS orbit transform ' + JSON.stringify(geometry));
  assert(geometry.ringTransform === 'none', scenarioId + ': mobile ring group retains a transform offset ' + JSON.stringify(geometry));
  assert(geometry.ringTextWidth > 20 && geometry.ringTextHeight > 8 && geometry.ringTextFontSize >= 17, scenarioId + ': mobile ring text is not visibly sized ' + JSON.stringify(geometry));

  await run.page.evaluate(() => new Promise((resolve) => {
    const map = window.__commonworldTestMap;
    map.once('render', resolve);
    map.jumpTo({ center: [10.2, 51.1], zoom: 1.2, bearing: 0, pitch: 0 });
    map.triggerRepaint();
  }));
  await run.page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    const stage = document.querySelector('.globe-stage');
    return Boolean(map && !map.isMoving() && stage?.dataset.countryMapState === 'ready' && map.getLayer('commonworld-country-compositions-base'));
  });
  await run.page.waitForFunction(() => {
    const map = window.__commonworldTestMap;
    if (!map || map.isMoving()) return false;
    return map.queryRenderedFeatures(map.project([10.2, 51.1]), { layers: ['commonworld-country-compositions-base'] }).length > 0;
  });
  const country = await run.page.evaluate(() => {
    const map = window.__commonworldTestMap;
    const opacity = map.getPaintProperty('commonworld-country-compositions-base', 'fill-opacity');
    const rendered = map.queryRenderedFeatures(map.project([10.2, 51.1]), { layers: ['commonworld-country-compositions-base'] }).length;
    const sourceFeatures = map.querySourceFeatures('commonworld-country-compositions').length;
    const diagnosticsFeatures = Number.parseInt(document.querySelector('.globe-stage')?.dataset.countryMapFeatures ?? '0', 10);
    const visibility = map.getLayoutProperty('commonworld-country-compositions-base', 'visibility') ?? 'visible';
    return { opacity, rendered, sourceFeatures, diagnosticsFeatures, visibility, zoom: map.getZoom() };
  });
  assert(JSON.stringify(country.opacity).includes('0.78'), scenarioId + ': overview country tint is not strong enough ' + JSON.stringify(country));
  assert(country.diagnosticsFeatures > 0 && country.rendered > 0, scenarioId + ': country composition is not rendered at mobile globe overview ' + JSON.stringify(country));
  assert(run.pageErrors.length === 0, scenarioId + ': page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: scenarioId, verdict: 'PASS', ...geometry, countryRendered: country.rendered });
  await run.context.close();
}

async function intentSearchLayoutScenario({ viewportOverride, scenarioId }) {
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: scenarioId }) + '\n');
  const run = await newPage({ viewportOverride, touch: true, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.locator('#commons-search').fill('mitmachen');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length > 0);
  const geometry = await run.page.evaluate(() => {
    const panel = document.querySelector('#discovery-panel');
    const rect = panel.getBoundingClientRect();
    const controls = [...panel.querySelectorAll('select, .discovery-result-main')].map((node) => node.getBoundingClientRect().height);
    return {
      panel: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      minimumControlHeight: Math.min(...controls),
    };
  });
  assert(geometry.panel.left >= -1 && geometry.panel.right <= geometry.width + 1, scenarioId + ': discovery panel overflows horizontally');
  assert(geometry.panel.top >= -1 && geometry.panel.bottom <= geometry.height + 1, scenarioId + ': discovery panel exceeds the viewport');
  assert(geometry.scrollWidth <= geometry.width + 1, scenarioId + ': document has horizontal overflow');
  assert(geometry.minimumControlHeight >= 44, scenarioId + ': a filter or result control is below the 44px touch target');
  const curationSelect = run.page.locator('[data-intent-filter="curation"]');
  await curationSelect.tap();
  await run.page.waitForTimeout(40);
  const selectFocusAppearance = await curationSelect.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      active: document.activeElement === node,
      modality: document.documentElement.dataset.inputModality,
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth),
    };
  });
  assert(selectFocusAppearance.modality === 'pointer', scenarioId + ': tapped select did not retain pointer modality ' + JSON.stringify(selectFocusAppearance));
  assert(selectFocusAppearance.outlineStyle === 'none' || selectFocusAppearance.outlineWidth === 0, scenarioId + ': tapped select exposed a focus ring ' + JSON.stringify(selectFocusAppearance));
  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), scenarioId + ': unexpected console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, scenarioId + ': page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: scenarioId, verdict: 'PASS', minimumControlHeight: geometry.minimumControlHeight, touchFocusRingsHidden: true });
  await run.context.close();
}

async function moveendBoundReturnScenario() {
  const run = await newPage({ reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  await run.page.waitForTimeout(820);
  const sphereBox = await run.page.locator('#digital-sphere').boundingBox();
  assert(sphereBox, 'moveend return: sphere geometry missing');
  await run.page.mouse.click(sphereBox.x + sphereBox.width * 0.85134, sphereBox.y + sphereBox.height * 0.14866);
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  // An artificially slow CSS opacity transition must not delay the sequence:
  // completion is bound to the MapLibre moveend, not to transitionend.
  await run.page.locator('#map').evaluate((node) => { node.style.transitionDuration = '10s'; });
  const startedAt = Date.now();
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  const elapsed = Date.now() - startedAt;
  assert(elapsed < 5000, `moveend return: completion waited for CSS instead of the MapLibre moveend (${elapsed}ms)`);
  assert(await run.page.evaluate(() => window.__commonworldTestMap?.isMoving() === false), 'moveend return: overview was declared while MapLibre was still moving');
  assert(await run.page.locator('#map').getAttribute('inert') === null, 'moveend return: returned globe remains inert');
  assert(run.consoleErrors.length === 0, `moveend return: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `moveend return: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'layer-journey-moveend-return', verdict: 'PASS', elapsedMs: elapsed });
  await run.context.close();
}


async function interruptedLayerJourneyScenario() {
  const run = await newPage({ reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  await run.page.waitForTimeout(820);
  const sphereBox = await run.page.locator('#digital-sphere').boundingBox();
  assert(sphereBox, 'interrupted journey: sphere geometry missing');
  await run.page.mouse.click(sphereBox.x + sphereBox.width * 0.85134, sphereBox.y + sphereBox.height * 0.14866);
  await run.page.waitForTimeout(150);
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'entering-layers', 'interrupted journey: entry phase missing');
  await run.page.keyboard.press('Escape');
  await run.page.waitForFunction(() => {
    const phase = document.querySelector('.globe-stage')?.dataset.viewPhase;
    return phase === 'leaving-layers' || phase === 'overview';
  });
  const escapePhase = await run.page.locator('.globe-stage').getAttribute('data-view-phase');
  assert(escapePhase !== 'preparing-overview', 'interrupted journey: escape used the return preparation instead of replacing the running camera');
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  await run.page.waitForTimeout(80);
  assert(await run.page.locator('#layer-panel').isHidden(), 'interrupted journey: stale full-screen layer panel remains');
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'overview', 'interrupted journey: stale transition timer changed the final state');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'sphere-edge-control', 'interrupted journey: focus did not return to the sphere');
  assert(run.pageErrors.length === 0, `interrupted journey: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'layer-journey-interrupted', verdict: 'PASS' });
  await run.context.close();
}


async function reducedMotionLayerScenario() {
  const run = await newPage();
  await run.page.goto(`${baseUrl}/?view=layers&digital_path=sphere/communication_networks/community_networks&lng=13.4&lat=52.5&z=1.2`, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks/community_networks');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.lastCameraCommand === 'jumpTo');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-camera-command')) === 'jumpTo', 'reduced motion: layer camera did not jump');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-camera-duration')) === '0', 'reduced motion: nonzero layer duration');
  await run.page.locator('#layer-close').click();
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'overview', 'reduced motion: return was not immediate');
  const search = new URL(run.page.url()).searchParams;
  assert(search.get('view') === null, 'reduced motion: closed layer view persisted');
  assert(search.get('digital_path') === 'sphere/communication_networks/community_networks', 'reduced motion: closed layer view lost digital path state');
  assert(Math.abs(Number(search.get('lng')) - 13.4) < 0.01, `reduced motion: overview longitude changed (${search.get('lng')})`);
  assert(Math.abs(Number(search.get('lat')) - 52.5) < 0.01, `reduced motion: overview latitude changed (${search.get('lat')})`);
  assert(run.pageErrors.length === 0, `reduced motion: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'layer-journey-reduced-motion', verdict: 'PASS' });
  await run.context.close();
}

async function legacyLayerAndAtomicFocusScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'legacy-layer-and-atomic-focus' })}\n`);
  const legacyRun = await newPage({ reducedMotion: 'reduce' });
  await legacyRun.page.goto(`${baseUrl}/?surface=text&layer=communication_networks`, { waitUntil: 'domcontentloaded' });
  await legacyRun.page.waitForSelector('html.runtime-ready');
  await legacyRun.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks/community_networks');
  const legacyParameters = new URL(legacyRun.page.url()).searchParams;
  assert(legacyParameters.get('layer') === 'communication_networks', 'legacy layer: canonicalization removed the legacy parameter');
  assert(!legacyParameters.has('digital_path'), 'legacy layer: orientation path replaced the legacy filter in the URL');
  const legacyIds = await legacyRun.page.locator('.catalog-card:not([hidden])').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
  assertSameIds(legacyIds, expectedDigitalProjection.legacyLayerIds.communication_networks, 'legacy layer: exact communication result set');
  assert(legacyIds.includes('mastodon'), 'legacy layer: communication result set lost Mastodon');

  await legacyRun.page.locator('#text-layer-breadcrumb .digital-breadcrumb-item[data-digital-path="sphere/communication_networks"]').click();
  await legacyRun.page.waitForFunction(() => new URL(location.href).searchParams.get('digital_path') === 'sphere/communication_networks');
  let selectedParameters = new URL(legacyRun.page.url()).searchParams;
  assert(!selectedParameters.has('layer'), 'legacy layer: explicit breadcrumb selection retained the legacy layer');
  await legacyRun.page.goBack();
  await legacyRun.page.waitForFunction(() => new URL(location.href).searchParams.get('layer') === 'communication_networks');
  const restoredLegacyIds = await legacyRun.page.locator('.catalog-card:not([hidden])').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
  assertSameIds(restoredLegacyIds, expectedDigitalProjection.legacyLayerIds.communication_networks, 'legacy layer: Back restored exact result set');
  await legacyRun.page.goForward();
  await legacyRun.page.waitForFunction(() => new URL(location.href).searchParams.get('digital_path') === 'sphere/communication_networks');
  selectedParameters = new URL(legacyRun.page.url()).searchParams;
  assert(!selectedParameters.has('layer'), 'legacy layer: Forward restored a mixed legacy/path state');
  await legacyRun.page.goto(`${baseUrl}/?surface=text&layer=communication_networks&digital_path=sphere/%20/communication_networks`, { waitUntil: 'domcontentloaded' });
  await legacyRun.page.waitForSelector('html.runtime-ready');
  const invalidExplicitParameters = new URL(legacyRun.page.url()).searchParams;
  assert(!invalidExplicitParameters.has('layer') && !invalidExplicitParameters.has('digital_path'), 'invalid explicit path: legacy layer or partial path survived fail-closed canonicalization');
  const invalidRootCountText = (await legacyRun.page.locator('#text-count').textContent()) ?? '';
  assert(invalidRootCountText.includes(`${expectedDigitalProjection.catalogEntryCount} Commons`), `invalid explicit path: root result truth was filtered (${invalidRootCountText})`);
  assert(legacyRun.consoleErrors.length === 0, `legacy layer: console errors: ${legacyRun.consoleErrors.join(' | ')}`);
  assert(legacyRun.pageErrors.length === 0, `legacy layer: page errors: ${legacyRun.pageErrors.join(' | ')}`);
  await legacyRun.context.close();

  const focusRun = await newPage({ reducedMotion: 'reduce' });
  await focusRun.page.goto(`${baseUrl}/?view=layers`, { waitUntil: 'domcontentloaded' });
  await focusRun.page.waitForSelector('html.runtime-ready');
  await focusRun.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  const focusTrigger = focusRun.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]').first();
  const focusProjectId = await focusTrigger.getAttribute('data-commonproject-id');
  assert(Boolean(focusProjectId), 'atomic focus: no rendered digital identity was available');
  const focusProjectTitle = expectedDigitalProjection.titleById[focusProjectId];
  assert(Boolean(focusProjectTitle), `atomic focus: rendered identity ${focusProjectId} is missing from canonical projection`);
  await focusTrigger.click();
  assert(await focusRun.page.locator('#project-focus').isVisible(), `atomic focus: ${focusProjectId} focus did not open`);
  assert(new URL(focusRun.page.url()).searchParams.get('project') === focusProjectId, `atomic focus: ${focusProjectId} was not written to history`);

  await focusRun.page.keyboard.press('Escape');
  assert(await focusRun.page.locator('#project-focus').isHidden(), 'atomic focus: Escape did not close the project overlay');
  const keyboardFocusTrigger = focusRun.page.locator(`.digital-ribbon-item[data-commonproject-id="${focusProjectId}"][data-ribbon-copy="0"]`);
  await keyboardFocusTrigger.focus();
  await focusRun.page.keyboard.press('Enter');
  assert(await focusRun.page.locator('#project-focus').isVisible(), `atomic focus: keyboard activation did not reopen ${focusProjectId}`);

  // Exercise the direct state regression without pretending the covered control receives a pointer interaction.
  await focusRun.page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks"]').evaluate((node) => node.click());
  await waitForAtomicHierarchyFocus(focusRun.page, {
    label: 'atomic focus: direct path mutation',
    expectedPath: 'sphere/communication_networks',
    activeSelector: '.digital-lane-scroll, .digital-breadcrumb-item',
  });
  const cleared = await focusRun.page.evaluate(() => ({
    project: new URL(location.href).searchParams.get('project'),
    path: new URL(location.href).searchParams.get('digital_path'),
    focusHidden: document.querySelector('#project-focus').hidden,
    selectedMarks: document.querySelectorAll('[data-commonproject-id].is-selected').length,
    activeHierarchy: document.activeElement?.matches('.digital-lane-scroll, .digital-breadcrumb-item') ?? false,
    activeVisible: Boolean(document.activeElement?.getClientRects().length),
  }));
  assert(cleared.project === null && cleared.path === 'sphere/communication_networks', `atomic focus: path mutation retained project state (${JSON.stringify(cleared)})`);
  assert(cleared.focusHidden && cleared.selectedMarks === 0, `atomic focus: overlay or selection marks survived path mutation (${JSON.stringify(cleared)})`);
  assert(cleared.activeHierarchy && cleared.activeVisible, `atomic focus: focus did not move to a visible hierarchy control (${JSON.stringify(cleared)})`);

  await focusRun.page.goBack();
  await focusRun.page.waitForFunction((projectId) => new URL(location.href).searchParams.get('project') === projectId, focusProjectId);
  assert(await focusRun.page.locator('#project-focus').isVisible(), `atomic focus: Back did not restore ${focusProjectId} focus`);
  assert((await focusRun.page.locator('#focus-title').textContent()) === focusProjectTitle, 'atomic focus: Back restored the wrong project');

  await focusRun.page.evaluate(() => {
    const selector = '#layer-track-deck .digital-lane-focus, #layer-track-deck .digital-lane-scroll, #layer-breadcrumb .digital-breadcrumb-item';
    const hideTargets = () => document.querySelectorAll(selector).forEach((node) => node.setAttribute('hidden', ''));
    const observer = new MutationObserver(hideTargets);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    hideTargets();
    window.setTimeout(() => {
      observer.disconnect();
      document.querySelectorAll(selector).forEach((node) => node.removeAttribute('hidden'));
    }, 240);
  });
  await focusRun.page.goForward();
  await waitForAtomicHierarchyFocus(focusRun.page, {
    label: 'atomic focus: delayed Forward restoration',
    expectedPath: 'sphere/communication_networks',
    activeSelector: '.digital-lane-focus, .digital-lane-scroll, .digital-breadcrumb-item',
  });
  assert(await focusRun.page.locator('#project-focus').isHidden(), 'atomic focus: Forward left the project panel visible');

  for (let iteration = 0; iteration < 3; iteration += 1) {
    await focusRun.page.goBack();
    await focusRun.page.waitForFunction((projectId) => new URL(location.href).searchParams.get('project') === projectId, focusProjectId);
    await focusRun.page.goForward();
    await waitForAtomicHierarchyFocus(focusRun.page, {
      label: `atomic focus: repeated Forward restoration ${iteration + 1}`,
      expectedPath: 'sphere/communication_networks',
      activeSelector: '.digital-lane-focus, .digital-lane-scroll, .digital-breadcrumb-item',
    });
  }
  const rapidFocus = await focusRun.page.evaluate(() => {
    const active = document.activeElement;
    return {
      tag: active?.tagName ?? null,
      id: active?.id ?? null,
      connected: active?.isConnected ?? false,
      visible: Boolean(active?.getClientRects().length),
      blocked: Boolean(active?.closest('[hidden], [inert], [aria-hidden="true"]')),
      body: active === document.body,
    };
  });
  assert(rapidFocus.connected && rapidFocus.visible && !rapidFocus.blocked && !rapidFocus.body, 'atomic focus: repeated Back/Forward produced an invalid target (' + JSON.stringify(rapidFocus) + ')');

  await focusRun.page.goto(`${baseUrl}/?view=layers&digital_path=sphere/communication_networks&project=wikipedia`, { waitUntil: 'domcontentloaded' });
  await focusRun.page.waitForSelector('html.runtime-ready');
  await focusRun.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks');
  const invalidCombination = new URL(focusRun.page.url()).searchParams;
  assert(invalidCombination.get('digital_path') === 'sphere/communication_networks', 'atomic focus: invalid direct combination lost its valid path');
  assert(!invalidCombination.has('project') && await focusRun.page.locator('#project-focus').isHidden(), 'atomic focus: invalid direct combination retained foreign project focus');
  assert(focusRun.consoleErrors.length === 0, `atomic focus: console errors: ${focusRun.consoleErrors.join(' | ')}`);
  assert(focusRun.pageErrors.length === 0, `atomic focus: page errors: ${focusRun.pageErrors.join(' | ')}`);
  await focusRun.context.close();

  const textFocusRun = await newPage({ reducedMotion: 'reduce' });
  await textFocusRun.page.goto(`${baseUrl}/?surface=text&view=layers&project=wikipedia`, { waitUntil: 'domcontentloaded' });
  await textFocusRun.page.waitForSelector('html.runtime-ready');
  assert(await textFocusRun.page.locator('#project-focus').isVisible(), 'text atomic focus: Wikipedia focus did not open');
  const textHierarchy = textFocusRun.page.locator('#text-layer-buttons .layer-filter[data-digital-path="sphere/communication_networks"]');
  await textHierarchy.focus();
  await textFocusRun.page.keyboard.press('Enter');
  await waitForAtomicHierarchyFocus(textFocusRun.page, {
    label: 'text atomic focus: hierarchy activation',
    expectedPath: 'sphere/communication_networks',
    activeSelector: '#text-layer-breadcrumb .digital-breadcrumb-item, #text-layer-buttons .layer-filter',
    requirePanel: false,
  });
  assert(await textFocusRun.page.locator('#project-focus').isHidden(), 'text atomic focus: incompatible path retained project overlay');
  assert(await textFocusRun.page.locator('#text-layer-breadcrumb .digital-breadcrumb-item[aria-current="page"]').isVisible(), 'text atomic focus: current breadcrumb is not visible');
  const textBundle = textFocusRun.page.locator('#text-layer-buttons .layer-filter[data-digital-path="sphere/communication_networks/community_networks"]');
  await textBundle.focus();
  await textFocusRun.page.keyboard.press('Enter');
  await waitForAtomicHierarchyFocus(textFocusRun.page, {
    label: 'text atomic focus: bundle activation',
    expectedPath: 'sphere/communication_networks/community_networks',
    activeSelector: '#text-layer-breadcrumb .digital-breadcrumb-item, #text-layer-buttons .layer-filter',
    requirePanel: false,
  });

  const textRootBreadcrumb = textFocusRun.page.locator('#text-layer-breadcrumb .digital-breadcrumb-item[data-digital-path="sphere"]');
  await textRootBreadcrumb.focus();
  await textFocusRun.page.keyboard.press('Enter');
  await waitForAtomicHierarchyFocus(textFocusRun.page, {
    label: 'text atomic focus: root activation',
    expectedPath: 'sphere',
    activeSelector: '#text-layer-breadcrumb .digital-breadcrumb-item, #text-layer-buttons .layer-filter',
    requirePanel: false,
  });

  assert(textFocusRun.pageErrors.length === 0, `text atomic focus: page errors: ${textFocusRun.pageErrors.join(' | ')}`);
  await textFocusRun.context.close();
  results.push({ id: 'legacy-layer-and-atomic-focus', verdict: 'PASS', backForwardFocus: true, textHierarchyFocus: true, keyboardPath: true });
}

async function historyFocusDiagnosticContractScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'history-focus-diagnostic-contract' })}\n`);
  const run = await newPage({ reducedMotion: 'reduce' });
  await run.page.goto(`${baseUrl}/?view=layers&digital_path=sphere/communication_networks`, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  let diagnosticMessage = '';
  try {
    await waitForAtomicHierarchyFocus(run.page, {
      label: 'history focus diagnostic contract',
      expectedPath: 'sphere/communication_networks',
      activeSelector: '#intentionally-missing-focus-target',
      timeout: 50,
    });
  } catch (error) {
    diagnosticMessage = error.message;
  }
  for (const field of [
    'url',
    'phase',
    'digitalPath',
    'dataVisible',
    'hidden',
    'inert',
    'pendingHierarchyFocusPath',
    'hierarchyFocusAttempt',
    'active',
  ]) {
    assert(diagnosticMessage.includes(field), `history focus diagnostic contract missing ${field}: ${diagnosticMessage}`);
  }
  assert(run.consoleErrors.length === 0, `history focus diagnostic contract: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `history focus diagnostic contract: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'history-focus-diagnostic-contract', verdict: 'PASS' });
  await run.context.close();
}

async function validEmptyDigitalPathScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'valid-empty-digital-path' })}\n`);
  const path = 'sphere/provision_land_ecology/water_irrigation';
  const run = await newPage({ reducedMotion: 'reduce' });
  await run.page.goto(`${baseUrl}/?surface=text&digital_path=${path}`, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction((expectedPath) => document.querySelector('.globe-stage')?.dataset.digitalPath === expectedPath, path);

  const parameters = new URL(run.page.url()).searchParams;
  assert(parameters.get('digital_path') === path, 'valid empty path: canonical URL discarded the taxonomy node');
  assert((await run.page.locator('#text-layer-current').textContent()) === 'Wasser und Bewässerung · 0 Commons', 'valid empty path: current node did not expose its empty state');
  assert((await run.page.locator('.catalog-card:not([hidden])').count()) === 0, 'valid empty path: unrelated Commons leaked into the empty node');
  assert((await run.page.locator('#globe-results').textContent()) === 'Keine Commons entsprechen dieser Suche oder Filterauswahl.', 'valid empty path: semantic empty-state message drifted');
  const currentCrumb = run.page.locator(`#text-layer-breadcrumb .digital-breadcrumb-item[data-digital-path="${path}"][aria-current="page"]`);
  assert(await currentCrumb.isVisible(), 'valid empty path: current breadcrumb is not visible');
  const crumbBox = await currentCrumb.boundingBox();
  assert(crumbBox && crumbBox.width >= 44 && crumbBox.height >= 44, `valid empty path: breadcrumb touch target is undersized (${JSON.stringify(crumbBox)})`);

  const parentPath = 'sphere/provision_land_ecology';
  await run.page.locator(`#text-layer-breadcrumb .digital-breadcrumb-item[data-digital-path="${parentPath}"]`).click();
  await run.page.waitForFunction((expectedPath) => new URL(location.href).searchParams.get('digital_path') === expectedPath, parentPath);
  await run.page.goBack();
  await run.page.waitForFunction((expectedPath) => (
    new URL(location.href).searchParams.get('digital_path') === expectedPath
    && document.activeElement?.matches(`#text-layer-breadcrumb .digital-breadcrumb-item[data-digital-path="${expectedPath}"]`)
    && document.activeElement.getClientRects().length > 0
    && !document.activeElement.closest('[hidden], [inert], [aria-hidden="true"]')
  ), path);
  assert(await currentCrumb.evaluate((node) => node === document.activeElement), 'valid empty path: Back did not restore hierarchy focus to the empty node');
  assert(run.consoleErrors.length === 0, `valid empty path: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `valid empty path: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'valid-empty-digital-path', verdict: 'PASS', pathStable: true, emptyState: true, breadcrumbTouchTarget: true });
  await run.context.close();
}

async function externalLinkSafetyScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'external-link-safety' })}\n`);
  const run = await newPage({ reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.evaluate(() => window.__commonworldInstallSyntheticRecordsForTest([{
    schema_version: 4,
    id: 'link-safety',
    title: 'Link Safety Commons',
    summary: 'Synthetischer Datensatz für die Prüfung externer Kataloglinks.',
    themes: ['communication', 'community-network'],
    actions: ['visit', 'learn', 'donate'],
    presence: {
      geographic: [],
      digital: { available: true, reach: 'global', label: 'Sichere digitale Präsenz' },
    },
    activity: { status: 'active' },
    curation: { state: 'listed', reviewed_at: '2026-07-18', next_review_at: '2027-01-01' },
    links: [
      { type: 'visit', label: 'Sichere Aktion', url: 'https://EXAMPLE.org:443/a/../safe' },
      { type: 'learn', label: 'Zugangsdaten-Link', url: 'https://user:secret@example.org/private' },
      { type: 'donate', label: 'Whitespace-Link', url: ' https://example.org/bad' },
      { type: 'source', label: 'Sichere Quelle', url: 'https://example.org/source' },
    ],
    provenance: {
      sources: [
        { label: 'Beleg', url: 'https://example.org/evidence' },
        { label: 'Unsicherer Beleg', url: 'https://user@example.org/evidence' },
      ],
    },
  }]));

  await run.page.locator('#filter-toggle').click();
  const discoveryLinks = run.page.locator('.discovery-result-actions a');
  assert((await discoveryLinks.count()) === 1, 'external link safety: unsafe action links were rendered');
  assert((await discoveryLinks.first().getAttribute('href')) === 'https://example.org/safe', 'external link safety: safe action URL was not canonicalized');
  await run.page.locator('.discovery-result-main[data-commonproject-id="link-safety"]').click();
  await run.page.waitForSelector('#project-focus:not([hidden])');
  const focusHrefs = await run.page.locator('#focus-links a').evaluateAll((nodes) => nodes.map((node) => node.href));
  assertSameIds(focusHrefs, ['https://example.org/safe', 'https://example.org/source'], 'external link safety: focus links');
  const sourceHrefs = await run.page.locator('#focus-sources a').evaluateAll((nodes) => nodes.map((node) => node.href));
  assertSameIds(sourceHrefs, ['https://example.org/evidence'], 'external link safety: provenance links');
  assert(run.consoleErrors.length === 0, 'external link safety: console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'external link safety: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'external-link-safety', verdict: 'PASS', canonicalHttpsOnly: true });
  await run.context.close();
}

async function syntheticCatalogueTruthScenario() {
  process.stdout.write(`${JSON.stringify({ state: 'RUNNING', scenario: 'synthetic-catalogue-truth' })}\n`);
  for (const size of [500, 5000]) {
    const run = await newPage({ reducedMotion: 'reduce' });
    await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await run.page.waitForSelector('html.runtime-ready');
    await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.publicMapProjectIds !== undefined);
    const installed = await run.page.evaluate((count) => {
      const records = Array.from({ length: count }, (_, index) => ({
        schema_version: 4,
        id: `synthetic-${String(index).padStart(5, '0')}`,
        title: `Synthetic Commons ${index}`,
        summary: 'Gemeinschaftliche synthetische Infrastruktur für die isolierte Runtime-Prüfung.',
        themes: ['communication', 'community-network'],
        actions: ['learn'],
        presence: {
          geographic: [{ id: `place-${index}`, mode: 'exact', label: `Testort ${index}`, geometry: { type: 'Point', coordinates: [8 + (index % 100) / 1000, 50 + (index % 100) / 1000] } }],
          digital: { available: true, reach: 'global', label: 'Synthetische digitale Präsenz' },
        },
        activity: { status: 'active' },
        curation: { state: 'listed', next_review_at: '2027-01-01' },
        links: [],
      }));
      return window.__commonworldInstallSyntheticRecordsForTest(records);
    }, size);
    assert(installed.records === size && installed.treeIdentities === size, `synthetic ${size}: installation lost identities ${JSON.stringify(installed)}`);
    await run.page.waitForFunction((count) => document.querySelector('.globe-stage')?.dataset.publicMapProjectIds === String(count), size);
    const geographicSummary = (await run.page.locator('#globe-results').textContent()) ?? '';
    assert(geographicSummary.startsWith(`${size} Commons in der aktuellen Auswahl. ${size} räumlich öffentlich belegte Commons:`), `synthetic ${size}: identity count is capped ${geographicSummary}`);
    assert(geographicSummary.includes(`${size} Gemeinschaftsnetz`) && geographicSummary.includes('keine Dichteaussage'), `synthetic ${size}: type distribution or coverage boundary is missing ${geographicSummary}`);

    const sphereEdge = run.page.locator('#sphere-edge-control');
    await sphereEdge.focus();
    await run.page.keyboard.press('Enter');
    await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
    await run.page.waitForSelector('#layer-panel[data-visible]:not([inert])');

    const field = run.page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks"]');
    await field.focus();
    await run.page.keyboard.press('Enter');
    await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks');
    const network = run.page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks/community_networks"]');
    await network.focus();
    await run.page.keyboard.press('Enter');
    await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/communication_networks/community_networks');
    await run.page.waitForFunction(() => document.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]').length === 48);
    const initialIds = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
    assert(new Set(initialIds).size === 48, `synthetic ${size}: initial ring identities duplicate`);
    const ringMore = run.page.locator('.identity-show-more');
    const ringMoreBox = await ringMore.boundingBox();
    assert(ringMoreBox && ringMoreBox.height >= 44, `synthetic ${size}: ring continuation touch target is undersized`);
    await ringMore.click();
    await run.page.waitForFunction(() => document.querySelectorAll('.digital-ribbon-item[data-ribbon-copy="0"]').length === 96);
    const continuedIds = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
    assert(new Set(continuedIds).size === 96, `synthetic ${size}: continued ring identities duplicate`);
    assert(await run.page.locator('.identity-show-more').evaluate((node) => node === document.activeElement), `synthetic ${size}: ring continuation lost focus`);

    await run.page.locator('#filter-toggle').click();
    assert((await run.page.locator('.discovery-result').count()) === 50, `synthetic ${size}: discovery preview is not bounded at 50`);
    assert((await run.page.locator('#discovery-count').textContent()) === `50 von ${size} Commons als Vorschau`, `synthetic ${size}: discovery total is not truthful`);
    await run.page.locator('#discovery-show-text').click();
    await run.page.waitForFunction((count) => document.querySelector('#text-count')?.textContent?.startsWith('48 von ' + count + ' Commons angezeigt. ' + count + ' räumlich öffentlich belegte Commons:'), size);
    assert((await run.page.locator('.catalog-card:not([hidden])').count()) === 48, `synthetic ${size}: initial text window is not bounded at 48`);
    const textMoreBox = await run.page.locator('#text-show-more').boundingBox();
    assert(textMoreBox && textMoreBox.height >= 44, `synthetic ${size}: text continuation touch target is undersized`);
    await run.page.locator('#text-show-more').click();
    await run.page.waitForFunction(() => document.querySelectorAll('.catalog-card:not([hidden])').length === 96);
    const textIds = await run.page.locator('.catalog-card:not([hidden])').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
    assert(new Set(textIds).size === 96, `synthetic ${size}: continued text identities duplicate`);
    const continuedTextSummary = (await run.page.locator('#text-count').textContent()) ?? '';
    assert(continuedTextSummary.startsWith('96 von ' + size + ' Commons angezeigt. ' + size + ' räumlich öffentlich belegte Commons:'), 'synthetic ' + size + ': text continuation count drifted ' + continuedTextSummary);
    assert(continuedTextSummary.includes(size + ' Gemeinschaftsnetz') && continuedTextSummary.includes('keine Dichteaussage'), 'synthetic ' + size + ': text view lost map-equivalent type or coverage semantics ' + continuedTextSummary);
    assert(run.pageErrors.length === 0, `synthetic ${size}: page errors: ${run.pageErrors.join(' | ')}`);
    await run.context.close();
  }
  results.push({ id: 'synthetic-catalogue-truth', verdict: 'PASS', sizes: [500, 5000], preview: 48, increment: 48 });
}

async function liveUiHardeningScenario() {
  for (const profile of [
    { id: '320x568', width: 320, height: 568 },
    { id: '390x844', width: 390, height: 844 },
  ]) {
    const run = await newPage({ mobile: true, viewportOverride: { width: profile.width, height: profile.height }, touch: true });
    await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await run.page.waitForSelector('html.runtime-ready');
    await run.page.waitForSelector('.maplibregl-ctrl-attrib a');
    const geometry = await run.page.evaluate(() => {
      const orientation = document.querySelector('.orientation-bar').getBoundingClientRect();
      const attribution = document.querySelector('.maplibregl-ctrl-attrib').getBoundingClientRect();
      const links = [...document.querySelectorAll('.maplibregl-ctrl-attrib a')].map((link) => {
        const rect = link.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {
          label: link.textContent.trim(),
          rect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
          centerHitsLink: hit === link || link.contains(hit),
        };
      });
      return {
        orientation: { top: orientation.top, bottom: orientation.bottom },
        attribution: { top: attribution.top, bottom: attribution.bottom },
        links,
      };
    });
    assert(geometry.attribution.bottom <= geometry.orientation.top - 1, `live UI ${profile.id}: attribution overlaps orientation bar (${JSON.stringify(geometry)})`);
    assert(geometry.links.length >= 4 && geometry.links.every(({ centerHitsLink }) => centerHitsLink), `live UI ${profile.id}: attribution link center is covered (${JSON.stringify(geometry.links)})`);
    assert(run.consoleErrors.length === 0, `live UI ${profile.id}: console errors: ${run.consoleErrors.join(' | ')}`);
    assert(run.pageErrors.length === 0, `live UI ${profile.id}: page errors: ${run.pageErrors.join(' | ')}`);
    await run.context.close();
  }

  const landscapeOverview = await newPage({ mobile: true, viewportOverride: { width: 667, height: 375 }, touch: true, reducedMotion: 'reduce' });
  await landscapeOverview.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await landscapeOverview.page.waitForSelector('html.runtime-ready');
  await landscapeOverview.page.waitForSelector('.maplibregl-ctrl-zoom-in');
  const overviewGeometry = await landscapeOverview.page.evaluate(() => {
    const rect = (node) => {
      const box = node.getBoundingClientRect();
      return {
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
        width: box.width,
        height: box.height,
      };
    };
    const layer = rect(document.querySelector('#layer-view-button'));
    const zoom = rect(document.querySelector('.maplibregl-ctrl-zoom-in'));
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      layer,
      zoom,
      overlap: {
        width: Math.max(0, Math.min(layer.right, zoom.right) - Math.max(layer.left, zoom.left)),
        height: Math.max(0, Math.min(layer.bottom, zoom.bottom) - Math.max(layer.top, zoom.top)),
      },
    };
  });
  const overviewOverlapArea = overviewGeometry.overlap.width * overviewGeometry.overlap.height;
  assert(overviewOverlapArea <= 0.5, `live UI 667x375: digital sphere button overlaps MapLibre zoom control (${JSON.stringify(overviewGeometry)})`);
  assert(
    [overviewGeometry.layer, overviewGeometry.zoom].every(({ left, top, right, bottom, width, height }) => (
      left >= -0.5
      && top >= -0.5
      && right <= overviewGeometry.viewport.width + 0.5
      && bottom <= overviewGeometry.viewport.height + 0.5
      && width >= 44
      && height >= 44
    )),
    `live UI 667x375: landscape control is clipped or undersized (${JSON.stringify(overviewGeometry)})`,
  );
  await landscapeOverview.page.locator('#settings-toggle').click();
  await landscapeOverview.page.waitForSelector('#settings-panel:not([hidden])');
  await landscapeOverview.page.locator('[data-presentation-choice="text"]').click();
  await landscapeOverview.page.waitForSelector('#text-view:not([hidden])');
  const catalogSelectBoxes = await landscapeOverview.page.locator('.catalog-card:not([hidden]) .catalog-select').evaluateAll((nodes) => nodes.map((node) => {
    const box = node.getBoundingClientRect();
    return { width: box.width, height: box.height };
  }));
  assert(catalogSelectBoxes.length > 0, 'live UI 667x375: no visible catalogue selection controls');
  const minimumCatalogSelectHeight = Math.min(...catalogSelectBoxes.map(({ height }) => height));
  assert(catalogSelectBoxes.every(({ width, height }) => width >= 44 && height >= 44), `live UI 667x375: catalogue selection control is undersized (${JSON.stringify(catalogSelectBoxes)})`);
  assert(landscapeOverview.consoleErrors.length === 0, `live UI 667x375: console errors: ${landscapeOverview.consoleErrors.join(' | ')}`);
  assert(landscapeOverview.pageErrors.length === 0, `live UI 667x375: page errors: ${landscapeOverview.pageErrors.join(' | ')}`);
  await landscapeOverview.context.close();

  const run = await newPage({ viewportOverride: { width: 844, height: 390 }, touch: true, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.locator('#layer-view-button').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]:not([inert])');
  await run.page.waitForFunction(({ expectedLaneCount, minimumLaneHeightPx }) => {
    const lanes = [...document.querySelectorAll('.digital-lane')];
    if (lanes.length !== expectedLaneCount) return false;
    return lanes.every((lane) => {
      const focus = lane.querySelector('.digital-lane-focus');
      const scroll = lane.querySelector('.digital-lane-scroll');
      if (!focus || !scroll) return false;
      return lane.getBoundingClientRect().height >= minimumLaneHeightPx
        && focus.getBoundingClientRect().height >= 44
        && scroll.getBoundingClientRect().height >= 44;
    });
  }, {
    expectedLaneCount: expectedDigitalProjection.fields.length,
    minimumLaneHeightPx: MIN_RENDERED_LANE_HEIGHT_PX,
  });
  const layout = await run.page.evaluate(() => {
    const rect = (node) => {
      const box = node.getBoundingClientRect();
      return { top: box.top, bottom: box.bottom, height: box.height };
    };
    const deck = document.querySelector('#layer-track-deck');
    const lanes = [...document.querySelectorAll('.digital-lane')].map((lane) => ({
      lane: rect(lane),
      focus: rect(lane.querySelector('.digital-lane-focus')),
      scroll: rect(lane.querySelector('.digital-lane-scroll')),
    }));
    const overlaps = lanes.slice(0, -1).map((lane, index) => ({
      focus: Math.max(0, lane.focus.bottom - lanes[index + 1].focus.top),
      scroll: Math.max(0, lane.scroll.bottom - lanes[index + 1].scroll.top),
    }));
    const orientation = document.querySelector('.orientation-bar');
    const globeReset = document.querySelector('#globe-reset');
    return {
      deck: { clientHeight: deck.clientHeight, scrollHeight: deck.scrollHeight, overflowY: getComputedStyle(deck).overflowY },
      lanes,
      overlaps,
      orientationInert: orientation.hasAttribute('inert'),
      orientationAriaHidden: orientation.getAttribute('aria-hidden'),
      globeResetSuppressed: Boolean(globeReset.closest('[inert]')),
    };
  });
  assert(layout.lanes.length === expectedDigitalProjection.fields.length, `live UI landscape: unexpected lane count (${JSON.stringify(layout)})`);
  assert(layout.lanes.every(({ lane, focus, scroll }) => lane.height >= MIN_RENDERED_LANE_HEIGHT_PX && focus.height >= 44 && scroll.height >= 44), `live UI landscape: lane controls are clipped (${JSON.stringify(layout.lanes)})`);
  assert(layout.overlaps.every(({ focus, scroll }) => focus <= 0.5 && scroll <= 0.5), `live UI landscape: adjacent controls overlap (${JSON.stringify(layout.overlaps)})`);
  assert(layout.deck.scrollHeight > layout.deck.clientHeight && ['auto', 'scroll'].includes(layout.deck.overflowY), `live UI landscape: compressed lanes did not become vertically scrollable (${JSON.stringify(layout.deck)})`);
  assert(layout.orientationInert && layout.orientationAriaHidden === 'true' && layout.globeResetSuppressed, `live UI landscape: hidden globe orientation remains keyboard interactive (${JSON.stringify(layout)})`);
  assert(run.consoleErrors.length === 0, `live UI landscape: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `live UI landscape: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({
    id: 'live-ui-hardening',
    verdict: 'PASS',
    landscapeOverview: {
      viewport: overviewGeometry.viewport,
      overlapArea: overviewOverlapArea,
      controlGap: overviewGeometry.zoom.left - overviewGeometry.layer.right,
      layerControl: overviewGeometry.layer,
      zoomControl: overviewGeometry.zoom,
      minimumCatalogSelectHeight,
    },
  });
  await run.context.close();
}

async function catalogueNetworkBlockedScenario() {
  const run = await newPage();
  const blockedCatalogRequests = [];
  await run.page.route('**/catalog/**', (route) => {
    blockedCatalogRequests.push(new URL(route.request().url()).pathname);
    return route.abort('failed');
  });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-runtime-state="ready"]');
  assert(blockedCatalogRequests.length === 0, `catalogue network blocked: build-bound runtime requested canonical catalog files: ${blockedCatalogRequests.join(' | ')}`);
  assert(await run.page.locator('.globe-stage').getAttribute('data-catalog-delivery') === 'build-bound-bootstrap', 'catalogue network blocked: runtime delivery mode is not build-bound');
  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForTimeout(220);
  assert((await run.page.locator('#globe-results').textContent())?.startsWith('1 Commons'), 'catalogue network blocked: embedded search did not work');
  await run.page.locator('#settings-toggle').click();
  assert(await run.page.locator('#settings-panel').isVisible(), 'catalogue network blocked: settings are dead');
  await run.page.getByRole('radio', { name: /Text/ }).click();
  assert(await run.page.locator('#text-view').isVisible(), 'catalogue network blocked: text view unavailable');
  assert(await run.page.locator('#project-debian').isVisible(), 'catalogue network blocked: matching static card unavailable');
  assert(run.pageErrors.length === 0, `catalogue network blocked: page errors: ${run.pageErrors.join(' | ')}`);
  assert(run.consoleErrors.length === 0, `catalogue network blocked: unexpected console errors: ${run.consoleErrors.join(' | ')}`);
  const appWarnings = run.consoleWarnings.filter((message) => message.includes('Commonworld'));
  assert(appWarnings.length === 0, `catalogue network blocked: unexpected application warnings (${appWarnings.length})`);
  results.push({ id: 'catalogue-network-blocked', verdict: 'PASS', blockedCatalogRequests: blockedCatalogRequests.length });
  await run.context.close();
}

async function providerFailureScenario() {
  const run = await newPage({ mobile: true });
  await run.page.route('https://tiles.openfreemap.org/**', (route) => route.abort('failed'));
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-runtime-state="degraded"]');
  assert(await run.page.locator('#map-status').isVisible(), 'provider failure: mobile degraded status hidden');
  assert((await run.page.locator('#map-status').textContent())?.includes('Basiskarte'), 'provider failure: degraded status unclear');

  const topbarFit = await run.page.evaluate(() => {
    const topbar = document.querySelector('.topbar');
    const bar = topbar.getBoundingClientRect();
    return {
      viewportWidth: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bar: { top: bar.top, bottom: bar.bottom },
      children: [...topbar.children].map((node) => {
        const rect = node.getBoundingClientRect();
        return { className: node.className, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
      }),
    };
  });
  assert(topbarFit.documentWidth <= topbarFit.viewportWidth + 1, `provider failure: mobile topbar caused horizontal overflow (${JSON.stringify(topbarFit)})`);
  assert(topbarFit.children.every(({ left, right, top, bottom }) => left >= -1 && right <= topbarFit.viewportWidth + 1 && top >= topbarFit.bar.top - 1 && bottom <= topbarFit.bar.bottom + 1), `provider failure: mobile topbar child escaped its single row or viewport (${JSON.stringify(topbarFit)})`);

  const touchSelectors = ['.brand', '.proposal-link', '#settings-toggle', '#globe-reset', '.maplibregl-ctrl-group button'];
  for (const selector of touchSelectors) {
    const boxes = await run.page.locator(selector).evaluateAll((nodes) => nodes.filter((node) => node.getClientRects().length).map((node) => {
      const rect = node.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }));
    assert(boxes.length > 0, `provider failure: no visible touch target for ${selector}`);
    assert(boxes.every(({ width, height }) => width >= 44 && height >= 44), `provider failure: undersized touch target ${selector}: ${JSON.stringify(boxes)}`);
  }

  await run.page.locator('.skip-link').focus();
  await run.page.keyboard.press('Enter');
  assert(await run.page.locator('#text-view').isVisible(), 'provider failure: text fallback unavailable');
  assert(run.pageErrors.length === 0, `provider failure: page errors: ${run.pageErrors.join(' | ')}`);
  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), `provider failure: unexpected console errors: ${run.consoleErrors.join(' | ')}`);
  const appWarnings = run.consoleWarnings.filter((message) => message.includes('Commonworld'));
  assert(appWarnings.length <= 2, `provider failure: application warning storm (${appWarnings.length})`);
  results.push({ id: 'provider-failure', verdict: 'PASS', applicationWarnings: appWarnings.length });
  await run.context.close();
}

async function methodScenario() {
  for (const profile of [
    { id: 'desktop', mobile: false, viewportOverride: { width: 1280, height: 800 }, fontScale: null },
    { id: 'mobile', mobile: true, viewportOverride: { width: 390, height: 844 }, fontScale: null },
    { id: 'mobile-text-200', mobile: true, viewportOverride: { width: 390, height: 844 }, fontScale: 200 },
  ]) {
    const run = await newPage({ mobile: profile.mobile, viewportOverride: profile.viewportOverride });
    if (profile.fontScale) {
      await run.page.route('**/index.css', async (route) => {
        const response = await route.fetch();
        await route.fulfill({ response, body: `${await response.text()}
html { font-size: ${profile.fontScale}% !important; }
` });
      });
    }
    const response = await run.page.goto(`${baseUrl}/method.html`, { waitUntil: 'domcontentloaded' });
    assert(response?.status() === 200, `method ${profile.id}: page is not served`);
    assert((await run.page.locator('h1').textContent()) === 'Methode, Abdeckung und Datenschutz', `method ${profile.id}: heading mismatch`);
    assert((await run.page.locator('main').textContent())?.includes('keine vollständige Weltstatistik'), `method ${profile.id}: coverage boundary missing`);
    const backLink = run.page.locator('.secondary-back-link');
    await backLink.waitFor({ state: 'visible' });
    const backBox = await backLink.boundingBox();
    assert(backBox && backBox.width >= 44 && backBox.height >= 44, `method ${profile.id}: back navigation is an undersized touch target (${JSON.stringify(backBox)})`);
    const overflow = await run.page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert(overflow <= 1, `method ${profile.id}: horizontal overflow ${overflow}`);
    const methodLinkHeights = await run.page.locator('main a').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
    assert(methodLinkHeights.length > 0 && methodLinkHeights.every((height) => height >= 44), `method ${profile.id}: undersized touch link (${JSON.stringify(methodLinkHeights)})`);
    assert(run.consoleErrors.length === 0, `method ${profile.id}: console errors: ${run.consoleErrors.join(' | ')}`);
    assert(run.pageErrors.length === 0, `method ${profile.id}: page errors: ${run.pageErrors.join(' | ')}`);
    results.push({ id: `method-${profile.id}`, verdict: 'PASS' });
    await run.context.close();
  }
}

let scenarioFailure = null;
try {
  await startupAndRingOrbitScenario();
  await reducedMotionRingScenario();
  await syntheticDigitalPerformanceScenario();
  await normalScenario();
  await intentSearchDiscoveryScenario();
  await spatialDiscoveryFiltersScenario();
  await androidGlobeUiScenario();
  await intentSearchLayoutScenario({ viewportOverride: { width: 1024, height: 1366 }, scenarioId: 'intent-search-ipad-portrait' });
  await intentSearchLayoutScenario({ viewportOverride: { width: 1366, height: 1024 }, scenarioId: 'intent-search-ipad-landscape' });
  await dualPresenceAxesScenario();
  await layerJourneyScenario();
  await layerJourneyScenario({ mobile: true });
  await layerJourneyScenario({ viewportOverride: { width: 1024, height: 1366 }, touch: true, scenarioId: 'layer-journey-ipad-portrait' });
  await layerJourneyScenario({ viewportOverride: { width: 1366, height: 1024 }, touch: true, scenarioId: 'layer-journey-ipad-landscape' });
  await moveendBoundReturnScenario();
  await interruptedLayerJourneyScenario();
  await reducedMotionLayerScenario();
  await legacyLayerAndAtomicFocusScenario();
  await historyFocusDiagnosticContractScenario();
  await validEmptyDigitalPathScenario();
  await externalLinkSafetyScenario();
  await syntheticCatalogueTruthScenario();
  await liveUiHardeningScenario();
  await catalogueNetworkBlockedScenario();
  await providerFailureScenario();
  await methodScenario();
} catch (error) {
  scenarioFailure = error;
} finally {
  await browser.close();
  server.closeAllConnections?.();
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}
if (scenarioFailure) {
  const failureResult = {
    verdict: 'FAIL',
    error: scenarioFailure?.stack ?? String(scenarioFailure),
    completedScenarios: results,
  };
  await writeResult(failureResult);
  process.stderr.write(`${JSON.stringify(failureResult)}\n`);
  process.exit(1);
}
const passResult = { verdict: 'PASS', scenarios: results };
await writeResult(passResult);
process.stdout.write(`${JSON.stringify(passResult)}\n`);
process.exit(0);
