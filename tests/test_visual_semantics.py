import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_visual_semantics import (
    FAMILY_IDS,
    ROOT,
    contrast_ratio,
    coverage_texture,
    density_band,
    family_composition,
    identity_family_style,
    load_cases,
    load_contract,
    privacy_decision,
    uncertainty_style,
    weighted_density_thresholds,
    validate_visual_semantics,
)


class VisualSemanticsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.cases = load_cases()

    def test_contract_and_real_cases_validate(self) -> None:
        self.assertEqual([], validate_visual_semantics(ROOT))

    def mutated_root(self, mutate_contract=None, mutate_cases=None) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        contract_dir = root / "contracts" / "commonworld"
        case_dir = root / "tests" / "cases"
        contract_dir.mkdir(parents=True)
        case_dir.mkdir(parents=True)
        for name in ("project.schema.json", "aggregation-zoom.contract.json"):
            shutil.copy2(ROOT / "contracts" / "commonworld" / name, contract_dir / name)
        contract = copy.deepcopy(self.contract)
        cases = copy.deepcopy(self.cases)
        if mutate_contract:
            mutate_contract(contract)
        if mutate_cases:
            mutate_cases(cases)
        (contract_dir / "visual-semantics.contract.json").write_text(
            json.dumps(contract, indent=2) + "\n", encoding="utf-8"
        )
        (case_dir / "visual-semantics.real-cases.json").write_text(
            json.dumps(cases, indent=2) + "\n", encoding="utf-8"
        )
        return temporary, root

    def test_public_geographic_profile_matches_filter_vocabulary_and_keeps_family_research_inactive(self) -> None:
        profiles = self.contract["classification_profiles"]
        self.assertEqual("exclusive_commons_type_v1", profiles["active_public_geographic_profile"])
        active = next(profile for profile in profiles["profiles"] if profile["id"] == "exclusive_commons_type_v1")
        self.assertEqual(
            ["knowledge", "software", "culture", "food-seeds", "water", "energy", "housing-land", "health-care", "tools-repair", "community-network", "other"],
            [value["id"] for value in active["values"]],
        )
        self.assertEqual(["WD", "SI", "KM", "SE", "WB", "EN", "BW", "PG", "WR", "GN", "AN"], [value["code"] for value in active["values"]])
        self.assertTrue(active["no_hue_blending"])
        self.assertTrue(active["text_label_required"])
        self.assertFalse(active["non_color_code_required"])
        self.assertEqual("forbidden", active["map_abbreviation_rendering"])
        self.assertTrue(active["accessible_text_equivalent_required"])
        self.assertEqual("preserve_discrete_hues_as_proportional_stripes_without_blending", active["country_composition_rule"])
        self.assertTrue(active["coverage_texture_reserved"])
        family = next(profile for profile in profiles["profiles"] if profile["id"] == "commons_family_v1")
        self.assertFalse(family["active_in_geographic_impressions_v1"])

    def test_family_composition_uses_dominance_without_hue_blending(self) -> None:
        self.assertEqual("knowledge_data", family_composition({"knowledge_data": 7, "making_infrastructure": 3}, self.contract))
        self.assertEqual("knowledge_data", family_composition({"knowledge_data": 6, "making_infrastructure": 4}, self.contract))
        self.assertEqual("mixed_cross_domain", family_composition({"knowledge_data": 5, "making_infrastructure": 5}, self.contract))
        self.assertTrue(self.contract["family_taxonomy"]["composition"]["no_hue_blending"])

    def test_family_composition_rejects_invalid_distributions(self) -> None:
        with self.assertRaises(ValueError):
            family_composition({}, self.contract)
        with self.assertRaises(ValueError):
            family_composition({"knowledge_data": 0}, self.contract)
        with self.assertRaises(ValueError):
            family_composition({"unknown": 1}, self.contract)
        with self.assertRaises(ValueError):
            family_composition({"knowledge_data": 1.5}, self.contract)

    def test_identity_family_assignment_has_no_false_precision(self) -> None:
        self.assertEqual(
            "knowledge_data",
            identity_family_style({"primary_family": "knowledge_data", "secondary_families": ["making_infrastructure"]}, self.contract),
        )
        self.assertEqual(
            "mixed_cross_domain",
            identity_family_style({"primary_family": None, "mixed_families": ["knowledge_data", "making_infrastructure"]}, self.contract),
        )
        with self.assertRaises(ValueError):
            identity_family_style({"primary_family": None, "mixed_families": ["knowledge_data"]}, self.contract)
        self.assertTrue(self.contract["family_taxonomy"]["numeric_identity_family_weights_forbidden"])

    def test_identity_family_assignment_rejects_duplicates(self) -> None:
        with self.assertRaises(ValueError):
            identity_family_style(
                {"primary_family": "knowledge_data", "secondary_families": ["making_infrastructure", "making_infrastructure"]},
                self.contract,
            )
        with self.assertRaises(ValueError):
            identity_family_style(
                {"primary_family": None, "mixed_families": ["knowledge_data", "knowledge_data"]},
                self.contract,
            )

    def test_all_families_have_distinct_hue_and_glyph_roles(self) -> None:
        families = self.contract["family_taxonomy"]["families"]
        self.assertEqual(list(FAMILY_IDS), [family["id"] for family in families])
        self.assertEqual(len(FAMILY_IDS), len({family["hue_role"] for family in families}))
        self.assertEqual(len(FAMILY_IDS), len({family["non_color"]["glyph_role"] for family in families}))
        for family in families:
            self.assertTrue(family["non_color"]["text_label_required"])
            self.assertNotIn("pattern", family["non_color"])

    def test_palette_seeds_meet_reference_surface_contrast(self) -> None:
        taxonomy = self.contract["family_taxonomy"]
        rules = taxonomy["palette_rules"]
        for family in taxonomy["families"]:
            with self.subTest(family=family["id"]):
                tokens = family["palette_tokens"]
                self.assertGreaterEqual(contrast_ratio(tokens["fill_seed_light_surface"], rules["reference_light_surface"]), 3.0)
                self.assertGreaterEqual(contrast_ratio(tokens["fill_seed_dark_surface"], rules["reference_dark_surface"]), 3.0)
        composition = taxonomy["composition"]
        self.assertGreaterEqual(contrast_ratio(composition["mixed_fill_seed_light_surface"], rules["reference_light_surface"]), 3.0)
        self.assertGreaterEqual(contrast_ratio(composition["mixed_fill_seed_dark_surface"], rules["reference_dark_surface"]), 3.0)

    def test_density_legend_keeps_zero_and_small_samples_honest(self) -> None:
        thresholds = (0.25, 1.0, 4.0)
        self.assertEqual("supported_zero", density_band(0, thresholds, 100, self.contract))
        self.assertEqual("raw_numeric_value_without_comparative_band", density_band(1.2, thresholds, 19, self.contract))
        self.assertEqual("positive_low", density_band(0.2, thresholds, 20, self.contract))
        self.assertEqual("positive_middle", density_band(0.8, thresholds, 20, self.contract))
        self.assertEqual("positive_high", density_band(2.0, thresholds, 20, self.contract))
        self.assertEqual("positive_exceptional", density_band(5.0, thresholds, 20, self.contract))

    def test_weighted_density_thresholds_are_executable_and_deterministic(self) -> None:
        samples = [(float(value), 10000.0) for value in range(1, 21)]
        self.assertEqual((5.0, 15.0, 19.0), weighted_density_thresholds(samples, self.contract))
        self.assertIsNone(weighted_density_thresholds(samples[:19], self.contract))
        weighted = [(1.0, 90000.0)] + [(10.0 + value, 1000.0) for value in range(19)]
        self.assertEqual((1.0, 1.0, 23.0), weighted_density_thresholds(weighted, self.contract))

    def test_weighted_density_thresholds_reject_invalid_samples(self) -> None:
        samples = [(float(value), 10000.0) for value in range(1, 20)] + [(0.0, 10000.0)]
        with self.assertRaises(ValueError):
            weighted_density_thresholds(samples, self.contract)
        samples[-1] = (20.0, 0.0)
        with self.assertRaises(ValueError):
            weighted_density_thresholds(samples, self.contract)

    def test_density_thresholds_use_one_non_overlapping_reference_population(self) -> None:
        calibration = self.contract["density_legend"]["calibration_population"]
        self.assertEqual("non_overlapping_equal_area_reference_cells", calibration["grid"])
        self.assertEqual(10000, calibration["nominal_cell_area_km2"])
        self.assertTrue(calibration["threshold_population_id_required"])
        self.assertTrue(calibration["nested_display_buckets_excluded_from_threshold_sample"])
        self.assertEqual(
            "smallest_value_whose_cumulative_assessed_surface_reaches_or_exceeds_quantile_times_total_weight",
            self.contract["density_legend"]["threshold_rules"]["weighted_quantile_rule"],
        )

    def test_density_legend_rejects_negative_or_unordered_inputs(self) -> None:
        with self.assertRaises(ValueError):
            density_band(-1, (1, 2, 3), 20, self.contract)
        with self.assertRaises(ValueError):
            density_band(1, (2, 1, 3), 20, self.contract)

    def test_coverage_uses_interior_texture_not_family_pattern(self) -> None:
        self.assertEqual("solid_or_none", coverage_texture("assessed", self.contract))
        self.assertEqual("sparse_diagonal_broken_hatch", coverage_texture("partial", self.contract))
        self.assertEqual("open_dot_grid", coverage_texture("unassessed", self.contract))
        self.assertTrue(self.contract["channel_separation"]["family_pattern_forbidden_to_reserve_texture_for_coverage"])

    def test_uncertainty_uses_boundary_and_halo(self) -> None:
        self.assertEqual(("solid_boundary", "none"), uncertainty_style("exact", self.contract))
        self.assertEqual(("solid_extent_boundary", "none"), uncertainty_style("public_extent", self.contract))
        self.assertEqual(("dashed_boundary", "graduated_uncertainty_halo"), uncertainty_style("approximate", self.contract))
        self.assertEqual(("none", "none"), uncertainty_style("hidden", self.contract))

    def test_privacy_release_is_k5_coarsen_first_and_filter_safe(self) -> None:
        base = {
            "mode": "approximate",
            "bucket_effective_diameter_m": 3000,
            "maximum_uncertainty_meters_min": 500,
            "filter_complement_count": 0,
            "complete_reference_cohort_selected": True,
        }
        self.assertEqual("coarsen", privacy_decision({**base, "identity_count": 4, "parent_available": True}, self.contract))
        self.assertEqual("withhold_numeric_value", privacy_decision({**base, "identity_count": 4, "parent_available": False}, self.contract))
        self.assertEqual("release_aggregate", privacy_decision({**base, "identity_count": 5, "parent_available": False}, self.contract))
        self.assertEqual(
            "withhold_selected_and_complement",
            privacy_decision({**base, "identity_count": 9, "filter_complement_count": 3, "complete_reference_cohort_selected": False, "parent_available": False}, self.contract),
        )

    def test_approximate_bucket_must_not_be_finer_than_uncertainty(self) -> None:
        scenario = {
            "mode": "approximate",
            "identity_count": 8,
            "filter_complement_count": 0,
            "complete_reference_cohort_selected": True,
            "bucket_effective_diameter_m": 999,
            "maximum_uncertainty_meters_min": 500,
            "parent_available": True,
        }
        self.assertEqual("coarsen", privacy_decision(scenario, self.contract))
        scenario["bucket_effective_diameter_m"] = 1000
        self.assertEqual("release_aggregate", privacy_decision(scenario, self.contract))

    def test_exact_public_and_hidden_locations_follow_different_release_paths(self) -> None:
        self.assertEqual("release_exact_public", privacy_decision({"mode": "exact", "identity_count": 1}, self.contract))
        self.assertEqual("release_public_extent", privacy_decision({"mode": "public_extent", "identity_count": 1}, self.contract))
        self.assertEqual("nonspatial_only", privacy_decision({"mode": "hidden", "identity_count": 20}, self.contract))

    def test_real_cases_cover_every_family_and_required_archetype(self) -> None:
        covered_families = set()
        for case in self.cases["cases"]:
            assignment = case["family_assignment"]
            if assignment.get("primary_family"):
                covered_families.add(assignment["primary_family"])
            covered_families.update(assignment.get("secondary_families", []))
            covered_families.update(assignment.get("mixed_families", []))
        covered_archetypes = {archetype for case in self.cases["cases"] for archetype in case["archetypes"]}
        self.assertEqual(set(FAMILY_IDS), covered_families)
        self.assertLessEqual(set(self.contract["case_matrix"]["required_archetypes"]), covered_archetypes)

    def test_source_review_is_dated_official_and_non_flaky(self) -> None:
        review = self.contract["case_matrix"]["source_review"]
        self.assertTrue(review["refresh_before_public_catalog_use"])
        self.assertFalse(review["network_fetch_in_ci"])
        self.assertTrue(all(source["source_kind"].startswith("official_") for source in self.cases["sources"].values()))
        self.assertEqual("2026-07-11", self.cases["checked_at"])

    def test_named_cases_are_research_inputs_not_catalog_entries(self) -> None:
        visibility = self.cases["visibility"]
        self.assertTrue(visibility["repository_test_only_not_product_content"])
        self.assertTrue(visibility["public_repository_visibility_acknowledged"])
        self.assertTrue(visibility["not_catalog_truth"])
        self.assertTrue(visibility["not_publication_verification"])

    def test_speculative_mesh_relation_is_excluded(self) -> None:
        case = next(case for case in self.cases["cases"] if case["id"] == "nyc-mesh-evidenced-versus-speculative-links")
        self.assertEqual("exclude", case["expected_relation_policy"]["speculative_connections"])
        self.assertIn("speculative_connection_as_faden", case["forbidden"])

    def test_privacy_stress_case_has_below_and_at_or_above_k_paths(self) -> None:
        case = next(case for case in self.cases["cases"] if case["id"] == "privacy-sensitive-approximate-cluster")
        decisions = {scenario["id"]: privacy_decision(scenario, self.contract) for scenario in case["privacy_scenarios"]}
        self.assertEqual("coarsen", decisions["child-below-k"])
        self.assertEqual("release_aggregate", decisions["parent-meets-k"])
        self.assertEqual("coarsen", decisions["bucket-too-fine"])
        self.assertEqual("withhold_selected_and_complement", decisions["filter-complement-below-k"])

    def test_validator_rejects_case_hue_drift(self) -> None:
        def mutate(cases: dict) -> None:
            cases["cases"][0]["expected_channels"]["hue"] = "care_provision"

        temporary, root = self.mutated_root(mutate_cases=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("expected hue" in error for error in errors))

    def test_validator_rejects_false_precision_family_weights_in_cases(self) -> None:
        def mutate(cases: dict) -> None:
            cases["cases"][0]["family_weights"] = {"knowledge_data": 1.0}

        temporary, root = self.mutated_root(mutate_cases=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("false-precision" in error for error in errors))

    def test_validator_rejects_color_only_family_semantics(self) -> None:
        def mutate(contract: dict) -> None:
            contract["family_taxonomy"]["families"][0]["non_color"]["text_label_required"] = False

        temporary, root = self.mutated_root(mutate_contract=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("text label" in error for error in errors))

    def test_validator_rejects_family_pattern_collision_with_coverage(self) -> None:
        def mutate(contract: dict) -> None:
            contract["family_taxonomy"]["families"][0]["non_color"]["pattern"] = "diagonal"

        temporary, root = self.mutated_root(mutate_contract=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("coverage texture channel" in error for error in errors))

    def test_validator_rejects_low_contrast_palette_seed(self) -> None:
        def mutate(contract: dict) -> None:
            contract["family_taxonomy"]["families"][0]["palette_tokens"]["fill_seed_light_surface"] = "#F8FAFC"

        temporary, root = self.mutated_root(mutate_contract=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("fill seeds must meet" in error for error in errors))

    def test_validator_rejects_weaker_privacy_threshold(self) -> None:
        temporary, root = self.mutated_root(
            mutate_contract=lambda contract: contract["privacy_release"].update({"k_anonymity_min": 4})
        )
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("k=5" in error for error in errors))

    def test_validator_rejects_exact_coordinates_in_research_cases(self) -> None:
        def mutate(cases: dict) -> None:
            cases["cases"][0]["coordinates"] = [0, 0]

        temporary, root = self.mutated_root(mutate_cases=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("coordinate fields" in error for error in errors))

    def test_validator_rejects_future_source_review_date(self) -> None:
        def mutate(cases: dict) -> None:
            cases["checked_at"] = "2999-01-01"

        temporary, root = self.mutated_root(mutate_cases=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("must not be in the future" in error for error in errors))

    def test_validator_rejects_missing_source_reference(self) -> None:
        def mutate(cases: dict) -> None:
            cases["cases"][0]["source_refs"] = ["missing-source"]

        temporary, root = self.mutated_root(mutate_cases=mutate)
        try:
            errors = validate_visual_semantics(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("resolve every source reference" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
