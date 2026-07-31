#!/usr/bin/env python3
"""Validate committed browser performance decisions and every bound attempt."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    from scripts.evaluate_catalog_browser_measurements import validate_decision_evidence
except ModuleNotFoundError:  # Direct execution adds scripts/ to sys.path.
    from evaluate_catalog_browser_measurements import validate_decision_evidence

ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json"
EVIDENCE_PATH = ROOT / "docs/evidence/catalog-delivery-benchmark-v1.json"
RELEASE_PROBE_METRIC_PATH = "/__cw_probe/<nonce>/manifest"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_party_surface_sha256(root: Path, requests: list[str]) -> str:
    digest = hashlib.sha256()
    resolved_root = root.resolve()
    for request_path in sorted(requests):
        if not isinstance(request_path, str) or not request_path.startswith("/"):
            raise ValueError(f"invalid first-party request path: {request_path!r}")
        if request_path == RELEASE_PROBE_METRIC_PATH:
            relative = "404.html"
        else:
            relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        target = (root / relative).resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise ValueError(f"first-party request escapes repository root: {request_path}")
        digest.update(request_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(target.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_attempt_surfaces(browser: dict, root: Path) -> list[str]:
    errors: list[str] = []
    for attempt_index, attempt in enumerate(browser.get("attempts", []), start=1):
        measurement = attempt.get("measurement", {}) if isinstance(attempt, dict) else {}
        profiles = measurement.get("profiles", []) if isinstance(measurement, dict) else []
        for profile in profiles:
            if not isinstance(profile, dict):
                errors.append(f"attempt {attempt_index}: profile must be an object")
                continue
            profile_name = profile.get("profile", "<unknown>")
            requests = profile.get("first_party_requests")
            if not isinstance(requests, list) or not requests:
                errors.append(
                    f"attempt {attempt_index} {profile_name}: first-party request inventory missing"
                )
                continue
            try:
                current_hash = first_party_surface_sha256(root, requests)
            except (OSError, ValueError) as error:
                errors.append(
                    f"attempt {attempt_index} {profile_name}: cannot verify first-party surface: {error}"
                )
                continue
            if profile.get("first_party_surface_sha256") != current_hash:
                errors.append(
                    f"attempt {attempt_index} {profile_name}: evidence is stale for the current first-party surface"
                )
    return errors


def validate(root: Path = ROOT) -> list[str]:
    budget_path = root / BUDGET_PATH.relative_to(ROOT)
    evidence_path = root / EVIDENCE_PATH.relative_to(ROOT)
    errors: list[str] = []
    for path in (budget_path, evidence_path):
        if not path.is_file():
            errors.append(f"missing browser decision artifact: {path.relative_to(root)}")
    if errors:
        return errors

    contract = load_json(budget_path)
    evidence = load_json(evidence_path)
    browser = evidence.get("optimized", {}).get("browser")
    if not isinstance(browser, dict):
        return ["catalogue benchmark lacks optimized browser decision evidence"]
    errors.extend(
        validate_decision_evidence(
            browser,
            contract.get("budgets", {}),
            budget_contract_sha256=file_sha256(budget_path),
            require_terminal_pass=True,
        )
    )
    errors.extend(validate_attempt_surfaces(browser, root))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    browser = load_json(EVIDENCE_PATH)["optimized"]["browser"]
    print(
        "browser measurement decision valid: "
        f"{browser['decision']}, {browser['attempt_count']} attempt(s), "
        f"surface {browser['first_party_surface_sha256'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
