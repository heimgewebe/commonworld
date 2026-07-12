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
TARGET = ROOT / "assets/vendor"
EXPECTED_VERSION = "5.24.0"
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
    TARGET.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in FILES.items():
        source = DIST / source_name
        if not source.is_file():
            print(f"ERROR: missing MapLibre distribution file: {source}", file=sys.stderr)
            return 1
        shutil.copyfile(source, TARGET / target_name)
    notice = TARGET / "MAPLIBRE-NOTICE.txt"
    notice.write_text(
        "MapLibre GL JS 5.24.0\n"
        "Source: npm package maplibre-gl@5.24.0\n"
        "License: BSD-3-Clause\n"
        "https://github.com/maplibre/maplibre-gl-js\n",
        encoding="utf-8",
    )
    print("commonworld public MapLibre runtime assets built")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
