#!/usr/bin/env python3
"""Validate the public Commonworld shell and progressive runtime surface."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_HTML = (
    '<html lang="de">',
    "<title>commonworld — Commons entdecken</title>",
    "Commons weltweit entdecken",
    "Die gemeinsame Welt wird sichtbar.",
    'class="globe-stage"',
    'class="globe-map"',
    'class="digital-sphere"',
    'id="sphere-edge-control"',
    'id="layer-panel"',
    'id="project-focus"',
    'href="#catalog"',
    "Erde → Großregion → Region → lokaler Zusammenhang → Commons",
    "Der erste interaktive Globus ist gebaut.",
    "MapLibre GL JS 5.24.0",
    "OpenFreeMap liefert die Basiskarte",
    "10 geprüfte Startdatensätze",
    "Erste öffentliche Commons",
    'id="catalog"',
    '<script src="./assets/vendor/maplibre-gl.js" defer></script>',
    '<script type="module" src="./assets/commonworld-app.js"></script>',
    '<meta http-equiv="Content-Security-Policy"',
)

FORBIDDEN_HTML = (
    "proof hub",
    "fixture",
    "aether",
    "atlas shift",
    "game feel",
    "gamification",
    "<form",
    "/proofs/",
    "/api/",
    "unpkg.com",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "three.js",
    "'unsafe-inline'",
    "'unsafe-eval'",
)

REQUIRED_CSS = (
    ".globe-stage",
    ".globe-map",
    ".digital-sphere",
    ".sphere-edge-control",
    ".layer-panel",
    ".project-focus",
    ".catalog-grid",
    ".catalog-card",
    ":focus-visible",
    "@media (min-width: 62rem)",
    "@media (prefers-reduced-motion: reduce)",
)


def validate_public_shell(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    html_path = root / "index.html"
    css_path = root / "index.css"
    if not html_path.is_file():
        return ["missing public index.html"]
    if not css_path.is_file():
        return ["missing public index.css"]

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    lowered = html.casefold()
    for token in REQUIRED_HTML:
        if token not in html:
            errors.append(f"public shell missing required token: {token}")
    for token in FORBIDDEN_HTML:
        if token.casefold() in lowered:
            errors.append(f"public shell contains obsolete or unsafe token: {token}")
    for token in REQUIRED_CSS:
        if token not in css:
            errors.append(f"public shell CSS missing required token: {token}")
    return errors


def main() -> int:
    errors = validate_public_shell(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld canonical public shell validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
