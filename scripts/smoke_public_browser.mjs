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
    return !map.isMoving() && Number.isFinite(globeDiameter) && globeDiameter > 0 && Math.abs(sphereWidth - globeDiameter * 1.18) <= 2;
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
  assert(Math.abs(before.width - declaredBefore * 1.18) <= 2, `layer journey: outer shell ratio is wrong (${before.width} vs ${declaredBefore})`);
  await waitForSphereOpacitySettled(run.page);
  const opacityBefore = Number(await run.page.locator('#digital-sphere').evaluate((node) => getComputedStyle(node).opacity));
  const ratioBefore = Number(await stage.getAttribute('data-globe-viewport-ratio'));
  assert(Math.abs(opacityBefore - sphereOpacityForGlobeRatio(ratioBefore)) <= 0.01, `layer journey: initial opacity does not follow visible globe ratio (${opacityBefore} at ${ratioBefore})`);

  const zoomInBox = await run.page.locator('.maplibregl-ctrl-zoom-in').boundingBox();
  assert(zoomInBox, 'layer journey: zoom-in control has no geometry');
  const activateZoomIn = async () => {
    if (mobile) await run.page.touchscreen.tap(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
    else await run.page.mouse.click(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
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
    assert(Math.abs(restoredScale.width - declaredZoomOut * 1.18) <= 2, `layer journey: zoom-out lost outer-shell ratio (${restoredScale.width} vs ${declaredZoomOut})`);
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
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers-preview"]');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel appeared at the exact end of the camera flight');
  assert(await run.page.locator('#layer-panel').getAttribute('inert') !== null, 'layer journey: hidden description panel became interactive before reveal');
  assert((await run.page.locator('#layer-panel').getAttribute('data-visible')) === null, 'layer journey: panel visible marker appeared before the visual pause');
  const settledSphere = await run.page.locator('#digital-sphere').boundingBox();
  assert(settledSphere, 'layer journey: transformed layers are missing during the panel-free pause');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  await run.page.waitForSelector('#layer-panel[data-visible]');
  assert(await run.page.locator('#layer-panel').isVisible(), 'layer journey: description panel did not fade in after the panel-free pause');
  assert(await run.page.locator('#layer-panel').getAttribute('inert') === null, 'layer journey: revealed description panel remains inert');
  const panelTiming = await run.page.locator('.globe-stage').evaluate((node) => ({
    preview: Number(node.dataset.layerPreviewStartedAt),
    visible: Number(node.dataset.layerPanelVisibleAt),
  }));
  assert(Number.isFinite(panelTiming.preview) && Number.isFinite(panelTiming.visible) && panelTiming.visible - panelTiming.preview >= 500, `layer journey: panel-free preview was too short (${JSON.stringify(panelTiming)})`);
  const mapOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(mapOpacity <= 0.02, `layer journey: globe remains visible beside layers (${mapOpacity})`);
  assert(await run.page.locator('#map').getAttribute('inert') !== null, 'layer journey: invisible globe remains keyboard reachable');
  assert((await run.page.locator('#map').getAttribute('aria-hidden')) === 'true', 'layer journey: invisible globe remains in the accessibility tree');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '-1', 'layer journey: old sphere trigger remains reachable inside side view');
  const panelBox = await run.page.locator('#layer-panel').boundingBox();
  const viewport = run.page.viewportSize();
  assert(panelBox && viewport && panelBox.width >= viewport.width - 1, `layer journey: layer surface is not full width (${JSON.stringify(panelBox)})`);
  const tangentView = await run.page.evaluate(() => {
    const sphere = document.querySelector('#digital-sphere').getBoundingClientRect();
    const rings = [...document.querySelectorAll('#sphere-rings use')].map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
    });
    const visibleLabels = [...document.querySelectorAll('.sphere-label[data-commonproject-id]')].flatMap((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      const intersects = rect.right > 0 && rect.left < innerWidth && rect.bottom > 0 && rect.top < innerHeight;
      return intersects && Number(style.opacity) > 0.2
        ? [{ id: node.dataset.commonprojectId, layer: node.dataset.layerId, width: rect.width, height: rect.height }]
        : [];
    });
    return {
      viewport: { width: innerWidth, height: innerHeight },
      sphere: { left: sphere.left, right: sphere.right, top: sphere.top, bottom: sphere.bottom, width: sphere.width, height: sphere.height },
      rings,
      visibleLabels,
      stackChildren: document.querySelector('#layer-stack-visual').childElementCount,
      projectChildren: document.querySelector('#layer-projects').childElementCount,
      filterChildren: document.querySelector('#layer-buttons').childElementCount,
    };
  });
  assert(tangentView.sphere.width > tangentView.viewport.width * 2, `layer journey: camera did not zoom into the sphere (${JSON.stringify(tangentView.sphere)})`);
  assert(tangentView.sphere.left < -tangentView.viewport.width * 0.45 && tangentView.sphere.right > tangentView.viewport.width * 1.45, `layer journey: full rings could still fit inside the viewport (${JSON.stringify(tangentView.sphere)})`);
  assert(tangentView.sphere.top < tangentView.viewport.height * 0.3 && tangentView.sphere.bottom > tangentView.viewport.height * 2, `layer journey: sphere is not cropped as a close tangent view (${JSON.stringify(tangentView.sphere)})`);
  assert(tangentView.rings.every(({ left, right, bottom }) => left < 0 && right > tangentView.viewport.width && bottom > tangentView.viewport.height), `layer journey: a complete ring remains visible (${JSON.stringify(tangentView.rings)})`);
  assert(tangentView.visibleLabels.length >= 3, `layer journey: overview contents did not remain visible on the enlarged tracks (${JSON.stringify(tangentView.visibleLabels)})`);
  assert(new Set(tangentView.visibleLabels.map(({ layer }) => layer)).size >= 3, `layer journey: close-up does not expose multiple content tracks (${JSON.stringify(tangentView.visibleLabels)})`);
  assert(tangentView.visibleLabels.every(({ height }) => height >= 18), `layer journey: close-up contents did not become legible (${JSON.stringify(tangentView.visibleLabels)})`);
  assert(tangentView.stackChildren === 0 && tangentView.projectChildren === 0 && tangentView.filterChildren === 0, `layer journey: substitute labels, cards or filters remain in the spatial view (${JSON.stringify(tangentView)})`);
  const directContent = run.page.locator('.sphere-label[data-commonproject-id="debian"]');
  await directContent.click();
  assert(await run.page.locator('#project-focus').isVisible(), 'layer journey: enlarged track content did not open its Commons focus');
  assert((await run.page.locator('#focus-title').textContent()) === 'Debian', 'layer journey: enlarged track opened the wrong Commons identity');
  await run.page.locator('#focus-close').click();
  assert(await run.page.locator('#project-focus').isHidden(), 'layer journey: Commons focus did not close');
  assert(await directContent.evaluate((node) => document.activeElement === node), 'layer journey: focus did not return to the same content track');
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

  await run.page.locator('#layer-close').click();
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'leaving-layers', 'layer journey: return phase missing');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the return camera flight');
  await run.page.waitForSelector('.globe-stage[data-view-phase="overview"]');
  const restoredOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(restoredOpacity >= 0.98, `layer journey: globe did not return (${restoredOpacity})`);
  assert(await run.page.locator('#map').getAttribute('inert') === null, 'layer journey: returned globe remains inert');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '0', 'layer journey: sphere trigger was not restored');
  assert((await run.page.evaluate(() => document.activeElement?.id)) === 'sphere-edge-control', 'layer journey: focus did not return to the clicked sphere edge');
  assert(run.consoleErrors.length === 0, `layer journey: console errors: ${run.consoleErrors.join(' | ')}`);
  assert(run.pageErrors.length === 0, `layer journey: page errors: ${run.pageErrors.join(' | ')}`);
  results.push({ id: scenarioId ?? (mobile ? 'layer-journey-mobile' : 'layer-journey-desktop'), verdict: 'PASS' });
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
  process.stdout.write(`${JSON.stringify({ verdict: 'PASS', scenarios: results })}\n`);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
