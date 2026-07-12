import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_digital_sphere import ROOT, load_contract, validate_digital_sphere


class DigitalSphereContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def errors_after(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "contracts/commonworld/digital-sphere.contract.json"
            path.parent.mkdir(parents=True)
            contract = copy.deepcopy(self.contract)
            mutate(contract)
            path.write_text(json.dumps(contract, indent=2) + "\n")
            return validate_digital_sphere(root)

    def test_contract_validates(self) -> None:
        self.assertEqual([], validate_digital_sphere(ROOT))

    def test_layers_are_ordered_and_derived(self) -> None:
        model = self.contract["layer_model"]
        self.assertEqual(model["order"], [item["id"] for item in model["layers"]])
        self.assertTrue(model["layer_count_is_presentation_configuration_not_catalog_truth"])

    def test_primary_representation_is_not_point_cloud(self) -> None:
        stream = self.contract["stream_model"]
        self.assertEqual("layered_glyph_paths_around_globe", stream["primary_geometry"])
        self.assertTrue(stream["isolated_point_cloud_as_primary_representation_forbidden"])

    def test_name_and_binary_glyphs_have_bounded_meaning(self) -> None:
        stream = self.contract["stream_model"]
        self.assertEqual(
            ["short_common_name_fragment", "binary_fragment_derived_from_stable_identity"],
            stream["glyph_cycle"],
        )
        self.assertEqual(
            "deterministic_visual_encoding_not_project_payload_or_quality_score",
            stream["binary_fragment_semantics"],
        )

    def test_center_and_zoom_fade_keep_globe_readable(self) -> None:
        globe = self.contract["globe_mode"]
        self.assertEqual(0.0, globe["center_fade"]["minimum_opacity_at_view_center"])
        self.assertEqual(1.0, globe["center_fade"]["maximum_opacity_near_outer_rim"])
        self.assertEqual(2.6, globe["zoom_fade"]["local_hidden_from_zoom"])

    def test_edge_click_opens_side_layer_view(self) -> None:
        interaction = self.contract["interaction"]
        self.assertEqual("annulus_around_visible_globe", interaction["sphere_edge_hit_target"]["shape"])
        self.assertEqual("transition_to_side_layer_view", interaction["open_action"])
        self.assertTrue(self.contract["side_layer_view"]["layers_stacked"])

    def test_selection_parity_is_plain_and_identity_bound(self) -> None:
        parity = self.contract["selection_parity"]
        self.assertIn("dieselbe CommonProject-ID", parity["definition_de"])
        self.assertIn("derselbe Name", parity["plain_language_test_de"])
        self.assertTrue(parity["same_id_across_globe_sphere_side_view_search_and_linear"])

    def test_voiceover_remains_unproven(self) -> None:
        accessibility = self.contract["accessibility"]
        self.assertFalse(accessibility["voiceover_physical_test_currently_proven"])
        self.assertTrue(accessibility["unproven_screen_reader_must_never_be_reported_as_pass"])
        self.assertFalse(accessibility["physical_screen_reader_test_required_for_non_public_prototype_acceptance"])
        self.assertTrue(accessibility["physical_screen_reader_test_waived_by_product_owner"])
        self.assertFalse(accessibility["screen_reader_product_support_claimed"])

    def test_real_surface_contract_binds_references_without_catalog_publication(self) -> None:
        real_surface = self.contract["real_surface_v1"]
        self.assertEqual("tests/cases/digital-sphere.reference-projects.json", real_surface["reference_set_path"])
        self.assertFalse(real_surface["reference_projects_are_public_catalog"])
        self.assertEqual("no_digital_layer", real_surface["layer_derivation"]["missing_digital_presence_result"])
        self.assertEqual("mixed_other", real_surface["layer_derivation"]["tie_or_unmapped_result"])

    def test_real_surface_focus_and_camera_are_source_derived(self) -> None:
        real_surface = self.contract["real_surface_v1"]
        self.assertTrue(real_surface["focus_panel"]["single_shared_panel"])
        self.assertEqual("same_commonproject_v3_record", real_surface["focus_panel"]["source"])
        self.assertEqual("maplibre.easeTo", real_surface["side_camera"]["animated_command"])
        self.assertEqual("maplibre.jumpTo", real_surface["side_camera"]["reduced_motion_command"])
        self.assertEqual(0, real_surface["side_camera"]["reduced_motion_duration_ms"])
        self.assertEqual(
            "renderer_selection_decision_against_public_seed_catalog",
            self.contract["decision_boundary"]["next_proof"],
        )

    def test_validator_rejects_catalog_layer_field(self) -> None:
        errors = self.errors_after(lambda contract: contract["catalog_boundary"].update({"manual_catalog_layer_field_forbidden": False}))
        self.assertTrue(any("catalog boundary" in error for error in errors))

    def test_validator_rejects_invented_coordinates(self) -> None:
        errors = self.errors_after(lambda contract: contract["catalog_boundary"].update({"invented_geographic_coordinates_forbidden": False}))
        self.assertTrue(any("catalog boundary" in error for error in errors))

    def test_validator_rejects_point_cloud_primary(self) -> None:
        errors = self.errors_after(lambda contract: contract["stream_model"].update({"primary_geometry": "point_cloud"}))
        self.assertTrue(any("layered glyph paths" in error for error in errors))

    def test_validator_rejects_binary_quality_claim(self) -> None:
        errors = self.errors_after(lambda contract: contract["stream_model"].update({"binary_fragment_semantics": "quality_score"}))
        self.assertTrue(any("payload or quality" in error for error in errors))

    def test_validator_rejects_missing_center_fade(self) -> None:
        errors = self.errors_after(lambda contract: contract["globe_mode"]["center_fade"].update({"enabled": False}))
        self.assertTrue(any("center-fade" in error for error in errors))

    def test_validator_rejects_non_monotonic_zoom_fade(self) -> None:
        errors = self.errors_after(lambda contract: contract["globe_mode"]["zoom_fade"].update({"fade_until_zoom": 1.5}))
        self.assertTrue(any("zoom-fade" in error or "zoom fade" in error for error in errors))

    def test_validator_rejects_blocking_globe_center(self) -> None:
        errors = self.errors_after(lambda contract: contract["interaction"]["sphere_edge_hit_target"].update({"must_not_block_globe_center_interaction": False}))
        self.assertTrue(any("hit-target" in error for error in errors))

    def test_validator_rejects_separate_digital_app(self) -> None:
        errors = self.errors_after(lambda contract: contract["side_layer_view"].update({"same_surface_not_separate_application": False}))
        self.assertTrue(any("side-view invariant" in error for error in errors))

    def test_validator_rejects_selection_drift(self) -> None:
        errors = self.errors_after(lambda contract: contract["selection_parity"].update({"view_change_must_preserve_selection": False}))
        self.assertTrue(any("selection parity invariant" in error for error in errors))

    def test_validator_rejects_fake_voiceover_proof(self) -> None:
        errors = self.errors_after(lambda contract: contract["accessibility"].update({"voiceover_physical_test_currently_proven": True}))
        self.assertTrue(any("VoiceOver physical proof" in error for error in errors))

    def test_validator_rejects_required_screenreader_for_prototype(self) -> None:
        errors = self.errors_after(lambda contract: contract["accessibility"].update({"physical_screen_reader_test_required_for_non_public_prototype_acceptance": True}))
        self.assertTrue(any("optional for non-public prototype" in error for error in errors))

    def test_validator_rejects_screenreader_support_claim(self) -> None:
        errors = self.errors_after(lambda contract: contract["accessibility"].update({"screen_reader_product_support_claimed": True}))
        self.assertTrue(any("product support" in error for error in errors))

    def test_validator_rejects_broad_screenreader_waiver(self) -> None:
        errors = self.errors_after(lambda contract: contract["accessibility"].update({"physical_screen_reader_waiver_scope": "all_products"}))
        self.assertTrue(any("waiver scope" in error for error in errors))

    def test_validator_rejects_unbounded_glyph_count(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"bounded_visible_glyph_count_required": False}))
        self.assertTrue(any("performance/privacy invariant" in error for error in errors))

    def test_validator_rejects_repeated_unchanged_geometry(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"unchanged_glyph_geometry_must_not_be_rewritten": False}))
        self.assertTrue(any("performance/privacy invariant" in error for error in errors))

    def test_validator_rejects_uncoalesced_state_writes(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"navigation_state_writes_must_be_coalesced": False}))
        self.assertTrue(any("performance/privacy invariant" in error for error in errors))

    def test_validator_rejects_idle_overlay_rendering(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"settled_idle_overlay_render_delta_max": 1}))
        self.assertTrue(any("idle overlay-render bound" in error for error in errors))

    def test_validator_rejects_unbound_benchmark(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"benchmark_requires_browser_frame_alignment_and_map_render_confirmation": False}))
        self.assertTrue(any("performance/privacy invariant" in error for error in errors))

    def test_validator_rejects_real_surface_catalog_publication(self) -> None:
        errors = self.errors_after(lambda contract: contract["real_surface_v1"].update({"reference_projects_are_public_catalog": True}))
        self.assertTrue(any("public catalog" in error for error in errors))

    def test_validator_rejects_css_only_side_camera(self) -> None:
        errors = self.errors_after(lambda contract: contract["real_surface_v1"]["side_camera"].update({"css_only_shift_forbidden": False}))
        self.assertTrue(any("side-camera invariant" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda contract: contract["decision_boundary"].update({"engine_selected": True}))
        self.assertTrue(any("decision boundary" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
