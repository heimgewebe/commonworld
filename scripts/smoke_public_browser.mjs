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

async function newPage({ mobile = false } = {}) {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 },
    isMobile: mobile,
    hasTouch: mobile,
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
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
  await catalogueFailureScenario();
  await providerFailureScenario();
  await methodScenario();
  process.stdout.write(`${JSON.stringify({ verdict: 'PASS', scenarios: results })}\n`);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
