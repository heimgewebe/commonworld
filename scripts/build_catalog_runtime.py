#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "catalog.json"
OUT = ROOT / "catalog" / "runtime"
SHARD_PREFIX_LENGTH = 2
SPATIAL_CELL_DEGREES = 10
DETAIL_DESCRIPTOR_VERSION = "1.0"


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


def spatial_cell(coordinates: list[float]) -> str:
    longitude, latitude = coordinates
    x = min(35, max(0, int((longitude + 180) // SPATIAL_CELL_DEGREES)))
    y = min(17, max(0, int((latitude + 90) // SPATIAL_CELL_DEGREES)))
    return f"{x:02d}:{y:02d}"


def detail_seed_entry(identifier: str, payload: bytes) -> dict:
    digest = sha256(payload)
    return {
        "identity": identifier,
        "url": f"catalog/runtime/details/{digest}.v1.json",
        "sha256": digest,
        "bytes": len(payload),
    }


def detail_descriptor(seed: dict, generation: str) -> dict:
    return {
        "version": DETAIL_DESCRIPTOR_VERSION,
        "identity": seed["identity"],
        "generation": generation,
        "url": seed["url"],
        "sha256": seed["sha256"],
        "bytes": seed["bytes"],
    }


def compact_record(record: dict, detail: dict) -> dict:
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
        "detail": detail,
    }


def main() -> int:
    source = json.loads(CATALOG.read_text(encoding="utf-8"))
    canonical_records: list[dict] = []
    detail_payloads: dict[str, bytes] = {}
    detail_seed_entries: list[dict] = []
    for relative in source["project_files"]:
        record = json.loads((ROOT / "catalog" / relative).read_text(encoding="utf-8"))
        payload = canonical_bytes(record)
        canonical_records.append(record)
        detail_payloads[record["id"]] = payload
        detail_seed_entries.append(detail_seed_entry(record["id"], payload))
    canonical_records.sort(key=lambda item: item["id"])
    detail_seed_entries.sort(key=lambda item: item["identity"])

    source_catalog_sha256 = sha256(CATALOG.read_bytes())
    detail_set_sha256 = sha256(canonical_bytes(detail_seed_entries))
    generation_seed = {
        "schema_version": "2.0",
        "source_catalog_sha256": source_catalog_sha256,
        "detail_set_sha256": detail_set_sha256,
        "project_schema_version": 4,
        "detail_descriptor_version": DETAIL_DESCRIPTOR_VERSION,
    }
    generation = sha256(canonical_bytes(generation_seed))
    descriptors = {
        seed["identity"]: detail_descriptor(seed, generation)
        for seed in detail_seed_entries
    }
    records = [compact_record(record, descriptors[record["id"]]) for record in canonical_records]

    details_dir = OUT / "details"
    details_dir.mkdir(parents=True, exist_ok=True)
    current_detail_names = {Path(descriptor["url"]).name for descriptor in descriptors.values()}
    for stale in details_dir.glob("*.v1.json"):
        if stale.name not in current_detail_names:
            stale.unlink()
    for identifier, payload in detail_payloads.items():
        path = ROOT / descriptors[identifier]["url"]
        path.write_bytes(payload)

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

    indexes = {"themes": {}, "spatial_cells": {}, "digital": {"available": [], "unavailable": []}}
    for record in records:
        key = shard_key(record["id"])
        for theme in record["themes"]:
            indexes["themes"].setdefault(theme, set()).add(key)
        indexes["digital"]["available" if record["presence"]["digital"] else "unavailable"].append(key)
        for location in record["presence"]["geographic"]:
            geometry = location.get("geometry", {})
            if geometry.get("type") == "Point" and len(geometry.get("coordinates", [])) >= 2:
                indexes["spatial_cells"].setdefault(spatial_cell(geometry["coordinates"]), set()).add(key)
    aggregate = {
        "kind": "commonworld.catalog_aggregate",
        "version": "1.0",
        "entry_count": len(records),
        "source_catalog_sha256": source_catalog_sha256,
        "spatial_cell_degrees": SPATIAL_CELL_DEGREES,
        "themes": {name: sorted(keys) for name, keys in sorted(indexes["themes"].items())},
        "spatial_cells": {name: sorted(keys) for name, keys in sorted(indexes["spatial_cells"].items())},
        "digital": {name: sorted(set(keys)) for name, keys in indexes["digital"].items()},
    }
    aggregate_bytes = canonical_bytes(aggregate)
    manifest = {
        "kind": "commonworld.catalog_runtime_manifest",
        "version": "1.0",
        "generation": generation,
        "entry_count": len(records),
        "world_index": {"url": "catalog/runtime/world.v1.json", "sha256": sha256(world_bytes), "bytes": len(world_bytes)},
        "aggregate": {"url": "catalog/runtime/aggregate.v1.json", "sha256": sha256(aggregate_bytes), "bytes": len(aggregate_bytes)},
        "details": {
            "strategy": "content-addressed-shard-descriptors",
            "descriptor_version": DETAIL_DESCRIPTOR_VERSION,
            "url_template": "catalog/runtime/details/{sha256}.v1.json",
            "entry_count": len(records),
            "detail_set_sha256": detail_set_sha256,
            "project_schema_version": 4,
        },
        "shards": {"strategy": "sha256-prefix", "prefix_length": SHARD_PREFIX_LENGTH, "entries": shard_entries},
        "source_catalog_sha256": source_catalog_sha256,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "world.v1.json").write_bytes(world_bytes)
    (OUT / "aggregate.v1.json").write_bytes(aggregate_bytes)
    (OUT / "manifest.v1.json").write_bytes(canonical_bytes(manifest))
    print(f"built catalog runtime generation {generation} with {len(records)} records and {len(current_detail_names)} details")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
