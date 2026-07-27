#!/usr/bin/env python3
"""Validate Commonworld catalogue scale evidence and pre-cutover authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-scale-gates.contract.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"
CURRENT_STATE_PATH = ROOT / "contracts" / "commonworld" / "current-state.contract.json"

REQUIRED_GATES = [
    "realistic-scale-fixtures",
    "measured-demand-loaded-runtime",
    "bounded-recovery-surface",
    "search-and-map-scale-budgets",
    "shard-growth-policy",
    "failure-and-device-parity",
    "cutover-authority",
    "editorial-boundary-preserved",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_shard_state(size: int, warn: int, maximum: int) -> str:
    if size >= maximum:
        return "fail"
    if size >= warn:
        return "warning"
    return "pass"


def validate_catalog_scale_gates(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    paths = [
        root / CONTRACT_PATH.relative_to(ROOT),
        root / EVIDENCE_PATH.relative_to(ROOT),
        root / CURRENT_STATE_PATH.relative_to(ROOT),
    ]
    for path in paths:
        if not path.is_file():
            errors.append(f"missing catalogue scale dependency: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        contract = load_json(paths[0])
        evidence = load_json(paths[1])
        current_state = load_json(paths[2])
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid catalogue scale dependency: {error}"]

    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_catalog_scale_gate_contract":
        errors.append("catalogue scale contract schema or kind mismatch")
    if contract.get("task_id") != "COMMONWORLD-PUBLIC-GLOBE-V1-T028":
        errors.append("catalogue scale contract must remain bound to T028")
    if contract.get("status") != "pre_cutover_gate_active":
        errors.append("catalogue scale contract status must remain pre-cutover")
    if contract.get("required_gates") != REQUIRED_GATES:
        errors.append("catalogue scale required gate inventory mismatch")

    measurement_contract = contract.get("measurement", {})
    scale_tiers = measurement_contract.get("scale_tiers")
    stress_tier = measurement_contract.get("stress_tier")
    if scale_tiers != [1_000, 10_000] or stress_tier != 100_000:
        errors.append("catalogue scale tiers must remain 1k, 10k and 100k stress")
    if measurement_contract.get("synthetic_only") is not True:
        errors.append("catalogue scale contract must disclose synthetic-only evidence")

    budgets = contract.get("budgets", {})
    expected_budget_keys = {
        "initial_world_index_max_gzip_bytes",
        "shard_warn_gzip_bytes",
        "shard_max_gzip_bytes",
        "world_index_initial_delivery",
        "shard_prefix_migration",
    }
    if set(budgets) != expected_budget_keys:
        errors.append("catalogue scale budget field inventory mismatch")
    initial_max = budgets.get("initial_world_index_max_gzip_bytes")
    shard_warn = budgets.get("shard_warn_gzip_bytes")
    shard_max = budgets.get("shard_max_gzip_bytes")
    if not all(isinstance(value, int) and value > 0 for value in (initial_max, shard_warn, shard_max)):
        errors.append("catalogue scale byte budgets must be positive integers")
    elif not shard_warn < shard_max:
        errors.append("catalogue shard warning budget must be below maximum")
    if budgets.get("world_index_initial_delivery") != "forbidden_when_over_budget":
        errors.append("full world index must fail closed when over the initial budget")
    if budgets.get("shard_prefix_migration") != "required_before_generated_shard_reaches_maximum":
        errors.append("catalogue scale contract must require prefix migration before shard overflow")

    if evidence.get("kind") != "commonworld.catalog_platform_scaling_evidence" or evidence.get("version") != "1.1":
        errors.append("catalogue scaling evidence schema or version mismatch")
    if evidence.get("synthetic_only") is not True:
        errors.append("catalogue scaling evidence must remain explicitly synthetic")
    if evidence.get("scale_tiers") != scale_tiers or evidence.get("stress_tier") != stress_tier:
        errors.append("catalogue scaling evidence tiers diverge from contract")
    if evidence.get("budgets") != {
        "initial_world_index_max_gzip_bytes": initial_max,
        "shard_warn_gzip_bytes": shard_warn,
        "shard_max_gzip_bytes": shard_max,
    }:
        errors.append("catalogue scaling evidence budgets diverge from contract")
    if evidence.get("shard_strategy") != {"algorithm": "sha256-prefix", "prefix_length": 2}:
        errors.append("catalogue scaling evidence shard strategy mismatch")

    measurements = evidence.get("measurements")
    if not isinstance(measurements, list):
        errors.append("catalogue scaling evidence measurements must be a list")
        measurements = []
    expected_counts = [*scale_tiers, stress_tier] if isinstance(scale_tiers, list) and isinstance(stress_tier, int) else []
    actual_counts = [item.get("entry_count") for item in measurements if isinstance(item, dict)]
    if actual_counts != expected_counts:
        errors.append("catalogue scaling evidence measurement order or inventory mismatch")

    for item in measurements:
        if not isinstance(item, dict):
            errors.append("catalogue scaling evidence contains a non-object measurement")
            continue
        count = item.get("entry_count")
        world = item.get("world_index", {})
        shards = item.get("shards", {})
        gates = item.get("gate_evaluation", {})
        world_gzip = world.get("gzip_bytes")
        shard_gzip = shards.get("gzip_max_bytes")
        if not isinstance(world_gzip, int) or world_gzip <= 0:
            errors.append(f"{count}: invalid world-index gzip size")
        elif isinstance(initial_max, int):
            expected_world_gate = "rejected" if world_gzip > initial_max else "within_budget"
            if gates.get("world_index_initial_delivery") != expected_world_gate:
                errors.append(f"{count}: world-index gate does not match measured size")
            if count in expected_counts and expected_world_gate != "rejected":
                errors.append(f"{count}: measured full index unexpectedly fits initial delivery budget")
        if not isinstance(shard_gzip, int) or shard_gzip <= 0:
            errors.append(f"{count}: invalid maximum shard gzip size")
        elif isinstance(shard_warn, int) and isinstance(shard_max, int):
            state = expected_shard_state(shard_gzip, shard_warn, shard_max)
            if gates.get("shard_gzip") != state:
                errors.append(f"{count}: shard gate does not match measured size")
            if shard_gzip >= shard_max:
                errors.append(f"{count}: maximum shard reaches or exceeds hard budget")
            if count in scale_tiers and gates.get("shard_gzip") != "pass":
                errors.append(f"{count}: cutover scale tier must remain below shard warning budget")
            if count == stress_tier and gates.get("shard_gzip") != "warning":
                errors.append(f"{count}: stress tier must preserve the measured prefix-depth warning")

    decision = evidence.get("decision", {})
    if decision.get("full_world_index_initial_delivery") != "rejected_for_all_measured_tiers":
        errors.append("catalogue scaling decision must reject every measured full start index")
    if decision.get("runtime_path") != "small aggregate manifest plus demand-loaded shards and details":
        errors.append("catalogue scaling decision runtime path mismatch")
    if decision.get("scale_cutover_task") != contract.get("task_id"):
        errors.append("catalogue scaling decision task binding mismatch")
    if decision.get("fixed_prefix_stress_state") != "warning":
        errors.append("catalogue scaling decision must expose fixed-prefix stress warning")

    authorization = contract.get("current_authorization", {})
    delivery = current_state.get("catalog_delivery", {})
    if authorization.get("cutover_authorized") is not False:
        errors.append("catalogue scale contract must not authorize cutover")
    if delivery.get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("current state must not authorize catalogue cutover")
    if delivery.get("runtime_catalogue_visible_source") != "compact_build_bound_bootstrap":
        errors.append("current visible catalogue source changed before cutover proof")
    if authorization.get("visible_catalogue_source") != delivery.get("runtime_catalogue_visible_source"):
        errors.append("scale contract and current state disagree on visible catalogue source")
    if delivery.get("design") != "compact_build_bound_bootstrap_with_generation_bound_selected_detail_shadow":
        errors.append("current catalogue delivery design changed before T028 cutover")

    policy = contract.get("decision_policy", {})
    if policy.get("backend_by_default") is not False:
        errors.append("catalogue scale contract must remain measurement-first, not backend-first")
    if policy.get("server_search_or_postgis_or_pmtiles") != "introduce_only_after_measured_static_boundary_failure":
        errors.append("catalogue scale infrastructure escalation policy mismatch")

    return errors


def main() -> int:
    errors = validate_catalog_scale_gates()
    if errors:
        print("Catalogue scale gate validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Catalogue scale gate validation passed: 1k and 10k pass, 100k fixed-prefix stress warning retained, cutover unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
