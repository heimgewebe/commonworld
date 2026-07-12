#!/usr/bin/env python3
"""Validate the honest public placeholder for the canonical globe."""

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
    'class="digital-sphere"',
    "Erde → Großregion → Region → lokaler Zusammenhang → Commons",
    "Der Globus erhält reale Katalogdaten.",
    "10 geprüfte Startdatensätze",
    "Erste öffentliche Commons",
    'id="catalog"',
)

FORBIDDEN_HTML = (
    "proof",
    "fixture",
    "aether",
    "atlas shift",
    "game feel",
    "gamification",
    "data-project",
    "<script",
    "<form",
    "/proofs/",
    "/api/",
)

REQUIRED_CSS = (
    ".globe-stage",
    ".digital-sphere",
    ".globe",
    ".field-one",
    ".catalog-grid",
    ".catalog-card",
    "@media (min-width: 58rem)",
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
