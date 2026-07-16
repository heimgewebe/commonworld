import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import { deriveLayer, globeHorizonCoordinates, LAYERS, ringOrbitDuration, sphereOpacityForGlobeRatio } from '../assets/commonworld-core.mjs';

const ROOT = process.cwd();
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
  const byLayer = new Map(LAYERS.map((layer) => [layer.id, []]));
  const allIds = [];
  for (const projectFile of manifest.project_files) {
    const record = JSON.parse(await readFile(path.join(ROOT, 'catalog', projectFile), 'utf8'));
    if (record?.presence?.digital?.available !== true) continue;
    const layerId = deriveLayer(record);
    assert(byLayer.has(layerId), `catalog projection: ${record.id} derived unknown layer ${layerId}`);
    byLayer.get(layerId).push(record.id);
    allIds.push(record.id);
  }
  assert(new Set(allIds).size === allIds.length, `catalog projection: duplicate digital IDs in catalog ${JSON.stringify(allIds)}`);
  return {
    allIds,
    totalCount: allIds.length,
    catalogEntryCount: manifest.entry_count,
    layers: LAYERS.map((layer) => ({
      id: layer.id,
      ids: byLayer.get(layer.id),
      count: byLayer.get(layer.id).length,
    })),
  };
}

const expectedDigitalProjection = await loadExpectedDigitalProjection();

