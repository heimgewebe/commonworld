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
        self.assertTrue(accessibility["unproven_screen_reader_must_be_reported_as_open_not_pass"])

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

    def test_validator_rejects_unbounded_glyph_count(self) -> None:
        errors = self.errors_after(lambda contract: contract["performance_and_privacy"].update({"bounded_visible_glyph_count_required": False}))
        self.assertTrue(any("performance/privacy invariant" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda contract: contract["decision_boundary"].update({"engine_selected": True}))
        self.assertTrue(any("decision boundary" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
