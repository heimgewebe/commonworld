#!/usr/bin/env python3
"""Patch the closed canonical inventory for permanent Commons admission files."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/validate_canonical_plan.py"


def replace_once(source: str, old: str, new: str) -> str:
    if new in source:
        return source
    if old not in source:
        raise ValueError(f"canonical inventory marker missing: {old!r}")
    return source.replace(old, new, 1)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old_contracts = 'EXPECTED_CONTRACT_FILES = {"catalog-platform.contract.json", "catalog-delivery-budget.contract.json", "catalog-scale-gates.contract.json", "catalog-diversity.contract.json", "editorial-review.contract.json", "proposal-path.contract.json", "proposal.schema.json", "current-state.contract.json", "aggregation-zoom.contract.json", "digital-ring-taxonomy.contract.json", "digital-sphere.contract.json", "production-delivery-provider.contract.json", "project.schema.json", "public-maplibre-vertical-slice.contract.json", "presence-axes.contract.json", "intent-search-discovery.contract.json", "renderer-selection.contract.json", "visual-semantics.contract.json"}'
    new_contracts = 'EXPECTED_CONTRACT_FILES = {"catalog-platform.contract.json", "catalog-delivery-budget.contract.json", "catalog-scale-gates.contract.json", "catalog-diversity.contract.json", "commons-basis.schema.json", "commons-definition.contract.json", "editorial-review.contract.json", "proposal-path.contract.json", "proposal.schema.json", "current-state.contract.json", "aggregation-zoom.contract.json", "digital-ring-taxonomy.contract.json", "digital-sphere.contract.json", "production-delivery-provider.contract.json", "project.schema.json", "public-maplibre-vertical-slice.contract.json", "presence-axes.contract.json", "intent-search-discovery.contract.json", "renderer-selection.contract.json", "visual-semantics.contract.json"}'
    source = replace_once(source, old_contracts, new_contracts)
    source = replace_once(
        source,
        '    "measure_catalog_delivery.py",\n',
        '    "evaluate_catalog_browser_measurements.py",\n    "measure_catalog_delivery.py",\n',
    )
    source = replace_once(
        source,
        '    "validate_contracts.py",\n',
        '    "validate_commons_admission.py",\n    "validate_contracts.py",\n',
    )
    source = replace_once(
        source,
        '    "validate_catalog_delivery_budget.py",\n',
        '    "validate_catalog_browser_measurement_decision.py",\n    "validate_catalog_delivery_budget.py",\n',
    )
    source = replace_once(
        source,
        '    "test_catalog_delivery_budget.py",\n',
        '    "test_catalog_browser_measurement_decision.py",\n    "test_catalog_delivery_budget.py",\n',
    )
    source = replace_once(
        source,
        '    "test_contracts.py",\n',
        '    "test_commons_admission.py",\n    "test_contracts.py",\n',
    )
    PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
