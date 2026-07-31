#!/usr/bin/env python3
"""Evaluate bounded browser measurements without discarding observed variance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUDGET_PATH = ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json"
EXPECTED_PROFILES = ("mobile-low-power", "desktop-low-power")
EXIT_CONFIRMATION_REQUIRED = 2
EXIT_CONSECUTIVE_BREACH = 3

METRIC_BUDGETS = (
    ("project_json_request_count", "max_startup_project_json_requests"),
    ("dom_node_count", "max_browser_dom_nodes"),
    ("runtime_ready_ms", "max_runtime_ready_ms_at_4x_cpu"),
    ("script_duration_ms", "max_script_duration_ms_at_4x_cpu"),
    ("task_duration_ms", "max_task_duration_ms_at_4x_cpu"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def assess_measurement(
    measurement: dict[str, Any],
    budgets: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], str | None]:
    """Return structural errors, budget breaches and the bound surface hash."""

    errors: list[str] = []
    breaches: list[dict[str, Any]] = []

    if measurement.get("schema_version") != 1:
        errors.append("measurement schema_version must be 1")
    if measurement.get("kind") != "commonworld_catalog_delivery_browser_metrics":
        errors.append("measurement kind is not browser metrics")
    if measurement.get("cpu_throttle_rate") != 4:
        errors.append("measurement must use fourfold CPU throttling")

    raw_profiles = measurement.get("profiles")
    if not isinstance(raw_profiles, list):
        return errors + ["measurement profiles must be an array"], breaches, None

    profiles: dict[str, dict[str, Any]] = {}
    for profile in raw_profiles:
        if not isinstance(profile, dict) or not isinstance(profile.get("profile"), str):
            errors.append("measurement contains a profile without a string name")
            continue
        name = profile["profile"]
        if name in profiles:
            errors.append(f"measurement contains duplicate profile: {name}")
        profiles[name] = profile

    if tuple(sorted(profiles)) != tuple(sorted(EXPECTED_PROFILES)):
        errors.append(f"measurement profiles must be exactly {list(EXPECTED_PROFILES)}")
        return errors, breaches, None

    surface_hashes: set[str] = set()
    for name in EXPECTED_PROFILES:
        profile = profiles[name]
        if profile.get("cpu_throttle_rate") != 4:
            errors.append(f"{name}: profile must use fourfold CPU throttling")
        if profile.get("runtime_ready") is not True:
            errors.append(f"{name}: runtime_ready must be true")
        if profile.get("runtime_failed") is not False:
            errors.append(f"{name}: runtime_failed must be false")

        requests = profile.get("first_party_requests")
        if not isinstance(requests, list) or not requests:
            errors.append(f"{name}: first_party_requests must be a non-empty array")
        surface_hash = profile.get("first_party_surface_sha256")
        if not isinstance(surface_hash, str) or len(surface_hash) != 64:
            errors.append(f"{name}: invalid first-party surface hash")
        else:
            surface_hashes.add(surface_hash)

        for metric, budget_name in METRIC_BUDGETS:
            actual = profile.get(metric)
            maximum = budgets.get(budget_name)
            if not is_number(actual):
                errors.append(f"{name}: missing numeric {metric}")
                continue
            if not is_number(maximum):
                errors.append(f"missing numeric budget {budget_name}")
                continue
            if actual > maximum:
                breaches.append(
                    {
                        "profile": name,
                        "metric": metric,
                        "actual": actual,
                        "maximum": maximum,
                    }
                )

        compile_p95 = profile.get("bootstrap_compile", {}).get("p95_ms")
        compile_maximum = budgets.get("max_bootstrap_compile_p95_ms_at_4x_cpu")
        if not is_number(compile_p95):
            errors.append(f"{name}: missing numeric bootstrap compile p95")
        elif not is_number(compile_maximum):
            errors.append("missing numeric budget max_bootstrap_compile_p95_ms_at_4x_cpu")
        elif compile_p95 > compile_maximum:
            breaches.append(
                {
                    "profile": name,
                    "metric": "bootstrap_compile.p95_ms",
                    "actual": compile_p95,
                    "maximum": compile_maximum,
                }
            )

    if len(surface_hashes) != 1:
        errors.append("all profiles in one measurement must bind the same first-party surface")
        return errors, breaches, None
    return errors, breaches, next(iter(surface_hashes))


def build_decision_evidence(
    measurements: list[dict[str, Any]],
    budgets: dict[str, Any],
    *,
    budget_contract_sha256: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Build deterministic decision evidence for one or two consecutive attempts."""

    if len(measurements) not in {1, 2}:
        return None, ["exactly one or two browser measurement attempts are required"]

    attempts: list[dict[str, Any]] = []
    errors: list[str] = []
    surface_hashes: set[str] = set()
    for index, measurement in enumerate(measurements, start=1):
        structural_errors, breaches, surface_hash = assess_measurement(measurement, budgets)
        errors.extend(f"attempt {index}: {error}" for error in structural_errors)
        if surface_hash is not None:
            surface_hashes.add(surface_hash)
        attempts.append(
            {
                "attempt": index,
                "verdict": "breach" if breaches else "pass",
                "measurement_sha256": canonical_sha256(measurement),
                "breaches": breaches,
                "measurement": deepcopy(measurement),
            }
        )

    if errors:
        return None, errors
    if len(surface_hashes) != 1:
        return None, ["all attempts must bind the same first-party surface"]

    first_breached = attempts[0]["verdict"] == "breach"
    if len(attempts) == 1:
        if first_breached:
            decision = "confirmation-required"
            gate_verdict = "pending"
            selected_attempt = None
            reason = "The first representative attempt breached a budget and requires exactly one confirmation run."
        else:
            decision = "pass"
            gate_verdict = "pass"
            selected_attempt = 1
            reason = "The first representative attempt passed every bound browser budget."
    else:
        if not first_breached:
            return None, ["a second attempt is only permitted after a first-attempt breach"]
        second_breached = attempts[1]["verdict"] == "breach"
        if second_breached:
            decision = "consecutive-breach"
            gate_verdict = "block"
            selected_attempt = None
            reason = "Two consecutive representative attempts breached a browser budget; architecture review is required."
        else:
            decision = "variance-observed"
            gate_verdict = "pass"
            selected_attempt = 2
            reason = "The first attempt breached and the required second attempt passed; both observations remain authoritative evidence of variance."

    projection: list[dict[str, Any]] = []
    if selected_attempt is not None:
        projection = deepcopy(attempts[selected_attempt - 1]["measurement"]["profiles"])

    evidence = {
        "schema_version": 1,
        "kind": "commonworld_catalog_delivery_browser_measurement_decision",
        "decision": decision,
        "gate_verdict": gate_verdict,
        "decision_reason": reason,
        "architecture_review_required": decision == "consecutive-breach",
        "cpu_throttle_rate": 4,
        "budget_contract_sha256": budget_contract_sha256,
        "first_party_surface_sha256": next(iter(surface_hashes)),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "selected_attempt": selected_attempt,
        "profiles": projection,
        "projection_note": (
            "Top-level profiles reproduce the accepted gate attempt for legacy consumers; "
            "the complete attempts array is the authoritative evidence."
            if selected_attempt is not None
            else "No passing attempt exists, so no top-level budget projection is published."
        ),
    }
    return evidence, []


