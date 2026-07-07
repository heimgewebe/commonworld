#!/usr/bin/env python3
"""Validate the mobile Atlas Shift doctrine document."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "blueprints" / "mobile-atlas-shift-interaction-model.md"

REQUIRED_TOKENS = (
    "# Mobile Atlas Shift Interaction Model",
    "Karte <-> Aether",
    "`Horizont` is not a selectable mode",
    "smartphone-first",
    "one primary mobile surface",
    "thumb-safe projection switch",
    "CommonProject",
    "map projection",
    "aether projection",
    "profile focus",
    "rising code pillar",
    "Ortssignal",
    "Project profile is a focus state",
    "no Horizont button",
    "no fake coordinates",
    "no backend, accounts, public submissions or weltgewebe write path",
    "static/read-only boundary",
)

FORBIDDEN_TOKENS = (
    "Karte / Horizont / Aether three-way navigation is allowed",
    "Horizont is a selectable mode",
    "public submissions are allowed",
    "fake coordinates are allowed",
    "join action",
    "manage action",
)


def validate_mobile_atlas_shift_doctrine(root: Path = ROOT) -> list[str]:
    doc = root / "docs" / "blueprints" / "mobile-atlas-shift-interaction-model.md"
    errors: list[str] = []
    if not doc.is_file():
        return [f"missing mobile Atlas Shift doctrine: {doc.relative_to(root)}"]

    text = doc.read_text(encoding="utf-8")

    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"mobile Atlas Shift doctrine missing {token}")

    for token in FORBIDDEN_TOKENS:
        if token in text:
            errors.append(f"mobile Atlas Shift doctrine contains forbidden token: {token}")

    if "Horizont" not in text or "not a selectable mode" not in text:
        errors.append("mobile Atlas Shift doctrine must explicitly demote Horizont from navigation to transition behavior")

    return errors


def main() -> int:
    errors = validate_mobile_atlas_shift_doctrine(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld mobile Atlas Shift doctrine validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
