#!/usr/bin/env python3
"""Headless browser screenshot smoke for the static proof hub.

This is an operator-facing visual capture, not the default CI gate. The script
opens the committed static hub with a local browser, captures desktop and mobile
PNG screenshots, validates the PNG headers, and emits a JSON receipt. Generated
screenshots stay under .artifacts/ by default and are intentionally ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".artifacts" / "proof-hub-browser-smoke"
BROWSER_ENV = "COMMONWORLD_BROWSER_BIN"
MIN_SCREENSHOT_BYTES = 10_000


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int


@dataclass(frozen=True)
class ScreenshotReceipt:
    viewport: str
    width: int
    height: int
    screenshot: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class BrowserSmokeReceipt:
    smoke_id: str
    browser_binary: str
    page: str
    screenshots: tuple[ScreenshotReceipt, ...]
    boundary: tuple[str, ...]


VIEWPORTS = (
    Viewport("desktop", 1440, 1600),
    Viewport("mobile", 390, 1200),
)

BOUNDARY = (
    "local static file only",
    "no server required",
    "no screenshot committed to git",
    "no backend, form, login, submission or weltgewebe write path",
)

BROWSER_CANDIDATES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def find_browser() -> str | None:
    configured = os.environ.get(BROWSER_ENV)
    if configured:
        return configured if Path(configured).exists() or shutil.which(configured) else None
    for candidate in BROWSER_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def read_png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def screenshot_command(browser: str, root: Path, output: Path, viewport: Viewport, profile_dir: Path) -> list[str]:
    page = (root / "index.html").resolve().as_uri()
    return [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        f"--window-size={viewport.width},{viewport.height}",
        f"--screenshot={output}",
        page,
    ]


def capture_viewport(browser: str, root: Path, output_dir: Path, viewport: Viewport, timeout_seconds: int) -> ScreenshotReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot = output_dir / f"proof-hub-{viewport.name}.png"
    with tempfile.TemporaryDirectory(prefix=f"commonworld-{viewport.name}-profile-", ignore_cleanup_errors=True) as profile:
        cmd = screenshot_command(browser, root, screenshot, viewport, Path(profile))
        try:
            completed = subprocess.run(
                cmd,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"browser screenshot timed out for {viewport.name}; binary={browser}; timeout={timeout_seconds}s"
            ) from error
    if completed.returncode != 0:
        stderr_tail = "\n".join(completed.stderr.splitlines()[-12:])
        raise RuntimeError(
            f"browser screenshot failed for {viewport.name}; binary={browser}; rc={completed.returncode}; stderr_tail={stderr_tail}"
        )
    if not screenshot.is_file():
        raise RuntimeError(f"browser did not create screenshot for {viewport.name}: {screenshot}")
    width, height = read_png_dimensions(screenshot)
    if width != viewport.width:
        raise RuntimeError(f"screenshot width mismatch for {viewport.name}: expected {viewport.width}, got {width}")
    if height <= 0 or height > max(viewport.height * 12, viewport.height + 1):
        raise RuntimeError(f"screenshot height out of range for {viewport.name}: {height}")
    size = screenshot.stat().st_size
    if size < MIN_SCREENSHOT_BYTES:
        raise RuntimeError(f"screenshot too small for visual smoke: {screenshot} has {size} bytes")
    try:
        screenshot_ref = str(screenshot.relative_to(root))
    except ValueError:
        screenshot_ref = str(screenshot)
    return ScreenshotReceipt(
        viewport=viewport.name,
        width=width,
        height=height,
        screenshot=screenshot_ref,
        sha256=sha256_file(screenshot),
        bytes=size,
    )


def run_browser_smoke(root: Path = ROOT, output_dir: Path = DEFAULT_OUTPUT_DIR, timeout_seconds: int = 45) -> BrowserSmokeReceipt:
    browser = find_browser()
    if not browser:
        raise RuntimeError(
            f"no supported browser found; set {BROWSER_ENV} or install one of: {', '.join(BROWSER_CANDIDATES)}"
        )
    screenshots = tuple(capture_viewport(browser, root, output_dir, viewport, timeout_seconds) for viewport in VIEWPORTS)
    return BrowserSmokeReceipt(
        smoke_id="commonworld.proof-hub.browser-screenshot-smoke.v1",
        browser_binary=browser,
        page=str((root / "index.html").resolve().as_uri()),
        screenshots=screenshots,
        boundary=BOUNDARY,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture static proof hub screenshots with a local headless browser.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()
    try:
        receipt = run_browser_smoke(ROOT, args.output_dir, args.timeout_seconds)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
