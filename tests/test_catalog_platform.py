import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_projection_is_deterministic_and_compact():
    subprocess.run(["python3", "scripts/build_catalog_runtime.py"], cwd=ROOT, check=True)
    manifest_path = ROOT / "catalog/runtime/manifest.v1.json"
    world_path = ROOT / "catalog/runtime/world.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world_bytes = world_path.read_bytes()
    assert manifest["entry_count"] == len(world["records"])
    assert manifest["world_index"]["sha256"] == hashlib.sha256(world_bytes).hexdigest()
    assert manifest["world_index"]["bytes"] == len(world_bytes)
    assert manifest["entry_count"] == json.loads((ROOT / "catalog/catalog.json").read_text())["entry_count"]
    forbidden = {"summary", "provenance", "links", "curation", "handoff"}
    for record in world["records"]:
        assert forbidden.isdisjoint(record)
        assert isinstance(record["detail"], dict)
        assert record["detail"]["identity"] == record["id"]
        assert record["detail"]["version"] == "1.0"
        assert record["detail"]["generation"] == manifest["generation"]
        for location in record["presence"]["geographic"]:
            assert location["mode"] != "hidden"
            assert "geometry" in location
    assert len(world_bytes) < 1024 * manifest["entry_count"]


def test_shards_are_complete_and_manifest_bound():
    subprocess.run(["python3", "scripts/build_catalog_runtime.py"], cwd=ROOT, check=True)
    manifest = json.loads((ROOT / "catalog/runtime/manifest.v1.json").read_text(encoding="utf-8"))
    seen = []
    for entry in manifest["shards"]["entries"]:
        path = ROOT / entry["url"]
        payload = path.read_bytes()
        shard = json.loads(payload)
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
        assert len(payload) == entry["bytes"]
        assert len(shard["records"]) == entry["entry_count"]
        assert shard["key"] == entry["key"]
        seen.extend(record["id"] for record in shard["records"])
    world = json.loads((ROOT / "catalog/runtime/world.v1.json").read_text(encoding="utf-8"))
    assert sorted(seen) == sorted(record["id"] for record in world["records"])


def test_scaling_evidence_rejects_100k_full_start_index():
    evidence = json.loads((ROOT / "docs/evidence/catalog-platform-scaling-v1.json").read_text(encoding="utf-8"))
    measurements = {item["entry_count"]: item for item in evidence["measurements"]}
    assert measurements[100_000]["world_index"]["gzip_bytes"] > 1_000_000
    assert measurements[100_000]["shards"]["gzip_max_bytes"] < 16_384
    assert evidence["decision"]["single_world_index_for_100k"] == "rejected"


def test_aggregate_indexes_only_manifest_shards():
    subprocess.run(["python3", "scripts/build_catalog_runtime.py"], cwd=ROOT, check=True)
    manifest = json.loads((ROOT / "catalog/runtime/manifest.v1.json").read_text(encoding="utf-8"))
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


def test_details_are_content_addressed_and_generation_bound():
    subprocess.run(["python3", "scripts/build_catalog_runtime.py"], cwd=ROOT, check=True)
    manifest = json.loads((ROOT / "catalog/runtime/manifest.v1.json").read_text(encoding="utf-8"))
    details = manifest["details"]
    assert details["strategy"] == "content-addressed-shard-descriptors"
    assert details["descriptor_version"] == "1.0"
    assert details["url_template"] == "catalog/runtime/details/{sha256}.v1.json"
    assert details["project_schema_version"] == 4
    assert details["entry_count"] == manifest["entry_count"]
    world = json.loads((ROOT / "catalog/runtime/world.v1.json").read_text(encoding="utf-8"))
    detail_urls = {record["detail"]["url"] for record in world["records"]}
    detail_sha256s = {record["detail"]["sha256"] for record in world["records"]}
    detail_dir = ROOT / "catalog/runtime/details"
    detail_files = {f.name for f in detail_dir.glob("*.v1.json")}
    for url in detail_urls:
        filename = url.split("/")[-1]
        assert filename in detail_files, f"declared detail file missing: {filename}"
    for filename in detail_files:
        path = detail_dir / filename
        payload = path.read_bytes()
        computed = hashlib.sha256(payload).hexdigest()
        assert computed in detail_sha256s, f"orphaned detail file: {filename}"
    for record in world["records"]:
        descriptor = record["detail"]
        assert descriptor["url"] == f"catalog/runtime/details/{descriptor['sha256']}.v1.json"
        detail_path = ROOT / descriptor["url"]
        assert detail_path.read_bytes()[:1] == b"{"  # canonical JSON
        assert descriptor["bytes"] == len(detail_path.read_bytes())
