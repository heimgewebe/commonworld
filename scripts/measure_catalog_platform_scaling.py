#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUT = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"
SCALE_COUNTS = (1_000, 10_000)
STRESS_COUNT = 100_000
INITIAL_WORLD_INDEX_MAX_GZIP_BYTES = 32_768
SHARD_WARN_GZIP_BYTES = 28_672
SHARD_MAX_GZIP_BYTES = 32_768

from scripts.catalog_scale_fixtures import (
    build_compact_stress_fixture,
    build_runtime_fixture,
    canonical_bytes,
    compact_fixture_coverage,
    fixture_coverage,
    fixture_digest,
    load_seed_records,
    representative_english_overlay,
    representative_records,
    repartition_runtime_fixture,
    sha256,
)


def gzip_size(payload: bytes) -> int:
    return len(gzip.compress(payload, compresslevel=9, mtime=0))


def parse_ms_median(payloads: list[bytes], *, repeats: int = 1) -> float:
    samples = []
    for payload in payloads:
        for _ in range(repeats):
            started = time.perf_counter()
            json.loads(payload)
            samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 3) if samples else 0.0


def payload_metrics(payload: bytes, *, include_parse_timing: bool, repeats: int = 1) -> dict:
    result = {"raw_bytes": len(payload), "gzip_bytes": gzip_size(payload)}
    if include_parse_timing:
        result["parse_ms_median"] = parse_ms_median([payload], repeats=repeats)
    return result


def collection_metrics(payloads: list[bytes], entry_counts: list[int], *, include_parse_timing: bool) -> dict:
    raw_sizes = [len(payload) for payload in payloads]
    gzip_sizes = [gzip_size(payload) for payload in payloads]
    result = {
        "count": len(payloads),
        "raw_total_bytes": sum(raw_sizes),
        "raw_max_bytes": max(raw_sizes),
        "gzip_total_bytes": sum(gzip_sizes),
        "gzip_max_bytes": max(gzip_sizes),
        "gzip_median_bytes": round(statistics.median(gzip_sizes), 1),
        "max_entries": max(entry_counts),
    }
    if include_parse_timing:
        result["parse_ms_median"] = parse_ms_median(payloads)
    return result


def sampled_payload_metrics(payloads: list[bytes], *, include_parse_timing: bool, sample_limit: int = 32) -> dict:
    raw_sizes = [len(payload) for payload in payloads]
    gzip_sizes = [gzip_size(payload) for payload in payloads]
    result = {
        "count": len(payloads),
        "raw_total_bytes": sum(raw_sizes),
        "raw_max_bytes": max(raw_sizes),
        "gzip_total_bytes": sum(gzip_sizes),
        "gzip_max_bytes": max(gzip_sizes),
        "gzip_median_bytes": round(statistics.median(gzip_sizes), 1),
    }
    if include_parse_timing:
        if len(payloads) <= sample_limit:
            sample = payloads
        else:
            sample = [payloads[round(index * (len(payloads) - 1) / (sample_limit - 1))] for index in range(sample_limit)]
        result["parse_sample_count"] = len(sample)
        result["parse_ms_median"] = parse_ms_median(sample)
    return result


def canonical_de_locale_payload(records: list[dict]) -> bytes:
    projects = {}
    for record in records:
        geographic_labels = {
            location["id"]: location["label"]
            for location in record.get("presence", {}).get("geographic", [])
            if isinstance(location, dict) and isinstance(location.get("id"), str) and isinstance(location.get("label"), str)
        }
        project = {"title": record["title"], "summary": record["summary"]}
        if geographic_labels:
            project["geographic_labels"] = geographic_labels
        digital_label = record.get("presence", {}).get("digital", {}).get("label")
        if isinstance(digital_label, str):
            project["digital_label"] = digital_label
        projects[record["id"]] = project
    return canonical_bytes({"schema_version": 1, "locale": "de", "source": "canonical-project-records", "projects": projects})


def shard_budget_state(gzip_max_bytes: int) -> str:
    if gzip_max_bytes >= SHARD_MAX_GZIP_BYTES:
        return "fail"
    if gzip_max_bytes >= SHARD_WARN_GZIP_BYTES:
        return "warning"
    return "pass"


def runtime_metrics(runtime: dict, *, include_parse_timing: bool, details_materialized: bool) -> dict:
    shard_payloads = [runtime["shard_payloads"][key] for key in sorted(runtime["shard_payloads"])]
    shard_entry_counts = [len(runtime["shard_objects"][key]["records"]) for key in sorted(runtime["shard_objects"])]
    result = {
        "manifest": payload_metrics(runtime["manifest_bytes"], include_parse_timing=include_parse_timing, repeats=5),
        "aggregate": payload_metrics(runtime["aggregate_bytes"], include_parse_timing=include_parse_timing, repeats=5),
        "world_index": payload_metrics(runtime["world_bytes"], include_parse_timing=include_parse_timing, repeats=5),
        "shards": collection_metrics(shard_payloads, shard_entry_counts, include_parse_timing=include_parse_timing),
    }
    if details_materialized:
        detail_payloads = [runtime["detail_payloads"][identifier] for identifier in sorted(runtime["detail_payloads"])]
        result["details"] = sampled_payload_metrics(detail_payloads, include_parse_timing=include_parse_timing)
    else:
        result["details"] = {"count": runtime["manifest"]["details"]["entry_count"], "materialized": False}
    return result


