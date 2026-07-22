import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { normalizeBootstrapForCompile } from './catalog_delivery_compile.mjs';

const ROOT = process.cwd();
const CPU_THROTTLE_RATE = 4;
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

function safePath(url) {
  const pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname);
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const target = path.resolve(ROOT, relative);
  if (target !== ROOT && !target.startsWith(`${ROOT}${path.sep}`)) return null;
  return { target, relative };
}

const server = createServer(async (request, response) => {
  try {
    const resolved = safePath(request.url ?? '/');
    if (!resolved || !(await stat(resolved.target)).isFile()) {
      response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end('not found');
      return;
    }
    response.writeHead(200, {
      'Content-Type': MIME.get(path.extname(resolved.target)) ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    response.end(await readFile(resolved.target));
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
if (!address || typeof address === 'string') throw new Error('benchmark server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  || (existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);
const browser = await chromium.launch({ headless: true, executablePath });
const bootstrapSource = await readFile(path.join(ROOT, 'assets/commonworld-bootstrap-catalog.mjs'), 'utf8');
const normalizedBootstrapSource = normalizeBootstrapForCompile(bootstrapSource);

function metricMap(metrics) {
  return Object.fromEntries(metrics.metrics.map(({ name, value }) => [name, value]));
}

async function measureProfile(profile) {
  const context = await browser.newContext({
    viewport: profile.viewport,
    deviceScaleFactor: profile.deviceScaleFactor ?? 1,
    isMobile: profile.isMobile ?? false,
    hasTouch: profile.hasTouch ?? false,
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Performance.enable');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU_THROTTLE_RATE });

  const firstPartyRequests = [];
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === baseUrl) await route.continue();
    else await route.abort('blockedbyclient');
  });
  page.on('requestfinished', (request) => {
    const url = new URL(request.url());
    if (url.origin === baseUrl) firstPartyRequests.push(url.pathname);
  });

  const startedAt = Date.now();
  await page.goto(baseUrl, { waitUntil: 'load', timeout: 30_000 });
  await page.waitForFunction(() => document.documentElement.classList.contains('runtime-ready'), null, { timeout: 30_000 });
  const runtimeReadyMs = Date.now() - startedAt;
  try {
    await page.waitForLoadState('networkidle', { timeout: 10_000 });
  } catch {
    // The provider fallback may keep browser-level work alive; local requests are still recorded.
  }
  await page.waitForTimeout(750);

  const performanceMetrics = metricMap(await cdp.send('Performance.getMetrics'));
  const pageMetrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0];
    return {
      dom_node_count: document.querySelectorAll('*').length,
      catalog_card_count: document.querySelectorAll('.catalog-card').length,
      interactive_catalog_card_count: document.querySelectorAll('.catalog-select').length,
      runtime_ready: document.documentElement.classList.contains('runtime-ready'),
      runtime_failed: document.documentElement.classList.contains('runtime-failed'),
      dom_content_loaded_ms: navigation?.domContentLoadedEventEnd ?? null,
      load_event_ms: navigation?.loadEventEnd ?? null,
      resource_count: performance.getEntriesByType('resource').length,
    };
  });
  const compileSamples = await page.evaluate((normalized) => {
    new Function(normalized);
    const samples = [];
    for (let index = 0; index < 21; index += 1) {
      const start = performance.now();
      new Function(normalized);
      samples.push(performance.now() - start);
    }
    samples.sort((left, right) => left - right);
    return {
      median_ms: samples[Math.floor(samples.length / 2)],
      p95_ms: samples[Math.floor(samples.length * 0.95)],
      samples_ms: samples,
    };
  }, normalizedBootstrapSource);

  const uniqueRequests = [...new Set(firstPartyRequests)].sort();
  const requestSizes = {};
  const firstPartySurfaceHash = createHash('sha256');
  for (const pathname of uniqueRequests) {
    const resolved = safePath(pathname);
    if (!resolved) continue;
    const bytes = await readFile(resolved.target);
    requestSizes[pathname] = bytes.length;
    firstPartySurfaceHash.update(pathname, 'utf8');
    firstPartySurfaceHash.update('\0', 'utf8');
    firstPartySurfaceHash.update(bytes);
    firstPartySurfaceHash.update('\0', 'utf8');
  }
  const projectJsonRequests = firstPartyRequests.filter((pathname) => pathname.startsWith('/catalog/projects/') && pathname.endsWith('.json'));
  const result = {
    profile: profile.name,
    viewport: profile.viewport,
    cpu_throttle_rate: CPU_THROTTLE_RATE,
    runtime_ready_ms: runtimeReadyMs,
    ...pageMetrics,
    script_duration_ms: Math.round((performanceMetrics.ScriptDuration ?? 0) * 1000 * 100) / 100,
    task_duration_ms: Math.round((performanceMetrics.TaskDuration ?? 0) * 1000 * 100) / 100,
    bootstrap_compile: compileSamples,
    first_party_request_count: firstPartyRequests.length,
    first_party_unique_request_count: uniqueRequests.length,
    first_party_raw_bytes: Object.values(requestSizes).reduce((sum, value) => sum + value, 0),
    first_party_requests: uniqueRequests,
    first_party_surface_sha256: firstPartySurfaceHash.digest('hex'),
    project_json_request_count: projectJsonRequests.length,
    project_json_unique_request_count: new Set(projectJsonRequests).size,
    project_json_requests: [...new Set(projectJsonRequests)].sort(),
  };
  await context.close();
  return result;
}

const outputIndex = process.argv.indexOf('--output');
const outputPath = outputIndex >= 0 ? process.argv[outputIndex + 1] : null;
if (outputIndex >= 0 && !outputPath) throw new Error('--output requires a path');

try {
  const profiles = [
    { name: 'mobile-low-power', viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    { name: 'desktop-low-power', viewport: { width: 1366, height: 768 } },
  ];
  const measurements = [];
  for (const profile of profiles) measurements.push(await measureProfile(profile));
  const payload = `${JSON.stringify({
    schema_version: 1,
    kind: 'commonworld_catalog_delivery_browser_metrics',
    measured_at: new Date().toISOString(),
    cpu_throttle_rate: CPU_THROTTLE_RATE,
    profiles: measurements,
  }, null, 2)}\n`;
  if (outputPath) await writeFile(outputPath, payload, 'utf8');
  process.stdout.write(payload);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
