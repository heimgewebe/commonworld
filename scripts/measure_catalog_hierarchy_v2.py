#!/usr/bin/env python3
"""Measure deterministic Commonworld catalogue hierarchy v2 fixtures."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "evidence" / "catalog-hierarchy-v2.json"
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-hierarchy-v2.contract.json"
BROWSER_EVIDENCE_PATH = ROOT / "docs/evidence/catalog-hierarchy-browser-v2.json"
SCALE_TIERS = (1_000, 10_000, 100_000)

try:
    from scripts.catalog_hierarchy_v2 import build_hierarchical_runtime_fixture
    from scripts.catalog_scale_fixtures import (
        build_compact_stress_fixture,
        build_runtime_fixture,
        canonical_bytes,
        compact_fixture_coverage,
        fixture_coverage,
        fixture_digest,
        representative_english_overlay,
        representative_records,
        sha256,
    )
except ModuleNotFoundError:  # Direct script execution adds scripts/ to sys.path.
    from catalog_hierarchy_v2 import build_hierarchical_runtime_fixture
    from catalog_scale_fixtures import (
        build_compact_stress_fixture,
        build_runtime_fixture,
        canonical_bytes,
        compact_fixture_coverage,
        fixture_coverage,
        fixture_digest,
        representative_english_overlay,
        representative_records,
        sha256,
    )


def gzip_size(payload: bytes) -> int:
    return len(gzip.compress(payload, compresslevel=9, mtime=0))


def payload_metrics(payload: bytes) -> dict:
    return {"raw_bytes": len(payload), "gzip_bytes": gzip_size(payload)}


def collection_metrics(payloads: dict[str, bytes], *, item_counts: dict[str, int] | None = None) -> dict:
    ordered = [payloads[key] for key in sorted(payloads)]
    raw = [len(payload) for payload in ordered]
    compressed = [gzip_size(payload) for payload in ordered]
    result = {
        "count": len(ordered),
        "raw_total_bytes": sum(raw),
        "raw_max_bytes": max(raw, default=0),
        "gzip_total_bytes": sum(compressed),
        "gzip_max_bytes": max(compressed, default=0),
        "gzip_median_bytes": round(statistics.median(compressed), 1) if compressed else 0.0,
    }
    if item_counts is not None:
        result["max_items"] = max(item_counts.values(), default=0)
        result["total_items"] = sum(item_counts.values())
    return result


def implementation_digests() -> dict[str, str]:
    paths = (
        "Makefile",
        "package.json",
        "assets/commonworld-catalog-runtime.mjs",
        "docs/catalog-hierarchy-v2.md",
        "contracts/commonworld/catalog-hierarchy-v2.contract.json",
        "scripts/build_catalog_runtime.py",
        "scripts/catalog_hierarchy_v2.py",
        "scripts/catalog_scale_fixtures.py",
        "scripts/smoke_catalog_hierarchy_v2_browser.mjs",
        "scripts/validate_catalog_hierarchy_browser_v2.py",
        "scripts/measure_catalog_hierarchy_v2.py",
        "scripts/validate_catalog_hierarchy_v2.py",
        "tests/js/catalog-runtime.test.mjs",
        "tests/test_catalog_hierarchy_v2.py",
        "tests/test_catalog_hierarchy_browser_v2_evidence.py",
        "tests/test_catalog_hierarchy_v2_evidence.py",
    )
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in paths
        if (ROOT / relative).is_file()
    }


def measure_runtime(count: int) -> dict:
    if count < 100_000:
        records = representative_records(count, ROOT, validate=True)
        overlay = representative_english_overlay(records, ROOT)
        v1 = build_runtime_fixture(records, ROOT, validate=False)
        scope = "full-schema-realistic"
        fixture_sha256 = fixture_digest(records, overlay)
        coverage = fixture_coverage(records, overlay)
    else:
        v1 = build_compact_stress_fixture(count, ROOT)
        scope = "compact-shard-stress"
        fixture_sha256 = sha256(v1["world_bytes"])
        coverage = compact_fixture_coverage(count, ROOT)

    v2 = build_hierarchical_runtime_fixture(v1)
    index_items = {
        key: value["shard_count"]
        for key, value in v2["shard_index_objects"].items()
    }
    segment_items = {
        key: value["value_count"]
        for key, value in v2["aggregate_segment_objects"].items()
    }
    leaf_items = {
        key: len(value["records"])
        for key, value in v2["shard_objects"].items()
    }
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    budgets = contract["budgets"]
    metrics = {
        "manifest_root": payload_metrics(v2["manifest_bytes"]),
        "aggregate_root": payload_metrics(v2["aggregate_bytes"]),
        "shard_indexes": collection_metrics(v2["shard_index_payloads"], item_counts=index_items),
        "aggregate_segments": collection_metrics(v2["aggregate_segment_payloads"], item_counts=segment_items),
        "leaf_shards": collection_metrics(v2["shard_payloads"], item_counts=leaf_items),
    }
    gates = {
        "manifest_root": "pass" if metrics["manifest_root"]["gzip_bytes"] <= budgets["manifest_root_max_gzip_bytes"] else "fail",
        "aggregate_root": "pass" if metrics["aggregate_root"]["gzip_bytes"] <= budgets["aggregate_root_max_gzip_bytes"] else "fail",
        "shard_indexes": "pass" if metrics["shard_indexes"]["gzip_max_bytes"] <= budgets["shard_index_max_gzip_bytes"] else "fail",
        "aggregate_segments": "pass" if metrics["aggregate_segments"]["gzip_max_bytes"] <= budgets["aggregate_segment_max_gzip_bytes"] else "fail",
        "leaf_shards": "pass" if metrics["leaf_shards"]["gzip_max_bytes"] <= budgets["shard_max_gzip_bytes"] else "fail",
    }
    return {
        "entry_count": count,
        "fixture_scope": scope,
        "fixture_sha256": fixture_sha256,
        "coverage": coverage,
        "v1_compatibility": {
            "manifest_version": v1["manifest"]["version"],
            "shard_prefix_length": v1["manifest"]["shards"]["prefix_length"],
            "entry_count": v1["manifest"]["entry_count"],
        },
        "v2_inventory": {
            "manifest_version": v2["manifest"]["version"],
            "aggregate_version": v2["aggregate"]["version"],
            "index_prefix_length": v2["manifest"]["shards"]["index_prefix_length"],
            "leaf_prefix_length": v2["manifest"]["shards"]["leaf_prefix_length"],
            "shard_index_count": len(v2["shard_index_objects"]),
            "aggregate_segment_count": len(v2["aggregate_segment_objects"]),
            "leaf_shard_count": len(v2["shard_objects"]),
        },
        "metrics": metrics,
        "gate_evaluation": {**gates, "overall": "pass" if all(value == "pass" for value in gates.values()) else "fail"},
    }


def build_result() -> dict:
    contract_bytes = CONTRACT_PATH.read_bytes()
    browser_bytes = BROWSER_EVIDENCE_PATH.read_bytes()
    browser_evidence = json.loads(browser_bytes)
    try: from scripts.validate_catalog_hierarchy_browser_v2 import validate_browser_evidence
    except ModuleNotFoundError: from validate_catalog_hierarchy_browser_v2 import validate_browser_evidence
    validate_browser_evidence(browser_evidence)
    measurements = [measure_runtime(count) for count in SCALE_TIERS]
    fixture_pass = all(item["gate_evaluation"]["overall"] == "pass" for item in measurements)
    browser_pass = browser_evidence.get("decision", {}).get("browser_transfer_budget_state") == "pass"
    all_pass = fixture_pass and browser_pass
    return {
        "kind": "commonworld.catalog_hierarchy_evidence",
        "version": "1.0",
        "task_id": "COMMONWORLD-PUBLIC-GLOBE-V1-T039",
        "source_main": "606efe727904a414c406a1ed95345e4c3ca32b3a",
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": hashlib.sha256(contract_bytes).hexdigest(),
        },
        "implementation_sha256": implementation_digests(),
        "browser_evidence": {"path": str(BROWSER_EVIDENCE_PATH.relative_to(ROOT)), "sha256": hashlib.sha256(browser_bytes).hexdigest(), "bytes": len(browser_bytes)},
        "scale_tiers": list(SCALE_TIERS),
        "measurements": measurements,
        "request_contract": {
            "root_load_max_requests": 2,
            "selection_loads_only_required_segments": True,
            "leaf_load_max_requests": 2,
            "complete_manifest_or_aggregate_eager_transfer": False,
        },
        "migration_guard": {
            "default_manifest_version": "1.0",
            "default_shard_prefix_length": 2,
            "candidate_manifest_version": "2.0",
            "cutover_authorized": False,
            "rollback_manifest_url": "catalog/runtime/manifest.v1.json",
            "required_gates": ["deterministic-fixtures", "browser-transfer-budget", "physical-device"],
            "satisfied_gates": ["deterministic-fixtures", "browser-transfer-budget"] if all_pass else [],
            "unsatisfied_gates": ["physical-device"] if all_pass else ["deterministic-fixtures", "browser-transfer-budget", "physical-device"],
        },
        "decision": {
            "hierarchical_fixture_budget_state": "pass" if fixture_pass else "fail",
            "browser_transfer_budget_state": "pass" if browser_pass else "fail",
            "runtime_catalogue_cutover_authorized": False,
            "default_runtime": "manifest-v1-two-hex",
            "candidate_runtime": "manifest-v2-three-hex-hierarchy",
        },
        "does_not_establish": [
            "runtime cutover",
            "bootstrap removal",
            "backend introduction",
            "production deployment",
            "physical-device approval",
            "real mobile-network latency",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result))
    print(json.dumps({
        "output": str(args.output),
        "state": result["decision"]["hierarchical_fixture_budget_state"],
        "tiers": [
            {
                "entry_count": item["entry_count"],
                "manifest_gzip": item["metrics"]["manifest_root"]["gzip_bytes"],
                "aggregate_gzip": item["metrics"]["aggregate_root"]["gzip_bytes"],
                "index_max_gzip": item["metrics"]["shard_indexes"]["gzip_max_bytes"],
                "segment_max_gzip": item["metrics"]["aggregate_segments"]["gzip_max_bytes"],
                "leaf_max_gzip": item["metrics"]["leaf_shards"]["gzip_max_bytes"],
                "overall": item["gate_evaluation"]["overall"],
            }
            for item in result["measurements"]
        ],
    }, indent=2, sort_keys=True))
    return 0 if result["decision"]["hierarchical_fixture_budget_state"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
