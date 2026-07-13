import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';

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

async function newPage({ mobile = false, reducedMotion = 'reduce' } = {}) {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 },
    isMobile: mobile,
    hasTouch: mobile,
    deviceScaleFactor: 1,
    reducedMotion,
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


async function layerJourneyScenario({ mobile = false } = {}) {
  const run = await newPage({ mobile, reducedMotion: 'no-preference' });
  await run.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await run.page.waitForSelector('html.runtime-ready');
  await run.page.waitForFunction(() => Number(document.querySelector('.globe-stage')?.dataset.sphereSize ?? 0) > 0);
  await run.page.waitForTimeout(820);

  const before = await run.page.locator('#digital-sphere').boundingBox();
  assert(before, 'layer journey: sphere has no initial geometry');
  const zoomInBox = await run.page.locator('.maplibregl-ctrl-zoom-in').boundingBox();
  assert(zoomInBox, 'layer journey: zoom-in control has no geometry');
  if (mobile) await run.page.touchscreen.tap(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
  else await run.page.mouse.click(zoomInBox.x + zoomInBox.width / 2, zoomInBox.y + zoomInBox.height / 2);
  await run.page.waitForTimeout(520);
  const afterZoom = await run.page.locator('#digital-sphere').boundingBox();
  assert(afterZoom && afterZoom.width > before.width * 1.18, `layer journey: sphere did not scale with globe zoom (${before.width} -> ${afterZoom?.width})`);
  const zoomOutBox = await run.page.locator('.maplibregl-ctrl-zoom-out').boundingBox();
  assert(zoomOutBox, 'layer journey: zoom-out control has no geometry');
  if (mobile) await run.page.touchscreen.tap(zoomOutBox.x + zoomOutBox.width / 2, zoomOutBox.y + zoomOutBox.height / 2);
  else await run.page.mouse.click(zoomOutBox.x + zoomOutBox.width / 2, zoomOutBox.y + zoomOutBox.height / 2);
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'overview', 'layer journey: scaled sphere stole the zoom-out control and opened layers');
  await run.page.waitForFunction((targetWidth) => {
    const width = document.querySelector('#digital-sphere')?.getBoundingClientRect().width ?? 0;
    return Math.abs(width - targetWidth) <= 2;
  }, before.width);
  const restoredScale = await run.page.locator('#digital-sphere').boundingBox();
  assert(restoredScale && Math.abs(restoredScale.width - before.width) <= 2, `layer journey: sphere scale did not return with globe zoom (${before.width} -> ${restoredScale?.width})`);
  const mapBox = await run.page.locator('#map').boundingBox();
  assert(mapBox, 'layer journey: map has no geometry');
  await run.page.mouse.move(mapBox.x + mapBox.width * 0.55, mapBox.y + mapBox.height * 0.52);
  await run.page.mouse.down();
  await run.page.mouse.move(mapBox.x + mapBox.width * 0.7, mapBox.y + mapBox.height * 0.52, { steps: 8 });
  await run.page.mouse.up();
  await run.page.waitForTimeout(180);
  const afterRotation = await run.page.locator('#digital-sphere').boundingBox();
  assert(afterRotation, 'layer journey: sphere disappeared after rotation');
  assert(Math.abs(afterRotation.width - before.width) <= 1, `layer journey: sphere extent changed on rotation (${before.width} -> ${afterRotation.width})`);

  const sphereBox = await run.page.locator('#digital-sphere').boundingBox();
  assert(sphereBox, 'layer journey: clickable sphere geometry missing');
  if (mobile) await run.page.touchscreen.tap(sphereBox.x + sphereBox.width * 0.93125, sphereBox.y + sphereBox.height * 0.5);
  else await run.page.mouse.click(sphereBox.x + sphereBox.width * 0.93125, sphereBox.y + sphereBox.height * 0.5);
  assert((await run.page.locator('.globe-stage').getAttribute('data-view-phase')) === 'entering-layers', 'layer journey: animated entry phase missing');
  assert(await run.page.locator('#layer-panel').isHidden(), 'layer journey: description panel obscures the camera flight');
  const enteringSphere = await run.page.locator('#digital-sphere').boundingBox();
  assert(enteringSphere, 'layer journey: transforming sphere is not visible during camera flight');
  await run.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  assert(await run.page.locator('#layer-panel').isVisible(), 'layer journey: description panel did not appear after camera flight');
  const mapOpacity = Number(await run.page.locator('#map').evaluate((node) => getComputedStyle(node).opacity));
  assert(mapOpacity <= 0.02, `layer journey: globe remains visible beside layers (${mapOpacity})`);
  assert(await run.page.locator('#map').getAttribute('inert') !== null, 'layer journey: invisible globe remains keyboard reachable');
  assert((await run.page.locator('#map').getAttribute('aria-hidden')) === 'true', 'layer journey: invisible globe remains in the accessibility tree');
  assert((await run.page.locator('#sphere-edge-control').getAttribute('tabindex')) === '-1', 'layer journey: old sphere trigger remains reachable inside side view');
  const panelBox = await run.page.locator('#layer-panel').boundingBox();
  const viewport = run.page.viewportSize();
  assert(panelBox && viewport && panelBox.width >= viewport.width - 1, `layer journey: layer surface is not full width (${JSON.stringify(panelBox)})`);
  const transformedRing = await run.page.locator('#sphere-rings use').first().evaluate((node) => getComputedStyle(node).transform);
  assert(transformedRing !== 'none', 'layer journey: source ring did not transform into a side-view ellipse');
  assert(await run.page.locator('.layer-stack-item').first().isVisible(), 'layer journey: side-view labels missing');
  const alignment = await run.page.evaluate(() => [...document.querySelectorAll('#sphere-rings use')].map((ring, index) => {
    const ringRect = ring.getBoundingClientRect();
    const labelRect = document.querySelectorAll('.layer-stack-item')[index].getBoundingClientRect();
    return Math.abs((ringRect.top + ringRect.height / 2) - (labelRect.top + labelRect.height / 2));
  }));
  assert(alignment.every((delta) => delta <= 42), `layer journey: labels no longer belong to their source rings (${JSON.stringify(alignment)})`);
  const viewportFit = await run.page.evaluate(() => ({
    viewportWidth: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    controls: [...document.querySelectorAll('#layer-panel button')].filter((node) => node.getClientRects().length).map((node) => {
      const rect = node.getBoundingClientRect();
      return { id: node.id || node.textContent.trim(), width: rect.width, height: rect.height };
    }),
  }));
  assert(viewportFit.documentWidth <= viewportFit.viewportWidth + 1, `layer journey: horizontal overflow (${JSON.stringify(viewportFit)})`);
  if (mobile) assert(viewportFit.controls.every(({ width, height }) => width >= 44 && height >= 44), `layer journey: undersized mobile layer control (${JSON.stringify(viewportFit.controls)})`);

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
  results.push({ id: mobile ? 'layer-journey-mobile' : 'layer-journey-desktop', verdict: 'PASS' });
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
  await run.page.mouse.click(sphereBox.x + sphereBox.width * 0.93125, sphereBox.y + sphereBox.height * 0.5);
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
