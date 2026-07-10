#!/usr/bin/env python3
"""Headless Chrome interaction smoke for the static map proof.

The smoke serves a temporary copy of the proof, replaces MapLibre and tile work
with a local DOM-only stub, clicks real marker buttons, and verifies that the map
panel is visible, motion-free, closable and reopenable. It is an operator-facing
browser check rather than a default CI browser dependency.
"""

from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.smoke_proof_hub_browser import BROWSER_ENV, find_browser
RESULT_PATTERN = re.compile(r'<pre id="result">(.*?)</pre>', re.DOTALL)


@dataclass(frozen=True)
class MapBrowserSmokeReceipt:
    smoke_id: str
    browser_binary: str
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
    "no external network required",
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

HARNESS = r'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>map smoke pending</title></head>
<body>
  <iframe id="map-frame" width="1024" height="800"></iframe>
  <pre id="result">pending</pre>
  <script>
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    async function waitFor(doc, selector, timeoutMs = 5000) {
      const deadline = performance.now() + timeoutMs;
      while (performance.now() < deadline) {
        const element = doc.querySelector(selector);
        if (element) return element;
        await sleep(25);
      }
      throw new Error(`Timed out waiting for ${selector}`);
    }
    async function waitForText(doc, selector, prefix, timeoutMs = 5000) {
      const deadline = performance.now() + timeoutMs;
      while (performance.now() < deadline) {
        const element = doc.querySelector(selector);
        if (element && element.textContent.startsWith(prefix)) return element;
        await sleep(25);
      }
      throw new Error(`Timed out waiting for ${selector} text ${prefix}`);
    }
    async function settle(win) {
      await new Promise((resolve) => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve)));
    }
    (async () => {
      const resultNode = document.getElementById("result");
      try {
        const frame = document.getElementById("map-frame");
        const frameLoaded = new Promise((resolve) => frame.addEventListener("load", resolve, { once: true }));
        frame.src = "/proofs/map/";
        await frameLoaded;
        const doc = frame.contentDocument;
        const firstMarker = await waitFor(doc, ".map-marker .mixed-node");
        const markers = [...doc.querySelectorAll(".map-marker .mixed-node")];
        const loadState = await waitForText(doc, "[data-load-state]", "Map ready.");
        const panel = doc.querySelector("[data-detail-surface]");
        const startedAt = performance.now();
        firstMarker.click();
        await settle(frame.contentWindow);
        const openElapsedMs = performance.now() - startedAt;
        const style = frame.contentWindow.getComputedStyle(panel);
        const rect = panel.getBoundingClientRect();
        const inViewport =
          rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 &&
          rect.left < frame.contentWindow.innerWidth && rect.top < frame.contentWindow.innerHeight;
        const openSnapshot = {
          hidden: panel.hidden,
          opacity: style.opacity,
          transform: style.transform,
          transitionDuration: style.transitionDuration,
          willChange: style.willChange,
          inViewport,
        };
        doc.querySelector("[data-close-detail]").click();
        await settle(frame.contentWindow);
        const closed = panel.hidden;
        markers[markers.length - 1].click();
        await settle(frame.contentWindow);
        const reopened = !panel.hidden && frame.contentWindow.getComputedStyle(panel).opacity === "1";
        resultNode.textContent = JSON.stringify({
          markerCount: markers.length,
          loadState: loadState.textContent,
          openElapsedMs,
          openSnapshot,
          closed,
          reopened,
        });
        document.title = "map smoke complete";
      } catch (error) {
        resultNode.textContent = JSON.stringify({ error: String(error) });
        document.title = "map smoke failed";
      }
    })();
  </script>
</body>
</html>
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
    (destination / "map-browser-smoke.html").write_text(HARNESS, encoding="utf-8")


def browser_command(browser: str, profile: Path, url: str, timeout_ms: int) -> list[str]:
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
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        "--run-all-compositor-stages-before-draw",
        f"--virtual-time-budget={timeout_ms}",
        f"--user-data-dir={profile}",
        "--dump-dom",
        url,
    ]


def parse_result(dom: str) -> dict[str, Any]:
    match = RESULT_PATTERN.search(dom)
    if not match:
        raise RuntimeError("browser output did not contain map smoke result")
    payload = html.unescape(match.group(1)).strip()
    try:
        result = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"map smoke result is not valid JSON: {payload[:240]}") from error
    if result.get("error"):
        raise RuntimeError(f"map browser harness failed: {result['error']}")
    return result


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


def run_browser_smoke(root: Path = ROOT, timeout_seconds: int = 20) -> MapBrowserSmokeReceipt:
    browser = find_browser()
    if not browser:
        raise RuntimeError(f"no supported browser found; set {BROWSER_ENV}")
    with tempfile.TemporaryDirectory(prefix="commonworld-map-browser-") as temp_dir:
        temp_root = Path(temp_dir)
        prepare_tree(root, temp_root)
        handler = functools.partial(QuietHandler, directory=str(temp_root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        profile = temp_root / "chrome-profile"
        url = f"http://127.0.0.1:{server.server_port}/map-browser-smoke.html"
        try:
            completed = subprocess.run(
                browser_command(browser, profile, url, timeout_seconds * 1000),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds + 10,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"map browser smoke timed out after {timeout_seconds}s") from error
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    if completed.returncode != 0:
        stderr_tail = "\n".join(completed.stderr.splitlines()[-12:])
        raise RuntimeError(f"map browser smoke failed rc={completed.returncode}; stderr_tail={stderr_tail}")
    result = parse_result(completed.stdout)
    errors = validate_result(result)
    if errors:
        raise RuntimeError("map browser smoke validation failed: " + "; ".join(errors))
    snapshot = result["openSnapshot"]
    return MapBrowserSmokeReceipt(
        smoke_id="commonworld.map-proof.browser-interaction-smoke.v1",
        browser_binary=browser,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local headless-browser interaction smoke for the map proof.")
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
