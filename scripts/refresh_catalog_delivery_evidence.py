#!/usr/bin/env python3
"""Refresh catalogue delivery evidence from freshly built and measured surfaces."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

try:
    from scripts.evaluate_catalog_browser_measurements import build_decision_evidence
    from scripts.measure_catalog_delivery import measure
except ModuleNotFoundError:
    from evaluate_catalog_browser_measurements import build_decision_evidence
    from measure_catalog_delivery import measure

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "docs/evidence/catalog-delivery-benchmark-v1.json"
SMOKE_PATH = ROOT / "docs/evidence/catalog-delivery-public-browser-smoke-v1.json"
CONTRACT_PATH = ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json"
SMOKE_SCRIPT_PATH = ROOT / "scripts/smoke_public_browser.mjs"
SMOKE_RUNNER_PATH = ROOT / "scripts/run_browser_smoke.py"
SMOKE_PLAN_PATH = ROOT / "scripts/browser_smoke_plan.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_static_from(static: dict) -> dict:
    baseline = copy.deepcopy(static)
    runtime_raw = (
        baseline["canonical_projects"]["raw_bytes"]
        + baseline["manifest"]["raw_bytes"]
    )
    runtime_gzip = (
        baseline["canonical_projects"]["gzip_bytes_individual_files"]
        + baseline["manifest"]["gzip_bytes"]
    )
    baseline["runtime_verification_fetch"] = {
        "enabled": True,
        "project_request_count": static["entry_count"],
        "duplicate_identity_payload_count": static["entry_count"],
        "raw_bytes": runtime_raw,
        "gzip_bytes": runtime_gzip,
    }
    baseline["catalog_initial_delivery"] = {
        "raw_bytes": baseline["bootstrap"]["raw_bytes"] + runtime_raw,
        "gzip_bytes": baseline["bootstrap"]["gzip_bytes"] + runtime_gzip,
    }
    return baseline


def profile_map(value: dict) -> dict[str, dict]:
    return {
        profile["profile"]: profile
        for profile in value.get("profiles", [])
        if isinstance(profile, dict) and isinstance(profile.get("profile"), str)
    }


def refresh(browser_measurement_path: Path, smoke_result_path: Path) -> None:
    evidence = load_json(BENCHMARK_PATH)
    smoke_evidence = load_json(SMOKE_PATH)
    contract = load_json(CONTRACT_PATH)
    browser_measurement = load_json(browser_measurement_path)
    smoke_result = load_json(smoke_result_path)
    static = measure(ROOT)
    budgets = contract.get("budgets", {})

    browser_decision, decision_errors = build_decision_evidence(
        [browser_measurement],
        budgets,
        budget_contract_sha256=file_sha256(CONTRACT_PATH),
    )
    if decision_errors or browser_decision is None:
        raise RuntimeError(
            "fresh browser measurement cannot form canonical decision evidence: "
            + "; ".join(decision_errors)
        )
    if browser_decision.get("decision") != "pass":
        raise RuntimeError(
            "fresh browser measurement is not a terminal pass: "
            + str(browser_decision.get("decision"))
        )

    surface_hash = browser_decision["first_party_surface_sha256"]
    evidence["base_commit"] = os.environ.get("GITHUB_SHA", evidence.get("base_commit"))
    evidence["optimized"]["static"] = static
    evidence["baseline"]["static"] = baseline_static_from(static)
    evidence["optimized"]["browser"] = browser_decision
    optimized_browser = browser_decision

    baseline_static = evidence["baseline"]["static"]
    optimized_static = evidence["optimized"]["static"]
    baseline_runtime = baseline_static["runtime_verification_fetch"]
    optimized_runtime = optimized_static["runtime_verification_fetch"]
    baseline_delivery = baseline_static["catalog_initial_delivery"]
    optimized_delivery = optimized_static["catalog_initial_delivery"]
    baseline_profiles = profile_map(evidence["baseline"].get("browser", {}))
    optimized_profiles = profile_map(optimized_browser)

    raw_delta = optimized_delivery["raw_bytes"] - baseline_delivery["raw_bytes"]
    gzip_delta = optimized_delivery["gzip_bytes"] - baseline_delivery["gzip_bytes"]
    evidence["delta"] = {
        "startup_project_json_requests": (
            optimized_runtime["project_request_count"] - baseline_runtime["project_request_count"]
        ),
        "duplicate_identity_payload_count": (
            optimized_runtime["duplicate_identity_payload_count"]
            - baseline_runtime["duplicate_identity_payload_count"]
        ),
        "catalog_initial_raw_bytes": raw_delta,
        "catalog_initial_gzip_bytes": gzip_delta,
        "catalog_initial_raw_reduction_percent": round(
            (-raw_delta / baseline_delivery["raw_bytes"]) * 100, 1
        ),
        "catalog_initial_gzip_reduction_percent": round(
            (-gzip_delta / baseline_delivery["gzip_bytes"]) * 100, 1
        ),
        "first_party_request_count_by_profile": {
            name: optimized_profiles[name].get("first_party_request_count", 0)
            - profile.get("first_party_request_count", 0)
            for name, profile in baseline_profiles.items()
            if name in optimized_profiles
        },
        "browser_dom_nodes_by_profile": {
            name: optimized_profiles[name].get("dom_node_count", 0)
            - profile.get("dom_node_count", 0)
            for name, profile in baseline_profiles.items()
            if name in optimized_profiles
        },
    }
    evidence["budget_binding"] = {
        "bootstrap_gzip_bytes": static["bootstrap"]["gzip_bytes"],
        "warn_bootstrap_gzip_bytes": budgets.get("warn_bootstrap_gzip_bytes"),
        "max_bootstrap_gzip_bytes": budgets.get("max_bootstrap_gzip_bytes"),
    }

    if smoke_result.get("verdict") != "PASS":
        raise RuntimeError("fresh public browser smoke is not PASS")
    scenarios = smoke_result.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise RuntimeError("fresh public browser smoke has no scenarios")
    scenario_ids = [scenario.get("id") for scenario in scenarios]
    if any(not isinstance(identifier, str) for identifier in scenario_ids):
        raise RuntimeError("fresh public browser smoke has malformed scenario identifiers")

    smoke_evidence["verdict"] = "PASS"
    smoke_evidence["scenarios"] = scenarios
    binding = smoke_evidence.setdefault("binding", {})
    binding.update(
        {
            "smoke_script_sha256": file_sha256(SMOKE_SCRIPT_PATH),
            "smoke_runner_sha256": file_sha256(SMOKE_RUNNER_PATH),
            "smoke_plan_sha256": file_sha256(SMOKE_PLAN_PATH),
            "first_party_surface_sha256": surface_hash,
            "scenario_ids": scenario_ids,
            "freshness_rule": (
                "The committed smoke result is valid only while all bound hashes and the ordered "
                "scenario set match the current repository surface."
            ),
        }
    )

    write_json(BENCHMARK_PATH, evidence)
    write_json(SMOKE_PATH, smoke_evidence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-measurement", type=Path, required=True)
    parser.add_argument("--smoke-result", type=Path, required=True)
    args = parser.parse_args()
    refresh(args.browser_measurement, args.smoke_result)
    print("catalogue delivery evidence refreshed from fresh static, browser and smoke measurements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
