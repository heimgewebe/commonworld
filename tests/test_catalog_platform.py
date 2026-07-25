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
        assert record["detail"] == f"catalog/projects/{record['id']}.json"
        for location in record["presence"]["geographic"]:
            assert location["mode"] != "hidden"
            assert "geometry" in location
    assert len(world_bytes) < 1024 * manifest["entry_count"]