def validate_decision_evidence(
    evidence: dict[str, Any],
    budgets: dict[str, Any],
    *,
    budget_contract_sha256: str,
    require_terminal_pass: bool,
) -> list[str]:
    """Recompute the full decision and reject omitted or manipulated attempts."""

    errors: list[str] = []
    raw_attempts = evidence.get("attempts")
    if not isinstance(raw_attempts, list):
        return ["browser decision attempts must be an array"]

    measurements: list[dict[str, Any]] = []
    for index, attempt in enumerate(raw_attempts, start=1):
        if not isinstance(attempt, dict):
            errors.append(f"attempt {index} must be an object")
            continue
        measurement = attempt.get("measurement")
        if not isinstance(measurement, dict):
            errors.append(f"attempt {index} measurement must be an object")
            continue
        measurements.append(measurement)
    if errors:
        return errors

    expected, build_errors = build_decision_evidence(
        measurements,
        budgets,
        budget_contract_sha256=budget_contract_sha256,
    )
    errors.extend(build_errors)
    if expected is None:
        return errors
    if evidence != expected:
        errors.append("browser measurement decision does not match its embedded attempts")
    if require_terminal_pass and expected["decision"] not in {"pass", "variance-observed"}:
        errors.append(
            f"committed browser measurement decision is not a terminal pass: {expected['decision']}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-contract", type=Path, default=DEFAULT_BUDGET_PATH)
    args = parser.parse_args()

    contract = load_json(args.budget_contract)
    measurements = [load_json(path) for path in args.attempt]
    evidence, errors = build_decision_evidence(
        measurements,
        contract.get("budgets", {}),
        budget_contract_sha256=file_sha256(args.budget_contract),
    )
    if errors or evidence is None:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    write_json(args.output, evidence)
    print(
        "browser measurement decision: "
        f"{evidence['decision']} from {evidence['attempt_count']} attempt(s)"
    )
    if evidence["decision"] == "confirmation-required":
        return EXIT_CONFIRMATION_REQUIRED
    if evidence["decision"] == "consecutive-breach":
        return EXIT_CONSECUTIVE_BREACH
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
