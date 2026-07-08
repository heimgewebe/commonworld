#!/usr/bin/env python3
"""Validate the commonworld map source strategy document."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "docs" / "blueprints" / "map-source-strategy.md"

REQUIRED_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T004",
    "commonworld must not operate a second tile infrastructure",
    "shared heimgewebe basemap",
    "proof",
    "staging",
    "production",
    "style URL",
    "attribution",
    "cache policy",
    "provider terms",
    "No bulk loading and no prefetch behavior",
    "proof README and UI copy",
    "failure mode copy",
    "Privacy projection remains independent from basemap choice",
    "weltgewebe remains the action, participation and administration layer",
    "COMMONWORLD-ATLAS-V1-T005 is implemented by `proofs/map/map-source.json`",
    "single replaceable boundary",
    "still avoids backend work, tile hosting, public write paths and weltgewebe handoff logic",
)

FORBIDDEN_PHRASES = (
    "commonworld tile server",
    "commonworld owns tile generation",
    "commonworld PMTiles packaging",
    "hard-code production provider",
)


def validate_map_source_strategy(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    strategy_path = root / "docs" / "blueprints" / "map-source-strategy.md"
    if not strategy_path.is_file():
        return ["missing map source strategy document"]

    text = strategy_path.read_text(encoding="utf-8")
    lowered = text.casefold()

    for phrase in REQUIRED_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"map source strategy missing required phrase: {phrase}")

    for phrase in FORBIDDEN_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"map source strategy includes forbidden scope: {phrase}")

    mode_positions = [lowered.find(f"### {mode}") for mode in ("proof", "staging", "production")]
    if any(position < 0 for position in mode_positions):
        errors.append("map source strategy must define proof, staging and production mode headings")
    elif mode_positions != sorted(mode_positions):
        errors.append("map source strategy modes must be ordered proof, staging, production")

    if "tile generation" not in lowered or "tile cache operations" not in lowered:
        errors.append("map source strategy must explicitly exclude basemap operations from commonworld ownership")

    return errors


def main() -> int:
    errors = validate_map_source_strategy(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld map source strategy validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
