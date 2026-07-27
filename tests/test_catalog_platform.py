import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_runtime() -> dict:
    subprocess.run(["python3", "scripts/build_catalog_runtime.py"], cwd=ROOT, check=True)
    return json.loads((ROOT / "catalog/runtime/manifest.v1.json").read_text(encoding="utf-8"))


def test_runtime_projection_is_deterministic_compact_and_generation_bound():
    manifest = build_runtime()
    first_hashes = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "catalog/runtime").rglob("*.json"))
    }
    manifest_again = build_runtime()
    second_hashes = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "catalog/runtime").rglob("*.json"))
    }
    assert manifest_again == manifest
    assert second_hashes == first_hashes

    world_path = ROOT / "catalog/runtime/world.v1.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world_bytes = world_path.read_bytes()
    assert manifest["entry_count"] == len(world["records"])
    assert manifest["world_index"]["sha256"] == hashlib.sha256(world_bytes).hexdigest()
    assert manifest["world_index"]["bytes"] == len(world_bytes)
    assert manifest["entry_count"] == json.loads((ROOT / "catalog/catalog.json").read_text())["entry_count"]
    assert manifest["details"] == {
        "strategy": "content-addressed-shard-descriptors",
        "descriptor_version": "1.0",
        "url_template": "catalog/runtime/details/{sha256}.v1.json",
        "entry_count": manifest["entry_count"],
        "detail_set_sha256": manifest["details"]["detail_set_sha256"],
        "project_schema_version": 4,
    }
    forbidden = {"summary", "provenance", "links", "curation", "handoff"}
    seen_detail_urls = set()
    for record in world["records"]:
        assert forbidden.isdisjoint(record)
        detail = record["detail"]
        assert detail["version"] == "1.0"
        assert detail["identity"] == record["id"]
        assert detail["generation"] == manifest["generation"]
        assert detail["url"] == f"catalog/runtime/details/{detail['sha256']}.v1.json"
        assert detail["url"] not in seen_detail_urls
        seen_detail_urls.add(detail["url"])
        detail_path = ROOT / detail["url"]
        payload = detail_path.read_bytes()
        canonical = json.loads(payload)
        assert canonical["schema_version"] == 4
        assert canonical["id"] == record["id"]
        assert hashlib.sha256(payload).hexdigest() == detail["sha256"]
        assert len(payload) == detail["bytes"]
        for location in record["presence"]["geographic"]:
            assert location["mode"] != "hidden"
            assert "geometry" in location
    assert len(seen_detail_urls) == manifest["details"]["entry_count"]
    assert len(world_bytes) < 1400 * manifest["entry_count"]


def test_shards_are_complete_manifest_bound_and_carry_current_detail_descriptors():
    manifest = build_runtime()
    seen = []
    for entry in manifest["shards"]["entries"]:
        path = ROOT / entry["url"]
        payload = path.read_bytes()
        shard = json.loads(payload)
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
        assert len(payload) == entry["bytes"]
        assert len(shard["records"]) == entry["entry_count"]
        assert shard["key"] == entry["key"]
        for record in shard["records"]:
            assert record["detail"]["identity"] == record["id"]
            assert record["detail"]["generation"] == manifest["generation"]
            seen.append(record["id"])
    world = json.loads((ROOT / "catalog/runtime/world.v1.json").read_text(encoding="utf-8"))
    assert sorted(seen) == sorted(record["id"] for record in world["records"])


def test_scaling_evidence_rejects_100k_full_start_index_and_bounds_demand_shards():
    evidence = json.loads((ROOT / "docs/evidence/catalog-platform-scaling-v1.json").read_text(encoding="utf-8"))
    measurements = {item["entry_count"]: item for item in evidence["measurements"]}
    assert measurements[100_000]["world_index"]["gzip_bytes"] > 1_000_000
    assert measurements[100_000]["shards"]["gzip_max_bytes"] < 32_768
    assert evidence["decision"]["single_world_index_for_100k"] == "rejected"
    assert evidence["decision"]["runtime_path"] == "small aggregate manifest plus demand-loaded shards and details"


def test_aggregate_indexes_only_manifest_shards():
    manifest = build_runtime()
    aggregate_path = ROOT / manifest["aggregate"]["url"]
    payload = aggregate_path.read_bytes()
    aggregate = json.loads(payload)
    shard_keys = {entry["key"] for entry in manifest["shards"]["entries"]}
    assert hashlib.sha256(payload).hexdigest() == manifest["aggregate"]["sha256"]
    assert len(payload) == manifest["aggregate"]["bytes"]
    assert aggregate["spatial_cell_degrees"] == 10
    indexed = set()
    for mapping in (aggregate["themes"], aggregate["spatial_cells"], aggregate["digital"]):
        for keys in mapping.values():
            indexed.update(keys)
    assert indexed <= shard_keys
    assert aggregate["digital"]["available"] or aggregate["digital"]["unavailable"]
