#!/usr/bin/env python3
"""Keep the canonical Commonworld masterplan aligned with executable scale gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-scale-gates.contract.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def format_de(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def validate_catalog_scale_masterplan(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract_path = root / CONTRACT_PATH.relative_to(ROOT)
    evidence_path = root / EVIDENCE_PATH.relative_to(ROOT)
    for path in (contract_path, evidence_path):
        if not path.is_file():
            errors.append(f"missing catalogue scale plan dependency: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        contract = load_json(contract_path)
        evidence = load_json(evidence_path)
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid catalogue scale plan dependency: {error}"]

    relative_plan = contract.get("canonical_plan")
    if relative_plan != "docs/blueprints/commonworld-masterplan.md":
        errors.append("catalogue scale contract canonical plan path mismatch")
        return errors
    plan_path = root / relative_plan
    if not plan_path.is_file():
        errors.append(f"missing canonical catalogue scale plan: {relative_plan}")
        return errors
    plan = plan_path.read_text(encoding="utf-8")

    measurements = {
        item.get("entry_count"): item
        for item in evidence.get("measurements", [])
        if isinstance(item, dict) and isinstance(item.get("entry_count"), int)
    }
    required_counts = (1_000, 10_000, 100_000)
    if set(measurements) != set(required_counts):
        errors.append("catalogue scale masterplan evidence inventory mismatch")
        return errors

    budgets = evidence.get("budgets", {})
    stress = measurements[100_000]
    migration = stress.get("prefix_migration_candidate", {})
    required_fragments = [
        "Die revisionsgebundene, schema-realistische Skalierungsprobe vom 2. August 2026",
        "1.000 und 10.000 Einträge",
        f"{format_de(measurements[1_000]['world_index']['gzip_bytes'])} Byte gzip",
        f"{format_de(measurements[10_000]['world_index']['gzip_bytes'])} Byte gzip",
        f"{format_de(measurements[1_000]['shards']['gzip_max_bytes'])} beziehungsweise {format_de(measurements[10_000]['shards']['gzip_max_bytes'])} Byte gzip",
        "100.000-Einträge-Stresstest",
        f"{format_de(stress['world_index']['gzip_bytes'])} Byte gzip",
        f"{format_de(stress['shards']['gzip_max_bytes'])} Byte gzip",
        f"Maximum von {format_de(budgets['shard_max_gzip_bytes'])} Byte",
        f"{format_de(migration['shards']['gzip_max_bytes'])} Byte",
        f"{format_de(migration['manifest']['gzip_bytes'])} Byte gzip Manifest",
        f"{format_de(migration['aggregate']['gzip_bytes'])} Byte gzip Aggregat",
        "hierarchischer Manifest- und Aggregatvertrag",
        "`contracts/commonworld/catalog-scale-gates.contract.json`",
    ]
    for fragment in required_fragments:
        if fragment not in plan:
            errors.append(f"canonical catalogue scale plan misses current fragment: {fragment}")

    for stale in (
        "1.541.423 Byte gzip",
        "7.885 Byte gzip",
        "Die Skalierungsprobe vom 25. Juli 2026",
        "Die revisionsgebundene Skalierungsprobe vom 27. Juli 2026",
        "62.845 Byte gzip",
        "624.128 Byte gzip",
        "28.683 Byte gzip",
    ):
        if stale in plan:
            errors.append(f"canonical catalogue scale plan retains stale fragment: {stale}")

    return errors


def main() -> int:
    errors = validate_catalog_scale_masterplan()
    if errors:
        print("Catalogue scale masterplan validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Catalogue scale masterplan validation passed: canonical plan matches schema-realistic 1k/10k gates and the fail-closed 100k migration boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
