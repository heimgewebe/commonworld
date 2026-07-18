import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import base_record
from scripts.validate_semantic_zoom import (
    ROOT,
    coverage_zero_meaning,
    density_record,
    identity_channels,
    load_contract,
    public_record,
    public_spatial_representation,
    theme_counts,
    unique_identity_ids,
    validate_semantic_zoom,
)


class SemanticZoomContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_contract_validates(self) -> None:
        self.assertEqual([], validate_semantic_zoom(ROOT))

    def mutated_root(self, mutation) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        target = root / "contracts" / "commonworld"
        target.mkdir(parents=True)
        shutil.copy2(ROOT / "contracts" / "commonworld" / "project.schema.json", target / "project.schema.json")
        contract = copy.deepcopy(self.contract)
        mutation(contract)
        (target / "aggregation-zoom.contract.json").write_text(
            json.dumps(contract, indent=2) + "\n",
            encoding="utf-8",
        )
        return temporary, root

    def test_validator_rejects_overlapping_public_and_excluded_states(self) -> None:
        temporary, root = self.mutated_root(
            lambda contract: contract["publication_eligibility"]["excluded_public_curation_states"].append("listed")
        )
        try:
            errors = validate_semantic_zoom(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("disjoint" in error for error in errors))

    def test_validator_rejects_density_for_partial_coverage(self) -> None:
        temporary, root = self.mutated_root(
            lambda contract: contract["intensity"].update(
                {"density_allowed_for_coverage_states": ["assessed", "partial"]}
            )
        )
        try:
            errors = validate_semantic_zoom(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("restricted to fully assessed" in error for error in errors))

    def test_validator_rejects_digital_coordinates(self) -> None:
        def mutation(contract: dict) -> None:
            contract["digital_levels"][0]["forbidden"].remove("invented_coordinates")

        temporary, root = self.mutated_root(mutation)
        try:
            errors = validate_semantic_zoom(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("must forbid invented coordinates" in error for error in errors))

    def test_output_shapes_bind_every_level_to_transport_neutral_fields(self) -> None:
        shapes = self.contract["output_shapes"]
        self.assertEqual(["assessed"], shapes["density_field"]["allowed_coverage_states"])
        self.assertEqual("CommonProject.id", shapes["identity_cluster"]["member_key"])
        self.assertTrue(shapes["focus_record"]["exactly_one_identity"])
        self.assertTrue(shapes["network_summary"]["member_identity_ids_forbidden"])
        self.assertNotIn("member_identity_ids", shapes["network_summary"]["required"])
        self.assertIn("scope_label", shapes["digital_coverage_summary"]["required"])
        self.assertNotIn("assessed_universe_label", shapes["digital_coverage_summary"]["required"])
        for level in self.contract["levels"] + self.contract["digital_levels"]:
            with self.subTest(level=level["id"]):
                self.assertTrue(level["shape_refs"])
                self.assertLessEqual(set(level["shape_refs"]), set(shapes))

    def test_validator_rejects_missing_required_output_shape(self) -> None:
        temporary, root = self.mutated_root(lambda contract: contract["output_shapes"].pop("focus_record"))
        try:
            errors = validate_semantic_zoom(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("output shapes" in error for error in errors))

    def test_multiple_anchors_never_multiply_identity_inside_bucket(self) -> None:
        record = base_record()
        second_anchor = copy.deepcopy(record["presence"]["geographic"][0])
        second_anchor["id"] = "second-public-workshop"
        second_anchor["geometry"]["coordinates"] = [10.1, 53.6]
        record["presence"]["geographic"].append(second_anchor)
        bucket_members = [record["id"] for _anchor in record["presence"]["geographic"]]
        self.assertEqual((record["id"],), unique_identity_ids(bucket_members))

    def test_identity_can_appear_in_multiple_buckets_but_global_total_is_deduplicated(self) -> None:
        project_id = base_record()["id"]
        bucket_a = unique_identity_ids([project_id])
        bucket_b = unique_identity_ids([project_id])
        self.assertEqual(1, len(bucket_a))
        self.assertEqual(1, len(bucket_b))
        self.assertEqual(1, len(unique_identity_ids(bucket_a + bucket_b)))

    def test_theme_counts_deduplicate_identity_per_theme(self) -> None:
        record = base_record()
        duplicate_projection = copy.deepcopy(record)
        counts = theme_counts([record, duplicate_projection])
        self.assertEqual({"repair": 1, "shared-tools": 1}, counts)

    def test_hidden_geographic_metadata_does_not_create_a_map_channel(self) -> None:
        record = base_record()
        record["kind"] = "digital"
        record["presence"] = {
            "geographic": [
                {
                    "id": "withheld-operator-location",
                    "mode": "hidden",
                    "label": "Operator location withheld",
                    "privacy_note": "The operator location is not published.",
                    "source_ids": ["official-website"],
                }
            ],
            "digital": {
                "available": True,
                "reach": "global",
                "label": "Available worldwide",
                "source_ids": ["official-website"],
            },
        }
        self.assertEqual(("digital",), identity_channels(record))

    def test_dual_presence_is_one_identity_with_two_channels(self) -> None:
        record = base_record()
        record["presence"] = {"digital": {"available": True}, "geographic": [{"mode": "approximate", "id": "1", "geometry": {"type": "Point", "coordinates": [0,0]}, "uncertainty_meters_min": 100}]}; record.pop("kind", None)
        record["presence"]["digital"] = {
            "available": True,
            "reach": "network",
            "label": "Distributed online network",
            "source_ids": ["official-website"],
        }
        self.assertEqual(("geographic", "digital"), identity_channels(record))
        self.assertEqual(1, len(unique_identity_ids([record["id"], record["id"]])))

    def test_stale_and_paused_records_remain_visible_but_do_not_raise_density(self) -> None:
        stale = base_record()
        stale["curation"].update({"state": "stale", "reviewed_by": "Editorial review"})
        paused = base_record()
        paused["curation"].update({"state": "listed", "reviewed_by": "Editorial review"})
        paused["activity"]["status"] = "paused"
        self.assertTrue(public_record(stale, self.contract))
        self.assertFalse(density_record(stale, self.contract))
        self.assertTrue(public_record(paused, self.contract))
        self.assertFalse(density_record(paused, self.contract))

    def test_public_and_density_state_partitions_are_disjoint(self) -> None:
        eligibility = self.contract["publication_eligibility"]
        public_states = set(eligibility["public_curation_states"])
        excluded_states = set(eligibility["excluded_public_curation_states"])
        density_states = set(eligibility["density_curation_states"])
        self.assertFalse(public_states & excluded_states)
        self.assertLessEqual(density_states, public_states)
        self.assertNotIn("stale", density_states)

    def test_zero_density_and_missing_data_have_different_meanings(self) -> None:
        self.assertEqual("supported_low_density", coverage_zero_meaning("assessed", self.contract))
        self.assertEqual("catalog_lower_bound_only", coverage_zero_meaning("partial", self.contract))
        self.assertEqual("unknown_not_zero", coverage_zero_meaning("unassessed", self.contract))

    def test_partial_and_unassessed_coverage_never_claim_normalized_density(self) -> None:
        intensity = self.contract["intensity"]
        self.assertEqual(["assessed"], intensity["density_allowed_for_coverage_states"])
        self.assertEqual("lower_bound_identity_count_without_density", intensity["partial_coverage_output"])
        self.assertEqual("unknown_without_zero_or_density", intensity["unassessed_coverage_output"])

    def test_digital_coverage_has_no_geographic_denominator(self) -> None:
        coverage = self.contract["digital_coverage"]
        self.assertTrue(coverage["no_geographic_area_denominator"])
        self.assertTrue(coverage["must_not_claim_global_completeness_without_defined_universe"])

    def test_hidden_location_has_no_spatial_representation(self) -> None:
        hidden = {
            "mode": "hidden",
            "label": "Location withheld",
            "privacy_note": "The location is withheld for participant safety.",
        }
        self.assertIsNone(public_spatial_representation(hidden, self.contract))

    def test_approximate_location_preserves_minimum_uncertainty(self) -> None:
        approximate = {
            "mode": "approximate",
            "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
            "uncertainty_meters_min": 5000,
        }
        projection = public_spatial_representation(approximate, self.contract)
        self.assertEqual(5000, projection["uncertainty_meters_min"])
        self.assertIn("without_sharpening", projection["rule"])

    def test_privacy_and_relation_invariants_are_fail_closed(self) -> None:
        privacy = self.contract["uncertainty_and_privacy"]
        relations = self.contract["relations"]
        self.assertTrue(privacy["aggregate_must_not_enable_reverse_inference"])
        self.assertTrue(privacy["small_count_suppression_required_when_privacy_would_be_weakened"])
        self.assertTrue(relations["no_inferred_relations"])
        self.assertTrue(relations["hidden_endpoint_must_not_be_relocated_or_revealed"])

    def test_semantic_clusters_end_before_local_identity_view(self) -> None:
        clusters = self.contract["clusters"]
        local = next(level for level in self.contract["levels"] if level["id"] == "local")
        self.assertEqual("local", clusters["semantic_clusters_dissolve_on_entry_to"])
        self.assertIn("semantic_clusters", local["forbidden"])
        self.assertIn("transient_collision_groups", local["outputs"])

    def test_every_digital_level_forbids_invented_coordinates(self) -> None:
        for level in self.contract["digital_levels"]:
            with self.subTest(level=level["id"]):
                self.assertIn("invented_coordinates", level["forbidden"])


if __name__ == "__main__":
    unittest.main()
