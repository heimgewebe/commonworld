#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"
COUNTS = (10_000, 100_000)
PREFIX_LENGTH = 2


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def record(index: int) -> dict:
    identifier = f"synthetic-common-{index:06d}"
    detail_sha256 = hashlib.sha256(identifier.encode()).hexdigest()
    return {
        "access": "public",
        "actions": ["learn", "contribute"],
        "activity": "active",
        "detail": {"version": "1.0", "identity": identifier, "generation": "b" * 64, "url": f"catalog/runtime/details/{detail_sha256}.v1.json", "sha256": detail_sha256, "bytes": 2048},
        "id": identifier,
        "languages": ["en"],
        "presence": {"digital": index % 3 == 0, "geographic": [{"geometry": {"coordinates": [((index * 37) % 360) - 180, ((index * 17) % 160) - 80], "type": "Point"}, "mode": "approximate"}]},
        "themes": ["community", f"theme-{index % 24}"],
        "title": f"Synthetic Common {index:06d}",
    }


def measure(count: int) -> dict:
    records = [record(i) for i in range(count)]
    payload = canonical_bytes({"kind": "commonworld.world_index", "records": records, "version": "1.0"})
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    shards: dict[str, list[dict]] = {}
    for item in records:
        key = hashlib.sha256(item["id"].encode()).hexdigest()[:PREFIX_LENGTH]
        shards.setdefault(key, []).append(item)
    shard_payloads = [canonical_bytes({"key": key, "kind": "commonworld.catalog_shard", "records": values, "version": "1.0"}) for key, values in sorted(shards.items())]
    parse_samples = []
    for _ in range(5):
        started = time.perf_counter()
        json.loads(payload)
        parse_samples.append((time.perf_counter() - started) * 1000)
    gzip_sizes = [len(gzip.compress(item, compresslevel=9, mtime=0)) for item in shard_payloads]
    return {
        "entry_count": count,
        "world_index": {"raw_bytes": len(payload), "gzip_bytes": len(compressed), "parse_ms_median": round(statistics.median(parse_samples), 3)},
        "shards": {"count": len(shard_payloads), "gzip_total_bytes": sum(gzip_sizes), "gzip_max_bytes": max(gzip_sizes), "gzip_median_bytes": round(statistics.median(gzip_sizes), 1), "max_entries": max(len(v) for v in shards.values())},
    }


def main() -> int:
    result = {
        "kind": "commonworld.catalog_platform_scaling_evidence",
        "version": "1.0",
        "synthetic_only": True,
        "shard_strategy": {"algorithm": "sha256-prefix", "prefix_length": PREFIX_LENGTH},
        "measurements": [measure(count) for count in COUNTS],
        "decision": {
            "single_world_index_for_100k": "rejected",
            "reason": "The measured full index is suitable as an offline export, not as initial browser payload.",
            "runtime_path": "small aggregate manifest plus demand-loaded shards and details",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(canonical_bytes(result))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
