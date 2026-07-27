#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"
SCALE_COUNTS = (1_000, 10_000)
STRESS_COUNT = 100_000
COUNTS = (*SCALE_COUNTS, STRESS_COUNT)
PREFIX_LENGTH = 2
INITIAL_WORLD_INDEX_MAX_GZIP_BYTES = 32_768
SHARD_WARN_GZIP_BYTES = 28_672
SHARD_MAX_GZIP_BYTES = 32_768


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def record(index: int) -> dict:
    identifier = f"synthetic-common-{index:06d}"
    detail_sha256 = hashlib.sha256(identifier.encode()).hexdigest()
    return {
        "access": "public",
        "actions": ["learn", "contribute"],
        "activity": "active",
        "detail": {
            "version": "1.0",
            "identity": identifier,
            "generation": "b" * 64,
            "url": f"catalog/runtime/details/{detail_sha256}.v1.json",
            "sha256": detail_sha256,
            "bytes": 2048,
        },
        "id": identifier,
        "languages": ["en"],
        "presence": {
            "digital": index % 3 == 0,
            "geographic": [
                {
                    "geometry": {
                        "coordinates": [((index * 37) % 360) - 180, ((index * 17) % 160) - 80],
                        "type": "Point",
                    },
                    "mode": "approximate",
                }
            ],
        },
        "themes": ["community", f"theme-{index % 24}"],
        "title": f"Synthetic Common {index:06d}",
    }


def shard_budget_state(gzip_max_bytes: int) -> str:
    if gzip_max_bytes >= SHARD_MAX_GZIP_BYTES:
        return "fail"
    if gzip_max_bytes >= SHARD_WARN_GZIP_BYTES:
        return "warning"
    return "pass"


def measure(count: int) -> dict:
    records = [record(i) for i in range(count)]
    payload = canonical_bytes({"kind": "commonworld.world_index", "records": records, "version": "1.0"})
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    shards: dict[str, list[dict]] = {}
    for item in records:
        key = hashlib.sha256(item["id"].encode()).hexdigest()[:PREFIX_LENGTH]
        shards.setdefault(key, []).append(item)
    shard_payloads = [
        canonical_bytes({"key": key, "kind": "commonworld.catalog_shard", "records": values, "version": "1.0"})
        for key, values in sorted(shards.items())
    ]
    parse_samples = []
    for _ in range(5):
        started = time.perf_counter()
        json.loads(payload)
        parse_samples.append((time.perf_counter() - started) * 1000)
    gzip_sizes = [len(gzip.compress(item, compresslevel=9, mtime=0)) for item in shard_payloads]
    gzip_max_bytes = max(gzip_sizes)
    world_index_gzip_bytes = len(compressed)
    return {
        "entry_count": count,
        "world_index": {
            "raw_bytes": len(payload),
            "gzip_bytes": world_index_gzip_bytes,
            "parse_ms_median": round(statistics.median(parse_samples), 3),
        },
        "shards": {
            "count": len(shard_payloads),
            "gzip_total_bytes": sum(gzip_sizes),
            "gzip_max_bytes": gzip_max_bytes,
            "gzip_median_bytes": round(statistics.median(gzip_sizes), 1),
            "max_entries": max(len(values) for values in shards.values()),
        },
        "gate_evaluation": {
            "world_index_initial_delivery": (
                "rejected" if world_index_gzip_bytes > INITIAL_WORLD_INDEX_MAX_GZIP_BYTES else "within_budget"
            ),
            "shard_gzip": shard_budget_state(gzip_max_bytes),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure deterministic Commonworld catalogue scale payloads.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    measurements = [measure(count) for count in COUNTS]
    result = {
        "kind": "commonworld.catalog_platform_scaling_evidence",
        "version": "1.1",
        "synthetic_only": True,
        "scale_tiers": list(SCALE_COUNTS),
        "stress_tier": STRESS_COUNT,
        "budgets": {
            "initial_world_index_max_gzip_bytes": INITIAL_WORLD_INDEX_MAX_GZIP_BYTES,
            "shard_warn_gzip_bytes": SHARD_WARN_GZIP_BYTES,
            "shard_max_gzip_bytes": SHARD_MAX_GZIP_BYTES,
        },
        "shard_strategy": {"algorithm": "sha256-prefix", "prefix_length": PREFIX_LENGTH},
        "measurements": measurements,
        "decision": {
            "full_world_index_initial_delivery": "rejected_for_all_measured_tiers",
            "reason": "Every measured full index exceeds the initial catalogue payload budget; it remains an export and audit surface.",
            "runtime_path": "small aggregate manifest plus demand-loaded shards and details",
            "scale_cutover_task": "COMMONWORLD-PUBLIC-GLOBE-V1-T028",
            "fixed_prefix_stress_state": next(
                item["gate_evaluation"]["shard_gzip"]
                for item in measurements
                if item["entry_count"] == STRESS_COUNT
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