async function newPage({ mobile = false, viewportOverride = null, touch = mobile, reducedMotion = 'reduce' } = {}) {
  const context = await browser.newContext({
    viewport: viewportOverride ?? (mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 }),
    isMobile: mobile,
    hasTouch: touch,
    deviceScaleFactor: 1,
    reducedMotion,
  });
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
              window.__commonworldTestMapOptions = arguments_[0];
              window.__commonworldCameraCommands = [];
              super(...arguments_);
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
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
    if (message.type() === 'warning') consoleWarnings.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  return { context, page, consoleErrors, consoleWarnings, pageErrors };
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
  await run.page.route('**/assets/map/openfreemap-liberty.json', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 650));
    await route.continue();
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

  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.visualReady === 'true');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  assert((await run.page.evaluate(() => window.__commonworldTestMap?.getProjection?.()?.type)) === 'globe', 'startup: active projection changed after map calibration');
  await waitForSphereOpacitySettled(run.page);

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
  assert(rings.length === expectedDigitalProjection.layers.length, `ring orbits: expected canonical ring planes (${rings.length})`);
  const allIds = rings.flatMap(({ ids }) => ids);
  assert(allIds.length === expectedDigitalProjection.totalCount && new Set(allIds).size === expectedDigitalProjection.totalCount, `ring orbits: catalog entries are duplicated or missing across rings (${JSON.stringify(allIds)})`);
  assertSameIds(allIds, expectedDigitalProjection.allIds, 'ring orbits: global digital identity set');
  for (const ring of rings) {
    const expectedLayer = expectedDigitalProjection.layers.find(({ id }) => id === ring.layer);
    assert(expectedLayer, `ring orbits: rendered unknown layer ${ring.layer}`);
    assert(ring.hasGuide, `ring orbits: ${ring.layer} lost its orbit guide`);
    assert(Number.isFinite(ring.entryCount) && ring.entryCount === expectedLayer.count && ring.ids.length === expectedLayer.count, `ring orbits: ${ring.layer} entry count diverges from catalog identities ${JSON.stringify({ ring, expectedLayer })}`);
    assertSameIds(ring.ids, expectedLayer.ids, `ring orbits: ${ring.layer} identity set`);
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

  assert(run.consoleErrors.length === 0, 'startup: console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'startup: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'startup-and-ring-orbits', verdict: 'PASS', directGlobeProjection: true, hiddenUntilCalibrated: true, outerHintRemoved: true, uniqueRingIdentities: allIds.length, movingRingMatrix: movedRing });
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
  assert(rings.length === expectedDigitalProjection.layers.length, `reduced motion rings: expected canonical ring planes (${rings.length})`);
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

  await run.page.locator('.skip-link').focus();
  await run.page.keyboard.press('Enter');
  assert(await run.page.locator('#text-view').isVisible(), 'normal: skip link did not switch to text');
  assert((await run.page.locator('body').getAttribute('data-presentation')) === 'text', 'normal: presentation did not become text');

  await run.page.locator('#settings-toggle').focus();
  await run.page.locator('#settings-toggle').click();
  assert(await run.page.locator('#settings-panel').isVisible(), 'normal: settings panel did not open');
  assert((await run.page.locator('#settings-panel').getAttribute('aria-modal')) === 'false', 'normal: non-modal settings contract changed');
  assert((await run.page.locator('#text-view').getAttribute('inert')) === null, 'normal: settings incorrectly block background navigation');
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#settings-panel').isHidden(), 'normal: settings panel did not close with Escape');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'settings-toggle', 'normal: settings focus was not restored');

  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForTimeout(220);
  const debianTrigger = run.page.locator('#project-debian .catalog-select');
  await debianTrigger.click();
  assert(await run.page.locator('#project-focus').isVisible(), 'normal: project focus did not open');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'project-focus', 'normal: project focus did not receive focus');
  assert(((await run.page.locator('#semantic-summary').textContent()) ?? '') === 'Digital · Ortsunabhängige digitale Präsenz', 'normal: digital-only focus lost its location-independent truth');
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
  assert(overviewRibbons.rings === expectedDigitalProjection.layers.length, `layer journey: overview does not contain all text rings (${JSON.stringify(overviewRibbons)})`);
  assert(overviewRibbons.names.includes('Debian') && overviewRibbons.names.includes('Wikipedia'), `layer journey: Commons names are missing from the rings (${JSON.stringify(overviewRibbons.names)})`);
  assert(overviewRibbons.binaries.some((value) => /^(?:[01]{8})(?: [01]{8})*$/.test(value)), 'layer journey: real bytewise binary names are missing from the rings');
  await waitForSphereOpacitySettled(run.page);
  const opacityBefore = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioBefore = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacityBefore - sphereOpacityForGlobeRatio(ratioBefore)) <= 0.01, `layer journey: initial opacity does not follow visible globe ratio (${opacityBefore} at ${ratioBefore})`);

  const zoomInBox = await run.page.locator('.maplibregl-ctrl-zoom-in').boundingBox();
  assert(zoomInBox, 'layer journey: zoom-in control has no geometry');
  const activateZoomIn = async () => {
    const previousSize = Number(await stage.getAttribute('data-sphere-size'));
    if (mobile) await run.page.touchscreen.tap(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
    else await run.page.mouse.click(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
    await run.page.waitForFunction((size) => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) !== size, previousSize);
    const synchronousGeometry = await run.page.evaluate(() => {
      const stage = document.querySelector('.globe-stage');
      const sphere = document.querySelector('#digital-sphere');
      return {
        rendered: sphere.getBoundingClientRect().width,
        declared: Number(stage.dataset.sphereSize),
        transitionProperty: getComputedStyle(sphere).transitionProperty,
      };
    });
    assert(Math.abs(synchronousGeometry.rendered - synchronousGeometry.declared) <= 2, `layer journey: digital sphere trails the moving globe (${JSON.stringify(synchronousGeometry)})`);
    assert(!synchronousGeometry.transitionProperty.split(',').map((value) => value.trim()).some((value) => ['width', 'height', 'left', 'top'].includes(value)), `layer journey: overview geometry still animates behind the globe (${JSON.stringify(synchronousGeometry)})`);
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
  await run.page.waitForTimeout(500);
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
      sphereOpacity: Number(getComputedStyle(sphereNode).opacity),
      panelVisible: panelNode?.hasAttribute('data-visible') ?? false,
      panelHidden: panelNode?.hidden ?? null,
      commandCount: window.__commonworldCameraCommands?.length ?? 0,
      at: performance.now(),
    });
    window.__commonworldPhaseLog.push(snapshot('initial'));
    window.__commonworldPhaseObserver = new MutationObserver((mutations) => {
      window.__commonworldPhaseLog.push(snapshot(mutations.map((mutation) => `${mutation.target.id || mutation.target.className}:${mutation.attributeName}`).join('|')));
    });
    window.__commonworldPhaseObserver.observe(stageNode, {
      attributes: true,
      attributeFilter: ['data-view-phase', 'data-globe-geometry-source', 'data-layer-panel-visible-at', 'data-last-camera-command', 'data-last-camera-duration'],
    });
    window.__commonworldPhaseObserver.observe(panelNode, {
      attributes: true,
      attributeFilter: ['data-visible', 'hidden', 'data-closing', 'inert'],
    });
  });
  if (touch) await run.page.touchscreen.tap(edgeX, edgeY);
  else await run.page.mouse.click(edgeX, edgeY);
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'entering-layers', 'layer journey: animated entry phase missing');
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'maplibre-projected-horizon', 'layer journey: entering flight abandoned the MapLibre horizon geometry');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the camera flight');
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
  assert(flightComposition.command === 'easeTo' && flightComposition.duration === 1080, 'layer journey: MapLibre is not the single camera authority for the flight ' + JSON.stringify(flightComposition));
  const openingCommands = await run.page.evaluate(() => window.__commonworldCameraCommands ?? []);
  assert(openingCommands.length === 1 && openingCommands[0].command === 'easeTo', `layer journey: opening issued multiple camera commands (${JSON.stringify(openingCommands)})`);
  const enteringSphere = await run.page.locator('#digital-sphere').boundingBox();
  assert(enteringSphere, 'layer journey: transforming sphere is not visible during camera flight');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  const phaseLog = await run.page.evaluate(() => window.__commonworldPhaseLog);
  assert(phaseLog.every((entry) => entry.phase !== 'entering-layers' || entry.source === 'maplibre-projected-horizon'), `layer journey: side layout appeared while the camera was still flying (${JSON.stringify(phaseLog)})`);
  assert(phaseLog.some((entry) => entry.phase === 'settling-layers' && entry.source === 'maplibre-projected-horizon' && entry.moving === false), `layer journey: post-move settling phase is missing or still moving (${JSON.stringify(phaseLog)})`);
  const firstSideEntry = phaseLog.find((entry) => entry.source === 'side-view-layout');
  assert(firstSideEntry && firstSideEntry.phase === 'layers' && firstSideEntry.moving === false && firstSideEntry.sphereOpacity <= 0.1, `layer journey: side layout was not entered after moveend with invisible sphere (${JSON.stringify(firstSideEntry)})`);
  const sideIndex = phaseLog.indexOf(firstSideEntry);
  const firstPanelEntry = phaseLog.find((entry) => entry.panelVisible);
  assert(firstPanelEntry && phaseLog.indexOf(firstPanelEntry) > sideIndex && firstPanelEntry.phase === 'layers' && firstPanelEntry.source === 'side-view-layout', `layer journey: panel became visible before the side layout was stable (${JSON.stringify({ firstPanelEntry, phaseLog })})`);
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout', 'layer journey: settled layers view is missing the side layout geometry');
  await run.page.waitForSelector('#layer-panel[data-visible]');
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
  assert(ribbonView.ringCount === 6 && ribbonView.ringNameCount > 0 && ribbonView.ringBinaryCount > 0, `layer journey: text-ring identity was lost during the flight (${JSON.stringify(ribbonView)})`);
  assert(ribbonView.lanes.length === expectedDigitalProjection.layers.length && ribbonView.lanes.every(({ displayed }) => displayed), `layer journey: multi-lane overview does not show all layers (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ scrollWidth, clientWidth }) => scrollWidth > clientWidth + 20), `layer journey: at least one lane is not horizontally scrollable (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ overflowX }) => ['auto', 'scroll'].includes(overflowX)), `layer journey: native horizontal overflow is disabled (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ touchAction }) => touchAction.includes('pan-x')), `layer journey: touch panning is not explicitly horizontal (${JSON.stringify(ribbonView.lanes)})`);
  for (const lane of ribbonView.lanes) {
    const expectedLayer = expectedDigitalProjection.layers.find(({ id }) => id === lane.layer);
    assert(expectedLayer, `layer journey: rendered unknown lane ${lane.layer}`);
    assertSameIds(lane.primary.map(({ id }) => id), expectedLayer.ids, `layer journey: ${lane.layer} primary identity set`);
  }
  const primarySegments = ribbonView.lanes.flatMap(({ primary }) => primary);
  assert(primarySegments.length === expectedDigitalProjection.totalCount, `layer journey: primary Commons identities were duplicated or lost (${primarySegments.length})`);
  assertSameIds(primarySegments.map(({ id }) => id), expectedDigitalProjection.allIds, 'layer journey: primary digital identity set');
  assert(primarySegments.every(({ name, binary, height }) => name && /^(?:[01]{8})(?: [01]{8})*$/.test(binary) && height >= 44), `layer journey: name/binary pairs or touch heights are invalid (${JSON.stringify(primarySegments)})`);
  assert(ribbonView.filterChildren === expectedDigitalProjection.layers.length, `layer journey: search surface does not contain all layer filters (${ribbonView.filterChildren})`);

  const firstScroller = run.page.locator('.digital-lane-scroll').first();
  const scrollBefore = await firstScroller.evaluate((node) => node.scrollLeft);
  await firstScroller.evaluate((node) => { node.scrollTo({ left: Math.min(node.scrollWidth - node.clientWidth, Math.max(120, node.clientWidth * 0.55)), behavior: 'instant' }); });
  await run.page.waitForTimeout(180);
  const scrollAfter = await firstScroller.evaluate((node) => node.scrollLeft);
  assert(scrollAfter > scrollBefore + 20, `layer journey: multi-lane horizontal scroll did not move (${scrollBefore} -> ${scrollAfter})`);

  const knowledgeFocus = run.page.locator('.digital-lane-focus[data-layer-id="knowledge_data"]');
  await knowledgeFocus.click();
  assert((await stage.getAttribute('data-focused-layer')) === 'knowledge_data', 'layer journey: selecting a lane did not enter single-lane focus');
  const focusedLane = await run.page.evaluate(() => {
    const visible = [...document.querySelectorAll('.digital-lane[data-layer-id]')].filter((lane) => getComputedStyle(lane).display !== 'none');
    const scroller = visible[0]?.querySelector('.digital-lane-scroll');
    return {
      visibleLayers: visible.map((lane) => lane.dataset.layerId),
      clientWidth: scroller?.clientWidth ?? 0,
      scrollWidth: scroller?.scrollWidth ?? 0,
    };
  });
  assert(JSON.stringify(focusedLane.visibleLayers) === JSON.stringify(['knowledge_data']), `layer journey: single-lane focus leaves other lanes visible (${JSON.stringify(focusedLane)})`);
  assert(focusedLane.scrollWidth > focusedLane.clientWidth + 20, `layer journey: focused lane is not horizontally scrollable (${JSON.stringify(focusedLane)})`);
  const focusedScroller = run.page.locator('.digital-lane[data-layer-id="knowledge_data"] .digital-lane-scroll');
  await focusedScroller.evaluate((node) => { node.scrollTo({ left: Math.min(node.scrollWidth - node.clientWidth, Math.max(160, node.clientWidth * 0.7)), behavior: 'instant' }); });
  await run.page.waitForTimeout(180);
  assert((await focusedScroller.evaluate((node) => node.scrollLeft)) > 20, 'layer journey: single-lane horizontal scroll did not move');

  await run.page.locator('#layer-search-toggle').click();
  assert(await run.page.locator('#layer-discovery').isVisible(), 'layer journey: search/filter magnifier did not open');
  assert((await run.page.locator('#layer-buttons .layer-filter').count()) === expectedDigitalProjection.layers.length, 'layer journey: search panel does not expose all lane filters');
  await run.page.locator('#layer-search').fill('Wikipedia');
  await run.page.waitForTimeout(220);
  assert((await run.page.locator('#commons-search').inputValue()) === 'Wikipedia', 'layer journey: lane search is not synchronized with global search');
  const searchedVisible = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]:not([hidden])').count();
  assert(searchedVisible === 1, `layer journey: focused search did not reduce to one visible identity (${searchedVisible})`);
  await run.page.locator('#layer-search').fill('');
  await run.page.waitForTimeout(220);
  await run.page.locator('#layer-search-toggle').click();
  assert(await run.page.locator('#layer-discovery').isHidden(), 'layer journey: search/filter panel did not close');
  await knowledgeFocus.click();
  assert((await stage.getAttribute('data-focused-layer')) === null, 'layer journey: selecting the focused lane did not return to all lanes');

  const directContent = run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]:not([hidden])').first();
  const directTitle = (await directContent.locator('.digital-ribbon-name').textContent()) ?? '';
  const directBox = await directContent.boundingBox();
  assert(directBox && directBox.width >= 44 && directBox.height >= 44, `layer journey: Commons ribbon has an undersized touch target (${JSON.stringify(directBox)})`);
  await directContent.click();
  assert(await run.page.locator('#project-focus').isVisible(), 'layer journey: ribbon content did not open its Commons focus');
  assert((await run.page.locator('#focus-title').textContent()) === directTitle, `layer journey: ribbon opened the wrong Commons identity (${directTitle})`);
  await run.page.locator('#focus-close').click();
  assert(await run.page.locator('#project-focus').isHidden(), 'layer journey: Commons focus did not close');
  assert(await directContent.evaluate((node) => document.activeElement === node), 'layer journey: focus did not return to the same ribbon identity');

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

  await run.page.evaluate(() => {
    window.__commonworldCameraCommands = [];
    window.__commonworldPhaseLog = [];
  });
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="preparing-overview"]');
  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout', 'layer journey: return preparation left side layout too early');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel did not close before return preparation');
  await run.page.waitForSelector('.globe-stage[data-view-phase="leaving-layers"]');
  assert((await stage.getAttribute('data-view-phase')) === 'leaving-layers', 'layer journey: return flight phase missing');
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
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'sphere-edge-control', 'layer journey: focus did not return to the clicked sphere edge');
  assert(run.consoleErrors.length === 0, `layer journey: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `layer journey: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: activeScenarioId, verdict: 'PASS' });
  await run.context.close();
}


async function realHybridCommonsScenario() {
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: 'real-hybrid-commons' }) + '\n');
  const run = await newPage({ viewportOverride: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => {
    const stage = document.querySelector('.globe-stage');
    const map = window.__commonworldTestMap;
    return stage?.dataset.publicMapFeatures === '3'
      && stage?.dataset.publicMapProjectIds === '2'
      && Boolean(map?.getSource('commonworld-public-representations'));
  });

  const initial = await run.page.evaluate(() => {
    const stage = document.querySelector('.globe-stage');
    const map = window.__commonworldTestMap;
    const style = map.getStyle();
    return {
      semanticLevel: stage.dataset.semanticLevel,
      semanticText: document.querySelector('#semantic-summary')?.textContent ?? '',
      featureIds: stage.dataset.publicMapFeatureIds?.split(',').filter(Boolean) ?? [],
      locationIds: stage.dataset.publicMapLocationIds?.split(',').filter(Boolean) ?? [],
      mapUpdateCount: Number(stage.dataset.publicMapUpdates ?? -1),
      sourceType: style.sources?.['commonworld-public-representations']?.type ?? null,
      layers: style.layers
        .filter(({ id }) => id.startsWith('commonworld-'))
        .map(({ id, type, minzoom, maxzoom }) => ({ id, type, minzoom, maxzoom })),
      ringNames: [...document.querySelectorAll('.sphere-ring-name')].map((node) => node.textContent.trim()),
    };
  });
  assert(initial.semanticLevel === 'planet', 'real hybrid: initial semantic level is not planet');
  assert(initial.semanticText.includes('2 räumlich belegte Commons'), 'real hybrid: spatial summary is missing');
  assert(JSON.stringify(initial.featureIds) === JSON.stringify([
    'cltb-le-nid:cltb-le-nid-entrance',
    'cltb-le-nid:cltb-le-nid-building',
    'freifunk-hamburg:freifunk-hamburg-community-area',
  ]), 'real hybrid: public map feature identities differ from reviewed data: ' + JSON.stringify(initial));
  assert(!initial.locationIds.includes('freifunk-hamburg-private-routers'), 'real hybrid: hidden router location leaked into map diagnostics');
  assert(initial.sourceType === 'geojson', 'real hybrid: MapLibre source is not a GeoJSON source: ' + JSON.stringify(initial));
  assert(initial.layers.some(({ id, type, minzoom }) => id === 'commonworld-public-extents' && type === 'fill' && minzoom === 3.4), 'real hybrid: public extent layer missing');
  assert(initial.layers.some(({ id, type, minzoom, maxzoom }) => id === 'commonworld-approximate-zones' && type === 'fill' && minzoom === 3.4 && maxzoom === undefined), 'real hybrid: approximate uncertainty zone must remain visible through local zoom');
  assert(initial.layers.some(({ id, type, minzoom }) => id === 'commonworld-exact-anchors' && type === 'circle' && minzoom === 5.5), 'real hybrid: exact anchor layer missing');
  assert(initial.ringNames.includes('Freifunk Hamburg'), 'real hybrid: hybrid identity missing from digital sphere');
  assert(!initial.ringNames.includes('Le Nid'), 'real hybrid: geographic-only identity leaked into digital sphere');

  await run.page.locator('#sphere-edge-control').focus();
  await run.page.keyboard.press('Enter');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  const digitalPrimaryIds = await run.page.locator('.digital-ribbon-item[data-ribbon-copy="0"]').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));
  assert(digitalPrimaryIds.length === expectedDigitalProjection.totalCount, 'real hybrid: digital lane identity count mismatch: ' + digitalPrimaryIds.length);
  assertSameIds(digitalPrimaryIds, expectedDigitalProjection.allIds, 'real hybrid: digital lane identity set');
  assert(digitalPrimaryIds.includes('freifunk-hamburg'), 'real hybrid: hybrid identity missing from digital lanes');
  assert(!digitalPrimaryIds.includes('cltb-le-nid'), 'real hybrid: geographic-only identity leaked into digital lanes');
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');

  await run.page.locator('#commons-search').fill('Le Nid');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.publicMapFeatures === '2');
  assert((await run.page.locator('.globe-stage').getAttribute('data-public-map-project-ids')) === '1', 'real hybrid: search did not reduce map identities');
  assert((await run.page.locator('#globe-results').textContent())?.includes('1 Commons'), 'real hybrid: shared search count mismatch');
  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.publicMapFeatures === '3');
  await run.page.locator('#discovery-close').click();
  assert(await run.page.locator('#discovery-panel').isHidden(), 'real hybrid: discovery panel blocked map activation');

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

  const updatesBeforeSelection = Number(await run.page.locator('.globe-stage').getAttribute('data-public-map-updates'));
  await activateMapIdentity({
    coordinates: [9.944545738399, 53.558314876911],
    zoom: 4.6,
    layerId: 'commonworld-approximate-zones',
    expectedLevel: 'region',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'real hybrid: approximate map click selected the wrong identity');
  const updatesAfterSelection = Number(await run.page.locator('.globe-stage').getAttribute('data-public-map-updates'));
  assert(updatesAfterSelection === updatesBeforeSelection, 'real hybrid: selecting a project resent unchanged GeoJSON to MapLibre');
  assert((await run.page.locator('#focus-kind').textContent()) === 'Hybrid · Kommunikation und Netze', 'real hybrid: hybrid presentation label mismatch');
  const hamburgLocations = (await run.page.locator('#focus-locations').textContent()) ?? '';
  assert(hamburgLocations.includes('mindestens 5 km Unschärfe') && hamburgLocations.includes('Ort verborgen'), 'real hybrid: approximate and hidden location truth missing');
  assert(((await run.page.locator('#focus-relations').textContent()) ?? '').includes('Teil von Freifunk'), 'real hybrid: evidenced parent relation missing');
  assert((await run.page.locator('.globe-stage').getAttribute('data-semantic-level')) === 'focus', 'real hybrid: selected identity did not enter semantic focus');
  await run.page.locator('#commons-search').fill('Le Nid');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.publicMapFeatures === '2');
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'real hybrid: filtering replaced or cleared the selected identity');
  assert((await run.page.locator('.globe-stage').getAttribute('data-semantic-level')) === 'focus', 'real hybrid: filtered selected identity lost semantic focus');
  assert(((await run.page.locator('#semantic-summary').textContent()) ?? '').startsWith('Hybrid'), 'real hybrid: semantic line no longer describes the filtered selected identity');
  await run.page.locator('#commons-search').fill('');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.publicMapFeatures === '3');
  await run.page.locator('#discovery-close').click();
  await run.page.locator('#focus-close').click();
  assert(await run.page.evaluate(() => document.activeElement === window.__commonworldTestMap?.getCanvas()), 'real hybrid: closing a map-selected focus did not restore focus to the map canvas');
  await activateMapIdentity({
    coordinates: [9.944545738399, 53.558314876911],
    zoom: 6.2,
    layerId: 'commonworld-approximate-zones',
    expectedLevel: 'local',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Freifunk Hamburg', 'real hybrid: local uncertainty-zone click lost the hybrid identity');
  assert(((await run.page.locator('#focus-locations').textContent()) ?? '').includes('mindestens 5 km Unschärfe'), 'real hybrid: local uncertainty zone lost its minimum-radius truth');
  await run.page.locator('#focus-close').click();
  assert(await run.page.evaluate(() => document.activeElement === window.__commonworldTestMap?.getCanvas()), 'real hybrid: local uncertainty-zone focus did not restore map focus');

  await activateMapIdentity({
    coordinates: [4.3152961, 50.8452417],
    zoom: 6.2,
    layerId: 'commonworld-exact-anchors',
    expectedLevel: 'local',
  });
  assert((await run.page.locator('#focus-title').textContent()) === 'Le Nid', 'real hybrid: exact map click selected the wrong identity');
  assert((await run.page.locator('#focus-kind').textContent()) === 'Geografisch', 'real hybrid: geographic presentation label mismatch');
  const leNidLocations = (await run.page.locator('#focus-locations').textContent()) ?? '';
  assert(leNidLocations.includes('exakter öffentlicher Punkt') && leNidLocations.includes('öffentliche Fläche'), 'real hybrid: point and extent truth missing from focus');
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
  assert(renderedExtent, 'real hybrid: reviewed Le Nid public extent is not rendered through MapLibre at building zoom');

  await run.page.locator('#settings-toggle').click();
  await run.page.getByRole('radio', { name: /Text/ }).click();
  assert(await run.page.locator('#text-view').isVisible(), 'real hybrid: text surface did not open');
  assert((await run.page.locator('body').getAttribute('data-presentation')) === 'text', 'real hybrid: presentation state did not become text');
  assert(await run.page.locator('#project-cltb-le-nid[data-selected]').isVisible(), 'real hybrid: text surface lost the selected CommonProject identity');
  assert(run.consoleErrors.length === 0, 'real hybrid: console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'real hybrid: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'real-hybrid-commons', verdict: 'PASS', publicFeatures: 3, publicIdentities: 2, digitalIdentities: expectedDigitalProjection.totalCount, unchangedMapUpdatesSkipped: true });
  await run.context.close();
}



async function intentSearchDiscoveryScenario() {
  process.stdout.write(JSON.stringify({ state: 'RUNNING', scenario: 'intent-search-discovery' }) + '\n');
  const run = await newPage({ viewportOverride: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => {
    const stage = document.querySelector('.globe-stage');
    return stage?.dataset.searchIndexedRecords === '12'
      && Number(stage?.dataset.searchIndexedTerms ?? 0) > 0
      && Boolean(window.__commonworldTestMap);
  });

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
  const resultIds = () => run.page.locator('.discovery-result').evaluateAll((nodes) => nodes.map((node) => node.dataset.commonprojectId));

  await run.page.locator('#commons-search').fill('ich möchte mitmachen');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 9);
  assert(await run.page.locator('#discovery-panel').isVisible(), 'intent search: result panel did not open');
  assert(JSON.stringify(await resultIds()) === JSON.stringify([
    'debian',
    'freifunk',
    'freifunk-hamburg',
    'libreoffice',
    'mastodon',
    'openstreetmap',
    'wikidata',
    'wikimedia-commons',
    'wikipedia',
  ]), 'intent search: German contribution ranking differs from the derived index');
  assert((await run.page.locator('#discovery-count').textContent()) === '9 Commons', 'intent search: ranked count mismatch');

  await run.page.locator('#commons-search').focus();
  await run.page.keyboard.press('ArrowDown');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === 'debian', 'intent search: ArrowDown did not focus the first result');
  await run.page.keyboard.press('ArrowDown');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === 'freifunk', 'intent search: result ArrowDown did not advance');
  await run.page.keyboard.press('End');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === 'wikipedia', 'intent search: End did not focus the last result');
  await run.page.keyboard.press('Home');
  assert((await run.page.evaluate(() => document.activeElement?.closest('.discovery-result')?.dataset.commonprojectId)) === 'debian', 'intent search: Home did not return to the first result');

  await run.page.waitForFunction(() => Boolean(window.__commonworldTestMap) && !window.__commonworldTestMap.isMoving());
  const queryCamera = await mapCamera();
  await run.page.locator('#commons-search').fill('Anderlecht');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['cltb-le-nid']), 'intent search: public place did not resolve to Le Nid');
  assert(sameCamera(queryCamera, await mapCamera()), 'intent search: typing a place moved the map before activation');

  await run.page.locator('#commons-search').fill('private heimrouter');
  await run.page.waitForFunction(() => document.querySelector('#discovery-empty')?.hidden === false);
  assert((await resultIds()).length === 0, 'intent search: hidden router information leaked into results');
  await run.page.locator('#commons-search').fill('quantenbanane-xyz');
  await run.page.waitForFunction(() => document.querySelector('#globe-results')?.hasAttribute('data-empty'));
  assert(await run.page.locator('#discovery-empty').isVisible(), 'intent search: empty result state is missing');
  assert(await run.page.locator('#discovery-list').isHidden(), 'intent search: empty result list remains exposed');

  await run.page.locator('#commons-search').fill('');
  await run.page.waitForTimeout(220);
  await run.page.waitForFunction(() => Boolean(window.__commonworldTestMap) && !window.__commonworldTestMap.isMoving());
  const filterCamera = await mapCamera();
  await run.page.locator('#filter-presence').selectOption('hybrid');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['freifunk-hamburg']), 'intent filters: hybrid presence did not preserve the CommonProject identity');
  assert(new URL(run.page.url()).searchParams.get('presence') === 'hybrid', 'intent filters: presence was not serialized');
  await run.page.locator('#filter-action').selectOption('volunteer');
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('action') === 'volunteer');
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['freifunk-hamburg']), 'intent filters: combined action and presence changed identity semantics');
  assert(sameCamera(filterCamera, await mapCamera()), 'intent filters: changing filters moved the map');

  const actionTypes = await run.page.locator('.discovery-result-actions a').evaluateAll((links) => links.map((link) => link.dataset.actionType));
  assert(JSON.stringify(actionTypes) === JSON.stringify(['use', 'learn', 'contribute', 'volunteer', 'contact']), 'intent actions: direct Freifunk Hamburg actions differ from the catalog');
  const actionTargets = await run.page.locator('.discovery-result-actions a').evaluateAll((links) => links.map((link) => link.href));
  assert(actionTargets.every((href) => href.startsWith('https://')), 'intent actions: a direct action target is not HTTPS');

  await run.page.goBack({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction(() => document.querySelector('#filter-presence')?.value === 'hybrid' && document.querySelector('#filter-action')?.value === '');
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['freifunk-hamburg']), 'intent history: Back did not restore the previous filter context');
  await run.page.goForward({ waitUntil: 'domcontentloaded' });
  await run.page.waitForFunction(() => document.querySelector('#filter-action')?.value === 'volunteer');
  assert(JSON.stringify(await resultIds()) === JSON.stringify(['freifunk-hamburg']), 'intent history: Forward did not restore the combined filter context');

  await run.page.locator('#filter-clear').click();
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 12);
  assert([...new URL(run.page.url()).searchParams.keys()].every((key) => !['presence', 'action', 'language', 'access', 'freshness', 'curation'].includes(key)), 'intent filters: reset left filter parameters in the URL');

  const digitalCamera = await mapCamera();
  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  await run.page.locator('.discovery-result-main').click();
  await run.page.waitForSelector('#project-focus:not([hidden])');
  assert((await run.page.locator('#focus-title').textContent()) === 'Debian', 'intent spatial: digital result did not open Debian');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-spatial-result')) === 'coordinate-free:debian', 'intent spatial: digital result was not kept coordinate-free');
  assert(sameCamera(digitalCamera, await mapCamera()), 'intent spatial: digital result moved the map');
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
  await run.page.waitForTimeout(220);
  await run.page.locator('#filter-presence').selectOption('hybrid');
  await run.page.waitForFunction(() => document.querySelectorAll('.discovery-result').length === 1);
  await run.page.locator('#discovery-close').click();
  await run.page.locator('#settings-toggle').click();
  await run.page.getByRole('radio', { name: /Text/ }).click();
  const visibleTextIds = await run.page.locator('.catalog-card:not([hidden])').evaluateAll((cards) => cards.map((card) => card.dataset.commonprojectId));
  assert(JSON.stringify(visibleTextIds) === JSON.stringify(['freifunk-hamburg']), 'intent parity: text view does not preserve the globe filter context');
  const staticActionTypes = await run.page.locator('#project-freifunk-hamburg .catalog-action-link').evaluateAll((links) => links.map((link) => link.dataset.actionType));
  assert(JSON.stringify(staticActionTypes) === JSON.stringify(['use', 'learn', 'contribute', 'volunteer', 'contact']), 'intent parity: static text actions differ from ranked result actions');

  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), 'intent search: unexpected console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, 'intent search: page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: 'intent-search-discovery', verdict: 'PASS', indexedRecords: expectedDigitalProjection.catalogEntryCount, rankedGermanIntentResults: 9, filters: 6, digitalCoordinateFree: true, spatialNavigation: true });
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
  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), scenarioId + ': unexpected console errors: ' + run.consoleErrors.join(' | '));
  assert(run.pageErrors.length === 0, scenarioId + ': page errors: ' + run.pageErrors.join(' | '));
  results.push({ id: scenarioId, verdict: 'PASS', minimumControlHeight: geometry.minimumControlHeight });
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
  await run.page.goto(`${baseUrl}/?view=layers&lng=13.4&lat=52.5&z=1.2`, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.lastCameraCommand === 'jumpTo');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-camera-command')) === 'jumpTo', 'reduced motion: layer camera did not jump');
  assert((await run.page.locator('.globe-stage').getAttribute('data-last-camera-duration')) === '0', 'reduced motion: nonzero layer duration');
  await run.page.locator('#layer-close').click();
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'overview', 'reduced motion: return was not immediate');
  const search = new URL(run.page.url()).searchParams;
  assert(search.get('view') === null, 'reduced motion: closed layer view persisted');
  assert(Math.abs(Number(search.get('lng')) - 13.4) < 0.01, `reduced motion: overview longitude changed (${search.get('lng')})`);
  assert(Math.abs(Number(search.get('lat')) - 52.5) < 0.01, `reduced motion: overview latitude changed (${search.get('lat')})`);
  assert(run.pageErrors.length === 0, `reduced motion: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'layer-journey-reduced-motion', verdict: 'PASS' });
  await run.context.close();
}

