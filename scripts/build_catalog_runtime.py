#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "catalog.json"
OUT = ROOT / "catalog" / "runtime"
SHARD_PREFIX_LENGTH = 2


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_points(record: dict) -> list[dict]:
    result = []
    for location in record.get("presence", {}).get("geographic", []):
        if location.get("mode") == "hidden" or "geometry" not in location:
            continue
        result.append({"mode": location["mode"], "geometry": location["geometry"]})
    return result


def shard_key(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:SHARD_PREFIX_LENGTH]


def compact_record(record: dict) -> dict:
    digital = record.get("presence", {}).get("digital", {})
    return {
        "id": record["id"],
        "title": record["title"],
        "themes": record.get("themes", []),
        "actions": record.get("actions", []),
        "languages": record.get("languages", {}).get("codes", []),
        "access": record.get("access", {}).get("type"),
        "presence": {
            "geographic": public_points(record),
            "digital": bool(digital.get("available")),
        },
        "activity": record.get("activity", {}).get("status", "unknown"),
        "detail": f"catalog/projects/{record['id']}.json",
    }


def main() -> int:
    source = json.loads(CATALOG.read_text(encoding="utf-8"))
    records = []
    for relative in source["project_files"]:
        record = json.loads((ROOT / "catalog" / relative).read_text(encoding="utf-8"))
        records.append(compact_record(record))
    records.sort(key=lambda item: item["id"])
    world = {"kind": "commonworld.world_index", "version": "1.0", "records": records}
    world_bytes = canonical_bytes(world)
    shards: dict[str, list[dict]] = {}
    for record in records:
        shards.setdefault(shard_key(record["id"]), []).append(record)
    shard_dir = OUT / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.v1.json"):
        stale.unlink()
    shard_entries = []
    for key, shard_records in sorted(shards.items()):
        payload = canonical_bytes({"kind": "commonworld.catalog_shard", "version": "1.0", "key": key, "records": shard_records})
        path = shard_dir / f"{key}.v1.json"
        path.write_bytes(payload)
        shard_entries.append({"key": key, "url": f"catalog/runtime/shards/{key}.v1.json", "sha256": sha256(payload), "bytes": len(payload), "entry_count": len(shard_records)})
    source_bytes = CATALOG.read_bytes()
    generation_seed = {
        "schema_version": "1.0",
        "catalog_manifest_sha256": sha256(source_bytes),
        "world_index_sha256": sha256(world_bytes),
    }
    generation = sha256(canonical_bytes(generation_seed))
    manifest = {
        "kind": "commonworld.catalog_runtime_manifest",
        "version": "1.0",
        "generation": generation,
        "entry_count": len(records),
        "world_index": {"url": "catalog/runtime/world.v1.json", "sha256": sha256(world_bytes), "bytes": len(world_bytes)},
        "detail_url_template": "catalog/projects/{id}.json",
        "shards": {"strategy": "sha256-prefix", "prefix_length": SHARD_PREFIX_LENGTH, "entries": shard_entries},
        "source_catalog_sha256": sha256(source_bytes),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "world.v1.json").write_bytes(world_bytes)
    (OUT / "manifest.v1.json").write_bytes(canonical_bytes(manifest))
    print(f"built catalog runtime generation {generation} with {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
