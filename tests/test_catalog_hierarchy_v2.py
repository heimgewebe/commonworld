import copy
import gzip
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.build_catalog_runtime import clear_generated_catalog_files
from scripts.catalog_hierarchy_v2 import (
    INDEX_PREFIX_LENGTH,
    LEAF_PREFIX_LENGTH,
    build_hierarchical_runtime_fixture,
    validate_hierarchical_runtime_fixture,
)
from scripts.catalog_scale_fixtures import build_runtime_fixture, representative_records

ROOT = Path(__file__).resolve().parents[1]


class CatalogHierarchyV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = representative_records(240, ROOT)
        cls.v1 = build_runtime_fixture(cls.records, ROOT)
        cls.v2 = build_hierarchical_runtime_fixture(cls.v1)

    def test_direct_build_import_does_not_require_jsonschema(self):
        probe = textwrap.dedent(
            """
            import builtins
            import runpy
            import sys

            original_import = builtins.__import__

            def block_jsonschema(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "jsonschema" or name.startswith("jsonschema."):
                    raise ModuleNotFoundError("jsonschema intentionally unavailable")
                return original_import(name, globals, locals, fromlist, level)

            builtins.__import__ = block_jsonschema
            sys.path.insert(0, "scripts")
            runpy.run_path(
                "scripts/build_catalog_runtime.py",
                run_name="commonworld_build_import_probe",
            )
            """
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", probe],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_hierarchy_is_deterministic_and_preserves_v1_source(self):
        second = build_hierarchical_runtime_fixture(self.v1)
        self.assertEqual(self.v2["manifest_bytes"], second["manifest_bytes"])
        self.assertEqual(self.v2["aggregate_bytes"], second["aggregate_bytes"])
        self.assertEqual(self.v2["shard_index_payloads"], second["shard_index_payloads"])
        self.assertEqual(self.v2["aggregate_segment_payloads"], second["aggregate_segment_payloads"])
        self.assertEqual(self.v1["manifest"]["version"], "1.0")
        self.assertEqual(self.v1["manifest"]["shards"]["prefix_length"], 2)

    def test_root_manifest_is_bounded_and_does_not_embed_leaf_directory(self):
        shards = self.v2["manifest"]["shards"]
        self.assertEqual(shards["index_prefix_length"], INDEX_PREFIX_LENGTH)
        self.assertEqual(shards["leaf_prefix_length"], LEAF_PREFIX_LENGTH)
        self.assertNotIn("entries", shards)
        self.assertLessEqual(len(shards["indexes"]), 16)
        self.assertLess(len(gzip.compress(self.v2["manifest_bytes"], mtime=0)), 32768)
        self.assertLess(len(gzip.compress(self.v2["aggregate_bytes"], mtime=0)), 32768)

    def test_hierarchy_reconciles_all_counts_digests_and_references(self):
        validate_hierarchical_runtime_fixture(self.v2)
        self.assertEqual(
            sum(value["entry_count"] for value in self.v2["shard_index_objects"].values()),
            len(self.records),
        )
        self.assertEqual(
            set(self.v2["shard_payloads"]),
            {entry["key"] for value in self.v2["shard_index_objects"].values() for entry in value["entries"]},
        )

    def test_migration_guard_keeps_v1_as_default_and_cutover_closed(self):
        guard = self.v2["manifest"]["migration_guard"]
        self.assertEqual(guard["default_manifest_version"], "1.0")
        self.assertEqual(guard["default_shard_prefix_length"], 2)
        self.assertEqual(guard["candidate_manifest_version"], "2.0")
        self.assertFalse(guard["cutover_authorized"])
        self.assertEqual(guard["rollback_manifest_url"], "catalog/runtime/manifest.v1.json")
        self.assertIn("physical-device", guard["required_gates"])

    def test_corrupt_shard_index_digest_fails_closed(self):
        mutated = copy.deepcopy(self.v2)
        key = next(iter(mutated["shard_index_payloads"]))
        mutated["shard_index_payloads"][key] += b" "
        with self.assertRaisesRegex(ValueError, "descriptor (byte length|digest) mismatch"):
            validate_hierarchical_runtime_fixture(mutated)

    def test_unknown_aggregate_shard_reference_fails_closed(self):
        mutated = copy.deepcopy(self.v2)
        segment_id = next(iter(mutated["aggregate_segment_objects"]))
        segment = mutated["aggregate_segment_objects"][segment_id]
        first_value = next(iter(segment["index"]))
        segment["index"][first_value] = ["fff"]
        mutated["aggregate_segment_payloads"][segment_id] = b"{}\n"
        descriptor = next(
            item
            for items in mutated["aggregate"]["segments"].values()
            for item in items
            if f"{item['dimension']}:{item['key']}" == segment_id
        )
        descriptor["bytes"] = len(mutated["aggregate_segment_payloads"][segment_id])
        from scripts.catalog_scale_fixtures import sha256
        descriptor["sha256"] = sha256(mutated["aggregate_segment_payloads"][segment_id])
        with self.assertRaisesRegex(ValueError, "unknown shard"):
            validate_hierarchical_runtime_fixture(mutated)

    def test_invalid_prefix_geometry_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "shorter than the leaf prefix"):
            build_hierarchical_runtime_fixture(self.v1, leaf_prefix_length=3, index_prefix_length=3)

    def test_generated_cleanup_preserves_v1_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);shards=root/"shards";indexes=root/"shard-indexes";segments=root/"aggregate-segments"
            shards.mkdir();indexes.mkdir();(segments/"themes").mkdir(parents=True);(segments/"obsolete").mkdir()
            (root/"manifest.v1.json").write_text("v1");(root/"aggregate.v1.json").write_text("aggregate")
            (shards/"aa.v1.json").write_text("old");(shards/"aaa.v1.json").write_text("old");(indexes/"a.v2.json").write_text("old");(segments/"themes"/"co.v2.json").write_text("old");(segments/"obsolete"/"x.v2.json").write_text("old")
            clear_generated_catalog_files(shards,indexes,segments)
            self.assertEqual((root/"manifest.v1.json").read_text(),"v1");self.assertEqual((root/"aggregate.v1.json").read_text(),"aggregate")
            self.assertEqual(list(shards.glob("*.v1.json")),[]);self.assertEqual(list(indexes.glob("*.v2.json")),[]);self.assertEqual(list(segments.rglob("*.v2.json")),[])


if __name__ == "__main__":
    unittest.main()
