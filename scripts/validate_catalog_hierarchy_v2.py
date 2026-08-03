#!/usr/bin/env python3
"""Validate committed Commonworld catalogue hierarchy v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "docs" / "evidence" / "catalog-hierarchy-v2.json"
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-hierarchy-v2.contract.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_evidence(evidence: dict, *, root: Path = ROOT) -> None:
    require(evidence.get("kind") == "commonworld.catalog_hierarchy_evidence", "hierarchy evidence kind mismatch")
    require(evidence.get("version") == "1.0", "hierarchy evidence version mismatch")
    require(evidence.get("task_id") == "COMMONWORLD-PUBLIC-GLOBE-V1-T039", "hierarchy evidence task mismatch")
    contract_path = root / evidence.get("contract", {}).get("path", "")
    require(contract_path == root / "contracts/commonworld/catalog-hierarchy-v2.contract.json", "hierarchy contract path mismatch")
    contract_bytes = contract_path.read_bytes()
    require(evidence["contract"].get("sha256") == hashlib.sha256(contract_bytes).hexdigest(), "hierarchy contract digest mismatch")
    contract = json.loads(contract_bytes)
    require(evidence.get("scale_tiers") == contract.get("scale_tiers"), "hierarchy scale tiers mismatch")

    implementation = evidence.get("implementation_sha256")
    require(isinstance(implementation, dict) and implementation, "hierarchy implementation digest inventory missing")
    for relative, digest in implementation.items():
        path = root / relative
        require(path.is_file(), f"hierarchy implementation file missing: {relative}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"hierarchy implementation digest mismatch: {relative}")

    browser_binding=evidence.get("browser_evidence")
    require(isinstance(browser_binding,dict) and set(browser_binding)=={"path","sha256","bytes"},"browser evidence binding mismatch")
    browser_path=root/browser_binding["path"];require(browser_path==root/"docs/evidence/catalog-hierarchy-browser-v2.json" and browser_path.is_file(),"browser evidence path mismatch")
    browser_bytes=browser_path.read_bytes();require(browser_binding["bytes"]==len(browser_bytes),"browser evidence byte length mismatch");require(browser_binding["sha256"]==hashlib.sha256(browser_bytes).hexdigest(),"browser evidence digest mismatch")
    try: from scripts.validate_catalog_hierarchy_browser_v2 import validate_browser_evidence
    except ModuleNotFoundError: from validate_catalog_hierarchy_browser_v2 import validate_browser_evidence
    validate_browser_evidence(json.loads(browser_bytes),root=root)

    measurements = evidence.get("measurements")
    require(isinstance(measurements, list) and [item.get("entry_count") for item in measurements] == contract["scale_tiers"], "hierarchy measurement tier inventory mismatch")
    budgets = contract["budgets"]
    for item in measurements:
        count = item["entry_count"]
        require(item.get("v1_compatibility") == {"manifest_version": "1.0", "shard_prefix_length": 2, "entry_count": count}, f"v1 compatibility mismatch at {count}")
        inventory = item.get("v2_inventory", {})
        require(inventory.get("manifest_version") == "2.0" and inventory.get("aggregate_version") == "2.0", f"v2 version mismatch at {count}")
        require(inventory.get("index_prefix_length") == 1 and inventory.get("leaf_prefix_length") == 3, f"v2 prefix mismatch at {count}")
        require(0 < inventory.get("shard_index_count", 0) <= 16, f"v2 root index count is unbounded at {count}")
        metrics = item.get("metrics", {})
        comparisons = {
            "manifest_root": (metrics.get("manifest_root", {}).get("gzip_bytes"), budgets["manifest_root_max_gzip_bytes"]),
            "aggregate_root": (metrics.get("aggregate_root", {}).get("gzip_bytes"), budgets["aggregate_root_max_gzip_bytes"]),
            "shard_indexes": (metrics.get("shard_indexes", {}).get("gzip_max_bytes"), budgets["shard_index_max_gzip_bytes"]),
            "aggregate_segments": (metrics.get("aggregate_segments", {}).get("gzip_max_bytes"), budgets["aggregate_segment_max_gzip_bytes"]),
            "leaf_shards": (metrics.get("leaf_shards", {}).get("gzip_max_bytes"), budgets["shard_max_gzip_bytes"]),
        }
        for label, (observed, limit) in comparisons.items():
            require(isinstance(observed, int) and 0 < observed <= limit, f"{label} budget exceeded or invalid at {count}")
            require(item.get("gate_evaluation", {}).get(label) == "pass", f"{label} gate did not pass at {count}")
        require(item.get("gate_evaluation", {}).get("overall") == "pass", f"hierarchy overall gate did not pass at {count}")

    request_contract = evidence.get("request_contract", {})
    require(request_contract == {
        "root_load_max_requests": 2,
        "selection_loads_only_required_segments": True,
        "leaf_load_max_requests": 2,
        "complete_manifest_or_aggregate_eager_transfer": False,
    }, "hierarchy request contract mismatch")
    guard = evidence.get("migration_guard", {})
    require(guard.get("default_manifest_version") == "1.0" and guard.get("default_shard_prefix_length") == 2, "hierarchy default runtime guard mismatch")
    require(guard.get("candidate_manifest_version") == "2.0" and guard.get("cutover_authorized") is False, "hierarchy candidate cutover guard mismatch")
    require(guard.get("rollback_manifest_url") == "catalog/runtime/manifest.v1.json", "hierarchy rollback target mismatch")
    require(guard.get("required_gates") == contract["migration_guard"]["required_gates"], "hierarchy required gates mismatch")
    require(guard.get("satisfied_gates") == ["deterministic-fixtures", "browser-transfer-budget"], "hierarchy satisfied gate state mismatch")
    require(guard.get("unsatisfied_gates") == ["physical-device"], "hierarchy unsatisfied gate state mismatch")
    decision = evidence.get("decision", {})
    require(decision.get("hierarchical_fixture_budget_state") == "pass", "hierarchy fixture decision is not pass")
    require(decision.get("browser_transfer_budget_state") == "pass", "hierarchy browser decision is not pass")
    require(decision.get("runtime_catalogue_cutover_authorized") is False, "hierarchy evidence must not authorize cutover")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_evidence(json.loads(args.evidence.read_text(encoding="utf-8")))
    print(f"catalog hierarchy v2 evidence valid: {args.evidence.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
