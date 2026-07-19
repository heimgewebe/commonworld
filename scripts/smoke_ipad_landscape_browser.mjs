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
if (!address || typeof address === 'string') throw new Error('ipad landscape smoke server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || (existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);
const browser = await chromium.launch({ headless: true, executablePath });
const results = [];

// Realistic iPad landscape CSS-pixel geometries covered by the ipad-layout.css breakpoint:
// iPad Air / 10.9" (1180x820), iPad Pro 11" (1194x834), iPad 9th gen / iPad mini (1024x768).
const IPAD_LANDSCAPE_VIEWPORTS = [
  { name: 'ipad-air-landscape', width: 1180, height: 820 },
  { name: 'ipad-pro11-landscape', width: 1194, height: 834 },
  { name: 'ipad-9gen-landscape', width: 1024, height: 768 },
];

for (const viewport of IPAD_LANDSCAPE_VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: true,
    hasTouch: true,
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));

  // 1. propose.html must scroll vertically instead of being clipped by the global body overflow:hidden rule.
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  const scrollInfo = await page.evaluate(() => ({
    scrollHeight: document.documentElement.scrollHeight,
    clientHeight: document.documentElement.clientHeight,
    bodyOverflowY: getComputedStyle(document.body).overflowY,
    horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  assert(scrollInfo.scrollHeight > scrollInfo.clientHeight, `${viewport.name}: propose.html content is not taller than the viewport, scroll cannot be exercised (${JSON.stringify(scrollInfo)})`);
  assert(scrollInfo.bodyOverflowY === 'auto' || scrollInfo.bodyOverflowY === 'scroll', `${viewport.name}: propose.html body overflow-y is "${scrollInfo.bodyOverflowY}", expected scrollable`);
  assert(scrollInfo.horizontalOverflow <= 1, `${viewport.name}: propose.html has horizontal overflow ${scrollInfo.horizontalOverflow}`);
  await page.mouse.wheel(0, 4000);
  await page.waitForTimeout(150);
  const scrolledY = await page.evaluate(() => window.scrollY || document.documentElement.scrollTop);
  assert(scrolledY > 200, `${viewport.name}: propose.html did not actually scroll after a wheel gesture (scrollY ${scrolledY})`);
  const submitButton = page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' });
  await submitButton.scrollIntoViewIfNeeded();
  assert(await submitButton.isVisible(), `${viewport.name}: submit button unreachable by scroll`);
  assert(pageErrors.length === 0, `${viewport.name}: propose.html page errors ${pageErrors.join('; ')}`);

  // 2. index.html discovery presence filter must be compact, side-by-side and keep >=44px touch targets.
  await page.goto(`${baseUrl}/index.html`, { waitUntil: 'networkidle' });
  await page.locator('#filter-toggle').click();
  await page.locator('#discovery-panel').waitFor({ state: 'visible' });
  const presenceGeometry = await page.evaluate(() => {
    const fieldset = document.querySelector('.filter-presence-group');
    const options = [...document.querySelectorAll('.filter-presence-options label')];
    const siblingLabel = document.querySelector('.intent-filter-grid > label:has(select)');
    const fieldsetRect = fieldset.getBoundingClientRect();
    const siblingRect = siblingLabel.getBoundingClientRect();
    return {
      fieldsetHeight: fieldsetRect.height,
      siblingHeight: siblingRect.height,
      options: options.map((node) => {
        const rect = node.getBoundingClientRect();
        return { top: rect.top, width: rect.width, height: rect.height };
      }),
    };
  });
  assert(presenceGeometry.options.length === 2, `${viewport.name}: presence filter does not expose exactly two options (${JSON.stringify(presenceGeometry.options)})`);
  const [first, second] = presenceGeometry.options;
  assert(Math.abs(first.top - second.top) < 1, `${viewport.name}: presence options are stacked instead of side-by-side (${JSON.stringify(presenceGeometry.options)})`);
  assert(presenceGeometry.options.every((option) => option.height >= 44), `${viewport.name}: presence option touch target below 44px (${JSON.stringify(presenceGeometry.options)})`);
  assert(presenceGeometry.fieldsetHeight <= presenceGeometry.siblingHeight + 1, `${viewport.name}: presence filter (${presenceGeometry.fieldsetHeight}px) is taller than a sibling filter cell (${presenceGeometry.siblingHeight}px)`);
  await page.locator('#discovery-close').click();

  // 3. The digital ring search panel must be wide, horizontally centered and fully inside the viewport.
  await page.locator('#layer-view-button').click();
  await page.locator('#layer-panel').waitFor({ state: 'visible' });
  await page.waitForTimeout(300);
  await page.locator('#layer-search-toggle').click();
  await page.locator('#layer-discovery').waitFor({ state: 'visible' });
  const layerDiscoveryBox = await page.locator('#layer-discovery').boundingBox();
  assert(layerDiscoveryBox, `${viewport.name}: #layer-discovery has no bounding box`);
  assert(layerDiscoveryBox.x >= 0 && layerDiscoveryBox.x + layerDiscoveryBox.width <= viewport.width + 1, `${viewport.name}: layer-discovery panel overflows the viewport horizontally ${JSON.stringify(layerDiscoveryBox)}`);
  const discoveryCenter = layerDiscoveryBox.x + layerDiscoveryBox.width / 2;
  const viewportCenter = viewport.width / 2;
  assert(Math.abs(discoveryCenter - viewportCenter) <= 4, `${viewport.name}: layer-discovery panel is not horizontally centered (panel center ${discoveryCenter}, viewport center ${viewportCenter})`);
  assert(layerDiscoveryBox.width >= viewport.width * 0.4, `${viewport.name}: layer-discovery panel is too narrow (${layerDiscoveryBox.width}px on a ${viewport.width}px viewport)`);
  const layerSearchInputBox = await page.locator('#layer-search').boundingBox();
  assert(layerSearchInputBox.width >= layerDiscoveryBox.width * 0.85, `${viewport.name}: digital ring search input is not near full width (input ${layerSearchInputBox.width}px, panel ${layerDiscoveryBox.width}px)`);
  await page.locator('#layer-search-toggle').click();

  // 4. Drilling into a leaf digital subcategory must yield a compact, in-viewport focused lane.
  await page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks"]').click();
  await page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks/community_networks"]').click();
  await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.focusedPath === 'sphere/communication_networks/community_networks');
  await page.waitForTimeout(300);
  const focusedLaneBox = await page.locator('.digital-lane.is-focused').boundingBox();
  const deckBox = await page.locator('#layer-track-deck').boundingBox();
  assert(focusedLaneBox, `${viewport.name}: focused digital lane has no bounding box`);
  assert(focusedLaneBox.height <= viewport.height * 0.45, `${viewport.name}: focused digital lane is excessively tall (${focusedLaneBox.height}px on a ${viewport.height}px viewport)`);
  assert(focusedLaneBox.y >= deckBox.y - 1 && focusedLaneBox.y + focusedLaneBox.height <= deckBox.y + deckBox.height + 1, `${viewport.name}: focused digital lane is torn apart from the track deck ${JSON.stringify({ focusedLaneBox, deckBox })}`);
  assert(focusedLaneBox.y + focusedLaneBox.height <= viewport.height, `${viewport.name}: focused digital lane overflows the viewport bottom (${focusedLaneBox.y + focusedLaneBox.height}px on a ${viewport.height}px viewport)`);
  const laneLabel = page.locator('.digital-lane.is-focused .digital-lane-focus');
  const laneContent = page.locator('.digital-lane.is-focused .digital-lane-scroll');
  assert(await laneLabel.isVisible(), `${viewport.name}: focused lane label is not visible`);
  assert(await laneContent.isVisible(), `${viewport.name}: focused lane content is not visible`);
  const labelBox = await laneLabel.boundingBox();
  const contentBox = await laneContent.boundingBox();
  assert(Math.abs(labelBox.y - contentBox.y) <= focusedLaneBox.height * 0.15, `${viewport.name}: focused lane label and content are not visually cohesive ${JSON.stringify({ labelBox, contentBox })}`);

  assert(pageErrors.length === 0, `${viewport.name}: index.html page errors ${pageErrors.join('; ')}`);
  results.push(viewport.name);
  await context.close();
}

await browser.close();
await new Promise((resolve) => server.close(resolve));
console.log(JSON.stringify({ status: 'pass', scenarios: results }, null, 2));
