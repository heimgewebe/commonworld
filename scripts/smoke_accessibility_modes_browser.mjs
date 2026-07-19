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
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'summary',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

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
if (!address || typeof address === 'string') throw new Error('accessibility smoke server has no TCP address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || (existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);
const browser = await chromium.launch({ headless: true, executablePath });
const scenarios = [];

async function newObservedPage({ viewport = { width: 1280, height: 900 }, forcedColors = 'none', contrast = 'no-preference' } = {}) {
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.emulateMedia({ forcedColors, contrast, reducedMotion: 'reduce' });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  return { context, page, pageErrors };
}

async function installTabProbe(page, rootSelector, label) {
  return page.evaluate(({ selector, focusableSelector, probeLabel }) => {
    const root = document.querySelector(selector);
    if (!root) throw new Error(`missing focus root: ${selector}`);
    document.querySelectorAll('[data-a11y-tab-probe]').forEach((node) => node.removeAttribute('data-a11y-tab-probe'));
    const nodes = [...root.querySelectorAll(focusableSelector)].filter((node) => {
      if (node.matches(':disabled, [aria-disabled="true"]')) return false;
      if (node.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
      const closedDetails = node.closest('details:not([open])');
      if (closedDetails && node.tagName !== 'SUMMARY') return false;
      const style = getComputedStyle(node);
      return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
    });
    nodes.forEach((node, index) => node.setAttribute('data-a11y-tab-probe', `${probeLabel}-${index}`));
    return nodes.map((node) => node.getAttribute('data-a11y-tab-probe'));
  }, { selector: rootSelector, focusableSelector: FOCUSABLE_SELECTOR, probeLabel: label });
}

async function waitForFocusedElementInViewport(page, label) {
  try {
    await page.waitForFunction(() => {
      const node = document.activeElement;
      if (!node || node === document.body) return false;
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.left < innerWidth && rect.bottom > 0 && rect.top < innerHeight;
    }, null, { timeout: 1000 });
  } catch (error) {
    const diagnostic = await page.evaluate(() => {
      const node = document.activeElement;
      const rect = node?.getBoundingClientRect?.();
      return {
        tag: node?.tagName ?? null,
        id: node?.id || null,
        className: node?.getAttribute?.('class') || null,
        probe: node?.getAttribute?.('data-a11y-tab-probe') || null,
        rect: rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null,
        viewport: { width: innerWidth, height: innerHeight },
      };
    });
    throw new Error(`${label}: focused element did not settle inside the viewport ${JSON.stringify(diagnostic)}`, { cause: error });
  }
}

async function activeFocusSnapshot(page) {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (!node || node === document.body) return null;
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      key: node.getAttribute('data-a11y-tab-probe'),
      tag: node.tagName,
      id: node.id || null,
      name: node.getAttribute('name'),
      focusVisible: node.matches(':focus-visible'),
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth) || 0,
      rect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height },
      viewport: { width: innerWidth, height: innerHeight },
      hidden: Boolean(node.closest('[hidden], [inert], [aria-hidden="true"]')),
    };
  });
}

function assertFocusIntegrity(snapshot, label) {
  assert(snapshot, `${label}: browser did not expose an active element`);
  assert(!snapshot.hidden, `${label}: focus entered a hidden, inert or aria-hidden surface ${JSON.stringify(snapshot)}`);
  assert(snapshot.focusVisible, `${label}: keyboard focus is not :focus-visible ${JSON.stringify(snapshot)}`);
  assert(snapshot.outlineStyle !== 'none' && snapshot.outlineWidth >= 2, `${label}: visible focus outline missing ${JSON.stringify(snapshot)}`);
  assert(snapshot.rect.width > 0 && snapshot.rect.height > 0, `${label}: focused control has no geometry ${JSON.stringify(snapshot)}`);
  assert(snapshot.rect.right > 0 && snapshot.rect.left < snapshot.viewport.width && snapshot.rect.bottom > 0 && snapshot.rect.top < snapshot.viewport.height, `${label}: focused control is outside the viewport ${JSON.stringify(snapshot)}`);
}

