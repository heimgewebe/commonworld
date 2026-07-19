import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const INTERACTIVE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'summary',
  '[role="button"]',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');
const VIEWPORTS = [
  { name: 'phone-small', width: 320, height: 568, mobile: true },
  { name: 'phone', width: 390, height: 844, mobile: true },
  { name: 'tablet', width: 768, height: 1024, mobile: true },
  { name: 'desktop', width: 1366, height: 768, mobile: false },
];
const MIME_TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
  ['.woff2', 'font/woff2'],
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function createServer() {
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://127.0.0.1');
      let relative = decodeURIComponent(url.pathname);
      if (relative === '/') relative = '/index.html';
      const target = path.resolve(ROOT, `.${relative}`);
      if (!target.startsWith(`${ROOT}${path.sep}`)) throw new Error('path traversal');
      const body = await readFile(target);
      response.writeHead(200, {
        'cache-control': 'no-store',
        'content-type': MIME_TYPES.get(path.extname(target)) ?? 'application/octet-stream',
      });
      response.end(body);
    } catch {
      response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('not found');
    }
  });
}

async function auditOpenFocus(page, viewportName) {
  const result = await page.evaluate((interactiveSelector) => {
    const focus = document.querySelector('#project-focus');
    const globe = document.querySelector('#globe-surface');
    const focusRect = focus.getBoundingClientRect();
    const identity = (element) => `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}${element.className ? `.${String(element.className.baseVal ?? element.className).trim().replace(/\s+/g, '.')}` : ''}`;
    const visibleRect = (element) => {
      if (element.closest('[hidden]')) return null;
      const style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return null;
      const rect = element.getBoundingClientRect();
      const left = Math.max(0, rect.left);
      const top = Math.max(0, rect.top);
      const right = Math.min(innerWidth, rect.right);
      const bottom = Math.min(innerHeight, rect.bottom);
      if (right <= left || bottom <= top) return null;
      return { left, top, right, bottom, area: (right - left) * (bottom - top) };
    };
    const coveredRatio = (rect) => {
      const width = Math.max(0, Math.min(rect.right, focusRect.right) - Math.max(rect.left, focusRect.left));
      const height = Math.max(0, Math.min(rect.bottom, focusRect.bottom) - Math.max(rect.top, focusRect.top));
      return rect.area > 0 ? (width * height) / rect.area : 0;
    };
    const isBlocked = (element) => Boolean(element.closest('[inert]')) || (
      element.getAttribute('tabindex') === '-1'
      && element.getAttribute('aria-hidden') === 'true'
      && getComputedStyle(element).pointerEvents === 'none'
    );
    const expected = [...globe.querySelectorAll(interactiveSelector)]
      .map((element) => ({ element, rect: visibleRect(element) }))
      .filter(({ rect }) => rect && coveredRatio(rect) >= 0.5);
    const missing = expected.filter(({ element }) => !isBlocked(element)).map(({ element }) => identity(element));
    const managed = [...document.querySelectorAll('[data-focus-overlap-inert="true"]')];
    const invalidManaged = managed.filter((element) => !isBlocked(element)).map(identity);
    const htmlFocusEscapes = [];
    for (const { element } of expected) {
      if (!(element instanceof HTMLElement)) continue;
      element.focus({ preventScroll: true });
      if (document.activeElement === element) htmlFocusEscapes.push(identity(element));
    }
    focus.focus({ preventScroll: true });
    return {
      expected: expected.map(({ element }) => identity(element)),
      focusHidden: focus.hidden,
      htmlFocusEscapes,
      invalidManaged,
      managed: managed.map(identity),
      missing,
      searchInert: Boolean(document.querySelector('#commons-search').closest('[inert]')),
      topbarInert: document.querySelector('.topbar').hasAttribute('inert'),
    };
  }, INTERACTIVE_SELECTOR);

  assert(!result.focusHidden, `${viewportName}: project focus is hidden`);
  assert(result.expected.length > 0, `${viewportName}: test did not find a covered target`);
  assert(result.managed.length > 0, `${viewportName}: no covered target was managed`);
  assert(result.missing.length === 0, `${viewportName}: covered targets remain active: ${result.missing.join(', ')}`);
  assert(result.invalidManaged.length === 0, `${viewportName}: managed targets are not blocked: ${result.invalidManaged.join(', ')}`);
  assert(result.htmlFocusEscapes.length === 0, `${viewportName}: blocked HTML targets accepted focus: ${result.htmlFocusEscapes.join(', ')}`);
  assert(!result.topbarInert, `${viewportName}: free topbar navigation was blocked`);
  assert(!result.searchInert, `${viewportName}: free search control was blocked`);

  await page.locator('#project-focus').focus();
  const tabEscapes = [];
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press('Tab');
    const escaped = await page.evaluate(() => {
      const active = document.activeElement;
      return active?.closest?.('[data-focus-overlap-inert="true"]')
        ? `${active.tagName.toLowerCase()}#${active.id || ''}`
        : null;
    });
    if (escaped) tabEscapes.push(escaped);
  }
  assert(tabEscapes.length === 0, `${viewportName}: covered targets entered tab order: ${tabEscapes.join(', ')}`);

  return result;
}

