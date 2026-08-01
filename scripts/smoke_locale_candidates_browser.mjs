import { createServer } from 'node:http';
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
const CANDIDATES = Object.freeze([
  { locale: 'es', direction: 'ltr', pages: ['es.html', 'method.es.html', 'propose.es.html'] },
  { locale: 'fr', direction: 'ltr', pages: ['fr.html', 'method.fr.html', 'propose.fr.html'] },
  { locale: 'pt-BR', direction: 'ltr', pages: ['pt-BR.html', 'method.pt-BR.html', 'propose.pt-BR.html'] },
  { locale: 'ar', direction: 'rtl', pages: ['ar.html', 'method.ar.html', 'propose.ar.html'] },
]);
const CANDIDATE_SOURCE = JSON.parse(
  await readFile(path.join(ROOT, 'assets/locales/wave1-candidates.json'), 'utf8'),
);

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
      response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' });
      response.end('not found');
      return;
    }
    response.writeHead(200, {
      'Content-Type': MIME.get(path.extname(target)) ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    response.end(await readFile(target));
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' });
    response.end('not found');
  }
});

await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
const address = server.address();
if (!address || typeof address === 'string') throw new Error('locale candidate smoke server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined;
const browser = await chromium.launch({
  headless: true,
  executablePath: executablePath,
  args: ['--enable-unsafe-swiftshader'],
});
const results = [];
const releasedIsolation = [];

try {
  for (const pageName of ['index.html', 'de.html']) {
    const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const candidatePackRequests = [];
    const pageErrors = [];
    page.on('request', (request) => {
      if (request.url().includes('/assets/commonworld-wave1-locales.mjs')) {
        candidatePackRequests.push(request.url());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));
    const response = await page.goto(`${baseUrl}/${pageName}`, { waitUntil: 'domcontentloaded' });
    assert(response?.status() === 200, `${pageName}: HTTP ${response?.status()}`);
    await page.waitForSelector('html.runtime-ready', { timeout: 30_000 });
    assert(pageErrors.length === 0, `${pageName}: page errors: ${pageErrors.join(' | ')}`);
    assert(candidatePackRequests.length === 0, `${pageName}: loaded hidden Wave-1 candidate pack: ${candidatePackRequests.join(' | ')}`);
    releasedIsolation.push({ page: pageName, candidatePackRequests: 0, verdict: 'PASS' });
    await context.close();
  }

  for (const candidate of CANDIDATES) {
    for (const pageName of candidate.pages) {
      const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
      const page = await context.newPage();
      const pageErrors = [];
      const consoleErrors = [];
      const failedResponses = [];
      page.on('pageerror', (error) => pageErrors.push(error.message));
      page.on('response', (networkResponse) => {
        if (networkResponse.status() < 400) return;
        const failedUrl = networkResponse.url();
        const expectedProbe = /\/(?:releases\/(?:current|[0-9a-f]{20})|__cw_probe\/[^/]+)\//u.test(failedUrl);
        if (!expectedProbe && !failedUrl.endsWith('/favicon.ico')) {
          failedResponses.push(`${networkResponse.status()} ${failedUrl}`);
        }
      });
      page.on('console', (message) => {
        if (message.type() !== 'error') return;
        if (message.text().startsWith('Failed to load resource:')) return;
        consoleErrors.push(`${message.text()} @ ${message.location()?.url ?? ''}`);
      });
      const response = await page.goto(`${baseUrl}/${pageName}`, { waitUntil: 'domcontentloaded' });
      assert(response?.status() === 200, `${pageName}: HTTP ${response?.status()}`);
      if (!pageName.startsWith('method.') && !pageName.startsWith('propose.')) {
        await page.waitForSelector('html.runtime-ready', { timeout: 30_000 });
      }
      let proposalRuntimeError = '';
      if (pageName.startsWith('propose.')) {
        const expectedRuntimeError = CANDIDATE_SOURCE.locales[candidate.locale].proposal_runtime['Automated submission blocked.'];
        await page.locator('input[name=website_confirm]').fill('bot');
        await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
        await page.waitForSelector('#proposal-errors:not([hidden])');
        proposalRuntimeError = (await page.locator('#proposal-errors').textContent()) ?? '';
        assert(proposalRuntimeError.includes(expectedRuntimeError), `${pageName}: candidate proposal runtime message drifted: ${proposalRuntimeError}`);
        assert(!proposalRuntimeError.includes('[missing:proposal_runtime:'), `${pageName}: proposal runtime fallback marker rendered`);
      }
      let runtimeCatalogBoundary = null;
      if (pageName === `${candidate.locale}.html`) {
        runtimeCatalogBoundary = await page.evaluate(async () => {
          const card = document.querySelector('.catalog-card[data-commonproject-id]');
          const button = card?.querySelector('.catalog-select');
          const staticTitle = card?.querySelector('h2')?.textContent ?? '';
          const staticSummary = card?.querySelector('h2 + p')?.textContent ?? '';
          const staticKind = card?.querySelector('.catalog-kind')?.textContent ?? '';
          const expectedPresence = staticKind.split(' · ').slice(1).join(' · ');
          button?.click();
          const deadline = performance.now() + 10_000;
          while ((document.querySelector('#focus-title')?.textContent ?? '') !== staticTitle) {
            if (performance.now() > deadline) throw new Error('candidate runtime focus did not open');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          return {
            staticTitle,
            staticSummary,
            expectedPresence,
            focusTitle: document.querySelector('#focus-title')?.textContent ?? '',
            focusSummary: document.querySelector('#focus-summary')?.textContent ?? '',
            focusTitleLang: document.querySelector('#focus-title')?.lang ?? '',
            focusSummaryLang: document.querySelector('#focus-summary')?.lang ?? '',
            focusPresence: document.querySelector('#focus-presence')?.textContent ?? '',
          };
        });
      }
      const state = await page.evaluate(() => ({
        lang: document.documentElement.lang,
        dir: document.documentElement.dir,
        robots: document.querySelector('meta[name="robots"]')?.content ?? '',
        description: document.querySelector('meta[name="description"]')?.content ?? '',
        titleCount: document.querySelectorAll('head > title').length,
        documentTitle: document.title,
        iconHref: document.querySelector('link[rel~="icon"]')?.getAttribute('href') ?? '',
        bannerVisible: Boolean(document.querySelector('.locale-candidate-banner')?.getClientRects().length),
        bodyText: document.body.textContent ?? '',
        candidateChoices: [...document.querySelectorAll('[data-locale-choice]')]
          .map((node) => node.getAttribute('data-locale-choice'))
          .filter((value) => ['es', 'fr', 'pt-BR', 'ar'].includes(value)),
        releasedChoices: [...document.querySelectorAll('[data-locale-choice]')]
          .map((node) => node.getAttribute('data-locale-choice'))
          .filter((value) => ['en', 'de'].includes(value)),
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        englishContentBlocks: document.querySelectorAll('[lang="en"]').length,
      }));
      assert(state.lang === candidate.locale, `${pageName}: lang drifted to ${state.lang}`);
      assert(state.dir === candidate.direction, `${pageName}: dir drifted to ${state.dir}`);
      assert(state.robots === 'noindex,nofollow', `${pageName}: candidate robots contract missing`);
      assert(state.description.trim().length > 0, `${pageName}: candidate description metadata is malformed`);
      assert(state.titleCount === 1 && state.documentTitle.trim().length > 0, `${pageName}: candidate title metadata is malformed`);
      assert(state.iconHref.includes('commonworld-mark.svg'), `${pageName}: candidate head swallowed the icon link`);
      assert(state.bannerVisible, `${pageName}: candidate banner is not visible`);
      const missingMarkers = state.bodyText.match(/\[missing:[^\]]+\]/gu) ?? [];
      assert(missingMarkers.length === 0, `${pageName}: missing translation marker rendered: ${missingMarkers.slice(0, 8).join(' | ')}`);
      assert(state.candidateChoices.length === 0, `${pageName}: candidate locale became selectable`);
      assert(JSON.stringify([...new Set(state.releasedChoices)].sort()) === JSON.stringify(['de', 'en']), `${pageName}: released locale choices drifted`);
      assert(state.documentWidth <= state.viewportWidth + 1, `${pageName}: horizontal overflow ${state.documentWidth}/${state.viewportWidth}`);
      if (pageName === `${candidate.locale}.html`) {
        assert(state.englishContentBlocks > 0, `${pageName}: canonical English catalog content lacks lang=en boundaries`);
        assert(runtimeCatalogBoundary?.focusTitle === runtimeCatalogBoundary?.staticTitle, `${pageName}: runtime title fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.focusSummary === runtimeCatalogBoundary?.staticSummary, `${pageName}: runtime summary fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.focusTitleLang === 'en' && runtimeCatalogBoundary?.focusSummaryLang === 'en', `${pageName}: runtime English content lacks lang=en boundaries`);
        const candidatePack = CANDIDATE_SOURCE.locales[candidate.locale];
        const focusPresence = runtimeCatalogBoundary?.focusPresence ?? '';
        const staticPresence = runtimeCatalogBoundary?.expectedPresence ?? '';
        const expectsGeographic = staticPresence.includes(candidatePack.ui.presence_geographic)
          || staticPresence.includes(candidatePack.ui.presence_both);
        const expectsDigital = staticPresence.includes(candidatePack.ui.presence_digital)
          || staticPresence.includes(candidatePack.ui.presence_both);
        if (expectsGeographic) assert(focusPresence.includes(candidatePack.ui.presence_geographic), `${pageName}: runtime geographic presence is not candidate-localized: ${focusPresence}`);
        if (expectsDigital) assert(focusPresence.includes(candidatePack.ui.presence_digital), `${pageName}: runtime digital presence is not candidate-localized: ${focusPresence}`);
        const taxonomyLabels = new Set(Object.values(candidatePack.taxonomy));
        const taxonomyPath = focusPresence.split(' · ').slice((expectsGeographic ? 1 : 0) + (expectsDigital ? 1 : 0)).join(' · ');
        for (const label of taxonomyPath.split(' › ').filter(Boolean)) {
          assert(taxonomyLabels.has(label), `${pageName}: runtime taxonomy label is not candidate-localized: ${label} / ${focusPresence}`);
        }
      }
      assert(pageErrors.length === 0, `${pageName}: page errors: ${pageErrors.join(' | ')}`);
      assert(failedResponses.length === 0, `${pageName}: failed resources: ${failedResponses.join(' | ')}`);
      assert(consoleErrors.length === 0, `${pageName}: console errors: ${consoleErrors.join(' | ')}`);
      results.push({ page: pageName, locale: candidate.locale, direction: candidate.direction, proposalRuntimeLocalized: pageName.startsWith('propose.'), verdict: 'PASS' });
      await context.close();
    }
  }
  console.log(JSON.stringify({ verdict: 'PASS', pages: results.length, releasedIsolation, results }, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
