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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    return validate_decision_evidence(
        browser,
        contract.get("budgets", {}),
        budget_contract_sha256=file_sha256(budget_path),
        require_terminal_pass=True,
    )


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
