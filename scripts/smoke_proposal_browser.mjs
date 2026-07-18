import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';

const ROOT = process.cwd();
const MIME = new Map([['.html', 'text/html; charset=utf-8'], ['.css', 'text/css; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'], ['.json', 'application/json; charset=utf-8']]);
function assert(condition, message) { if (!condition) throw new Error(message); }
function safePath(url) { const relative = decodeURIComponent(new URL(url, 'http://localhost').pathname).replace(/^\/+/, '') || 'propose.html'; const target = path.resolve(ROOT, relative); return target === ROOT || target.startsWith(`${ROOT}${path.sep}`) ? target : null; }
const server = createServer(async (request, response) => {
  try {
    const target = safePath(request.url ?? '/propose.html');
    if (!target || !(await stat(target)).isFile()) throw new Error('missing');
    response.writeHead(200, { 'Content-Type': MIME.get(path.extname(target)) ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
    response.end(await readFile(target));
  } catch { response.writeHead(404, { 'Content-Type': 'text/plain' }); response.end('not found'); }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const address = server.address();
if (!address || typeof address === 'string') throw new Error('proposal smoke server missing address');
const baseUrl = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined });
const results = [];

async function fillValid(page, name = 'Browser Test Commons') {
  await page.getByLabel('Name des Commons').fill(name);
  await page.getByLabel('Kurze Beschreibung').fill('Eine gemeinschaftlich verwaltete Ressource mit offenen Regeln, offiziellen Quellen und einem realen öffentlichen Beteiligungsweg.');
  await page.getByLabel('Offizielle Website').fill('https://example.net/commons');
  await page.getByLabel('Commons-Art').selectOption('other');
  await page.getByRole('checkbox', { name: 'Vor Ort', exact: true }).check();
  await page.getByRole('checkbox', { name: 'Digital', exact: true }).check();
  await page.getByLabel('Grobe Region oder Ort').fill('Norddeutschland');
  await page.getByLabel('HTTPS-Link').first().fill('https://example.net/commons/about');
  await page.getByLabel('Primärnahe Quellen').fill('https://example.net/commons/governance');
  await page.getByLabel('Mir ist bewusst, dass der bevorzugte GitHub-Eingang öffentlich ist.').check();
  await page.getByLabel('Ich willige in die redaktionelle Verarbeitung der übermittelten Angaben ein.').check();
  await page.getByLabel('Ich habe keine private Adresse, Koordinate, E-Mail-Adresse, Telefonnummer oder private Netz- und Haushaltsangabe eingetragen.').check();
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
  assert(await page.getByRole('heading', { name: 'Ein Commons vorschlagen' }).isVisible(), `${profile.name}: heading missing`);
  assert(await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).isVisible(), `${profile.name}: submit missing`);
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
  assert(JSON.stringify(fieldsetLegends) === JSON.stringify(['Projekt', 'Präsenz', 'Belegte Handlungswege', 'Quellen und Hinweise', 'Einwilligung und Öffentlichkeit']), `${profile.name}: semantic fieldsets differ ${JSON.stringify(fieldsetLegends)}`);
  assert(await page.locator('input[name="region"]').isDisabled(), `${profile.name}: geographic region is active without Vor Ort`);
  assert(pageErrors.length === 0, `${profile.name}: page errors ${pageErrors.join('; ')}`);
  results.push(profile.name);
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => ({ opener: window }); });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Success Test Commons');
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  await page.getByText('GitHub wurde geöffnet.').waitFor();
  assert((await page.getByRole('link', { name: 'GitHub direkt öffnen' }).getAttribute('href')).includes('body='), 'success: structured issue body missing');
  results.push('success-message');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => ({ opener: window }); });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Digital Only Test Commons');
  await page.getByRole('checkbox', { name: 'Vor Ort', exact: true }).uncheck();
  const region = page.locator('input[name="region"]');
  assert(await region.isDisabled(), 'digital-only: region remained editable');
  assert(await region.getAttribute('required') === null, 'digital-only: region remained required');
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  await page.getByText('GitHub wurde geöffnet.').waitFor();
  const issueUrl = new URL(await page.getByRole('link', { name: 'GitHub direkt öffnen' }).getAttribute('href'));
  assert(issueUrl.searchParams.get('body').includes('nicht zutreffend (nur digital)'), 'digital-only: issue body invented a region');
  results.push('digital-only-without-region');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, reducedMotion: 'reduce' });
  await context.addInitScript(() => { window.open = () => null; });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page);
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).press('Enter');
  await page.getByText('Der GitHub-Tab wurde blockiert.').waitFor();
  assert(await page.getByRole('link', { name: 'GitHub direkt öffnen' }).isVisible(), 'popup-blocked: direct link missing');
  assert(await page.getByRole('button', { name: 'Validiertes JSON herunterladen' }).isVisible(), 'popup-blocked: JSON fallback missing');
  results.push('keyboard-popup-blocked-fallback');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 820, height: 1180 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'Offline Test Commons');
  await context.setOffline(true);
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  await page.getByText('Keine Netzverbindung erkannt.').waitFor();
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
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  assert((await page.getByRole('alert').textContent()).includes('Name ist bereits'), 'duplicate-index: existing catalog title was not blocked');
  results.push('catalog-duplicate-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, '52.5200, 13.4050');
  await page.getByLabel('Grobe Region oder Ort').fill('52.5200, 13.4050');
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  assert(await page.getByRole('alert').isVisible(), 'privacy-invalid: error surface missing');
  assert((await page.getByRole('alert').textContent()).includes('keine Adresse oder Koordinate'), 'privacy-invalid: fail-closed reason missing');
  results.push('privacy-fail-closed');
  await context.close();
}

{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.html`, { waitUntil: 'networkidle' });
  await fillValid(page, 'No Presence Test');
  await page.getByRole('checkbox', { name: 'Vor Ort', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'Digital', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Öffentliches GitHub-Issue vorbereiten' }).click();
  assert(await page.getByRole('alert').isVisible(), 'presence-missing: error surface missing');
  results.push('presence-missing-fail-closed');
  await context.close();
}

await browser.close();
await new Promise((resolve) => server.close(resolve));
console.log(JSON.stringify({ status: 'pass', scenarios: results }, null, 2));
