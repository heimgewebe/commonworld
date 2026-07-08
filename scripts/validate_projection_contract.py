#!/usr/bin/env python3
"""Validate the CommonProject projection contract documentation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "blueprints" / "commonproject-projection-contract.md"

REQUIRED_TOKENS = (
    "# CommonProject Projection Contract",
    "schema_version: 2",
    "explicit `projections` object",
    "pre-projection v1 project entries are not valid",
    "place | digital | hybrid",
    "map | aether | profile",
    "Every project must have a `profile` projection",
    "Hidden locations must not expose a `map` projection",
    "hidden `hybrid` projects must include `aether` and must not include `map`",
    "ortssignal: true",
    "map projection claims must not be more precise than the location mode permits",
    "projection metadata must not create a second project identity",
    "OpenStreetMap",
    "OSM Hamburg hybrid fixture",
)


def validate_projection_contract(root: Path = ROOT) -> list[str]:
    doc = root / "docs" / "blueprints" / "commonproject-projection-contract.md"
    if not doc.is_file():
        return [f"missing projection contract doc: {doc.relative_to(root)}"]
    text = doc.read_text(encoding="utf-8")
    return [f"projection contract doc missing {token}" for token in REQUIRED_TOKENS if token not in text]


def main() -> int:
    errors = validate_projection_contract(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld projection contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