async function catalogueFailureScenario() {
  const run = await newPage();
  await run.page.route('**/catalog/catalog.json', (route) => route.abort('failed'));
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForSelector('.globe-stage[data-runtime-state="degraded"]');
  await run.page.locator('#commons-search').fill('Debian');
  await run.page.waitForTimeout(220);
  assert((await run.page.locator('#globe-results').textContent())?.startsWith('1 Commons'), 'catalogue failure: embedded search did not work');
  await run.page.locator('#settings-toggle').click();
  assert(await run.page.locator('#settings-panel').isVisible(), 'catalogue failure: settings are dead');
  await run.page.getByRole('radio', { name: /Text/ }).click();
  assert(await run.page.locator('#text-view').isVisible(), 'catalogue failure: text view unavailable');
  assert(await run.page.locator('#project-debian').isVisible(), 'catalogue failure: matching static card unavailable');
  assert(run.pageErrors.length === 0, `catalogue failure: page errors: ${run.pageErrors.join(' | ')}`);
  assert(run.consoleErrors.every((message) => message.includes('Failed to load resource')), `catalogue failure: unexpected console errors: ${run.consoleErrors.join(' | ')}`);
  const appWarnings = run.consoleWarnings.filter((message) => message.includes('Commonworld'));
  assert(appWarnings.length <= 2, `catalogue failure: application warning storm (${appWarnings.length})`);
  results.push({ id: 'catalogue-failure', verdict: 'PASS', applicationWarnings: appWarnings.length });
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

  const touchSelectors = ['.brand', '#settings-toggle', '#globe-reset', '.maplibregl-ctrl-group button'];
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
  const run = await newPage();
  const response = await run.page.goto(`${baseUrl}/method.html`, { waitUntil: 'domcontentloaded' });
  assert(response?.status() === 200, 'method: page is not served');
  assert((await run.page.locator('h1').textContent()) === 'Methode, Abdeckung und Datenschutz', 'method: heading mismatch');
  assert((await run.page.locator('main').textContent())?.includes('keine vollständige Weltstatistik'), 'method: coverage boundary missing');
  assert(run.consoleErrors.length === 0, `method: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `method: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'method', verdict: 'PASS' });
  await run.context.close();
}

