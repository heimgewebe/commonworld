#!/usr/bin/env python3
"""Measure deterministic bounded catalogue recovery at the T028 scale tiers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.catalog_recovery import (
    PAGE_SIZE,
    RECOVERY_LOCALES,
    index_relative_path,
    inventory_digest,
    load_records,
    localize_fixture_records,
    page_count,
    payload_metrics,
    project_relative_path,
    render_index,
    render_project,
)
from scripts.catalog_scale_fixtures import (
    fixture_digest,
    load_seed_records,
    representative_english_overlay,
    representative_records,
)
from scripts.commonworld_i18n import localize_records

EVIDENCE_PATH = ROOT / "docs/evidence/catalog-recovery-scale-v1.json"
SCALE_TIERS = (1_000, 10_000)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def max_metrics(values: list[dict[str, int]]) -> dict[str, int]:
    return {key: max(value[key] for value in values) for key in values[0]}


def measure_records(
    records: list[dict],
    localized_by_locale: dict[str, list[dict]],
    *,
    project_sample_count: int,
    root: Path = ROOT,
) -> dict:
    identifiers = [record["id"] for record in records]
    locales: dict[str, dict] = {}
    for locale in RECOVERY_LOCALES:
        localized = localized_by_locale[locale]
        pages = [
            payload_metrics(render_index(localized, locale, number, root))
            for number in range(1, page_count(len(localized)) + 1)
        ]
        projects = [
            payload_metrics(render_project(record, locale, root))
            for record in localized[:project_sample_count]
        ]
        inventory = [
            index_relative_path(locale, number).as_posix()
            for number in range(1, page_count(len(localized)) + 1)
        ] + [project_relative_path(locale, identifier).as_posix() for identifier in identifiers]
        locales[locale] = {
            "index_page_count": len(pages),
            "index_page_max": max_metrics(pages),
            "landing_page": pages[0],
            "project_page_count": len(localized),
            "project_page_sample_count": len(projects),
            "project_page_sample_strategy": "one-per-canonical-seed-shape",
            "project_page_sample_max": max_metrics(projects),
            "generated_inventory_sha256": inventory_digest(inventory),
        }
    return {
        "entry_count": len(records),
        "identity_order_sha256": hashlib.sha256((canonical_json(identifiers) + "\n").encode("utf-8")).hexdigest(),
        "page_size": PAGE_SIZE,
        "locales": locales,
    }


def build_result(root: Path = ROOT) -> dict:
    seeds = load_seed_records(root)
    current = load_records(root)
    current_locales = {
        locale: sorted(localize_records(current, locale, root), key=lambda record: record["id"])
        for locale in RECOVERY_LOCALES
    }
    current_measurement = measure_records(
        current,
        current_locales,
        project_sample_count=len(current),
        root=root,
    )
    measurements = []
    for count in SCALE_TIERS:
        records = representative_records(count, root, validate=False)
        overlay = representative_english_overlay(records, root)
        localized = {
            locale: localize_fixture_records(records, overlay, locale, root)
            for locale in RECOVERY_LOCALES
        }
        measurement = measure_records(
            records,
            localized,
            project_sample_count=len(seeds),
            root=root,
        )
        measurement["fixture_sha256"] = fixture_digest(records, overlay)
        measurements.append(measurement)
    source_catalog = root / "catalog/catalog.json"
    source_overlay = root / "catalog/locales/en.json"
    return {
        "kind": "commonworld.catalog_recovery_scale_evidence",
        "version": "1.0",
        "task_id": "COMMONWORLD-PUBLIC-GLOBE-V1-T028",
        "source_catalog_sha256": hashlib.sha256(source_catalog.read_bytes()).hexdigest(),
        "source_english_overlay_sha256": hashlib.sha256(source_overlay.read_bytes()).hexdigest(),
        "scale_tiers": list(SCALE_TIERS),
        "page_size": PAGE_SIZE,
        "locales": list(RECOVERY_LOCALES),
        "current_catalog": current_measurement,
        "measurements": measurements,
        "decision": {
            "bounded_recovery_surface": "pass_de_en",
            "landing_embeds_complete_catalog": False,
            "runtime_catalogue_cutover_authorized": False,
            "does_not_establish": [
                "scale-native visible search, map or digital navigation",
                "physical-device parity",
                "production deployment or readback",
                "editorial publishability of generated fixtures",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build_result(ROOT)
    payload = canonical_json(result) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            print(f"catalogue recovery evidence drift: {args.output}", file=sys.stderr)
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
