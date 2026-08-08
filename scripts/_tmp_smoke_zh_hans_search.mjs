import { chromium } from 'playwright';

const baseUrl = process.env.CW_SMOKE_BASE_URL ?? 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  const response = await page.goto(`${baseUrl}/zh-Hans.html`, { waitUntil: 'domcontentloaded' });
  if (response?.status() !== 200) throw new Error(`zh-Hans surface HTTP ${response?.status()}`);
  await page.waitForSelector('html.runtime-ready', { timeout: 30_000 });
  await page.waitForFunction(
    () => document.querySelector('.globe-stage')?.dataset.localePack === 'ready',
    { timeout: 30_000 },
  );
  await page.locator('#commons-search').fill('自由办公套件');
  await page.waitForFunction(
    () => (document.querySelector('#discovery-list')?.textContent ?? '').includes('LibreOffice'),
    { timeout: 10_000 },
  );
  const resultText = (await page.locator('#discovery-list').textContent()) ?? '';
  const energyLabel = await page.locator('#filter-commons-type option[value="energy"]').textContent();
  if ((energyLabel ?? '').trim() !== '能源') throw new Error(`energy filter label drifted: ${energyLabel}`);
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join(' | ')}`);
  console.log(JSON.stringify({
    kind: 'commonworld.zh_hans_search_semantics_smoke',
    verdict: 'PASS',
    locale: 'zh-Hans',
    query: '自由办公套件',
    expected_project: 'LibreOffice',
    result_contains_expected_project: resultText.includes('LibreOffice'),
    localized_filter_probe: { value: 'energy', label: energyLabel?.trim() ?? '' },
    claim: 'Chinese product-owned search semantics are active; this is not browser-rendered translation only.',
  }, null, 2));
} finally {
  await browser.close();
}
