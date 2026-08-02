#!/usr/bin/env python3
"""Copy the exactly pinned MapLibre browser distribution into public assets."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "node_modules/maplibre-gl/package.json"
DIST = ROOT / "node_modules/maplibre-gl/dist"
RTL_PACKAGE = ROOT / "node_modules/@mapbox/mapbox-gl-rtl-text/package.json"
RTL_DIST = ROOT / "node_modules/@mapbox/mapbox-gl-rtl-text/dist"
RTL_LICENSE = ROOT / "node_modules/@mapbox/mapbox-gl-rtl-text/LICENSE.md"
TARGET = ROOT / "assets/vendor"
EXPECTED_VERSION = "5.24.0"
EXPECTED_RTL_VERSION = "0.3.0"
FILES = {
    "maplibre-gl.js": "maplibre-gl.js",
    "maplibre-gl.css": "maplibre-gl.css",
    "LICENSE.txt": "MAPLIBRE-LICENSE.txt",
}


def main() -> int:
    if not PACKAGE.is_file():
        print("ERROR: maplibre-gl is not installed; run npm ci", file=sys.stderr)
        return 1
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if package.get("version") != EXPECTED_VERSION:
        print(
            f"ERROR: expected maplibre-gl {EXPECTED_VERSION}, got {package.get('version')!r}",
            file=sys.stderr,
        )
        return 1
    if not RTL_PACKAGE.is_file():
        print("ERROR: mapbox-gl-rtl-text is not installed; run npm ci", file=sys.stderr)
        return 1
    rtl_package = json.loads(RTL_PACKAGE.read_text(encoding="utf-8"))
    if rtl_package.get("version") != EXPECTED_RTL_VERSION:
        print(
            f"ERROR: expected mapbox-gl-rtl-text {EXPECTED_RTL_VERSION}, got {rtl_package.get('version')!r}",
            file=sys.stderr,
        )
        return 1
    TARGET.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in FILES.items():
        source = DIST / source_name
        if not source.is_file():
            print(f"ERROR: missing MapLibre distribution file: {source}", file=sys.stderr)
            return 1
        shutil.copyfile(source, TARGET / target_name)
    rtl_source = RTL_DIST / "mapbox-gl-rtl-text.js"
    if not rtl_source.is_file() or not RTL_LICENSE.is_file():
        print("ERROR: missing mapbox-gl-rtl-text distribution or license", file=sys.stderr)
        return 1
    shutil.copyfile(rtl_source, TARGET / "mapbox-gl-rtl-text.js")
    shutil.copyfile(RTL_LICENSE, TARGET / "MAPBOX-RTL-TEXT-LICENSE.md")
    notice = TARGET / "MAPLIBRE-NOTICE.txt"
    notice.write_text(
        "MapLibre GL JS 5.24.0\n"
        "Source: npm package maplibre-gl@5.24.0\n"
        "License: BSD-3-Clause\n"
        "https://github.com/maplibre/maplibre-gl-js\n",
        encoding="utf-8",
    )
    rtl_notice = TARGET / "MAPBOX-RTL-TEXT-NOTICE.txt"
    rtl_notice.write_text(
        "Mapbox GL RTL Text 0.3.0\n"
        "Source: npm package @mapbox/mapbox-gl-rtl-text@0.3.0\n"
        "License: BSD-2-Clause\n"
        "https://github.com/mapbox/mapbox-gl-rtl-text\n",
        encoding="utf-8",
    )
    print("commonworld public MapLibre and RTL text runtime assets built")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
