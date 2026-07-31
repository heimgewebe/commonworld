#!/usr/bin/env python3
"""Select a representative browser measurement without weakening its budgets."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json"
EXPECTED_PROFILES = {"mobile-low-power", "desktop-low-power"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assess(candidate: dict, budgets: dict) -> list[str]:
    errors: list[str] = []
    if candidate.get("cpu_throttle_rate") != 4:
        errors.append("measurement must use fourfold CPU throttling")
    profiles = {
        item.get("profile"): item
        for item in candidate.get("profiles", [])
        if isinstance(item, dict) and isinstance(item.get("profile"), str)
    }
    if set(profiles) != EXPECTED_PROFILES:
        errors.append(f"profiles must be exactly {sorted(EXPECTED_PROFILES)}")
        return errors

    checks = {
        "project JSON requests": (
            "project_json_request_count",
            "max_startup_project_json_requests",
        ),
        "DOM nodes": ("dom_node_count", "max_browser_dom_nodes"),
        "runtime ready milliseconds": (
            "runtime_ready_ms",
            "max_runtime_ready_ms_at_4x_cpu",
        ),
        "script duration milliseconds": (
            "script_duration_ms",
            "max_script_duration_ms_at_4x_cpu",
        ),
        "task duration milliseconds": (
            "task_duration_ms",
            "max_task_duration_ms_at_4x_cpu",
        ),
    }
    for name, profile in profiles.items():
        if profile.get("runtime_ready") is not True or profile.get("runtime_failed") is not False:
            errors.append(f"{name}: runtime did not reach a healthy ready state")
        for label, (field, budget_field) in checks.items():
            actual = profile.get(field)
            maximum = budgets.get(budget_field)
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                errors.append(f"{name}: missing numeric {label}")
            elif actual > maximum:
                errors.append(f"{name}: {label} exceeds budget: {actual} > {maximum}")
        compile_p95 = profile.get("bootstrap_compile", {}).get("p95_ms")
        compile_max = budgets.get("max_bootstrap_compile_p95_ms_at_4x_cpu")
        if not isinstance(compile_p95, (int, float)) or isinstance(compile_p95, bool):
            errors.append(f"{name}: missing bootstrap compile p95")
        elif compile_p95 > compile_max:
            errors.append(
                f"{name}: bootstrap compile p95 exceeds budget: {compile_p95} > {compile_max}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()

    budgets = load(BUDGET_PATH)["budgets"]
    candidate = load(args.candidate)
    errors = assess(candidate, budgets)
    if errors:
        print(
            f"Representative browser measurement attempt {args.attempt} breached a budget:",
            file=sys.stderr,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    shutil.copyfile(args.candidate, args.output)
    print(f"Representative browser measurement attempt {args.attempt} accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
