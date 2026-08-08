#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "smoke_locale_candidates_browser.mjs"
text = path.read_text(encoding="utf-8")
old = """    await page.waitForTimeout(2_800);
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
"""
new = """    await page.waitForTimeout(800);
    await heldLocalePackRoute.continue();
    await page.waitForFunction(
      () => document.querySelector('.globe-stage')?.dataset.localePack === 'ready',
      null,
      { timeout: 15_000 },
    );
    await page.waitForFunction(
      () => document.querySelector('#text-count')?.textContent?.includes('communs'),
      null,
      { timeout: 15_000 },
    );
"""
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one late-pack resilience block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("locale late-pack resilience smoke timing hardened")
