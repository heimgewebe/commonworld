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
    from scripts.measure_catalog_delivery import measure
except ModuleNotFoundError:
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


def payload_sha256(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def browser_breaches(measurement: dict, budgets: dict) -> list[str]:
    checks = {
        "project_json_request_count": "max_startup_project_json_requests",
        "dom_node_count": "max_browser_dom_nodes",
        "runtime_ready_ms": "max_runtime_ready_ms_at_4x_cpu",
        "script_duration_ms": "max_script_duration_ms_at_4x_cpu",
        "task_duration_ms": "max_task_duration_ms_at_4x_cpu",
    }
    breaches: list[str] = []
    for profile in measurement.get("profiles", []):
        name = profile.get("profile", "unknown")
        for metric, budget_key in checks.items():
            actual = profile.get(metric)
            maximum = budgets.get(budget_key)
            if not isinstance(actual, (int, float)) or not isinstance(maximum, (int, float)):
                breaches.append(f"{name}:{metric}:missing")
            elif actual > maximum:
                breaches.append(f"{name}:{metric}:{actual}>{maximum}")
        p95 = profile.get("bootstrap_compile", {}).get("p95_ms")
        p95_max = budgets.get("max_bootstrap_compile_p95_ms_at_4x_cpu")
        if not isinstance(p95, (int, float)) or not isinstance(p95_max, (int, float)):
            breaches.append(f"{name}:bootstrap_compile_p95_ms:missing")
        elif p95 > p95_max:
            breaches.append(f"{name}:bootstrap_compile_p95_ms:{p95}>{p95_max}")
        if profile.get("runtime_ready") is not True or profile.get("runtime_failed") is not False:
            breaches.append(f"{name}:runtime-health")
    return breaches


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

    breaches = browser_breaches(browser_measurement, budgets)
    if breaches:
        raise RuntimeError("fresh browser measurement breaches delivery budgets: " + ", ".join(breaches))
    if browser_measurement.get("cpu_throttle_rate") != 4:
        raise RuntimeError("fresh browser measurement did not use fourfold CPU throttling")

    profiles = browser_measurement.get("profiles", [])
    surface_hashes = {
        profile.get("first_party_surface_sha256")
        for profile in profiles
        if isinstance(profile, dict)
    }
    if len(surface_hashes) != 1 or None in surface_hashes:
        raise RuntimeError(f"fresh browser profiles disagree on first-party surface: {surface_hashes}")
    surface_hash = next(iter(surface_hashes))

    evidence["base_commit"] = os.environ.get("GITHUB_SHA", evidence.get("base_commit"))
    evidence["optimized"]["static"] = static
    evidence["baseline"]["static"] = baseline_static_from(static)

    optimized_browser = evidence["optimized"].setdefault("browser", {})
    optimized_browser.update(
        {
            "schema_version": 1,
            "kind": "commonworld_catalog_delivery_browser_measurement_decision",
            "decision": "pass",
            "gate_verdict": "pass",
            "decision_reason": (
                "Fresh fourfold-CPU mobile and desktop measurements passed every bound startup budget. "
                "Post-ready work remains diagnostic and is not folded into the startup gate."
            ),
            "architecture_review_required": False,
            "cpu_throttle_rate": browser_measurement["cpu_throttle_rate"],
            "budget_contract_sha256": file_sha256(CONTRACT_PATH),
            "first_party_surface_sha256": surface_hash,
            "measured_at": browser_measurement.get("measured_at"),
            "profiles": profiles,
            "attempt_count": 1,
            "attempts": [
                {
                    "attempt": 1,
                    "verdict": "pass",
                    "measurement_sha256": payload_sha256(browser_measurement),
                    "breaches": [],
                    "measurement": browser_measurement,
                }
            ],
        }
    )

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
