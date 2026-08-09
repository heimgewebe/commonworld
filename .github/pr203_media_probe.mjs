import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
const context = await browser.newContext({ viewport: { width: 844, height: 390 }, reducedMotion: 'no-preference' });
const page = await context.newPage();
await page.setContent(`<!doctype html><style>
@keyframes probe-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.orbit { transform-box: view-box; transform-origin: 50px 50px; animation: probe-spin 20s linear infinite; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition: none !important;
  }
  body { --probe-media: reduce; }
}
</style>
<div id="html-probe" class="orbit" style="width:40px;height:40px"></div>
<svg id="svg" width="200" height="120" viewBox="0 0 100 100">
  <defs><ellipse id="ring-path" cx="50" cy="50" rx="44" ry="36" /></defs>
  <g id="static-parent">
    <use id="use-probe" class="orbit" href="#ring-path" fill="none" stroke="black" />
    <text id="text-probe" class="orbit"><textPath href="#ring-path">Commonworld ring label probe</textPath></text>
  </g>
</svg>`);
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
  const box = (selector) => {
    const rect = document.querySelector(selector).getBoundingClientRect();
    return [rect.x, rect.y, rect.width, rect.height];
  };
  const style = (selector) => {
    const value = getComputedStyle(document.querySelector(selector));
    return { name: value.animationName, duration: value.animationDuration, iterations: value.animationIterationCount, playState: value.animationPlayState };
  };
  return {
    media: matchMedia('(prefers-reduced-motion: reduce)').matches,
    cssMedia: getComputedStyle(document.body).getPropertyValue('--probe-media').trim(),
    html: matrix('#html-probe'),
    use: matrix('#use-probe'),
    text: matrix('#text-probe'),
    textBox: box('#text-probe'),
    htmlStyle: style('#html-probe'),
    useStyle: style('#use-probe'),
    textStyle: style('#text-probe'),
    events: [...window.__probeEvents],
  };
});
const changed = (a, b, key, threshold = 1e-5) => a[key] && b[key] && b[key].some((value, index) => Math.abs(value - a[key][index]) > threshold);
const pair = async () => {
  const before = await sample();
  await page.waitForTimeout(350);
  const after = await sample();
  return {
    before,
    after,
    htmlMoved: changed(before, after, 'html'),
    useMoved: changed(before, after, 'use'),
    textMoved: changed(before, after, 'text'),
    textBoxMoved: changed(before, after, 'textBox', 1e-3),
  };
};

const baseline = await pair();
await page.emulateMedia({ reducedMotion: 'reduce' });
await page.waitForTimeout(100);
const reduced = await pair();
await page.emulateMedia({ reducedMotion: 'no-preference' });
await page.waitForTimeout(100);
const resumedNaturally = await pair();

await page.evaluate(() => {
  const nodes = [document.querySelector('#html-probe'), document.querySelector('#use-probe'), document.querySelector('#text-probe')];
  nodes.forEach((node) => node.style.setProperty('animation', 'none', 'important'));
  document.querySelector('#svg').getBoundingClientRect();
});
await page.waitForTimeout(50);
await page.evaluate(() => {
  for (const selector of ['#html-probe', '#use-probe', '#text-probe']) document.querySelector(selector).style.removeProperty('animation');
});
await page.waitForTimeout(100);
const resumedAfterExplicitRestart = await pair();

console.log(JSON.stringify({ baseline, reduced, resumedNaturally, resumedAfterExplicitRestart }, null, 2));
await browser.close();