async function tabThroughSurface(page, rootSelector, label) {
  const expected = await installTabProbe(page, rootSelector, label);
  assert(expected.length > 0, `${label}: surface has no keyboard-focusable controls`);
  await page.evaluate(() => document.activeElement?.blur?.());
  const observed = [];
  const observedDetails = [];
  const maxAttempts = expected.length + 4;
  for (let attempt = 0; attempt < maxAttempts && observed.length < expected.length; attempt += 1) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(() => document.activeElement === document.body)) continue;
    await waitForFocusedElementInViewport(page, `${label} tab ${observed.length + 1}/${expected.length}`);
    const snapshot = await activeFocusSnapshot(page);
    assertFocusIntegrity(snapshot, `${label} tab ${observed.length + 1}/${expected.length}`);
    assert(snapshot.key, `${label}: browser focused an unprobed element ${JSON.stringify(snapshot)}`);
    assert(!observed.includes(snapshot.key), `${label}: focus cycled before every visible control was reached ${JSON.stringify({ expected, observed, repeated: snapshot.key })}`);
    observed.push(snapshot.key);
    observedDetails.push({ key: snapshot.key, tag: snapshot.tag, id: snapshot.id, name: snapshot.name });
  }
  const firstIndex = expected.indexOf(observed[0]);
  const rotatedExpected = firstIndex < 0 ? [] : [...expected.slice(firstIndex), ...expected.slice(0, firstIndex)];
  const expectedDetails = await page.evaluate(() => [...document.querySelectorAll('[data-a11y-tab-probe]')].map((node) => ({
    key: node.getAttribute('data-a11y-tab-probe'),
    tag: node.tagName,
    id: node.id || null,
    className: node.getAttribute('class') || null,
  })));
  assert(observed.length === expected.length && JSON.stringify(observed) === JSON.stringify(rotatedExpected), `${label}: tab order diverged from the visible cyclic DOM order ${JSON.stringify({ expected: expectedDetails, observed: observedDetails })}`);
  return expected.length;
}

async function tabTo(page, selector, label, maxTabs = 400) {
  await installTabProbe(page, 'body', `${label}-target`);
  await page.evaluate(() => document.activeElement?.blur?.());
  for (let index = 0; index < maxTabs; index += 1) {
    await page.keyboard.press('Tab');
    const matches = await page.evaluate((target) => document.activeElement?.matches(target) === true, selector);
    if (!matches) continue;
    await waitForFocusedElementInViewport(page, label);
    const snapshot = await activeFocusSnapshot(page);
    assertFocusIntegrity(snapshot, label);
    return snapshot;
  }
  throw new Error(`${label}: ${selector} was not reached by keyboard within ${maxTabs} tabs`);
}

async function activateByKeyboard(page, selector, label, key = 'Enter') {
  await tabTo(page, selector, label);
  await page.keyboard.press(key);
}

