#!/usr/bin/env python3
"""Validate the commonworld runtime and scale boundary doctrine."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "blueprints" / "runtime-scale-boundary.md"

REQUIRED_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T009",
    "plan-before-build",
    "no backend service",
    "no database",
    "no ingestion worker",
    "no public submissions",
    "no write path",
    "read-only catalog API",
    "search index derived from accepted catalog data",
    "spatial index only when static proof data no longer answers the product question",
    "import candidate preview, not automatic publication",
    "review console only if ownership remains explicit",
    "source of truth for catalog entries",
    "read-only API contract",
    "search index input and rebuild policy",
    "spatial indexing need and privacy impact",
    "import candidate acceptance path",
    "review authority owner",
    "failure mode and cache behavior",
    "deployment and observability boundary",
    "own administration backend",
    "Supabase core",
    "PostGIS core",
    "Rust API",
    "automatic global imports",
    "exact location defaults",
    "weltgewebe write path",
    "read-only catalog API contract or static catalog export contract",
)

FORBIDDEN_PHRASES = (
    "implement the api now",
    "create a database now",
    "public submissions are allowed",
    "automatic publication is allowed",
    "exact location by default",
)


def validate_runtime_scale_boundary(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = root / DOC_PATH.relative_to(ROOT)
    if not path.is_file():
        return ["missing runtime and scale boundary document"]

    text = path.read_text(encoding="utf-8")
    lowered = text.casefold()
    for phrase in REQUIRED_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"runtime scale boundary missing required phrase: {phrase}")
    for phrase in FORBIDDEN_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"runtime scale boundary includes forbidden shortcut: {phrase}")
    return errors


def main() -> int:
    errors = validate_runtime_scale_boundary(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld runtime scale boundary validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
