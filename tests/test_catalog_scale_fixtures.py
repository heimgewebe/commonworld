import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "catalog_scale_fixtures",
    ROOT / "scripts" / "catalog_scale_fixtures.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CatalogScaleFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = MODULE.representative_records(240, ROOT)
        cls.overlay = MODULE.representative_english_overlay(cls.records, ROOT)
        cls.runtime = MODULE.build_runtime_fixture(cls.records, ROOT)

    def test_fixture_reconstruction_is_deterministic_and_schema_realistic(self):
        second_records = MODULE.representative_records(240, ROOT)
        second_overlay = MODULE.representative_english_overlay(second_records, ROOT)
        self.assertEqual(self.records, second_records)
        self.assertEqual(self.overlay, second_overlay)
        self.assertEqual(
            MODULE.fixture_digest(self.records, self.overlay),
            MODULE.fixture_digest(second_records, second_overlay),
        )
        coverage = MODULE.fixture_coverage(self.records, self.overlay)
        self.assertEqual(coverage["location_modes"], ["approximate", "exact", "hidden"])
        self.assertGreater(coverage["presence_classes"]["digital_only"], 0)
        self.assertGreater(coverage["presence_classes"]["geographic_only"], 0)
        self.assertGreater(coverage["presence_classes"]["hybrid"], 0)
        self.assertGreater(coverage["presence_classes"]["contains_hidden_location"], 0)
        self.assertGreater(coverage["relation_count"], 0)
        self.assertEqual(coverage["english_overlay_project_count"], len(self.records))
        self.assertEqual(coverage["released_locale_overlays"], ["de", "en"])

    def test_seed_project_path_cannot_escape_catalog_projects(self):
        with self.assertRaisesRegex(ValueError, "direct catalog/projects JSON file"):
            MODULE.seed_project_path(ROOT, "../catalog.json")
        with self.assertRaisesRegex(ValueError, "direct catalog/projects JSON file"):
            MODULE.seed_project_path(ROOT, "/tmp/project.json")

    def test_incomplete_canonical_english_overlay_fails_closed(self):
        source = copy.deepcopy(MODULE.load_english_overlay(ROOT))
        source["projects"].pop(next(iter(source["projects"])))
        original = MODULE.load_english_overlay
        MODULE.load_english_overlay = lambda root=ROOT: source
        try:
            with self.assertRaisesRegex(ValueError, "English overlay identities"):
                MODULE.representative_english_overlay(self.records, ROOT)
        finally:
            MODULE.load_english_overlay = original

    def test_fixture_count_below_the_canonical_seed_inventory_fails_closed(self):
        seed_count = len(MODULE.load_seed_records(ROOT))
        with self.assertRaisesRegex(ValueError, "fixture count must be at least the canonical seed count"):
            MODULE.representative_records(seed_count - 1, ROOT)

    def test_compact_stress_coverage_is_projected_to_the_requested_tier(self):
        coverage = MODULE.compact_fixture_coverage(100_000, ROOT)
        self.assertEqual(coverage["english_overlay_project_count"], 0)
        self.assertGreaterEqual(coverage["provenance_source_count"], 100_000)
        self.assertEqual(
            sum(coverage["handoff_states"].values()),
            100_000,
        )
        self.assertFalse(coverage["stress_projection"]["details_materialized"])
        self.assertFalse(coverage["stress_projection"]["locale_overlays_materialized"])

    def test_relations_stay_inside_the_fixture_and_never_self_reference(self):
        known_ids = {record["id"] for record in self.records}
        for record in self.records:
            for relation in record.get("relations", []):
                self.assertIn(relation["target_id"], known_ids)
                self.assertNotEqual(relation["target_id"], record["id"])

    def test_runtime_fixture_binds_every_compact_record_to_content_addressed_detail(self):
        MODULE.validate_runtime_fixture(self.runtime, self.records)
        self.assertEqual(self.runtime["manifest"]["entry_count"], len(self.records))
        self.assertEqual(
            sum(entry["entry_count"] for entry in self.runtime["manifest"]["shards"]["entries"]),
            len(self.records),
        )
        for compact in self.runtime["compact_records"]:
            payload = self.runtime["detail_payloads"][compact["id"]]
            descriptor = compact["detail"]
            self.assertEqual(descriptor["bytes"], len(payload))
            self.assertEqual(descriptor["sha256"], MODULE.sha256(payload))
            self.assertEqual(json.loads(payload)["id"], compact["id"])

    def test_three_hex_repartition_preserves_records_and_reduces_maximum_shard_membership(self):
        migrated = MODULE.repartition_runtime_fixture(self.runtime, prefix_length=3)
        self.assertEqual(migrated["world_bytes"], self.runtime["world_bytes"])
        self.assertEqual(migrated["manifest"]["shards"]["prefix_length"], 3)
        current_max = max(len(shard["records"]) for shard in self.runtime["shard_objects"].values())
        migrated_max = max(len(shard["records"]) for shard in migrated["shard_objects"].values())
        self.assertLess(migrated_max, current_max)
        self.assertEqual(
            sorted(record["id"] for record in migrated["compact_records"]),
            sorted(record["id"] for record in self.runtime["compact_records"]),
        )

    def test_invalid_public_location_fails_closed(self):
        mutated = copy.deepcopy(self.records)
        record = next(
            item
            for item in mutated
            if any(location.get("mode") == "exact" for location in item["presence"]["geographic"])
        )
        location = next(location for location in record["presence"]["geographic"] if location.get("mode") == "exact")
        location.pop("geometry", None)
        with self.assertRaisesRegex(ValueError, "fixture project .* invalid"):
            MODULE.validate_fixture_records(mutated, ROOT)

    def test_unknown_relation_target_fails_closed(self):
        mutated = copy.deepcopy(self.records)
        record = next(item for item in mutated if item.get("relations"))
        record["relations"][0]["target_id"] = "unknown-fixture-target"
        with self.assertRaisesRegex(ValueError, "fixture relation target is not present"):
            MODULE.validate_fixture_records(mutated, ROOT)

    def test_locale_identity_drift_fails_closed(self):
        mutated = copy.deepcopy(self.overlay)
        mutated["projects"].pop(next(iter(mutated["projects"])))
        with self.assertRaisesRegex(ValueError, "locale identities"):
            MODULE.validate_fixture_locale_overlay(mutated, self.records)

    def test_detail_hash_drift_fails_closed(self):
        mutated = copy.deepcopy(self.runtime)
        identifier = mutated["compact_records"][0]["id"]
        mutated["detail_payloads"][identifier] += b" "
        with self.assertRaisesRegex(ValueError, "detail descriptor mismatch"):
            MODULE.validate_runtime_fixture(mutated, self.records)


if __name__ == "__main__":
    unittest.main()
