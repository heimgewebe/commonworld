import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';

const ROOT = process.cwd();
const MIME = new Map([['.html', 'text/html; charset=utf-8'], ['.css', 'text/css; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'], ['.mjs', 'text/javascript; charset=utf-8'], ['.json', 'application/json; charset=utf-8'], ['.svg', 'image/svg+xml']]);
// Tunable constants for the iPad landscape scroll probe and geometry stability wait.
const SCROLL_PROBE_HEIGHT_PX = 5000;
const SCROLL_WHEEL_DELTA_PX = 4000;
const MIN_SCROLL_Y_PX = 200;
const STABLE_FRAME_THRESHOLD = 3;
const GEOMETRY_EPSILON_PX = 0.5;
const STABILITY_TIMEOUT_MS = 2000;
const SCROLL_WAIT_TIMEOUT_MS = 5000;
function assert(condition, message) { if (!condition) throw new Error(message); }
function safePath(url) { const relative = decodeURIComponent(new URL(url, 'http://localhost').pathname).replace(/^\/+/, '') || 'propose.html'; const target = path.resolve(ROOT, relative); return target === ROOT || target.startsWith(`${ROOT}${path.sep}`) ? target : null; }
async function respondNotFound(response) {
  response.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
  response.end(await readFile(path.join(ROOT, '404.html')));
}
const server = createServer(async (request, response) => {
  try {
    const target = safePath(request.url ?? '/propose.html');
    if (!target || !(await stat(target)).isFile()) throw new Error('missing');
    response.writeHead(200, { 'Content-Type': MIME.get(path.extname(target)) ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
    response.end(await readFile(target));
  } catch { await respondNotFound(response); }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const address = server.address();
if (!address || typeof address === 'string') throw new Error('proposal smoke server missing address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
  args: ['--enable-unsafe-swiftshader'],
});
const results = [];

async function fillValid(page, name = 'Browser Test Commons') {
  await page.getByLabel('Name of the Commons').fill(name);
  await page.getByLabel('Short description').fill('Eine gemeinschaftlich verwaltete Ressource mit offenen Regeln, offiziellen Quellen und einem realen öffentlichen Beteiligungsweg.');
  await page.getByLabel('Official website').fill('https://example.net/commons');
  await page.getByLabel('Commons type').selectOption('other');
  await page.getByRole('checkbox', { name: 'On site', exact: true }).check();
  await page.getByRole('checkbox', { name: 'Digital', exact: true }).check();
  await page.getByLabel('Broad region or place').fill('Norddeutschland');
  await page.getByLabel('HTTPS link').first().fill('https://example.net/commons/about');
  await page.getByLabel('Primary-near sources').fill('https://example.net/commons/governance');
  await page.getByLabel('I understand that the preferred GitHub intake path is public.').check();
  await page.getByLabel('I consent to editorial processing of the submitted information.').check();
  await page.getByLabel('I have not entered a private address, coordinates, email address, phone number, or private network or household information.').check();
}

async function fillCandidateValid(page, { name, description, region }) {
  const form = page.locator('#commons-proposal-form');
  await form.locator('[name="name"]').fill(name);
  await form.locator('[name="description"]').fill(description);
  await form.locator('[name="official_website"]').fill('https://example.net/commons');
  await form.locator('[name="commons_type"]').selectOption('other');
  await form.locator('[name="presence_geographic"]').check();
  await form.locator('[name="presence_digital"]').check();
  await form.locator('[name="region"]').fill(region);
  await form.locator('[name="action_url_1"]').fill('https://example.net/commons/about');
  await form.locator('[name="sources"]').fill('https://example.net/commons/governance');
  await form.locator('[name="public_issue_acknowledged"]').check();
  await form.locator('[name="processing_agreed"]').check();
  await form.locator('[name="no_sensitive_data_confirmed"]').check();
}

for (const profile of [
  { name: 'desktop', viewport: { width: 1280, height: 900 }, mobile: false },
  { name: 'mobile', viewport: { width: 390, height: 844 }, mobile: true },
  { name: 'ipad-portrait', viewport: { width: 820, height: 1180 }, mobile: true },
  { name: 'ipad-landscape', viewport: { width: 1180, height: 820 }, mobile: true },
  { name: 'mobile-text-200', viewport: { width: 390, height: 844 }, mobile: true, fontScale: 200 },
]) {
  const context = await browser.newContext({ viewport: profile.viewport, isMobile: profile.mobile, hasTouch: profile.mobile, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const pageErrors = []; page.on('pageerror', (error) => pageErrors.push(String(error)));
  if (profile.fontScale) {
    await page.route('**/index.css', async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, body: `${await response.text()}
html { font-size: ${profile.fontScale}% !important; }
` });
    });
  }
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  assert(await page.getByRole('heading', { name: 'Suggest a Commons' }).isVisible(), `${profile.name}: heading missing`);
  assert(await page.getByRole('button', { name: 'Prepare public GitHub issue' }).isVisible(), `${profile.name}: submit missing`);
  const backLink = page.locator('.secondary-back-link');
  await backLink.waitFor({ state: 'visible' });
  const backBox = await backLink.boundingBox();
  assert(backBox && backBox.width >= 44 && backBox.height >= 44, `${profile.name}: back navigation is an undersized touch target ${JSON.stringify(backBox)}`);
  const contractLinkBoxes = await page.locator('.proposal-contracts a').evaluateAll((nodes) => nodes.map((node) => {
    const rect = node.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  }));
  assert(contractLinkBoxes.length === 4 && contractLinkBoxes.every(({ width, height }) => width >= 44 && height >= 44), `${profile.name}: proposal contract navigation has undersized touch targets ${JSON.stringify(contractLinkBoxes)}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert(overflow <= 1, `${profile.name}: horizontal overflow ${overflow}`);
  if (profile.fontScale) {
    const skipLink = page.locator('.skip-link');
    await skipLink.focus();
    const skipBox = await skipLink.boundingBox();
    assert(skipBox && skipBox.x >= 0 && skipBox.x + skipBox.width <= profile.viewport.width + 1, `${profile.name}: focused skip link overflows the viewport ${JSON.stringify(skipBox)}`);
  }
  const fieldsetLegends = await page.locator('form fieldset > legend').allTextContents();
  assert(JSON.stringify(fieldsetLegends) === JSON.stringify(['Project', 'Presence', 'Evidenced ways to engage', 'Sources and notes', 'Consent and public visibility']), `${profile.name}: semantic fieldsets differ ${JSON.stringify(fieldsetLegends)}`);
  assert(await page.locator('input[name="region"]').isDisabled(), `${profile.name}: geographic region is active without Vor Ort`);
  assert(pageErrors.length === 0, `${profile.name}: page errors ${pageErrors.join('; ')}`);
  results.push(profile.name);
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.de.html`, { waitUntil: 'networkidle' });
  assert(await page.getByRole('heading', { name: 'Ein Commons vorschlagen' }).isVisible(), 'German proposal locale: heading missing');
  assert(await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).isVisible(), 'German proposal locale: submit missing');
  assert(await page.locator('.language-switch a[data-locale-choice="en"][lang="en"]').count() > 0, 'German proposal locale: English switch target missing');
  results.push('locale-german');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const currentManifest = JSON.parse(await readFile(path.join(ROOT, 'assets/commonworld-page-builds.json'), 'utf8'));
  const latestRelease = 'f'.repeat(20);
  const latestManifest = { ...currentManifest, release_id: latestRelease };
  let releaseFirstProbe = null;
  let probeCount = 0;
  await page.route('**/__cw_probe/**', async (route) => {
    probeCount += 1;
    if (probeCount === 1) await new Promise((resolve) => { releaseFirstProbe = resolve; });
    await route.fulfill({
      status: 404,
      contentType: 'text/html; charset=utf-8',
      body: `<!doctype html><!-- commonworld-release-manifest:${JSON.stringify(latestManifest)} -->`,
    });
  });
  await page.route(`**/releases/${latestRelease}/**`, async (route) => {
    const requested = new URL(route.request().url());
    const suffix = requested.pathname.slice(`/releases/${latestRelease}/`.length);
    const translated = `${baseUrl}/releases/${currentManifest.release_id}/${suffix}${requested.search}`;
    const response = await route.fetch({ url: translated });
    await route.fulfill({ response });
  });
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Suggest a Commons' }).waitFor();
  await fillValid(page, 'Release Draft Test Commons');
  const description = 'A community-managed resource whose started proposal must survive one release-bound reload without server-side form storage.';
  await page.getByLabel('Short description').fill(description);
  for (let attempt = 0; !releaseFirstProbe && attempt < 100; attempt += 1) await page.waitForTimeout(10);
  assert(typeof releaseFirstProbe === 'function', 'release-draft: initial path probe was not intercepted');
  const navigated = page.waitForURL((url) => url.pathname === `/releases/${latestRelease}/propose.html`, { waitUntil: 'domcontentloaded', timeout: 10_000 });
  releaseFirstProbe();
  await navigated;
  await page.getByRole('heading', { name: 'Suggest a Commons' }).waitFor();
  assert(await page.getByLabel('Name of the Commons').inputValue() === 'Release Draft Test Commons', 'release-draft: name was not restored');
  assert(await page.getByLabel('Short description').inputValue() === description, 'release-draft: description was not restored');
  assert((await page.locator('#proposal-status').textContent())?.includes('Draft input was restored'), 'release-draft: restoration status missing');
  assert(await page.evaluate(() => sessionStorage.getItem('commonworldProposalReleaseDraftV1')) === null, 'release-draft: one-shot session draft was not deleted');
  assert(probeCount >= 2, `release-draft: expected a post-navigation probe, got ${probeCount}`);
  results.push('path-release-reload-preserves-one-shot-draft');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function setItem(key, value) {
      if (key === 'commonworldProposalReleaseDraftV1') throw new DOMException('storage blocked', 'QuotaExceededError');
      return original.call(this, key, value);
    };
  });
  const page = await context.newPage();
  const currentManifest = JSON.parse(await readFile(path.join(ROOT, 'assets/commonworld-page-builds.json'), 'utf8'));
  const latestRelease = 'e'.repeat(20);
  const latestManifest = { ...currentManifest, release_id: latestRelease };
  let releaseProbe = null;
  await page.route('**/__cw_probe/**', async (route) => {
    await new Promise((resolve) => { releaseProbe = resolve; });
    await route.fulfill({
      status: 404,
      contentType: 'text/html; charset=utf-8',
      body: `<!doctype html><!-- commonworld-release-manifest:${JSON.stringify(latestManifest)} -->`,
    });
  });
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Suggest a Commons' }).waitFor();
  await page.getByLabel('Name of the Commons').fill('Unsaved Protected Draft');
  for (let attempt = 0; !releaseProbe && attempt < 100; attempt += 1) await page.waitForTimeout(10);
  assert(typeof releaseProbe === 'function', 'release-draft-storage-failure: path probe was not intercepted');
  releaseProbe();
  await page.locator('#proposal-status').filter({ hasText: 'automatic release change was paused' }).waitFor({ timeout: 5000 });
  assert(new URL(page.url()).pathname === '/propose.html', `release-draft-storage-failure: unexpected navigation ${page.url()}`);
  assert(await page.getByLabel('Name of the Commons').inputValue() === 'Unsaved Protected Draft', 'release-draft-storage-failure: form input changed');
  assert(await page.evaluate(() => sessionStorage.getItem('commonworldProposalReleaseDraftV1')) === null, 'release-draft-storage-failure: failed draft unexpectedly persisted');
  results.push('release-navigation-pauses-when-draft-storage-fails');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => ({ opener: window }); });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Success Test Commons');
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  await page.getByText('GitHub was opened.').waitFor();
  assert((await page.getByRole('link', { name: 'Open GitHub directly' }).getAttribute('href')).includes('body='), 'success: structured issue body missing');
  results.push('success-message');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => ({ opener: window }); });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Digital Only Test Commons');
  await page.getByRole('checkbox', { name: 'On site', exact: true }).uncheck();
  const region = page.locator('input[name="region"]');
  assert(await region.isDisabled(), 'digital-only: region remained editable');
  assert(await region.getAttribute('required') === null, 'digital-only: region remained required');
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  await page.getByText('GitHub was opened.').waitFor();
  const issueUrl = new URL(await page.getByRole('link', { name: 'Open GitHub directly' }).getAttribute('href'));
  assert(issueUrl.searchParams.get('body').includes('not applicable (digital only)'), 'digital-only: issue body invented a region');
  results.push('digital-only-without-region');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Reset Sync Test Commons');
  const geographic = page.getByRole('checkbox', { name: 'On site', exact: true });
  const region = page.locator('input[name="region"]');
  assert(await geographic.isChecked(), 'reset-sync: geographic presence was not enabled before reset');
  assert(!(await region.isDisabled()), 'reset-sync: region was disabled before reset');
  await page.locator('#commons-proposal-form').evaluate((form) => form.reset());
  await page.waitForFunction(() => document.querySelector('input[name="region"]')?.disabled === true);
  assert(!(await geographic.isChecked()), 'reset-sync: geographic checkbox did not reset');
  assert(await region.isDisabled(), 'reset-sync: region did not resynchronize after native form reset');
  assert(await region.getAttribute('required') === null, 'reset-sync: region remained required after native form reset');
  results.push('native-reset-resynchronizes-geographic-fields');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => null; });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page);
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).press('Enter');
  await page.getByText('The GitHub tab was blocked.').waitFor();
  assert(await page.getByRole('link', { name: 'Open GitHub directly' }).isVisible(), 'popup-blocked: direct link missing');
  assert(await page.getByRole('button', { name: 'Download validated JSON' }).isVisible(), 'popup-blocked: JSON fallback missing');
  results.push('keyboard-popup-blocked-fallback');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 820, height: 1180 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Offline Test Commons');
  await context.setOffline(true);
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  await page.getByText('No network connection detected.').waitFor();
  results.push('offline-fallback');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  const embeddedIndex = await page.locator('#proposal-catalog-index').evaluate((node) => JSON.parse(node.textContent || '{}'));
  assert(embeddedIndex.titles.includes('Debian'), 'duplicate-index: embedded catalog JSON is invalid or incomplete');
  await fillValid(page, 'Debian');
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  assert((await page.getByRole('alert').textContent()).includes('name is already present'), 'duplicate-index: existing catalog title was not blocked');
  results.push('catalog-duplicate-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, '52.5200, 13.4050');
  await page.getByLabel('Broad region or place').fill('52.5200, 13.4050');
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  assert(await page.getByRole('alert').isVisible(), 'privacy-invalid: error surface missing');
  assert((await page.getByRole('alert').textContent()).includes('no private address or coordinates'), 'privacy-invalid: fail-closed reason missing');
  results.push('privacy-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await page.locator('#commons-proposal-form [name="name"]').fill('مشاع اختبار الإحداثيات');
  await page.locator('#commons-proposal-form [name="description"]').fill('مورد مشترك تديره جماعة محلية وفق قواعد مفتوحة ومصادر رسمية ومسار مشاركة عام موثّق.');
  await page.locator('#commons-proposal-form [name="official_website"]').fill('https://example.net/commons');
  await page.locator('#commons-proposal-form [name="commons_type"]').selectOption('other');
  await page.locator('#commons-proposal-form [name="presence_geographic"]').check();
  await page.locator('#commons-proposal-form [name="presence_digital"]').check();
  await page.locator('#commons-proposal-form [name="region"]').fill('٢٥٫٢٠٤٨، ٥٥٫٢٧٠٨');
  await page.locator('#commons-proposal-form [name="action_url_1"]').fill('https://example.net/commons/about');
  await page.locator('#commons-proposal-form [name="sources"]').fill('https://example.net/commons/governance');
  await page.locator('#commons-proposal-form [name="public_issue_acknowledged"]').check();
  await page.locator('#commons-proposal-form [name="processing_agreed"]').check();
  await page.locator('#commons-proposal-form [name="no_sensitive_data_confirmed"]').check();
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const nativeCoordinateError = (await alert.textContent()) ?? '';
  assert(nativeCoordinateError.includes('إحداثيات'), `privacy-native-arabic: native coordinates were not blocked: ${nativeCoordinateError}`);
  results.push('privacy-native-arabic-coordinates-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'مشاع اختبار درجات الموقع',
    description: 'مورد مشترك تديره جماعة محلية وفق قواعد مفتوحة ومصادر رسمية ومسار مشاركة عام موثّق.',
    region: '٤٨° ٨′ ٠″ شمال، ١١° ٣٤′ ٠″ شرق',
  });
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const error = (await alert.textContent()) ?? '';
  assert(error.includes('إحداثيات'), `privacy-native-arabic-dms: localized DMS coordinates were not blocked: ${error}`);
  assert(await page.locator('#proposal-direct-link').isHidden(), 'privacy-native-arabic-dms: public issue URL became available');
  assert(await page.locator('#proposal-download').isVisible(), 'privacy-native-arabic-dms: validated download control is unavailable');
  let invalidDownloadStarted = false;
  page.once('download', () => { invalidDownloadStarted = true; });
  await page.locator('#proposal-download').click();
  await page.waitForTimeout(100);
  assert(!invalidDownloadStarted, 'privacy-native-arabic-dms: invalid JSON download started');
  assert(((await alert.textContent()) ?? '').includes('إحداثيات'), 'privacy-native-arabic-dms: download validation lost the coordinate error');
  results.push('privacy-native-arabic-dms-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'مشاع اختبار الهاتف',
    description: 'مورد مشترك تديره جماعة محلية وفق قواعد مفتوحة. رقم التواصل الخاص هو +٩٧١ ٥٠ ١٢٣ ٤٥٦٧ ويجب حجبه.',
    region: 'دبي',
  });
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const error = (await alert.textContent()) ?? '';
  assert(error.includes('هاتف'), `privacy-native-arabic-phone: native-digit phone number was not blocked: ${error}`);
  results.push('privacy-native-arabic-phone-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.es.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'Común de prueba de dirección',
    description: 'Recurso compartido administrado por una comunidad con reglas abiertas, fuentes oficiales y participación pública comprobable.',
    region: 'Calle Mayor, nº 12, Madrid',
  });
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const error = (await alert.textContent()) ?? '';
  assert(/direcci|coordenad/iu.test(error), `privacy-spanish-number-marker: localized address marker was not blocked: ${error}`);
  results.push('privacy-spanish-number-marker-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'ا',
    description: 'مورد مشترك تديره جماعة محلية وفق قواعد مفتوحة ومصادر رسمية ومسار مشاركة عام موثّق.',
    region: 'د',
  });
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const error = (await alert.textContent()) ?? '';
  assert(error.includes('الاسم:'), `candidate-field-labels: Arabic Name prefix missing: ${error}`);
  assert(error.includes('المنطقة:'), `candidate-field-labels: Arabic Region prefix missing: ${error}`);
  assert(!error.includes('Name:') && !error.includes('Region:'), `candidate-field-labels: English field prefix leaked: ${error}`);
  results.push('candidate-field-labels-localized');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'No Presence Test');
  await page.getByRole('checkbox', { name: 'On site', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'Digital', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Prepare public GitHub issue' }).click();
  assert(await page.getByRole('alert').isVisible(), 'presence-missing: error surface missing');
  results.push('presence-missing-fail-closed');
  await context.close();
}

async function waitForStableBoundingBox(page, selector, { stableFrames = STABLE_FRAME_THRESHOLD, epsilon = GEOMETRY_EPSILON_PX, timeoutMs = STABILITY_TIMEOUT_MS } = {}) {
  const outcome = await page.evaluate(async ({ sel, stableFrames, epsilon, timeoutMs }) => {
    const el = document.querySelector(sel);
    if (!el) return { ok: false, reason: 'element not found' };
    return await new Promise((resolve) => {
      let lastRect = null;
      let stableCount = 0;
      const near = (a, b) => Math.abs(a - b) < epsilon;
      // A real timer guarantees termination even if requestAnimationFrame stops
      // firing (e.g. a backgrounded or frozen page); it is cleared on success.
      const watchdog = setTimeout(
        () => resolve({ ok: false, reason: 'geometry did not stabilize before timeout' }),
        timeoutMs,
      );
      function finish(result) {
        clearTimeout(watchdog);
        resolve(result);
      }
      function check() {
        const rect = el.getBoundingClientRect();
        if (lastRect && near(lastRect.width, rect.width) && near(lastRect.height, rect.height) && near(lastRect.x, rect.x) && near(lastRect.y, rect.y)) {
          stableCount++;
          if (stableCount >= stableFrames) return finish({ ok: true });
        } else {
          stableCount = 0;
          lastRect = rect;
        }
        requestAnimationFrame(check);
      }
      requestAnimationFrame(check);
    });
  }, { sel: selector, stableFrames, epsilon, timeoutMs });
  assert(outcome.ok, `waitForStableBoundingBox(${selector}): ${outcome.reason}`);
}

// iPad landscape CSS-pixel geometries covered by the ipad-layout.css breakpoint:
// iPad Air / 10.9" (1180x820), iPad Pro 11" (1194x834), iPad 9th gen / iPad mini (1024x768), large iPad/desktop (1366x1024).
const IPAD_LANDSCAPE_VIEWPORTS = [
  { name: 'ipad-large-landscape', width: 1366, height: 1024 },
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

  // propose.html must scroll vertically instead of being clipped by the global body overflow:hidden rule.
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  const scrollInfo = await page.evaluate(() => ({
    bodyOverflowY: getComputedStyle(document.body).overflowY,
    horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  assert(scrollInfo.bodyOverflowY === 'auto' || scrollInfo.bodyOverflowY === 'scroll', `${viewport.name}: propose.html body overflow-y is "${scrollInfo.bodyOverflowY}", expected scrollable`);
  assert(scrollInfo.horizontalOverflow <= 1, `${viewport.name}: propose.html has horizontal overflow ${scrollInfo.horizontalOverflow}`);
  
  await page.evaluate((height) => {
    const probe = document.createElement('div');
    probe.id = 'test-scroll-probe';
    probe.setAttribute('aria-hidden', 'true');
    probe.style.height = `${height}px`;
    document.body.appendChild(probe);
  }, SCROLL_PROBE_HEIGHT_PX);

  try {
    await page.mouse.wheel(0, SCROLL_WHEEL_DELTA_PX);
    await page.waitForFunction(
      (minScroll) => (window.scrollY || document.documentElement.scrollTop) > minScroll,
      MIN_SCROLL_Y_PX,
      { timeout: SCROLL_WAIT_TIMEOUT_MS },
    );
    const scrolledY = await page.evaluate(() => window.scrollY || document.documentElement.scrollTop);
    assert(scrolledY > MIN_SCROLL_Y_PX, `${viewport.name}: propose.html did not actually scroll after a wheel gesture (scrollY ${scrolledY})`);
  } finally {
    // Always remove the probe, even if the scroll assertion above fails.
    await page.evaluate(() => document.getElementById('test-scroll-probe')?.remove());
  }

  // With the probe gone, prove the real submit button is reachable by scrolling.
  const ipadSubmitButton = page.getByRole('button', { name: 'Prepare public GitHub issue' });
  await ipadSubmitButton.scrollIntoViewIfNeeded();
  assert(await ipadSubmitButton.isVisible(), `${viewport.name}: submit button unreachable by scroll`);
  assert(pageErrors.length === 0, `${viewport.name}: propose.html page errors ${pageErrors.join('; ')}`);

  await page.goto(`${baseUrl}/index.html`, { waitUntil: 'networkidle' });

  // The digital ring search panel must be wide, horizontally centered and fully inside the viewport.
  await page.locator('#layer-view-button').click();
  await page.locator('#layer-panel').waitFor({ state: 'visible' });
  await waitForStableBoundingBox(page, '#layer-panel');
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

  // Drilling into a leaf digital subcategory must yield a compact, in-viewport focused lane.
  await page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks"]').click();
  await page.locator('.digital-lane-focus[data-digital-path="sphere/communication_networks/community_networks"]').click();
  await page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.focusedPath === 'sphere/communication_networks/community_networks');
  await waitForStableBoundingBox(page, '.digital-lane.is-focused');
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

const PRESENCE_VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844, mobile: true },
  { name: 'desktop', width: 1280, height: 900, mobile: false },
  ...IPAD_LANDSCAPE_VIEWPORTS.map(vp => ({ ...vp, mobile: true }))
];

for (const viewport of PRESENCE_VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: viewport.mobile,
    hasTouch: viewport.mobile,
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  
  await page.goto(`${baseUrl}/index.html`, { waitUntil: 'networkidle' });
  await page.locator('#filter-toggle').click();
  await page.locator('#discovery-panel').waitFor({ state: 'visible' });
  const presenceGeometry = await page.evaluate(() => {
    const fieldset = document.querySelector('.filter-presence-group');
    const options = [...document.querySelectorAll('.filter-presence-options label')];
    const siblingLabel = document.querySelector('#filter-country')?.closest('label');
    const fieldsetRect = fieldset.getBoundingClientRect();
    const siblingRect = siblingLabel.getBoundingClientRect();
    return {
      fieldsetHeight: fieldsetRect.height,
      fieldsetTop: fieldsetRect.top,
      fieldsetBottom: fieldsetRect.bottom,
      siblingHeight: siblingRect.height,
      options: options.map((node) => {
        const rect = node.getBoundingClientRect();
        return { top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height, right: rect.right, left: rect.left };
      }),
    };
  });
  assert(presenceGeometry.options.length === 2, `${viewport.name}: presence filter does not expose exactly two options (${JSON.stringify(presenceGeometry.options)})`);
  const [firstPresenceOption, secondPresenceOption] = presenceGeometry.options;
  
  assert(presenceGeometry.options.every((option) => option.height >= 44), `${viewport.name}: presence option touch target below 44px (${JSON.stringify(presenceGeometry.options)})`);
  assert(presenceGeometry.options.every(opt => opt.top >= presenceGeometry.fieldsetTop && opt.bottom <= presenceGeometry.fieldsetBottom), `${viewport.name}: options not fully inside fieldset`);
  assert(presenceGeometry.options.every(opt => opt.top >= 0 && opt.bottom <= viewport.height && opt.left >= 0 && opt.right <= viewport.width), `${viewport.name}: options not fully in viewport`);

  if (viewport.width >= 768) {
    assert(Math.abs(firstPresenceOption.top - secondPresenceOption.top) < 1, `${viewport.name}: presence options are stacked instead of side-by-side (${JSON.stringify(presenceGeometry.options)})`);
  }
  
  assert(presenceGeometry.fieldsetHeight <= presenceGeometry.siblingHeight * 2.5, `${viewport.name}: presence filter is an unexpected vertical large block`);

  results.push(`presence-${viewport.name}`);
  await context.close();
}

await browser.close();
await new Promise((resolve) => server.close(resolve));
console.log(JSON.stringify({ status: 'pass', scenarios: results }, null, 2));
