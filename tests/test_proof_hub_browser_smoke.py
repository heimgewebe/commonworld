import os
import stat
import tempfile
import textwrap
import unittest
import zlib
from pathlib import Path
from unittest import mock

from scripts.smoke_proof_hub_browser import (
    BROWSER_ENV,
    VIEWPORTS,
    find_browser,
    read_png_dimensions,
    run_browser_smoke,
)
from scripts.validate_contracts import ROOT


def png_bytes(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + bytes(channel for x in range(width) for channel in ((x * 17 + y * 31) % 256, (x * 7 + y * 13) % 256, (x * 3 + y * 5) % 256)) for y in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + body + crc.to_bytes(4, "big")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def write_fake_browser(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            r'''
            #!/usr/bin/env python3
            import pathlib
            import sys
            import zlib

            def png_bytes(width, height):
                raw = b"".join(b"\x00" + bytes(channel for x in range(width) for channel in ((x * 17 + y * 31) % 256, (x * 7 + y * 13) % 256, (x * 3 + y * 5) % 256)) for y in range(height))
                def chunk(kind, data):
                    body = kind + data
                    crc = zlib.crc32(body) & 0xFFFFFFFF
                    return len(data).to_bytes(4, "big") + body + crc.to_bytes(4, "big")
                return (
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
                    + chunk(b"IDAT", zlib.compress(raw))
                    + chunk(b"IEND", b"")
                )

            screenshot = None
            width = None
            height = None
            for arg in sys.argv[1:]:
                if arg.startswith("--screenshot="):
                    screenshot = pathlib.Path(arg.split("=", 1)[1])
                if arg.startswith("--window-size="):
                    width, height = [int(value) for value in arg.split("=", 1)[1].split(",")]
            if screenshot is None or width is None or height is None:
                raise SystemExit(2)
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            screenshot.write_bytes(png_bytes(width, height))
            '''
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ProofHubBrowserSmokeTests(unittest.TestCase):
    def test_read_png_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "capture.png"
            path.write_bytes(png_bytes(1440, 1600))
            self.assertEqual((1440, 1600), read_png_dimensions(path))

    def test_find_browser_honors_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            browser = Path(tmp_dir) / "fake-browser"
            write_fake_browser(browser)
            with mock.patch.dict(os.environ, {BROWSER_ENV: str(browser)}, clear=False):
                self.assertEqual(str(browser), find_browser())

    def test_browser_smoke_writes_receipt_for_desktop_and_mobile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            browser = tmp / "fake-browser"
            write_fake_browser(browser)
            output_dir = tmp / "captures"
            with mock.patch.dict(os.environ, {BROWSER_ENV: str(browser)}, clear=False):
                receipt = run_browser_smoke(ROOT, output_dir, timeout_seconds=5)
            self.assertEqual("commonworld.proof-hub.browser-screenshot-smoke.v1", receipt.smoke_id)
            self.assertEqual(tuple(viewport.name for viewport in VIEWPORTS), tuple(item.viewport for item in receipt.screenshots))
            for screenshot in receipt.screenshots:
                self.assertTrue(screenshot.screenshot.startswith(str(output_dir)))
                actual = output_dir / f"proof-hub-{screenshot.viewport}.png"
                self.assertTrue(actual.is_file())
                self.assertEqual(screenshot.width, read_png_dimensions(actual)[0])
                self.assertGreater(screenshot.bytes, 10_000)
                self.assertEqual(64, len(screenshot.sha256))
            self.assertIn("no screenshot committed to git", receipt.boundary)

    def test_missing_browser_fails_with_actionable_error(self) -> None:
        with mock.patch.dict(os.environ, {BROWSER_ENV: "/definitely/missing/browser"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "no supported browser found"):
                run_browser_smoke(ROOT, Path(tempfile.mkdtemp()), timeout_seconds=1)

    def test_browser_timeout_reports_runtime_error_without_cleanup_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            browser = tmp / "slow-browser"
            browser.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys, time\n"
                "for arg in sys.argv[1:]:\n"
                "    if arg.startswith('--user-data-dir='):\n"
                "        pathlib.Path(arg.split('=', 1)[1], 'Default').mkdir(parents=True, exist_ok=True)\n"
                "time.sleep(5)\n",
                encoding="utf-8",
            )
            browser.chmod(browser.stat().st_mode | stat.S_IXUSR)
            with mock.patch.dict(os.environ, {BROWSER_ENV: str(browser)}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "browser screenshot timed out for desktop"):
                    run_browser_smoke(ROOT, tmp / "captures", timeout_seconds=1)


if __name__ == "__main__":
    unittest.main()