async function verifyRestoration(page, viewportName) {
  await page.locator('#focus-close').click();
  await page.waitForFunction(() => document.querySelector('#project-focus').hidden);
  await page.waitForTimeout(50);
  const restored = await page.evaluate(() => ({
    globeResetInert: document.querySelector('#globe-reset').hasAttribute('inert'),
    managedInert: document.querySelectorAll('[inert][data-focus-overlap-inert]').length,
    markers: document.querySelectorAll('[data-focus-overlap-inert="true"]').length,
    sphereAriaHidden: document.querySelector('#sphere-edge-control').getAttribute('aria-hidden'),
    spherePointerEvents: getComputedStyle(document.querySelector('#sphere-edge-control')).pointerEvents,
    sphereTabindex: document.querySelector('#sphere-edge-control').getAttribute('tabindex'),
    zoomInInert: document.querySelector('.maplibregl-ctrl-zoom-in')?.hasAttribute('inert') ?? false,
  }));
  assert(restored.markers === 0, `${viewportName}: managed markers remained after close`);
  assert(restored.managedInert === 0, `${viewportName}: managed inert state remained after close`);
  assert(!restored.zoomInInert, `${viewportName}: zoom control remained inert after close`);
  assert(!restored.globeResetInert, `${viewportName}: globe reset remained inert after close`);
  assert(restored.sphereTabindex === '0', `${viewportName}: sphere tabindex was not restored`);
  assert(restored.sphereAriaHidden === null, `${viewportName}: sphere aria-hidden was not restored`);
  assert(restored.spherePointerEvents !== 'none', `${viewportName}: sphere pointer events were not restored`);
  return restored;
}

async function verifyJourneyOwnership(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  try {
    await page.goto(`${baseUrl}/?project=wikidata&view=layers`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('html.runtime-ready');
    await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.viewPhase === 'layers');
    let state = await page.evaluate(() => ({
      focusHidden: document.querySelector('#project-focus').hidden,
      layerToggleInert: document.querySelector('#layer-view-button').hasAttribute('inert'),
      orientationInert: document.querySelector('.orientation-bar').hasAttribute('inert'),
    }));
    assert(!state.focusHidden && state.layerToggleInert && state.orientationInert, `journey initial ownership failed: ${JSON.stringify(state)}`);
    await page.locator('#focus-close').click();
    await page.waitForFunction(() => document.querySelector('#project-focus').hidden);
    state = await page.evaluate(() => ({
      layerToggleInert: document.querySelector('#layer-view-button').hasAttribute('inert'),
      orientationInert: document.querySelector('.orientation-bar').hasAttribute('inert'),
    }));
    assert(state.layerToggleInert && state.orientationInert, `journey ownership was lost after focus close: ${JSON.stringify(state)}`);
    await page.locator('#layer-close').click();
    await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.viewPhase === 'overview');
    state = await page.evaluate(() => ({
      layerToggleInert: document.querySelector('#layer-view-button').hasAttribute('inert'),
      orientationInert: document.querySelector('.orientation-bar').hasAttribute('inert'),
    }));
    assert(!state.layerToggleInert && !state.orientationInert, `journey ownership was not released: ${JSON.stringify(state)}`);
    return state;
  } finally {
    await context.close();
  }
}

