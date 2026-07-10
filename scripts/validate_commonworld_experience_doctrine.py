#!/usr/bin/env python3
"""Validate the canonical Commonworld immersive experience doctrine."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTRINE = ROOT / "docs" / "blueprints" / "commonworld-experience-doctrine.md"
MASTERPLAN = ROOT / "docs" / "blueprints" / "commonworld-masterplan.md"
LEGACY_MOBILE = ROOT / "docs" / "blueprints" / "mobile-atlas-shift-interaction-model.md"

REQUIRED_DOCTRINE_TOKENS = (
    "# Commonworld Immersive Experience Doctrine",
    "game feel without gamification",
    "orient -> notice -> approach -> open -> understand -> continue -> return",
    "## One world shell",
    "## Control model",
    "must not require WASD",
    "semantically ordered linear equivalent",
    "### World",
    "### Near",
    "### Find",
    "localized in the interface",
    "Project focus",
    "## Rendering strategy",
    "semantic HTML and CSS",
    "Canvas or WebGL only after profiling proves",
    "browser-history state",
    "160–320 ms",
    "no long task above 50 ms",
    "60 Hz frame budget",
    "no continuous animation when the scene is idle",
    "reduced-motion mode",
    "points or experience levels",
    "leaderboards",
    "autoplay audio",
    "8–12 real Commons",
    "Playable` means that the complete discovery loop works",
    "fixed `Karte <-> Aether` switch does not remain as public doctrine",
)

FORBIDDEN_DOCTRINE_TOKENS = (
    "WASD is required",
    "leaderboards are allowed",
    "autoplay audio is required",
    "points reward browsing",
    "continuous animation is required",
    "Aether is the primary public navigation",
)


def validate_commonworld_experience_doctrine(root: Path = ROOT) -> list[str]:
    doctrine = root / DOCTRINE.relative_to(ROOT)
    masterplan = root / MASTERPLAN.relative_to(ROOT)
    legacy_mobile = root / LEGACY_MOBILE.relative_to(ROOT)
    errors: list[str] = []

    if not doctrine.is_file():
        return ["missing Commonworld immersive experience doctrine"]
    if not masterplan.is_file():
        return ["missing Commonworld masterplan"]
    if not legacy_mobile.is_file():
        return ["missing legacy mobile Atlas Shift doctrine"]

    doctrine_text = doctrine.read_text(encoding="utf-8")
    for token in REQUIRED_DOCTRINE_TOKENS:
        if token not in doctrine_text:
            errors.append(f"experience doctrine missing required token: {token}")
    for token in FORBIDDEN_DOCTRINE_TOKENS:
        if token.casefold() in doctrine_text.casefold():
            errors.append(f"experience doctrine contains forbidden token: {token}")

    masterplan_text = masterplan.read_text(encoding="utf-8")
    for token in (
        "# commonworld.net Product Plan v2.1",
        "docs/blueprints/commonworld-experience-doctrine.md",
        "Playable real-content vertical slice",
        "8–12 real reviewed Commons",
        "World, Near, Find and Focus",
    ):
        if token not in masterplan_text:
            errors.append(f"masterplan missing experience alignment token: {token}")

    legacy_text = legacy_mobile.read_text(encoding="utf-8")
    if "superseded for public navigation" not in legacy_text:
        errors.append("legacy mobile Atlas Shift doctrine must be superseded for public navigation")
    if "fixed `Karte <-> Aether` switch is no longer the public navigation doctrine" not in legacy_text:
        errors.append("legacy mobile doctrine must explicitly demote its fixed projection switch")

    return errors


def main() -> int:
    errors = validate_commonworld_experience_doctrine(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld immersive experience doctrine validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
