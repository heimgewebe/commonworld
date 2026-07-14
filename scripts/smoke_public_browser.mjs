import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import { globeHorizonCoordinates, sphereOpacityForGlobeRatio } from '../assets/commonworld-core.mjs';

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
              super(...arguments_);
              window.__commonworldTestMap = this;
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

async function normalScenario() {
  const run = await newPage();
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  assert(await run.page.locator('#globe-surface').isVisible(), 'normal: globe is not visible');
  assert((await run.page.locator('#globe-results').textContent())?.includes('10 Commons'), 'normal: result count missing');

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
  await run.page.locator('#commons-search').focus();
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'commons-search', 'normal: project focus incorrectly blocks background navigation');
  await run.page.keyboard.press('Escape');
  assert(await run.page.locator('#project-focus').isHidden(), 'normal: project focus did not close with Escape');
  assert(await debianTrigger.evaluate((node) => document.activeElement === node), 'normal: project focus did not restore its trigger');

  await run.page.locator('#commons-search').fill('kein-solches-commons');
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
  assert(overviewRibbons.rings === 6, `layer journey: overview does not contain six text rings (${JSON.stringify(overviewRibbons)})`);
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
  if (touch) await run.page.touchscreen.tap(edgeX, edgeY);
  else await run.page.mouse.click(edgeX, edgeY);
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'entering-layers', 'layer journey: animated entry phase missing');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the camera flight');
  const enteringSphere = await run.page.locator('#digital-sphere').boundingBox();
  assert(enteringSphere, 'layer journey: transforming sphere is not visible during camera flight');
  await run.page.waitForFunction(() => ['layers-preview', 'layers'].includes(document.querySelector('.globe-stage')?.dataset.viewPhase));
  const observedPhase = await stage.getAttribute('data-view-phase');
  if (observedPhase === 'layers-preview') {
    assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel appeared at the exact end of the camera flight');
    assert(await run.page.locator('#layer-panel').getAttribute('inert') !== null, 'layer journey: hidden description panel became interactive before reveal');
    assert((await run.page.locator('#layer-panel').getAttribute('data-visible')) === null, 'layer journey: panel visible marker appeared before the visual pause');
    const settledSphere = await run.page.locator('#digital-sphere').boundingBox();
    assert(settledSphere, 'layer journey: transformed text sphere is missing during the panel-free pause');
  }
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  await run.page.waitForFunction(() => Number(getComputedStyle(document.querySelector('#digital-sphere')).opacity) <= 0.1);
  assert(await run.page.locator('#layer-panel').isVisible(), 'layer journey: description panel did not fade in after the panel-free pause');
  assert(await run.page.locator('#layer-panel').getAttribute('inert') === null, 'layer journey: revealed description panel remains inert');
  const panelTiming = await run.page.locator('.globe-stage').evaluate((node) => ({
    preview: Number(node.dataset.layerPreviewStartedAt),
    visible: Number(node.dataset.layerPanelVisibleAt),
  }));
  assert(Number.isFinite(panelTiming.preview) && Number.isFinite(panelTiming.visible) && panelTiming.visible - panelTiming.preview >= 240, `layer journey: panel-free preview was too short (${JSON.stringify(panelTiming)})`);
  const mapOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(mapOpacity <= 0.02, `layer journey: globe remains visible beside layers (${mapOpacity})`);
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
  assert(ribbonView.lanes.length === 6 && ribbonView.lanes.every(({ displayed }) => displayed), `layer journey: multi-lane overview does not show all six layers (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ scrollWidth, clientWidth }) => scrollWidth > clientWidth + 20), `layer journey: at least one lane is not horizontally scrollable (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ overflowX }) => ['auto', 'scroll'].includes(overflowX)), `layer journey: native horizontal overflow is disabled (${JSON.stringify(ribbonView.lanes)})`);
  assert(ribbonView.lanes.every(({ touchAction }) => touchAction.includes('pan-x')), `layer journey: touch panning is not explicitly horizontal (${JSON.stringify(ribbonView.lanes)})`);
  const primarySegments = ribbonView.lanes.flatMap(({ primary }) => primary);
  assert(primarySegments.length === 10, `layer journey: primary Commons identities were duplicated or lost (${primarySegments.length})`);
  assert(primarySegments.every(({ name, binary, height }) => name && /^(?:[01]{8})(?: [01]{8})*$/.test(binary) && height >= 44), `layer journey: name/binary pairs or touch heights are invalid (${JSON.stringify(primarySegments)})`);
  assert(ribbonView.filterChildren === 6, `layer journey: search surface does not contain all six layer filters (${ribbonView.filterChildren})`);

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
  assert((await run.page.locator('#layer-buttons .layer-filter').count()) === 6, 'layer journey: search panel does not expose all lane filters');
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

  const returnMarkerBefore = await stage.getAttribute('data-layer-return-started-at');
  await run.page.locator('#layer-close').click();
  await run.page.waitForFunction((previous) => {
    const current = document.querySelector('.globe-stage')?.dataset.layerReturnStartedAt;
    return Boolean(current && current !== previous);
  }, returnMarkerBefore);
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the return camera flight');
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  const restoredOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(restoredOpacity >= 0.98, `layer journey: globe did not return (${restoredOpacity})`);
  assert(await run.page.locator('#map').getAttribute('inert') === null, 'layer journey: returned globe remains inert');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '0', 'layer journey: sphere trigger was not restored');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'sphere-edge-control', 'layer journey: focus did not return to the clicked sphere edge');
  assert(run.consoleErrors.length === 0, `layer journey: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `layer journey: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: activeScenarioId, verdict: 'PASS' });
  await run.context.close();
}


async function delayedReturnTransitionScenario() {
  const run = await newPage({ reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  await run.page.waitForTimeout(820);
  const sphereBox = await run.page.locator('#digital-sphere').boundingBox();
  assert(sphereBox, 'delayed return: sphere geometry missing');
  await run.page.mouse.click(sphereBox.x + sphereBox.width * 0.85134, sphereBox.y + sphereBox.height * 0.14866);
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  await run.page.locator('#map').evaluate((node) => { node.style.transitionDuration = '10s'; });
  const startedAt = Date.now();
  await run.page.locator('#layer-close').click();
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  const elapsed = Date.now() - startedAt;
  const restoredOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(elapsed >= 1800, `delayed return: fallback was not exercised (${elapsed}ms)`);
  assert(restoredOpacity >= 0.98, `delayed return: overview was declared before the globe returned (${restoredOpacity})`);
  assert(await run.page.locator('#map').getAttribute('inert') === null, 'delayed return: returned globe remains inert');
  assert(run.consoleErrors.length === 0, `delayed return: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `delayed return: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: 'layer-journey-delayed-return', verdict: 'PASS', elapsedMs: elapsed });
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
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'leaving-layers', 'interrupted journey: escape did not reverse the camera');
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
  await normalScenario();
  await layerJourneyScenario();
  await layerJourneyScenario({ mobile: true });
  await layerJourneyScenario({ viewportOverride: { width: 1024, height: 1366 }, touch: true, scenarioId: 'layer-journey-ipad-portrait' });
  await layerJourneyScenario({ viewportOverride: { width: 1366, height: 1024 }, touch: true, scenarioId: 'layer-journey-ipad-landscape' });
  await delayedReturnTransitionScenario();
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
