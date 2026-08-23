#!/usr/bin/env python3
"""Capture isolated SVG textPath paint evidence in locally installed browsers."""
from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/svg_textpath_paint_probe.html"
CASES = (
    "ellipse-static",
    "path-static",
    "ellipse-parent-transform",
    "path-parent-transform",
    "ellipse-parent-mask",
    "path-parent-mask",
    "ellipse-parent-filter",
    "path-parent-filter",
    "ellipse-parent-mask-filter",
    "path-parent-mask-filter",
)
CASE_BOXES = {
    case_id: (16 + (index % 2) * 438, 52 + (index // 2) * 288, 420, 280)
    for index, case_id in enumerate(CASES)
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextlib.contextmanager
def fixture_server():
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/{FIXTURE.relative_to(ROOT).as_posix()}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def browser_version(executable: Path) -> str:
    completed = subprocess.run(
        (str(executable), "--version"),
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return (completed.stdout or completed.stderr).strip()


def capture_playwright(browser_name: str, executable: Path, url: str, output: Path) -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=True,
            args=(
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ),
        )
        try:
            page = browser.new_page(viewport={"width": 900, "height": 1500}, device_scale_factor=1)
            page.goto(url, wait_until="load")
            page.wait_for_selector("html#ready")
            page.screenshot(path=str(output / f"{browser_name}-labels.png"), full_page=True)
            page.goto(f"{url}?hide-labels", wait_until="load")
            page.wait_for_selector("html#ready[data-hide-labels]")
            page.screenshot(path=str(output / f"{browser_name}-no-labels.png"), full_page=True)
            return browser.version
        finally:
            browser.close()


def capture_firefox_cli(executable: Path, url: str, output: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="commonworld-firefox-paint-profile-") as profile:
        for suffix, target_url in (("labels", url), ("no-labels", f"{url}?hide-labels")):
            command = (
                str(executable),
                "--headless",
                "--no-remote",
                "--profile",
                profile,
                "--window-size",
                "900,1500",
                "--screenshot",
                str(output / f"firefox-{suffix}.png"),
                target_url,
            )
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
    return browser_version(executable)


def pixel_evidence(labels_path: Path, no_labels_path: Path, output: Path, browser_name: str) -> list[dict]:
    labels = Image.open(labels_path).convert("RGB")
    no_labels = Image.open(no_labels_path).convert("RGB")
    if labels.size != no_labels.size:
        raise RuntimeError(f"screenshot size mismatch: {labels.size} != {no_labels.size}")
    result = []
    for case_id, (left, top, width, height) in CASE_BOXES.items():
        box = (left, top, left + width, top + height)
        labels_roi = labels.crop(box)
        no_labels_roi = no_labels.crop(box)
        difference = ImageChops.difference(labels_roi, no_labels_roi)
        changed_pixels = sum(1 for pixel in difference.getdata() if max(pixel) >= 12)
        bbox = difference.getbbox()
        labels_roi.save(output / f"{browser_name}-{case_id}-labels.png")
        difference.save(output / f"{browser_name}-{case_id}-diff.png")
        result.append(
            {
                "case": case_id,
                "changed_pixels": changed_pixels,
                "difference_bbox": list(bbox) if bbox else None,
                "painted": changed_pixels >= 100,
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("brave", "chrome", "firefox"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    executables = {
        "brave": Path("/usr/bin/brave-browser"),
        "chrome": Path("/usr/bin/google-chrome"),
        "firefox": Path("/usr/bin/firefox"),
    }
    executable = executables[args.browser]
    with fixture_server() as url:
        if args.browser == "firefox":
            engine_version = capture_firefox_cli(executable, url, args.output)
        else:
            engine_version = capture_playwright(args.browser, executable, url, args.output)
    cases = pixel_evidence(
        args.output / f"{args.browser}-labels.png",
        args.output / f"{args.browser}-no-labels.png",
        args.output,
        args.browser,
    )
    result = {
        "browser": args.browser,
        "version": browser_version(executable),
        "engine_version": engine_version,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "cases": cases,
        "all_path_labels_painted": all(case["painted"] for case in cases if case["case"].startswith("path-")),
        "all_ellipse_labels_painted": all(case["painted"] for case in cases if case["case"].startswith("ellipse-")),
    }
    result_path = args.output / f"{args.browser}-result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["all_path_labels_painted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
