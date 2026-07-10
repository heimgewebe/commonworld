#!/usr/bin/env python3
"""Playwright interaction smoke for the static map proof.

The smoke serves a temporary copy of the proof, replaces MapLibre and tile work
with a local DOM-only stub, clicks real marker buttons, and verifies that the map
panel is visible, motion-free, closable and reopenable.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import shutil
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MapBrowserSmokeReceipt:
    smoke_id: str
    browser_version: str
    marker_count: int
    load_state: str
    panel_opacity: str
    panel_transform: str
    panel_transition_duration: str
    panel_will_change: str
    panel_in_viewport: bool
    panel_closed: bool
    panel_reopened: bool
    open_elapsed_ms: float
    boundary: tuple[str, ...]


BOUNDARY = (
    "temporary local proof copy",
    "MapLibre and raster tiles replaced by a DOM-only local stub",
    "Playwright-managed Chromium",
    "no external map network required",
    "no deploy, DNS, backend, submission or weltgewebe write path",
)

MAPLIBRE_STUB = r'''
window.maplibregl = {
  Map: class {
    constructor(options) {
      this.container = document.getElementById(options.container);
      this.container.dataset.maplibreStub = "true";
    }
    addControl() {}
  },
  NavigationControl: class {},
  Marker: class {
    constructor(options) { this.element = options.element; }
    setLngLat() { return this; }
    addTo(map) {
      map.container.append(this.element);
      return this;
    }
  }
};
'''


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        return


def prepare_tree(source_root: Path, destination: Path) -> None:
    shutil.copytree(source_root / "proofs", destination / "proofs")
    shutil.copytree(source_root / "examples", destination / "examples")
    assets = destination / "test-assets" / "dist"
    assets.mkdir(parents=True)
    (assets / "maplibre-gl.js").write_text(MAPLIBRE_STUB, encoding="utf-8")
    (assets / "maplibre-gl.css").write_text("/* browser smoke stub */\n", encoding="utf-8")
    source_path = destination / "proofs" / "map" / "map-source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["library"]["script_url"] = "/test-assets/dist/maplibre-gl.js"
    source["library"]["css_url"] = "/test-assets/dist/maplibre-gl.css"
    source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")


def validate_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    snapshot = result.get("openSnapshot", {})
    if result.get("markerCount", 0) < 2:
        errors.append("map browser smoke must render at least two location-safe markers")
    if not str(result.get("loadState", "")).startswith("Map ready."):
        errors.append("map browser smoke did not reach Map ready state")
    if snapshot.get("hidden") is not False:
        errors.append("map detail panel remained hidden after marker click")
    if snapshot.get("opacity") != "1":
        errors.append(f"map detail panel opacity must be 1, got {snapshot.get('opacity')}")
    if snapshot.get("transform") != "none":
        errors.append(f"map detail panel transform must be none, got {snapshot.get('transform')}")
    if snapshot.get("transitionDuration") not in ("0s", "0s, 0s"):
        errors.append(f"map detail panel must not inherit proof transitions, got {snapshot.get('transitionDuration')}")
    if snapshot.get("willChange") != "auto":
        errors.append(f"map detail panel will-change must be auto, got {snapshot.get('willChange')}")
    if snapshot.get("inViewport") is not True:
        errors.append("map detail panel is outside the viewport")
    if result.get("closed") is not True:
        errors.append("map detail panel did not close")
    if result.get("reopened") is not True:
        errors.append("map detail panel did not reopen")
    elapsed = result.get("openElapsedMs")
    if not isinstance(elapsed, (int, float)) or elapsed > 250:
        errors.append(f"map detail panel open path exceeded 250ms: {elapsed}")
    return errors


def receipt_from_result(browser_version: str, result: dict[str, Any]) -> MapBrowserSmokeReceipt:
    errors = validate_result(result)
    if errors:
        raise RuntimeError("map browser smoke validation failed: " + "; ".join(errors))
    snapshot = result["openSnapshot"]
    return MapBrowserSmokeReceipt(
        smoke_id="commonworld.map-proof.browser-interaction-smoke.v1",
        browser_version=browser_version,
        marker_count=result["markerCount"],
        load_state=result["loadState"],
        panel_opacity=snapshot["opacity"],
        panel_transform=snapshot["transform"],
        panel_transition_duration=snapshot["transitionDuration"],
        panel_will_change=snapshot["willChange"],
        panel_in_viewport=snapshot["inViewport"],
        panel_closed=result["closed"],
        panel_reopened=result["reopened"],
        open_elapsed_ms=round(float(result["openElapsedMs"]), 2),
        boundary=BOUNDARY,
    )


def run_browser_smoke(root: Path = ROOT, timeout_seconds: int = 20) -> MapBrowserSmokeReceipt:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is not installed; install requirements-dev.txt") from error

    with tempfile.TemporaryDirectory(prefix="commonworld-map-browser-") as temp_dir:
        temp_root = Path(temp_dir)
        prepare_tree(root, temp_root)
        handler = functools.partial(QuietHandler, directory=str(temp_root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/proofs/map/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1024, "height": 800})
                page.set_default_timeout(timeout_seconds * 1000)
                page.goto(url, wait_until="networkidle")
                page.wait_for_function(
                    "document.querySelector('[data-load-state]')?.textContent.startsWith('Map ready.')"
                )
                markers = page.locator(".map-marker .mixed-node")
                marker_count = markers.count()
                started_at = page.evaluate("performance.now()")
                markers.first.click()
                page.wait_for_function("document.querySelector('[data-detail-surface]')?.hidden === false")
                page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                open_elapsed_ms = page.evaluate("performance.now()") - started_at
                snapshot = page.locator("[data-detail-surface]").evaluate(
                    """panel => {
                      const style = getComputedStyle(panel);
                      const rect = panel.getBoundingClientRect();
                      return {
                        hidden: panel.hidden,
                        opacity: style.opacity,
                        transform: style.transform,
                        transitionDuration: style.transitionDuration,
                        willChange: style.willChange,
                        inViewport:
                          rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 &&
                          rect.left < innerWidth && rect.top < innerHeight,
                      };
                    }"""
                )
                page.locator("[data-close-detail]").click()
                page.wait_for_function("document.querySelector('[data-detail-surface]')?.hidden === true")
                closed = page.locator("[data-detail-surface]").evaluate("panel => panel.hidden")
                markers.last.click()
                page.wait_for_function("document.querySelector('[data-detail-surface]')?.hidden === false")
                reopened = page.locator("[data-detail-surface]").evaluate(
                    "panel => !panel.hidden && getComputedStyle(panel).opacity === '1'"
                )
                load_state = page.locator("[data-load-state]").inner_text()
                browser_version = browser.version
                browser.close()
        except Exception as error:
            raise RuntimeError(f"map Playwright smoke failed: {error}") from error
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    result = {
        "markerCount": marker_count,
        "loadState": load_state,
        "openElapsedMs": open_elapsed_ms,
        "openSnapshot": snapshot,
        "closed": closed,
        "reopened": reopened,
    }
    return receipt_from_result(browser_version, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Playwright interaction smoke for the map proof.")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        receipt = run_browser_smoke(ROOT, args.timeout_seconds)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
