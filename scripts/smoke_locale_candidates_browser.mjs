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
const LOCALE_RELEASE_CONTRACT = JSON.parse(
  await readFile(path.join(ROOT, 'docs/architecture/locale-release.contract.json'), 'utf8'),
);
const WAVE1_SOURCE = JSON.parse(
  await readFile(path.join(ROOT, 'assets/locales/wave1-locales.json'), 'utf8'),
);
const WAVE1_LOCALES = Object.freeze(
  (LOCALE_RELEASE_CONTRACT.rollout?.wave_1 ?? []).map((locale) => {
    const entry = LOCALE_RELEASE_CONTRACT.locale_registry?.[locale] ?? {};
    const surfaces = entry.surface_files ?? {};
    return {
      locale,
      status: entry.status ?? 'candidate',
      direction: entry.direction ?? 'ltr',
      pages: [surfaces.index, surfaces.method, surfaces.proposal].filter(Boolean),
    };
  }),
);
// Backward-compatible alias while callers migrate from candidate-only naming.
const CANDIDATES = WAVE1_LOCALES;
const CANDIDATE_SOURCE = WAVE1_SOURCE;

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
if (!address || typeof address === 'string') throw new Error('locale lifecycle smoke server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined;
const browser = await chromium.launch({
  headless: true,
  executablePath: executablePath,
  args: ['--enable-unsafe-swiftshader'],
});
const results = [];
const releasedIsolation = [];
const localePackResilience = [];
const claims = Object.freeze({
  full_wcag_conformance: false,
  manual_screen_reader_acceptance: false,
  native_language_approval: false,
  scope: 'automated lifecycle smoke for Wave-1 locales: state preservation, keyboard focus paths, accessible names, RTL overflow/direction, mixed-script boundaries',
});

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
    assert(candidatePackRequests.length === 0, `${pageName}: loaded Wave-1 pack on baseline released surface: ${candidatePackRequests.join(' | ')}`);
    releasedIsolation.push({ page: pageName, wave1PackRequests: 0, verdict: 'PASS' });
    await context.close();
  }

  for (const candidate of WAVE1_LOCALES) {
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
        if (pageName === `${candidate.locale}.html`) {
          await page.waitForFunction(
            () => document.querySelector('.globe-stage')?.dataset.localePack === 'ready',
            { timeout: 30_000 },
          );
        }
        if (pageName === 'ar.html') {
          await page.waitForFunction(
            () => window.maplibregl?.getRTLTextPluginStatus?.() === 'loaded',
            { timeout: 30_000 },
          );
        }
      }
      let proposalRuntimeError = '';
      let proposalDigitalLabel = '';
      let proposalIssueBody = '';
      if (pageName.startsWith('propose.')) {
        proposalDigitalLabel = ((await page.locator('#commons-proposal-form [name="presence_digital"]').locator('xpath=ancestor::label[1]//span').textContent()) ?? '').trim();
        assert(proposalDigitalLabel === WAVE1_SOURCE.locales[candidate.locale].static.digital, `${pageName}: candidate Digital option is not localized: ${proposalDigitalLabel}`);
        const expectedRuntimeError = WAVE1_SOURCE.locales[candidate.locale].proposal_runtime['Automated submission blocked.'];
        await page.locator('input[name=website_confirm]').fill('bot');
        await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
        await page.waitForSelector('#proposal-errors:not([hidden])');
        proposalRuntimeError = (await page.locator('#proposal-errors').textContent()) ?? '';
        assert(proposalRuntimeError.includes(expectedRuntimeError), `${pageName}: candidate proposal runtime message drifted: ${proposalRuntimeError}`);
        assert(!proposalRuntimeError.includes('[missing:proposal_runtime:'), `${pageName}: proposal runtime fallback marker rendered`);
        proposalIssueBody = await page.evaluate(async () => {
          const moduleScript = [...document.scripts].find((script) => script.src.includes('/assets/commonworld-proposal.js'));
          if (!moduleScript?.src) throw new Error('candidate proposal module script is missing');
          const proposalModule = await import(moduleScript.src);
          const proposal = proposalModule.proposalFromFields({
            name: 'Candidate Issue Body Commons',
            description: 'A community-managed resource with open rules, primary-near sources and a real public participation path.',
            official_website: 'https://example.net/commons',
            commons_type: 'other',
            presence_geographic: false,
            presence_digital: true,
            region: '',
            actions: [{ type: 'learn', url: 'https://example.net/commons/about' }, { type: '', url: '' }, { type: '', url: '' }],
            sources: 'https://example.net/commons/governance',
            sensitive_location_risk: false,
            editorial_note: '',
            public_issue_acknowledged: true,
            processing_agreed: true,
            no_sensitive_data_confirmed: true,
          }, new Date('2026-08-02T00:00:00Z'));
          return proposalModule.buildIssueBody(proposal);
        });
        const expectedName = WAVE1_SOURCE.locales[candidate.locale].proposal_runtime.Name;
        assert(proposalIssueBody.includes(`**${expectedName}:**`), `${pageName}: localized Name label missing from issue body: ${proposalIssueBody}`);
        assert(proposalIssueBody.includes(proposalDigitalLabel), `${pageName}: localized Digital value missing from issue body: ${proposalIssueBody}`);
        assert(!proposalIssueBody.includes('**Name:**'), `${pageName}: hardcoded English Name leaked into issue body`);
      }
      let runtimeCatalogBoundary = null;
      if (pageName === `${candidate.locale}.html`) {
        runtimeCatalogBoundary = await page.evaluate(async () => {
          const card = document.querySelector('#catalog .catalog-card[data-commonproject-id="aflaj-irrigation-systems-oman"]');
          if (!card) throw new Error('candidate dual-presence fixture card is missing');
          const button = card.querySelector('.catalog-select');
          if (!button) throw new Error('candidate dual-presence fixture select control is missing');
          const staticTitleNode = card?.querySelector('h2');
          const staticSummaryNode = card?.querySelector('h2 + p');
          const staticTitle = staticTitleNode?.textContent ?? '';
          const staticSummary = staticSummaryNode?.textContent ?? '';
          const staticTitleLang = staticTitleNode?.getAttribute('lang') ?? '';
          const staticSummaryLang = staticSummaryNode?.getAttribute('lang') ?? '';
          const staticTitleDir = staticTitleNode?.getAttribute('dir') ?? '';
          const staticSummaryDir = staticSummaryNode?.getAttribute('dir') ?? '';
          const staticKind = card?.querySelector('.catalog-kind')?.textContent ?? '';
          const expectedPresence = staticKind.split(' · ').slice(1).join(' · ');
          const sphereNameNodes = [...document.querySelectorAll('.sphere-ring-name')];
          const sphereSummaryTitleNodes = [...document.querySelectorAll('#sphere-ring-accessible-summary .sphere-ring-accessible-title')];
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
          const focusLinkNodes = [...document.querySelectorAll('#focus-links a')];
          const focusSourceNodes = [...document.querySelectorAll('#focus-sources a')];
          const focusLinkLangs = focusLinkNodes.map((node) => node.getAttribute('lang') ?? '');
          const focusLinkDirs = focusLinkNodes.map((node) => node.getAttribute('dir') ?? '');
          const focusLinkBidi = focusLinkNodes.map((node) => getComputedStyle(node).unicodeBidi);
          const focusSourceLangs = focusSourceNodes.map((node) => node.getAttribute('lang') ?? '');
          const focusSourceDirs = focusSourceNodes.map((node) => node.getAttribute('dir') ?? '');
          const focusSourceBidi = focusSourceNodes.map((node) => getComputedStyle(node).unicodeBidi);
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
            staticTitleLang,
            staticSummaryLang,
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
            focusLinkLangs,
            focusLinkDirs,
            focusLinkBidi,
            focusSourceLangs,
            focusSourceDirs,
            focusSourceBidi,
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
            ribbonTitleLabelsLanguageSafe: ribbonControls.every((node) => {
              const ids = (node.getAttribute('aria-labelledby') ?? '').split(/\s+/u).filter(Boolean);
              const title = ids.map((id) => document.getElementById(id)).find((label) => label?.classList.contains('digital-ribbon-name'));
              const lang = title?.getAttribute('lang') ?? '';
              const direction = title?.getAttribute('dir') ?? '';
              return (lang === 'en' && direction === 'ltr') || (lang === '' && direction === 'auto');
            }),
          };
        });
      }
      const shellLayouts = [];
      if (pageName === `${candidate.locale}.html`) {
        for (const viewport of [{ width: 1024, height: 768 }, { width: 390, height: 844 }]) {
          await page.setViewportSize(viewport);
          await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          shellLayouts.push(await page.evaluate(() => {
            const banner = document.querySelector('.locale-candidate-banner');
            const topbar = document.querySelector('.topbar');
            const stage = document.querySelector('.globe-stage');
            const bannerRect = banner?.getBoundingClientRect();
            const topbarRect = topbar?.getBoundingClientRect();
            const stageRect = stage?.getBoundingClientRect();
            const visibleBottomControls = [...document.querySelectorAll('.orientation-bar, .maplibregl-ctrl-bottom-left, .maplibregl-ctrl-bottom-right')]
              .filter((node) => node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden');
            const bottomControlBottom = visibleBottomControls.reduce(
              (maximum, node) => Math.max(maximum, node.getBoundingClientRect().bottom),
              0,
            );
            const hit = bannerRect
              ? document.elementFromPoint((bannerRect.left + bannerRect.right) / 2, (bannerRect.top + bannerRect.bottom) / 2)
              : null;
            return {
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              candidateMarker: document.body.dataset.localeCandidate ?? '',
              bannerHit: Boolean(banner && hit && banner.contains(hit)),
              bannerBottom: bannerRect?.bottom ?? -1,
              topbarTop: topbarRect?.top ?? -1,
              stageBottom: stageRect?.bottom ?? -1,
              bottomControlBottom,
              documentHeight: document.documentElement.scrollHeight,
            };
          }));
        }
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
        candidateMarker: document.body.dataset.localeCandidate ?? '',
        bodyText: document.body.textContent ?? '',
        allChoices: [...document.querySelectorAll('[data-locale-choice]')]
          .map((node) => node.getAttribute('data-locale-choice'))
          .filter(Boolean),
        candidateStatusChoices: [...document.querySelectorAll('[data-locale-status="candidate"][data-locale-choice]')]
          .map((node) => node.getAttribute('data-locale-choice'))
          .filter(Boolean),
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
      const isCandidate = candidate.status === 'candidate';
      if (isCandidate) {
        assert(state.robots === 'noindex,nofollow', `${pageName}: candidate robots contract missing`);
        assert(state.bannerVisible, `${pageName}: candidate banner is not visible`);
        assert(state.candidateMarker === candidate.locale, `${pageName}: candidate body marker drifted: ${state.candidateMarker}`);
      } else {
        // Released lifecycle: no preview markers; language and direction remain authoritative.
        assert(state.robots !== 'noindex,nofollow', `${pageName}: released surface must not keep candidate noindex`);
        assert(!state.bannerVisible, `${pageName}: released surface must not show candidate banner`);
        assert(state.candidateMarker === '', `${pageName}: released surface must not keep data-locale-candidate`);
      }
      assert(state.description.trim().length > 0, `${pageName}: description metadata is malformed`);
      assert(state.titleCount === 1 && state.documentTitle.trim().length > 0, `${pageName}: title metadata is malformed`);
      assert(state.iconHref.includes('commonworld-mark.svg'), `${pageName}: head swallowed the icon link`);
      for (const layout of shellLayouts) {
        if (isCandidate) {
          assert(layout.candidateMarker === candidate.locale, `${pageName}: shell candidate marker drifted at ${layout.viewportWidth}x${layout.viewportHeight}`);
          assert(layout.bannerHit, `${pageName}: candidate banner is occluded at ${layout.viewportWidth}x${layout.viewportHeight}`);
          assert(layout.topbarTop + 1 >= layout.bannerBottom, `${pageName}: topbar overlaps candidate banner at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        }
        assert(layout.stageBottom <= layout.viewportHeight + 1 && layout.stageBottom >= layout.viewportHeight - 1, `${pageName}: stage is clipped or undersized at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        assert(layout.bottomControlBottom <= layout.viewportHeight + 1, `${pageName}: bottom controls leave the viewport at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        assert(layout.documentHeight <= layout.viewportHeight + 1, `${pageName}: shell exceeds the viewport at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
      }
      const proposalSurface = pageName === `propose.${candidate.locale}.html`;
      if (proposalSurface) {
        assert(state.effectiveLanguage === '', `${pageName}: redundant effective-language status is still present: ${state.effectiveLanguage}`);
      } else {
        assert(state.effectiveLanguage === WAVE1_SOURCE.locales[candidate.locale].static.effective_language, `${pageName}: effective-language status drifted: ${state.effectiveLanguage}`);
      }
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
        const connector = WAVE1_SOURCE.locales[candidate.locale].ui.semantic_breadcrumb_connector;
        assert(state.brandHref === `./${candidate.locale}.html`, `${pageName}: brand reset leaves the candidate surface: ${state.brandHref}`);
        assert(state.semanticBreadcrumb.includes(` ${connector} `), `${pageName}: semantic breadcrumb connector drifted: ${state.semanticBreadcrumb}`);
        assert(!state.semanticBreadcrumb.includes(' nach '), `${pageName}: German semantic breadcrumb connector leaked: ${state.semanticBreadcrumb}`);
      }
      const missingMarkers = state.bodyText.match(/\[missing:[^\]]+\]/gu) ?? [];
      assert(missingMarkers.length === 0, `${pageName}: missing translation marker rendered: ${missingMarkers.slice(0, 8).join(' | ')}`);
      if (proposalSurface) {
        assert(state.candidateChoices.length === 0, `${pageName}: redundant Wave-1 locale choices are still present on proposal`);
        assert(state.releasedChoices.length === 0, `${pageName}: redundant released locale choices are still present on proposal`);
      } else {
        const wave1Choices = [...new Set(state.candidateChoices)].sort();
        const releasedChoices = [...new Set(state.releasedChoices)].sort();
        if (isCandidate) {
          // Candidate previews expose Wave-1 links as technical previews, not public selection.
          assert(JSON.stringify(wave1Choices) === JSON.stringify(['ar', 'es', 'fr', 'pt-BR']), `${pageName}: Wave-1 locale choices drifted`);
          assert(JSON.stringify(releasedChoices) === JSON.stringify(['de', 'en']), `${pageName}: released locale choices drifted`);
        } else {
          // After promotion, Wave-1 languages join released selection without preview status.
          const allChoices = [...new Set(state.allChoices)].sort();
          assert(allChoices.includes(candidate.locale), `${pageName}: released surface lacks self language link`);
          assert(allChoices.includes('en') && allChoices.includes('de'), `${pageName}: released baseline language links missing`);
          assert(state.candidateStatusChoices.length === 0, `${pageName}: released language choices still carry candidate status`);
          assert(!state.bannerVisible && state.candidateMarker === '', `${pageName}: released surface still looks like a candidate preview`);
        }
      }
      assert(state.documentWidth <= state.viewportWidth + 1, `${pageName}: horizontal overflow ${state.documentWidth}/${state.viewportWidth}`);
      if (pageName === `${candidate.locale}.html`) {
        assert(state.englishContentBlocks > 0, `${pageName}: canonical English catalog content lacks lang=en boundaries`);
        assert(runtimeCatalogBoundary?.focusTitle === runtimeCatalogBoundary?.staticTitle, `${pageName}: runtime title fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.focusSummary === runtimeCatalogBoundary?.staticSummary, `${pageName}: runtime summary fell off the English content overlay`);
        assert(runtimeCatalogBoundary?.staticTitleLang === 'en' && runtimeCatalogBoundary?.staticTitleDir === 'ltr', `${pageName}: static canonical title lacks lang=en dir=ltr`);
        assert(runtimeCatalogBoundary?.staticSummaryLang === candidate.locale && runtimeCatalogBoundary?.staticSummaryDir === 'auto', `${pageName}: static localized summary lacks candidate language boundary`);
        assert(runtimeCatalogBoundary?.focusTitleLang === 'en' && runtimeCatalogBoundary?.focusSummaryLang === candidate.locale, `${pageName}: runtime title/summary language boundaries drifted`);
        assert(runtimeCatalogBoundary?.focusTitleDir === 'ltr' && runtimeCatalogBoundary?.focusSummaryDir === 'auto', `${pageName}: runtime title/summary direction boundaries drifted`);
        assert(runtimeCatalogBoundary?.semanticLevelText === runtimeCatalogBoundary?.staticTitle, `${pageName}: visible semantic focus crumb lost the selected title`);
        assert(runtimeCatalogBoundary?.semanticLevelLang === 'en' && runtimeCatalogBoundary?.semanticLevelDir === 'ltr', `${pageName}: visible semantic focus crumb lacks lang=en dir=ltr`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbContentText === runtimeCatalogBoundary?.staticTitle, `${pageName}: accessible semantic breadcrumb lost the selected title`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbContentLang === 'en' && runtimeCatalogBoundary?.semanticBreadcrumbContentDir === 'ltr', `${pageName}: accessible semantic title crumb lacks lang=en dir=ltr`);
        assert(runtimeCatalogBoundary?.semanticBreadcrumbLabelsResolve, `${pageName}: semantic breadcrumb aria-labelledby references are incomplete`);
        assert((runtimeCatalogBoundary?.focusLocationItemCount ?? 0) > 0, `${pageName}: expected dual-presence focus fixture has no locations`);
        assert(runtimeCatalogBoundary.focusLocationContentLangs.length === runtimeCatalogBoundary.focusLocationItemCount && runtimeCatalogBoundary.focusLocationContentLangs.every((lang) => lang === candidate.locale), `${pageName}: focus location content labels lack candidate language boundaries`);
        assert(runtimeCatalogBoundary.focusLocationContentDirs.every((direction) => direction === 'auto'), `${pageName}: focus location content labels lack dir=auto boundaries`);
        assert((runtimeCatalogBoundary?.focusDigitalText ?? '').trim().length > 0 && runtimeCatalogBoundary?.focusDigitalLang === candidate.locale, `${pageName}: focus digital content label lacks candidate language boundary`);
        assert(runtimeCatalogBoundary?.focusDigitalDir === 'auto', `${pageName}: focus digital content label lacks dir=auto boundary`);
        assert((runtimeCatalogBoundary?.focusLinkLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.focusLinkLangs.every((lang) => [candidate.locale, ''].includes(lang)), `${pageName}: focus link labels carry an unexpected language boundary: ${runtimeCatalogBoundary?.focusLinkLangs?.join(' | ')}`);
        assert(runtimeCatalogBoundary.focusLinkDirs.every((direction, index) => direction === (runtimeCatalogBoundary.focusLinkLangs[index] === 'en' ? 'ltr' : 'auto')), `${pageName}: focus link directions drifted: ${runtimeCatalogBoundary?.focusLinkDirs?.join(' | ')}`);
        assert(runtimeCatalogBoundary.focusLinkBidi.every((value) => value === 'isolate'), `${pageName}: focus link bidi isolation is missing: ${runtimeCatalogBoundary?.focusLinkBidi?.join(' | ')}`);
        assert((runtimeCatalogBoundary?.focusSourceLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.focusSourceLangs.every((lang) => lang === candidate.locale), `${pageName}: generated compact source labels lack the candidate language boundary`);
        assert(runtimeCatalogBoundary.focusSourceDirs.every((direction) => direction === 'auto'), `${pageName}: generated compact source labels lack dir=auto boundaries`);
        assert(runtimeCatalogBoundary.focusSourceBidi.every((value) => value === 'isolate'), `${pageName}: focus source bidi isolation is missing`);
        assert((runtimeCatalogBoundary?.sphereNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereNameLangs.every((lang) => ['en', ''].includes(lang)), `${pageName}: sphere ring titles carry an unexpected language boundary`);
        assert(runtimeCatalogBoundary.sphereNameDirs.every((direction, index) => direction === (runtimeCatalogBoundary.sphereNameLangs[index] === 'en' ? 'ltr' : 'auto')), `${pageName}: sphere ring title directions drifted`);
        assert((runtimeCatalogBoundary?.sphereSummaryTitleLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereSummaryTitleLangs.every((lang) => ['en', ''].includes(lang)), `${pageName}: sphere accessible summary titles carry an unexpected language boundary`);
        assert(runtimeCatalogBoundary.sphereSummaryTitleDirs.every((direction, index) => direction === (runtimeCatalogBoundary.sphereSummaryTitleLangs[index] === 'en' ? 'ltr' : 'auto')), `${pageName}: sphere accessible summary title directions drifted`);
        assert((runtimeCatalogBoundary?.ribbonNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.ribbonNameLangs.every((lang) => ['en', ''].includes(lang)), `${pageName}: digital ribbon titles carry an unexpected language boundary`);
        assert(runtimeCatalogBoundary.ribbonNameDirs.every((direction, index) => direction === (runtimeCatalogBoundary.ribbonNameLangs[index] === 'en' ? 'ltr' : 'auto')), `${pageName}: digital ribbon title directions drifted`);
        if (candidate.direction === 'rtl') assert(runtimeCatalogBoundary.sphereAccessibleText.includes('، '), `${pageName}: accessible ring list lacks Arabic separator`);
        assert(runtimeCatalogBoundary?.ribbonLabelsBound && runtimeCatalogBoundary?.ribbonTitleLabelsLanguageSafe, `${pageName}: digital ribbon accessible labels do not preserve source-language-safe boundaries`);
        const candidatePack = WAVE1_SOURCE.locales[candidate.locale];
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
        assert(placeBoundary?.searchLabel && placeBoundary.title === placeBoundary.searchLabel, `${pageName}: place-search title drifted from the localized location label`);
        assert(placeBoundary?.titleLang === candidate.locale && placeBoundary?.titleDir === 'auto', `${pageName}: place-search title lacks localized language boundary`);
        if (placeBoundary?.context === runtimeCatalogBoundary?.staticTitle) {
          assert(placeBoundary.contextLang === 'en' && placeBoundary.contextDir === 'ltr', `${pageName}: place-search project context lacks lang=en dir=ltr`);
        } else {
          assert(placeBoundary?.context === candidatePack.ui.published_location, `${pageName}: place-search interface context drifted: ${placeBoundary?.context}`);
          assert(placeBoundary?.contextLang === '' && placeBoundary?.contextDir === '', `${pageName}: localized place-search context was mislabeled as catalog content`);
        }
        assert(placeBoundary?.buttonsBound, `${pageName}: place-search accessible labels do not separate interface action and localized place title`);
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
      results.push({
        page: pageName,
        locale: candidate.locale,
        status: candidate.status,
        direction: candidate.direction,
        proposalRuntimeLocalized: pageName.startsWith('propose.'),
        proposalDigitalLabel,
        proposalIssueBodyLocalized: Boolean(proposalIssueBody),
        verdict: 'PASS',
      });
      await context.close();
    }
  }
  {
    const candidate = WAVE1_LOCALES.find(({ locale }) => locale === 'fr');
    assert(candidate, 'Wave-1 non-blocking smoke requires the released French locale');
    const pageName = `${candidate.locale}.html`;
    const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const pageErrors = [];
    const warnings = [];
    let heldLocalePackRoute = null;
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('console', (message) => {
      if (message.type() === 'warning') warnings.push(message.text());
    });
    await page.route('**/assets/commonworld-wave1-locales.mjs*', (route) => {
      heldLocalePackRoute = route;
    });
    const navigation = page.goto(`${baseUrl}/${pageName}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('html.runtime-ready', { timeout: 5_000 });
    const response = await navigation;
    assert(response?.status() === 200, `${pageName}: pending-pack HTTP ${response?.status()}`);
    assert(heldLocalePackRoute, `${pageName}: locale pack request was not held`);
    const pendingState = await page.evaluate(() => ({
      presentation: document.body.dataset.presentation ?? '',
      fallbackPresent: Boolean(document.querySelector('[data-static-catalog-fallback]')),
      runtimeReady: document.documentElement.classList.contains('runtime-ready'),
    }));
    assert(pendingState.runtimeReady, `${pageName}: pending locale pack blocked runtime-ready`);
    assert(pendingState.presentation === 'globe', `${pageName}: pending locale pack changed presentation to ${pendingState.presentation}`);
    assert(!pendingState.fallbackPresent, `${pageName}: pending locale pack left the static catalogue over the globe`);
    const pendingCount = (await page.locator('#text-count').textContent()) ?? '';
    assert(pendingCount.includes('Commons'), `${pageName}: pending locale pack did not use the English runtime fallback: ${pendingCount}`);
    await page.waitForTimeout(2_800);
    await heldLocalePackRoute.continue();
    await page.waitForFunction(
      () => document.querySelector('.globe-stage')?.dataset.localePack === 'ready',
      null,
      { timeout: 5_000 },
    );
    await page.waitForFunction(
      () => document.querySelector('#text-count')?.textContent?.includes('communs'),
      null,
      { timeout: 5_000 },
    );
    assert(pageErrors.length === 0, `${pageName}: late-pack page errors: ${pageErrors.join(' | ')}`);
    const fallbackWarnings = warnings.filter((message) => message.includes('Wave-1 locale pack unavailable'));
    assert(fallbackWarnings.length === 0, `${pageName}: late successful locale pack was treated as failed: ${warnings.join(' | ')}`);
    localePackResilience.push({
      page: pageName,
      locale: candidate.locale,
      surface: 'globe',
      pendingPackNonBlocking: true,
      latePackRelocalized: true,
      verdict: 'PASS',
    });
    await context.close();
  }

  for (const candidate of WAVE1_LOCALES) {
    const pageName = `${candidate.locale}.html`;
    const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const pageErrors = [];
    const warnings = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('console', (message) => {
      if (message.type() === 'warning') warnings.push(message.text());
    });
    await page.route('**/assets/commonworld-wave1-locales.mjs*', (route) => route.abort('failed'));
    const response = await page.goto(`${baseUrl}/${pageName}`, { waitUntil: 'domcontentloaded' });
    assert(response?.status() === 200, `${pageName}: fallback HTTP ${response?.status()}`);
    await page.waitForSelector('html.runtime-ready', { timeout: 30_000 });
    await page.waitForFunction(() => {
      const stage = document.querySelector('.globe-stage');
      const canvas = document.querySelector('.maplibregl-canvas');
      return document.body.dataset.presentation === 'globe'
        && Number(stage?.dataset.mapRenders ?? 0) > 0
        && Boolean(canvas && canvas.width > 0 && canvas.height > 0);
    }, { timeout: 30_000 });
    const state = await page.evaluate(() => {
      const stage = document.querySelector('.globe-stage');
      const canvas = document.querySelector('.maplibregl-canvas');
      return {
        lang: document.documentElement.lang,
        runtimeReady: document.documentElement.classList.contains('runtime-ready'),
        presentation: document.body.dataset.presentation ?? '',
        mapRenders: Number(stage?.dataset.mapRenders ?? 0),
        mapCanvasReady: Boolean(canvas && canvas.width > 0 && canvas.height > 0),
        bodyText: document.body.textContent ?? '',
      };
    });
    assert(state.lang === candidate.locale, `${pageName}: fallback lang drifted to ${state.lang}`);
    assert(state.runtimeReady, `${pageName}: fallback runtime did not become ready`);
    assert(state.presentation === 'globe', `${pageName}: fallback presentation is ${state.presentation}`);
    assert(state.mapRenders > 0 && state.mapCanvasReady, `${pageName}: fallback globe did not render`);
    assert(!/\[missing:[^\]]+\]/u.test(state.bodyText), `${pageName}: fallback rendered a missing marker`);
    assert(pageErrors.length === 0, `${pageName}: fallback page errors: ${pageErrors.join(' | ')}`);
    const fallbackWarnings = warnings.filter((message) => message.includes('Wave-1 locale pack unavailable'));
    assert(fallbackWarnings.length === 1, `${pageName}: expected one fallback warning, got ${fallbackWarnings.length}: ${warnings.join(' | ')}`);
    localePackResilience.push({ page: pageName, locale: candidate.locale, surface: 'globe', mapRenders: state.mapRenders, verdict: 'PASS' });
    await context.close();

    const proposalName = `propose.${candidate.locale}.html`;
    const proposalContext = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
    const proposalPage = await proposalContext.newPage();
    const proposalErrors = [];
    const proposalWarnings = [];
    proposalPage.on('pageerror', (error) => proposalErrors.push(error.message));
    proposalPage.on('console', (message) => {
      if (message.type() === 'warning') proposalWarnings.push(message.text());
    });
    await proposalPage.route('**/assets/commonworld-wave1-locales.mjs*', (route) => route.abort('failed'));
    const proposalResponse = await proposalPage.goto(`${baseUrl}/${proposalName}`, { waitUntil: 'domcontentloaded' });
    assert(proposalResponse?.status() === 200, `${proposalName}: fallback HTTP ${proposalResponse?.status()}`);
    await proposalPage.locator('input[name=website_confirm]').fill('bot');
    await proposalPage.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
    await proposalPage.waitForSelector('#proposal-errors:not([hidden])');
    const proposalState = await proposalPage.evaluate(() => ({
      lang: document.documentElement.lang,
      errors: document.querySelector('#proposal-errors')?.textContent ?? '',
      bodyText: document.body.textContent ?? '',
    }));
    assert(proposalState.lang === candidate.locale, `${proposalName}: fallback lang drifted to ${proposalState.lang}`);
    assert(proposalState.errors.includes('Automated submission blocked.'), `${proposalName}: English runtime fallback missing: ${proposalState.errors}`);
    assert(!/\[missing:[^\]]+\]/u.test(proposalState.bodyText), `${proposalName}: fallback rendered a missing marker`);
    assert(proposalErrors.length === 0, `${proposalName}: fallback page errors: ${proposalErrors.join(' | ')}`);
    const proposalFallbackWarnings = proposalWarnings.filter((message) => message.includes('Proposal locale pack unavailable'));
    assert(proposalFallbackWarnings.length === 1, `${proposalName}: expected one fallback warning, got ${proposalFallbackWarnings.length}: ${proposalWarnings.join(' | ')}`);
    localePackResilience.push({ page: proposalName, locale: candidate.locale, surface: 'proposal', verdict: 'PASS' });
    await proposalContext.close();
  }

  console.log(JSON.stringify({
    kind: 'commonworld.locale_lifecycle_browser_smoke',
    verdict: 'PASS',
    pages: results.length,
    claims,
    releasedIsolation,
    localePackResilience,
    results,
  }, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
