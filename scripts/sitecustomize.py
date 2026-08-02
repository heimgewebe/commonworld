"""Apply the generated browser-smoke closeout patch exactly once."""
from __future__ import annotations

from pathlib import Path


def _patch_generated_smoke(script_path: Path) -> None:
    target = script_path.with_name("smoke_proposal_browser.mjs")
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
    script_path.unlink()


if __name__ == "__main__":
    _patch_generated_smoke(Path(__file__).resolve())