try {
  await startupAndRingOrbitScenario();
  await reducedMotionRingScenario();
  await normalScenario();
  await intentSearchDiscoveryScenario();
  await intentSearchLayoutScenario({ viewportOverride: { width: 1024, height: 1366 }, scenarioId: 'intent-search-ipad-portrait' });
  await intentSearchLayoutScenario({ viewportOverride: { width: 1366, height: 1024 }, scenarioId: 'intent-search-ipad-landscape' });
  await realHybridCommonsScenario();
  await layerJourneyScenario();
  await layerJourneyScenario({ mobile: true });
  await layerJourneyScenario({ viewportOverride: { width: 1024, height: 1366 }, touch: true, scenarioId: 'layer-journey-ipad-portrait' });
  await layerJourneyScenario({ viewportOverride: { width: 1366, height: 1024 }, touch: true, scenarioId: 'layer-journey-ipad-landscape' });
  await moveendBoundReturnScenario();
  await interruptedLayerJourneyScenario();
  await reducedMotionLayerScenario();
  await catalogueFailureScenario();
  await providerFailureScenario();
  await methodScenario();
} finally {
  await browser.close();
  server.closeAllConnections?.();
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}
process.stdout.write(`${JSON.stringify({ verdict: 'PASS', scenarios: results })}\n`);
process.exit(0);
