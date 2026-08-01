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
      const rtlPluginRequests = [];
      page.on('pageerror', (error) => pageErrors.push(error.message));
      page.on('request', (request) => {
        if (request.url().includes('/assets/vendor/mapbox-gl-rtl-text.js')) rtlPluginRequests.push(request.url());
      });
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
        if (pageName === 'ar.html') {
          await page.waitForFunction(
            () => window.maplibregl?.getRTLTextPluginStatus?.() === 'loaded',
            { timeout: 30_000 },
          );
        }
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
          const staticTitleNode = card?.querySelector('h2');
          const staticSummaryNode = card?.querySelector('h2 + p');
          const staticTitle = staticTitleNode?.textContent ?? '';
          const staticSummary = staticSummaryNode?.textContent ?? '';
          const staticTitleDir = staticTitleNode?.getAttribute('dir') ?? '';
          const staticSummaryDir = staticSummaryNode?.getAttribute('dir') ?? '';
          const staticKind = card?.querySelector('.catalog-kind')?.textContent ?? '';
          const expectedPresence = staticKind.split(' · ').slice(1).join(' · ');
          const sphereNameNodes = [...document.querySelectorAll('.sphere-ring-name')];
          const sphereSummaryTitleNodes = [...document.querySelectorAll('#sphere-ring-accessible-summary span[lang]')];
          const sphereNameLangs = sphereNameNodes.map((node) => node.getAttribute('lang') ?? '');
          const sphereNameDirs = sphereNameNodes.map((node) => node.getAttribute('dir') ?? '');
          const sphereSummaryTitleLangs = sphereSummaryTitleNodes.map((node) => node.getAttribute('lang') ?? '');
          const sphereSummaryTitleDirs = sphereSummaryTitleNodes.map((node) => node.getAttribute('dir') ?? '');
          const sphereAccessibleText = document.querySelector('#sphere-ring-accessible-summary')?.textContent ?? '';
          button?.click();
          const deadline = performance.now() + 10_000;
          while ((document.querySelector('#focus-title')?.textContent ?? '') !== staticTitle) {
            if (performance.now() > deadline) throw new Error('candidate runtime focus did not open');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          const focusTitle = document.querySelector('#focus-title')?.textContent ?? '';
          const focusSummary = document.querySelector('#focus-summary')?.textContent ?? '';
          const focusTitleNode = document.querySelector('#focus-title');
          const focusSummaryNode = document.querySelector('#focus-summary');
          const focusTitleLang = focusTitleNode?.lang ?? '';
          const focusSummaryLang = focusSummaryNode?.lang ?? '';
          const focusTitleDir = focusTitleNode?.getAttribute('dir') ?? '';
          const focusSummaryDir = focusSummaryNode?.getAttribute('dir') ?? '';
          const focusPresence = document.querySelector('#focus-presence')?.textContent ?? '';
          const focusLocationItems = [...document.querySelectorAll('#focus-locations > li')];
          const focusLocationContentNodes = focusLocationItems.map((item) => item.querySelector('[data-content-language]'));
          const focusLocationContentLabels = focusLocationContentNodes.map((node) => node?.textContent ?? '');
          const focusLocationContentLangs = focusLocationContentNodes.map((node) => node?.getAttribute('lang') ?? '');
          const focusLocationContentDirs = focusLocationContentNodes.map((node) => node?.getAttribute('dir') ?? '');
          const focusDigital = document.querySelector('#focus-digital');
          const focusDigitalText = focusDigital?.textContent ?? '';
          const focusDigitalLang = focusDigital?.getAttribute('lang') ?? '';
          const focusDigitalDir = focusDigital?.getAttribute('dir') ?? '';
          const semanticLevelNode = document.querySelector('#semantic-level');
          const semanticBreadcrumbContentNode = document.querySelector('#semantic-breadcrumb-accessible [data-content-language]');
          const semanticSummaryNode = document.querySelector('#semantic-summary');
          const semanticBreadcrumbLabelledBy = (semanticSummaryNode?.getAttribute('aria-labelledby') ?? '')
            .split(/\s+/u)
            .filter(Boolean);
          const semanticBreadcrumbLabelsResolve = semanticBreadcrumbLabelledBy.length > 0
            && semanticBreadcrumbLabelledBy.every((id) => Boolean(document.getElementById(id)));
          const semanticLevelText = semanticLevelNode?.textContent ?? '';
          const semanticLevelLang = semanticLevelNode?.getAttribute('lang') ?? '';
          const semanticLevelDir = semanticLevelNode?.getAttribute('dir') ?? '';
          const semanticBreadcrumbContentText = semanticBreadcrumbContentNode?.textContent ?? '';
          const semanticBreadcrumbContentLang = semanticBreadcrumbContentNode?.getAttribute('lang') ?? '';
          const semanticBreadcrumbContentDir = semanticBreadcrumbContentNode?.getAttribute('dir') ?? '';
          const placeSearchLabel = focusLocationContentLabels.find((label) => label.trim()) ?? '';
          document.querySelector('#focus-close')?.click();

          const spatialSearch = document.querySelector('#spatial-destination-search');
          spatialSearch.value = placeSearchLabel;
          spatialSearch.dispatchEvent(new Event('input', { bubbles: true }));
          const placeDeadline = performance.now() + 10_000;
          while (!document.querySelector('[data-destination-type="place"]')) {
            if (performance.now() > placeDeadline) throw new Error('candidate place search did not render');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          const placeResult = document.querySelector('[data-destination-type="place"]');
          const placeTitle = placeResult?.querySelector('.spatial-destination-result-copy > strong');
          const placeContext = placeResult?.querySelector('.spatial-destination-result-copy > span');
          const placeButtons = [...(placeResult?.querySelectorAll('button') ?? [])];
          const placeTitleId = placeTitle?.id ?? '';
          const placeButtonsBound = placeButtons.length === 2 && placeButtons.every((control) => {
            const ids = (control.getAttribute('aria-labelledby') ?? '').split(/\s+/u).filter(Boolean);
            return !control.hasAttribute('aria-label')
              && ids.includes(placeTitleId)
              && ids.length === 2
              && ids.every((id) => Boolean(document.getElementById(id)));
          });
          const placeResultBoundary = {
            searchLabel: placeSearchLabel,
            title: placeTitle?.textContent ?? '',
            titleLang: placeTitle?.getAttribute('lang') ?? '',
            titleDir: placeTitle?.getAttribute('dir') ?? '',
            context: placeContext?.textContent ?? '',
            contextLang: placeContext?.getAttribute('lang') ?? '',
            contextDir: placeContext?.getAttribute('dir') ?? '',
            buttonsBound: placeButtonsBound,
          };
          spatialSearch.value = '';
          spatialSearch.dispatchEvent(new Event('input', { bubbles: true }));

          const search = document.querySelector('#commons-search');
          search.value = staticTitle;
          search.dispatchEvent(new Event('input', { bubbles: true }));
          const countDeadline = performance.now() + 10_000;
          while (document.querySelectorAll('#discovery-list > li').length !== 1) {
            if (performance.now() > countDeadline) throw new Error('candidate exact discovery count did not settle');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          const exactDiscoveryCount = document.querySelector('#discovery-count')?.textContent?.trim() ?? '';
          document.querySelector('[data-presentation-choice="text"]')?.click();
          while (document.body.dataset.presentation !== 'text') {
            if (performance.now() > countDeadline) throw new Error('candidate text presentation did not open');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          const exactTextCount = document.querySelector('#text-count')?.textContent?.trim() ?? '';
          document.querySelector('[data-presentation-choice="globe"]')?.click();
          while (document.body.dataset.presentation !== 'globe') {
            if (performance.now() > countDeadline) throw new Error('candidate globe presentation did not restore');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          search.value = '';
          search.dispatchEvent(new Event('input', { bubbles: true }));
          await new Promise((resolve) => requestAnimationFrame(resolve));

          document.querySelector('#layer-view-button')?.click();
          const layerDeadline = performance.now() + 15_000;
          while (!document.querySelector('.digital-ribbon-name')) {
            if (performance.now() > layerDeadline) throw new Error('candidate digital ribbon did not render');
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
          const ribbonNames = [...document.querySelectorAll('.digital-ribbon-name')];
          const ribbonControls = [...document.querySelectorAll('.digital-ribbon-item')];
          const digitalLaneCounts = [...document.querySelectorAll('.digital-lane-focus > small')]
            .map((node) => node.textContent?.trim() ?? '')
            .filter(Boolean);
          const digitalLaneLabels = [...document.querySelectorAll('.digital-lane')]
            .map((node) => node.getAttribute('aria-label') ?? '')
            .filter(Boolean);
          return {
            staticTitle,
            staticSummary,
            staticTitleDir,
            staticSummaryDir,
            expectedPresence,
            focusTitle,
            focusSummary,
            focusTitleLang,
            focusSummaryLang,
            focusTitleDir,
            focusSummaryDir,
            focusPresence,
            focusLocationItemCount: focusLocationItems.length,
            focusLocationContentLabels,
            focusLocationContentLangs,
            focusLocationContentDirs,
            focusDigitalText,
            focusDigitalLang,
            focusDigitalDir,
            semanticLevelText,
            semanticLevelLang,
            semanticLevelDir,
            semanticBreadcrumbContentText,
            semanticBreadcrumbContentLang,
            semanticBreadcrumbContentDir,
            semanticBreadcrumbLabelsResolve,
            placeResultBoundary,
            exactDiscoveryCount,
            exactTextCount,
            digitalLaneCounts,
            digitalLaneLabels,
            sphereNameLangs,
            sphereNameDirs,
            sphereSummaryTitleLangs,
            sphereSummaryTitleDirs,
            sphereAccessibleText,
            ribbonNameLangs: ribbonNames.map((node) => node.getAttribute('lang') ?? ''),
            ribbonNameDirs: ribbonNames.map((node) => node.getAttribute('dir') ?? ''),
            ribbonLabelsBound: ribbonControls.every((node) => !node.hasAttribute('aria-label') && Boolean(node.getAttribute('aria-labelledby'))),
            ribbonTitleLabelsEnglish: ribbonControls.every((node) => {
              const ids = (node.getAttribute('aria-labelledby') ?? '').split(/\s+/u).filter(Boolean);
              const title = ids.map((id) => document.getElementById(id)).find((label) => label?.classList.contains('digital-ribbon-name'));
              return title?.getAttribute('lang') === 'en';
            }),
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
        effectiveLanguage: document.querySelector('[data-locale-effective]')?.textContent?.trim() ?? '',
        semanticBreadcrumb: document.querySelector('#semantic-breadcrumb-accessible')?.textContent ?? '',
        brandHref: document.querySelector('.brand')?.getAttribute('href') ?? '',
        languageOptions: [...document.querySelectorAll('#filter-language option[value]:not([value=""])')].map((node) => ({
          value: node.value,
          lang: node.getAttribute('lang') ?? '',
          dir: node.getAttribute('dir') ?? '',
        })),
        naturalTextDirections: [...document.querySelectorAll('input[type="text"], input[type="search"], textarea')].map((node) => getComputedStyle(node).direction),
        structuredInputDirections: [...document.querySelectorAll('input[type="url"], input[type="email"], input[type="tel"], input[type="number"]')].map((node) => getComputedStyle(node).direction),
        rtlTextPluginStatus: document.querySelector('.globe-stage')?.dataset.rtlTextPlugin ?? '',
      }));
      assert(state.lang === candidate.locale, `${pageName}: lang drifted to ${state.lang}`);
      assert(state.dir === candidate.direction, `${pageName}: dir drifted to ${state.dir}`);
      assert(state.robots === 'noindex,nofollow', `${pageName}: candidate robots contract missing`);
      assert(state.description.trim().length > 0, `${pageName}: candidate description metadata is malformed`);
      assert(state.titleCount === 1 && state.documentTitle.trim().length > 0, `${pageName}: candidate title metadata is malformed`);
      assert(state.iconHref.includes('commonworld-mark.svg'), `${pageName}: candidate head swallowed the icon link`);
      assert(state.bannerVisible, `${pageName}: candidate banner is not visible`);
      assert(state.effectiveLanguage === CANDIDATE_SOURCE.locales[candidate.locale].static.effective_language, `${pageName}: effective-language status drifted: ${state.effectiveLanguage}`);
      if (pageName === `${candidate.locale}.html`) {
        const catalogLanguageOptions = state.languageOptions.filter(({ value }) => value !== 'unknown');
        assert(catalogLanguageOptions.length > 0, `${pageName}: generated catalog language options are missing`);
        for (const option of catalogLanguageOptions) {
          const expectedDirection = ['ar', 'syr'].includes(option.value.split('-')[0]) ? 'rtl' : 'ltr';
          assert(option.lang === option.value, `${pageName}: language option ${option.value} has lang=${option.lang}`);
          assert(option.dir === expectedDirection, `${pageName}: language option ${option.value} has dir=${option.dir}`);
        }
      }
      if (pageName === 'ar.html') {
        assert(state.rtlTextPluginStatus === 'loaded', `${pageName}: local RTL text plugin status is ${state.rtlTextPluginStatus}`);
        const rtlPluginUrl = rtlPluginRequests.length === 1 ? new URL(rtlPluginRequests[0]) : null;
        assert(
          rtlPluginUrl
            && /\/releases\/[0-9a-f]{20}\/assets\/vendor\/mapbox-gl-rtl-text\.js$/u.test(rtlPluginUrl.pathname)
            && rtlPluginUrl.searchParams.get('v') === 'd1c690352956',
          `${pageName}: RTL plugin was not loaded exactly once from the local versioned asset: ${rtlPluginRequests.join(' | ')}`,
        );
      } else {
        assert(rtlPluginRequests.length === 0, `${pageName}: unexpected RTL plugin request: ${rtlPluginRequests.join(' | ')}`);
      }
      if (candidate.locale === 'ar' && pageName !== 'method.ar.html') {
        assert(state.naturalTextDirections.length > 0 && state.naturalTextDirections.every((direction) => direction === 'rtl'), `${pageName}: Arabic natural-language controls are not RTL: ${state.naturalTextDirections.join(', ')}`);
        if (pageName === 'propose.ar.html') {
          assert(state.structuredInputDirections.length > 0 && state.structuredInputDirections.every((direction) => direction === 'ltr'), `${pageName}: structured URL/contact controls are not LTR: ${state.structuredInputDirections.join(', ')}`);
        }
      }
      if (pageName === `${candidate.locale}.html`) {
        const connector = CANDIDATE_SOURCE.locales[candidate.locale].ui.semantic_breadcrumb_connector;
        assert(state.brandHref === `./${candidate.locale}.html`, `${pageName}: brand reset leaves the candidate surface: ${state.brandHref}`);
        assert(state.semanticBreadcrumb.includes(` ${connector} `), `${pageName}: semantic breadcrumb connector drifted: ${state.semanticBreadcrumb}`);
        assert(!state.semanticBreadcrumb.includes(' nach '), `${pageName}: German semantic breadcrumb connector leaked: ${state.semanticBreadcrumb}`);
      }
      const missingMarkers = state.bodyText.match(/\[missing:[^\]]+\]/gu) ?? [];
      assert(missingMarkers.length === 0, `${pageName}: missing translation marker rendered: ${missingMarkers.slice(0, 8).join(' | ')}`);
      assert(state.candidateChoices.length === 0, `${pageName}: candidate locale became selectable`);
      assert(JSON.stringify([...new Set(state.releasedChoices)].sort()) === JSON.stringify(['de', 'en']), `${pageName}: released locale choices drifted`);
      assert(state.documentWidth <= state.viewportWidth + 1, `${pageName}: horizontal overflow ${state.documentWidth}/${state.viewportWidth}`);
      if (pageName === `${candidate.locale}.html`) {
        assert(state.englishContentBlocks > 0, `${pageName}: canonical English catalog content lacks lang=en boundaries`);
        assert(runtimeCatalogBoundary?.focusTitle === runtimeCatalogBoundary?.staticTitle, `${pageName}: runtime title fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.focusSummary === runtimeCatalogBoundary?.staticSummary, `${pageName}: runtime summary fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.staticTitleDir === 'ltr' && runtimeCatalogBoundary?.staticSummaryDir === 'ltr', `${pageName}: static English content lacks dir=ltr boundaries`);
        assert(runtimeCatalogBoundary?.focusTitleLang === 'en' && runtimeCatalogBoundary?.focusSummaryLang === 'en', `${pageName}: runtime English content lacks lang=en boundaries`);
        assert(runtimeCatalogBoundary?.focusTitleDir === 'ltr' && runtimeCatalogBoundary?.focusSummaryDir === 'ltr', `${pageName}: runtime English content lacks dir=ltr boundaries`);
        assert(runtimeCatalogBoundary?.semanticLevelText === runtimeCatalogBoundary?.staticTitle, `${pageName}: visible semantic focus crumb lost the selected title`);
        assert(runtimeCatalogBoundary?.semanticLevelLang === 'en' && runtimeCatalogBoundary?.semanticLevelDir === 'ltr', `${pageName}: visible semantic focus crumb lacks lang=en dir=ltr`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbContentText === runtimeCatalogBoundary?.staticTitle, `${pageName}: accessible semantic breadcrumb lost the selected title`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbContentLang === 'en' && runtimeCatalogBoundary?.semanticBreadcrumbContentDir === 'ltr', `${pageName}: accessible semantic title crumb lacks lang=en dir=ltr`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbLabelsResolve, `${pageName}: semantic breadcrumb aria-labelledby references are incomplete`);
        assert((runtimeCatalogBoundary?.focusLocationItemCount ?? 0) > 0, `${pageName}: expected dual-presence focus fixture has no locations`);
        assert(runtimeCatalogBoundary.focusLocationContentLangs.length === runtimeCatalogBoundary.focusLocationItemCount && runtimeCatalogBoundary.focusLocationContentLangs.every((lang) => lang === 'en'), `${pageName}: focus location content labels lack lang=en boundaries`);
        assert(runtimeCatalogBoundary.focusLocationContentDirs.every((direction) => direction === 'ltr'), `${pageName}: focus location content labels lack dir=ltr boundaries`);
        assert((runtimeCatalogBoundary?.focusDigitalText ?? '').trim().length > 0 && runtimeCatalogBoundary?.focusDigitalLang === 'en', `${pageName}: focus digital content label lacks lang=en boundary`);
        assert(runtimeCatalogBoundary?.focusDigitalDir === 'ltr', `${pageName}: focus digital content label lacks dir=ltr boundary`);
        assert((runtimeCatalogBoundary?.sphereNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereNameLangs.every((lang) => lang === 'en'), `${pageName}: sphere ring titles lack lang=en boundaries`);
        assert(runtimeCatalogBoundary.sphereNameDirs.every((direction) => direction === 'ltr'), `${pageName}: sphere ring titles lack dir=ltr boundaries`);
        assert((runtimeCatalogBoundary?.sphereSummaryTitleLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereSummaryTitleLangs.every((lang) => lang === 'en'), `${pageName}: sphere accessible summary titles lack lang=en boundaries`);
        assert(runtimeCatalogBoundary.sphereSummaryTitleDirs.every((direction) => direction === 'ltr'), `${pageName}: sphere accessible summary titles lack dir=ltr boundaries`);
        assert((runtimeCatalogBoundary?.ribbonNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.ribbonNameLangs.every((lang) => lang === 'en'), `${pageName}: digital ribbon titles lack lang=en boundaries`);
        assert(runtimeCatalogBoundary.ribbonNameDirs.every((direction) => direction === 'ltr'), `${pageName}: digital ribbon titles lack dir=ltr boundaries`);
        if (candidate.direction === 'rtl') assert(runtimeCatalogBoundary.sphereAccessibleText.includes('، '), `${pageName}: accessible ring list lacks Arabic separator`);
        assert(runtimeCatalogBoundary?.ribbonLabelsBound && runtimeCatalogBoundary?.ribbonTitleLabelsEnglish, `${pageName}: digital ribbon accessible labels do not preserve mixed-language boundaries`);
        const candidatePack = CANDIDATE_SOURCE.locales[candidate.locale];
        const localizedExactCount = (count) => candidatePack.ui.commons_count.replace('{count}', String(count));
        const expectedExactCount = localizedExactCount(1);
        assert(runtimeCatalogBoundary?.exactDiscoveryCount === expectedExactCount, `${pageName}: exact discovery count is not localized: ${runtimeCatalogBoundary?.exactDiscoveryCount}`);
        assert((runtimeCatalogBoundary?.exactTextCount ?? '').startsWith(`${expectedExactCount}.`), `${pageName}: exact text count is not localized: ${runtimeCatalogBoundary?.exactTextCount}`);
        assert((runtimeCatalogBoundary?.digitalLaneCounts?.length ?? 0) > 0 && runtimeCatalogBoundary.digitalLaneCounts.every((value) => {
          const count = value.match(/\d+/u)?.[0];
          return count && value === localizedExactCount(count);
        }), `${pageName}: exact digital lane counts are not localized: ${runtimeCatalogBoundary?.digitalLaneCounts?.join(' | ')}`);
        assert((runtimeCatalogBoundary?.digitalLaneLabels?.length ?? 0) > 0 && runtimeCatalogBoundary.digitalLaneLabels.every((value) => {
          const count = value.match(/\d+/u)?.[0];
          return count && value.endsWith(localizedExactCount(count));
        }), `${pageName}: digital lane accessible counts are not localized: ${runtimeCatalogBoundary?.digitalLaneLabels?.join(' | ')}`);
        const placeBoundary = runtimeCatalogBoundary?.placeResultBoundary;
        assert(placeBoundary?.searchLabel && placeBoundary.title === placeBoundary.searchLabel, `${pageName}: place-search title drifted from the English location label`);
        assert(placeBoundary?.titleLang === 'en' && placeBoundary?.titleDir === 'ltr', `${pageName}: place-search title lacks lang=en dir=ltr`);
        if (placeBoundary?.context === runtimeCatalogBoundary?.staticTitle) {
          assert(placeBoundary.contextLang === 'en' && placeBoundary.contextDir === 'ltr', `${pageName}: place-search project context lacks lang=en dir=ltr`);
        } else {
          assert(placeBoundary?.context === candidatePack.ui.published_location, `${pageName}: place-search interface context drifted: ${placeBoundary?.context}`);
          assert(placeBoundary?.contextLang === '' && placeBoundary?.contextDir === '', `${pageName}: localized place-search context was mislabeled as catalog content`);
        }
        assert(placeBoundary?.buttonsBound, `${pageName}: place-search accessible labels do not separate interface action and English title`);
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
