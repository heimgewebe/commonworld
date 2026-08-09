import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
const context = await browser.newContext({ viewport: { width: 844, height: 390 }, reducedMotion: 'no-preference' });
const page = await context.newPage();
await page.setContent(`<!doctype html><style>
@keyframes probe-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
#html-probe { width: 40px; height: 40px; transform-origin: 20px 20px; animation: probe-spin 20s linear infinite; }
#svg-probe { transform-box: view-box; transform-origin: 50px 50px; animation: probe-spin 20s linear infinite; }
@media (prefers-reduced-motion: reduce) { body { --probe-media: reduce; } }
</style>
<div id="html-probe"></div>
<svg width="100" height="100" viewBox="0 0 100 100"><rect id="svg-probe" x="20" y="20" width="60" height="20" /></svg>`);
await page.evaluate(() => {
  window.__probeEvents = [];
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  media.addEventListener('change', (event) => window.__probeEvents.push({ matches: event.matches, at: performance.now() }));
});

const sample = () => page.evaluate(() => {
  const matrix = (selector) => {
    const value = getComputedStyle(document.querySelector(selector)).transform;
    const m = value && value !== 'none' ? new DOMMatrixReadOnly(value) : null;
    return m ? [m.a, m.b, m.c, m.d, m.e, m.f] : null;
  };
  return {
    media: matchMedia('(prefers-reduced-motion: reduce)').matches,
    cssMedia: getComputedStyle(document.body).getPropertyValue('--probe-media').trim(),
    html: matrix('#html-probe'),
    svg: matrix('#svg-probe'),
    events: [...window.__probeEvents],
  };
});
const changed = (a, b, key) => a[key] && b[key] && b[key].some((value, index) => Math.abs(value - a[key][index]) > 1e-5);
const pair = async () => {
  const before = await sample();
  await page.waitForTimeout(350);
  const after = await sample();
  return { before, after, htmlMoved: changed(before, after, 'html'), svgMoved: changed(before, after, 'svg') };
};

const baseline = await pair();
await page.emulateMedia({ reducedMotion: 'reduce' });
await page.waitForTimeout(100);
const reduced = await pair();
await page.emulateMedia({ reducedMotion: 'no-preference' });
await page.waitForTimeout(100);
const resumed = await pair();

console.log(JSON.stringify({ baseline, reduced, resumed }, null, 2));
await browser.close();
