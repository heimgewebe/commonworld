#!/usr/bin/env python3
"""Generate deterministic evidence for the conflict-resistant release lifecycle."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_release_snapshot_lifecycle import (
    DELIVERY_EVIDENCE,
    PROPOSED_HEAD_INPUTS,
    file_sha256,
    reproduce_append_only_merge,
    reproduce_legacy_conflict,
)

TARGET = ROOT / "docs/evidence/release-snapshot-lifecycle-v1.json"
CURRENT_MANIFEST_PATH = ROOT / "assets/commonworld-page-builds.json"


def scope_sha256(input_hashes: dict[str, str]) -> str:
    payload = json.dumps(input_hashes, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_evidence(root: Path = ROOT) -> dict[str, object]:
    manifest = json.loads((root / CURRENT_MANIFEST_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))
    proposed_head_inputs = {
        relative: file_sha256(root / relative)
        for relative in PROPOSED_HEAD_INPUTS
    }
    delivery_evidence = {
        relative: file_sha256(root / relative)
        for relative in DELIVERY_EVIDENCE
    }
    legacy_conflicts, legacy_unmerged = reproduce_legacy_conflict()
    append_clean, append_unmerged = reproduce_append_only_merge()
    return {
        "schema_version": 1,
        "kind": "commonworld.release_snapshot_lifecycle_evidence",
        "task_id": "COMMONWORLD-PUBLIC-GLOBE-V1-T040",
        "status": "fresh",
        "freshness_model": "digest-defined-proposed-head-scope",
        "current_release_id": manifest.get("release_id"),
        "proposed_head_scope_sha256": scope_sha256(proposed_head_inputs),
        "proposed_head_inputs": proposed_head_inputs,
        "delivery_evidence": delivery_evidence,
        "conflict_reproduction": {
            "legacy": {
                "conflict": legacy_conflicts,
                "unmerged_path_count": legacy_unmerged,
            },
            "append_only": {
                "clean_merge": append_clean,
                "unmerged_path_count": append_unmerged,
            },
        },
    }


def main() -> int:
    evidence = build_evidence(ROOT)
    TARGET.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "release snapshot lifecycle evidence generated: "
        f"scope={evidence['proposed_head_scope_sha256']} release={evidence['current_release_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