def measure_representative(count: int, *, include_parse_timing: bool) -> dict:
    records = representative_records(count, ROOT, validate=True)
    english_overlay = representative_english_overlay(records, ROOT)
    runtime = build_runtime_fixture(records, ROOT, validate=False)
    metrics = runtime_metrics(runtime, include_parse_timing=include_parse_timing, details_materialized=True)
    english_payload = canonical_bytes(english_overlay)
    german_payload = canonical_de_locale_payload(records)
    metrics["locale_payloads"] = {
        "de": payload_metrics(german_payload, include_parse_timing=include_parse_timing, repeats=3),
        "en": payload_metrics(english_payload, include_parse_timing=include_parse_timing, repeats=3),
    }
    shard_max = metrics["shards"]["gzip_max_bytes"]
    world_gzip = metrics["world_index"]["gzip_bytes"]
    return {
        "entry_count": count,
        "fixture_scope": "full-schema-realistic",
        "fixture_sha256": fixture_digest(records, english_overlay),
        "coverage": fixture_coverage(records, english_overlay),
        **metrics,
        "gate_evaluation": {
            "world_index_initial_delivery": "rejected" if world_gzip > INITIAL_WORLD_INDEX_MAX_GZIP_BYTES else "within_budget",
            "shard_gzip": shard_budget_state(shard_max),
        },
    }


def measure_stress(*, include_parse_timing: bool) -> dict:
    runtime = build_compact_stress_fixture(STRESS_COUNT, ROOT)
    metrics = runtime_metrics(runtime, include_parse_timing=include_parse_timing, details_materialized=False)
    migration_runtime = repartition_runtime_fixture(runtime, prefix_length=3)
    migration_metrics = runtime_metrics(
        migration_runtime,
        include_parse_timing=include_parse_timing,
        details_materialized=False,
    )
    shard_max = metrics["shards"]["gzip_max_bytes"]
    world_gzip = metrics["world_index"]["gzip_bytes"]
    migration_shard_max = migration_metrics["shards"]["gzip_max_bytes"]
    return {
        "entry_count": STRESS_COUNT,
        "fixture_scope": "compact-shard-stress",
        "fixture_sha256": sha256(runtime["world_bytes"]),
        "coverage": compact_fixture_coverage(STRESS_COUNT, ROOT),
        **metrics,
        "prefix_migration_candidate": {
            "algorithm": "sha256-prefix",
            "prefix_length": 3,
            "runtime_compatible_with_current_manifest": False,
            "manifest": migration_metrics["manifest"],
            "aggregate": migration_metrics["aggregate"],
            "shards": migration_metrics["shards"],
            "gate_evaluation": {"shard_gzip": shard_budget_state(migration_shard_max)},
            "required_follow_up": "Introduce a versioned hierarchical manifest and aggregate contract before enabling three-hex runtime shards.",
        },
        "gate_evaluation": {
            "world_index_initial_delivery": "rejected" if world_gzip > INITIAL_WORLD_INDEX_MAX_GZIP_BYTES else "within_budget",
            "shard_gzip": shard_budget_state(shard_max),
        },
    }


def build_result(*, include_parse_timing: bool = True) -> dict:
    seed_records = load_seed_records(ROOT)
    measurements = [
        *(measure_representative(count, include_parse_timing=include_parse_timing) for count in SCALE_COUNTS),
        measure_stress(include_parse_timing=include_parse_timing),
    ]
    return {
        "kind": "commonworld.catalog_platform_scaling_evidence",
        "version": "2.0",
        "representative_fixture_only": True,
        "scale_tiers": list(SCALE_COUNTS),
        "stress_tier": STRESS_COUNT,
        "fixture_model": {
            "kind": "schema-realistic-derived-fixtures",
            "source_catalog": "catalog/catalog.json",
            "source_catalog_sha256": hashlib.sha256((ROOT / "catalog" / "catalog.json").read_bytes()).hexdigest(),
            "source_project_set_sha256": sha256(canonical_bytes(seed_records)),
            "source_english_overlay_sha256": hashlib.sha256((ROOT / "catalog" / "locales" / "en.json").read_bytes()).hexdigest(),
            "source_entry_count": len(seed_records),
            "project_schema_version": 4,
            "released_locale_overlays": ["de", "en"],
            "full_schema_tiers": list(SCALE_COUNTS),
            "compact_only_stress_tier": STRESS_COUNT,
            "does_not_establish": [
                "that generated fixture projects are editorially publishable",
                "real mobile-network latency",
                "physical-device usability",
                "production catalogue cutover",
                "100,000-entry detail-delivery readiness",
            ],
        },
        "budgets": {
            "initial_world_index_max_gzip_bytes": INITIAL_WORLD_INDEX_MAX_GZIP_BYTES,
            "shard_warn_gzip_bytes": SHARD_WARN_GZIP_BYTES,
            "shard_max_gzip_bytes": SHARD_MAX_GZIP_BYTES,
        },
        "shard_strategy": {"algorithm": "sha256-prefix", "prefix_length": 2},
        "measurements": measurements,
        "decision": {
            "full_world_index_initial_delivery": "rejected_for_all_measured_tiers",
            "reason": "Every measured full index exceeds the initial catalogue payload budget; it remains an export and audit surface.",
            "runtime_path": "small aggregate manifest plus demand-loaded shards and details",
            "scale_cutover_task": "COMMONWORLD-PUBLIC-GLOBE-V1-T028",
            "fixture_milestone": "schema-realistic-scale-fixtures-v1",
            "fixed_prefix_stress_state": next(
                item["gate_evaluation"]["shard_gzip"]
                for item in measurements
                if item["entry_count"] == STRESS_COUNT
            ),
            "prefix_migration_candidate_state": next(
                item["prefix_migration_candidate"]["gate_evaluation"]["shard_gzip"]
                for item in measurements
                if item["entry_count"] == STRESS_COUNT
            ),
            "runtime_catalogue_cutover_authorized": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure deterministic schema-realistic Commonworld catalogue scale fixtures.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
