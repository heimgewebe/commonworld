#!/usr/bin/env python3
"""Validate the static mobile Atlas Shift proof."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "proofs" / "mobile-atlas-shift"

FILES = {
    "html": PROOF / "index.html",
    "css": PROOF / "mobile-atlas-shift.css",
    "js": PROOF / "mobile-atlas-shift.js",
    "readme": PROOF / "README.md",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_mobile_atlas_shift(root: Path = ROOT) -> list[str]:
    proof = root / "proofs" / "mobile-atlas-shift"
    files = {
        "html": proof / "index.html",
        "css": proof / "mobile-atlas-shift.css",
        "js": proof / "mobile-atlas-shift.js",
        "readme": proof / "README.md",
    }
    errors: list[str] = []

    for label, path in files.items():
        if not path.is_file():
            errors.append(f"missing mobile atlas shift {label}: {path.relative_to(root)}")
    if errors:
        return errors

    html = read(files["html"])
    css = read(files["css"])
    js = read(files["js"])
    readme = read(files["readme"])

    html_tokens = (
        "COMMONWORLD-ATLAS-V1-T010",
        "data-mode=\"map\"",
        "data-mode-target=\"map\"",
        "data-mode-target=\"aether\"",
        "class=\"atlas-stage\"",
        "class=\"map-surface\"",
        "class=\"code-pillar\"",
        "class=\"aether-surface\"",
        "class=\"aether-stream\"",
        "Fokusprofil",
        "Handoff",
        "locked",
    )
    for token in html_tokens:
        if token not in html:
            errors.append(f"mobile Atlas Shift HTML missing {token}")

    css_tokens = (
        ".atlas-phone",
        ".mode-switch",
        ".atlas-stage",
        ".map-surface",
        ".code-pillar",
        ".aether-surface",
        ".aether-stream",
        ".focus-strip",
        "prefers-reduced-motion",
    )
    for token in css_tokens:
        if token not in css:
            errors.append(f"mobile Atlas Shift CSS missing {token}")

    js_tokens = (
        "MODE_COPY",
        "map",
        "aether",
        "data-mode-target",
        "aria-pressed",
        "document.body.dataset.mode",
    )
    for token in js_tokens:
        if token not in js:
            errors.append(f"mobile Atlas Shift JS missing {token}")

    readme_tokens = (
        "Karte -> Aether",
        "rising code pillar",
        "Ortssignal",
        "not a selectable mode",
        "Project profile remains a focus state",
        "no backend",
        "public submissions",
        "weltgewebe write path",
    )
    for token in readme_tokens:
        if token not in readme:
            errors.append(f"mobile Atlas Shift README missing {token}")

    forbidden_terms = (
        "form action",
        "method=\"post\"",
        "type=\"submit\"",
        "login",
        "signup",
        "fetch(",
        "XMLHttpRequest",
        "MapLibre",
        "data-mode-target=\"horizon\"",
        "class=\"horizon-surface\"",
    )
    haystack = "\n".join((html, css, js, readme)).casefold()
    for term in forbidden_terms:
        if term.casefold() in haystack:
            errors.append(f"mobile Atlas Shift must not introduce redundant/runtime affordance: {term}")

    return errors


def main() -> int:
    errors = validate_mobile_atlas_shift(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld mobile Atlas Shift validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