async function forcedColorsPublicScenario() {
  const run = await newObservedPage({ forcedColors: 'active' });
  const { page } = run;
  await page.goto(`${baseUrl}/index.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('html.runtime-ready');
  assert(await page.evaluate(() => matchMedia('(forced-colors: active)').matches), 'public forced colors: media query is not active');

  const globeCount = await tabThroughSurface(page, 'body', 'forced-public-globe');
  assert(globeCount >= 8, `public forced colors: unexpectedly small globe keyboard surface (${globeCount})`);

  await activateByKeyboard(page, '#filter-toggle', 'public discovery toggle');
  await page.locator('#discovery-panel').waitFor({ state: 'visible' });
  assert(await page.locator('#filter-toggle').getAttribute('aria-expanded') === 'true', 'public discovery: aria-expanded did not become true');
  await tabThroughSurface(page, 'body', 'forced-public-discovery');
  await activateByKeyboard(page, '#filter-presence-geographic', 'public geographic presence checkbox', 'Space');
  assert(await page.locator('#filter-presence-geographic').isChecked(), 'public discovery: keyboard Space did not expose native checked state');
  const checkedStyle = await page.locator('#filter-presence-geographic').evaluate((node) => {
    const style = getComputedStyle(node);
    return { outlineStyle: style.outlineStyle, outlineWidth: Number.parseFloat(style.outlineWidth) || 0 };
  });
  assert(checkedStyle.outlineStyle !== 'none' && checkedStyle.outlineWidth >= 2, `public discovery: checked state lacks a non-color outline ${JSON.stringify(checkedStyle)}`);
  await activateByKeyboard(page, '#discovery-close', 'public discovery close');
  await page.locator('#discovery-panel').waitFor({ state: 'hidden' });

  await activateByKeyboard(page, '#settings-toggle', 'public settings toggle');
  await page.locator('#settings-panel').waitFor({ state: 'visible' });
  assert(await page.locator('#settings-panel').getAttribute('aria-modal') === 'true', 'public settings: modal semantic missing');
  await tabThroughSurface(page, '#settings-panel', 'forced-public-settings');
  await activateByKeyboard(page, '[data-presentation-choice="text"]', 'public text presentation');
  assert(await page.locator('[data-presentation-choice="text"]').getAttribute('aria-checked') === 'true', 'public settings: text radio did not expose aria-checked=true');
  if (await page.locator('#settings-panel').isVisible()) {
    await activateByKeyboard(page, '#settings-close', 'public settings close');
  }
  await page.locator('#settings-panel').waitFor({ state: 'hidden' });
  await page.locator('#text-view').waitFor({ state: 'visible' });

  const textCount = await tabThroughSurface(page, 'body', 'forced-public-text');
  assert(textCount > globeCount, `public text view: expected a larger complete keyboard surface (${textCount} <= ${globeCount})`);
  await activateByKeyboard(page, '.catalog-select', 'public catalog selection');
  await page.locator('#project-focus').waitFor({ state: 'visible' });
  assert(await page.locator('.catalog-select[aria-pressed="true"]').count() === 1, 'public catalog selection: exactly one aria-pressed=true state was not exposed');

  assert(run.pageErrors.length === 0, `public forced colors: page errors ${run.pageErrors.join(' | ')}`);
  scenarios.push({ id: 'forced-colors-public-keyboard', verdict: 'PASS', globeFocusables: globeCount, textFocusables: textCount });
  await run.context.close();
}

async function forcedColorsProposalScenario() {
  const run = await newObservedPage({ forcedColors: 'active', viewport: { width: 1024, height: 768 } });
  const { page } = run;
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'domcontentloaded' });
  assert(await page.evaluate(() => matchMedia('(forced-colors: active)').matches), 'proposal forced colors: media query is not active');
  assert(await page.locator('input[name="region"]').isDisabled(), 'proposal forced colors: region should start disabled');

  const initialCount = await tabThroughSurface(page, 'body', 'forced-proposal-initial');
  await activateByKeyboard(page, 'input[name="presence_geographic"]', 'proposal geographic presence checkbox', 'Space');
  assert(await page.locator('input[name="presence_geographic"]').isChecked(), 'proposal forced colors: checkbox did not become checked');
  assert(!(await page.locator('input[name="region"]').isDisabled()), 'proposal forced colors: region did not expose enabled state');
  const enabledCount = await tabThroughSurface(page, 'body', 'forced-proposal-geographic');
  assert(enabledCount >= initialCount + 2, `proposal forced colors: enabling geography did not add both controls (${initialCount} -> ${enabledCount})`);

  await activateByKeyboard(page, 'button[type="submit"]', 'proposal invalid submit');
  await page.locator('#proposal-errors').waitFor({ state: 'visible' });
  const errorState = await page.locator('#proposal-errors').evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      role: node.getAttribute('role'),
      focused: document.activeElement === node,
      borderStyle: style.borderStyle,
      borderWidth: Number.parseFloat(style.borderWidth) || 0,
      text: node.textContent,
    };
  });
  assert(errorState.role === 'alert' && errorState.focused, `proposal forced colors: validation alert did not receive semantic focus ${JSON.stringify(errorState)}`);
  assert(errorState.borderStyle !== 'none' && errorState.borderWidth >= 2, `proposal forced colors: validation alert lacks a structural boundary ${JSON.stringify(errorState)}`);
  assert(errorState.text.includes('Bitte korrigieren'), `proposal forced colors: validation message missing ${JSON.stringify(errorState)}`);

  assert(run.pageErrors.length === 0, `proposal forced colors: page errors ${run.pageErrors.join(' | ')}`);
  scenarios.push({ id: 'forced-colors-proposal-keyboard', verdict: 'PASS', initialFocusables: initialCount, geographicFocusables: enabledCount });
  await run.context.close();
}

async function increasedContrastScenario() {
  for (const target of [
    { id: 'public', path: 'index.html', focus: '#filter-toggle', border: '#filter-toggle' },
    { id: 'proposal', path: 'propose.html', focus: 'input[name="name"]', border: 'input[name="name"]' },
  ]) {
    const run = await newObservedPage({ contrast: 'more' });
    const { page } = run;
    await page.goto(`${baseUrl}/${target.path}`, { waitUntil: 'domcontentloaded' });
    if (target.id === 'public') await page.waitForSelector('html.runtime-ready');
    assert(await page.evaluate(() => matchMedia('(prefers-contrast: more)').matches), `${target.id} contrast: media query is not active`);
    await tabTo(page, target.focus, `${target.id} increased-contrast focus`);
    const style = await page.locator(target.border).evaluate((node) => {
      const value = getComputedStyle(node);
      return {
        transitionProperty: value.transitionProperty,
        outlineStyle: value.outlineStyle,
        outlineWidth: Number.parseFloat(value.outlineWidth) || 0,
        focusToken: getComputedStyle(document.documentElement).getPropertyValue('--focus').trim(),
        matchingMedia: [...document.styleSheets].flatMap((sheet) => {
          try {
            return [...sheet.cssRules].filter((rule) => rule.media?.mediaText?.includes('prefers-contrast')).map((rule) => ({ media: rule.media.mediaText, matches: matchMedia(rule.media.mediaText).matches }));
          } catch { return []; }
        }),
        borderWidth: Math.max(
          Number.parseFloat(value.borderTopWidth) || 0,
          Number.parseFloat(value.borderRightWidth) || 0,
          Number.parseFloat(value.borderBottomWidth) || 0,
          Number.parseFloat(value.borderLeftWidth) || 0,
        ),
      };
    });
    assert(style.transitionProperty === 'none', `${target.id} contrast: reduced-motion mode still transitions focus properties ${JSON.stringify(style)}`);
    assert(style.outlineStyle !== 'none' && style.outlineWidth >= 4, `${target.id} contrast: strengthened focus indicator missing ${JSON.stringify(style)}`);
    assert(style.borderWidth >= 2, `${target.id} contrast: strengthened control boundary missing ${JSON.stringify(style)}`);
    assert(run.pageErrors.length === 0, `${target.id} contrast: page errors ${run.pageErrors.join(' | ')}`);
    scenarios.push({ id: `increased-contrast-${target.id}`, verdict: 'PASS' });
    await run.context.close();
  }
}

try {
  await forcedColorsPublicScenario();
  await forcedColorsProposalScenario();
  await increasedContrastScenario();
} finally {
  await browser.close();
  server.closeAllConnections?.();
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

process.stdout.write(`${JSON.stringify({ verdict: 'PASS', scenarios })}\n`);