async function verifyDeferredSphereRestoration(browser, baseUrl) {
  const context = await browser.newContext({
    viewport: { width: 320, height: 568 },
    isMobile: true,
    hasTouch: true,
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  try {
    await page.goto(`${baseUrl}/?project=wikidata`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('html.runtime-ready');
    await page.waitForFunction(() => document.querySelector('#sphere-edge-control')?.dataset.focusOverlapInert === 'true');
    await page.evaluate(() => {
      const url = new URL(location.href);
      url.searchParams.set('view', 'layers');
      history.pushState(null, '', url);
      dispatchEvent(new PopStateEvent('popstate'));
    });
    await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.viewPhase === 'layers');
    await page.locator('#focus-close').click();
    await page.waitForFunction(() => document.querySelector('#project-focus').hidden);
    let sphere = await page.evaluate(() => {
      const edge = document.querySelector('#sphere-edge-control');
      return {
        ariaHidden: edge.getAttribute('aria-hidden'),
        marker: edge.dataset.focusOverlapInert ?? null,
        pointerEvents: getComputedStyle(edge).pointerEvents,
        tabindex: edge.getAttribute('tabindex'),
      };
    });
    assert(sphere.marker === 'true' && sphere.tabindex === '-1' && sphere.ariaHidden === 'true' && sphere.pointerEvents === 'none', `deferred sphere block was lost: ${JSON.stringify(sphere)}`);
    await page.locator('#layer-close').click();
    await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.viewPhase === 'overview');
    await page.waitForFunction(() => document.querySelector('#sphere-edge-control')?.dataset.focusOverlapInert === undefined);
    sphere = await page.evaluate(() => {
      const edge = document.querySelector('#sphere-edge-control');
      return {
        ariaHidden: edge.getAttribute('aria-hidden'),
        marker: edge.dataset.focusOverlapInert ?? null,
        pointerEvents: getComputedStyle(edge).pointerEvents,
        tabindex: edge.getAttribute('tabindex'),
      };
    });
    assert(sphere.marker === null && sphere.tabindex === '0' && sphere.ariaHidden === null && sphere.pointerEvents !== 'none', `deferred sphere block was not restored: ${JSON.stringify(sphere)}`);
    return sphere;
  } finally {
    await context.close();
  }
}

const server = createServer();
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/google-chrome' });
const results = [];
try {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.mobile,
      hasTouch: viewport.mobile,
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));
    try {
      await page.goto(`${baseUrl}/?project=wikidata`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('html.runtime-ready');
      await page.waitForFunction(() => document.querySelectorAll('[data-focus-overlap-inert="true"]').length > 0);
      const opened = await auditOpenFocus(page, viewport.name);
      const restored = await verifyRestoration(page, viewport.name);
      assert(pageErrors.length === 0, `${viewport.name}: page errors: ${pageErrors.join('; ')}`);
      results.push({ viewport: viewport.name, opened, restored });
    } finally {
      await context.close();
    }
  }
  results.push({ journeyOwnership: await verifyJourneyOwnership(browser, baseUrl) });
  results.push({ deferredSphereRestoration: await verifyDeferredSphereRestoration(browser, baseUrl) });
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

process.stdout.write(`${JSON.stringify({ verdict: 'PASS', results })}\n`);
