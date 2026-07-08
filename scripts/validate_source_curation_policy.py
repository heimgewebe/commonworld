#!/usr/bin/env python3
"""Validate the source and curation policy documentation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "blueprints" / "source-curation-policy.md"

REQUIRED_TOKENS = (
    "# Source and Curation Policy",
    "commonworld separates project identity, projection and trust state",
    "`provenance.sources` describes where a claim came from",
    "`curation.state` describes how far commonworld has reviewed that claim",
    "fixture entries must use fixture provenance",
    "candidate, curated and archived entries must not use fixture provenance",
    "official-source and public-registry sources must include `url` and `retrieved_at`",
    "manual-curation and derived sources must include `note`",
    "curated entries need at least two non-fixture sources",
    "handoff actions require `curation.state: curated`",
    "archived entries must not expose handoff actions",
    "Curation does not override projection privacy",
    "does not create public submissions, accounts, backend ingestion",
)


def validate_source_curation_policy(root: Path = ROOT) -> list[str]:
    doc = root / "docs" / "blueprints" / "source-curation-policy.md"
    if not doc.is_file():
        return [f"missing source curation policy doc: {doc.relative_to(root)}"]
    text = doc.read_text(encoding="utf-8")
    return [f"source curation policy missing {token}" for token in REQUIRED_TOKENS if token not in text]


def main() -> int:
    errors = validate_source_curation_policy(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld source curation policy validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
