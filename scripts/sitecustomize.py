"""One-shot closeout hook removed by its first interpreter process."""
from __future__ import annotations

import atexit
from pathlib import Path


def _patch_generated_smoke() -> None:
    target = Path(__file__).with_name("smoke_proposal_browser.mjs")
    text = target.read_text(encoding="utf-8")
    old = "  assert(await page.locator('#proposal-download').isHidden(), 'privacy-native-arabic-dms: JSON download became available');\n"
    new = """  assert(await page.locator('#proposal-download').isVisible(), 'privacy-native-arabic-dms: validated download control is unavailable');
  let invalidDownloadStarted = false;
  page.once('download', () => { invalidDownloadStarted = true; });
  await page.locator('#proposal-download').click();
  await page.waitForTimeout(100);
  assert(!invalidDownloadStarted, 'privacy-native-arabic-dms: invalid JSON download started');
  assert(((await alert.textContent()) ?? '').includes('إحداثيات'), 'privacy-native-arabic-dms: download validation lost the coordinate error');
"""
    if text.count(old) != 1:
        raise RuntimeError("localized DMS download assertion was not generated exactly once")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    Path(__file__).unlink()


atexit.register(_patch_generated_smoke)
