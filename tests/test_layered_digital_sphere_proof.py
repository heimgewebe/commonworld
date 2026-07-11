import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_layered_digital_sphere_proof import ROOT, load_result, validate_layered_digital_sphere_proof


class LayeredDigitalSphereProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def errors_after(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            research = root / "docs/research"
            research.mkdir(parents=True)
            result = copy.deepcopy(self.result)
            mutate(result)
            (research / "layered-digital-sphere-v1.result.json").write_text(json.dumps(result, indent=2) + "\n")
            shutil.copy2(ROOT / "docs/research/layered-digital-sphere-v1.md", research / "layered-digital-sphere-v1.md")
            for name in ("index.html", "404.html"):
                source = ROOT / name
                if source.is_file(): shutil.copy2(source, root / name)
            return validate_layered_digital_sphere_proof(root)

    def test_proof_validates(self) -> None:
        self.assertEqual([], validate_layered_digital_sphere_proof(ROOT))

    def test_input_is_design_not_acceptance(self) -> None:
        source = self.result["source_input"]
        self.assertEqual(0, source["automatic_performance_runs"])
        self.assertEqual("not_run", source["shared_selection"])
        self.assertEqual("not_run", source["voiceover_or_talkback"])
        self.assertFalse(source["acceptance_claimed"])

    def test_six_layered_paths_replace_point_cloud(self) -> None:
        self.assertEqual(6, self.result["canonical_contract"]["layer_count"])
        self.assertEqual("layered_glyph_paths_around_globe", self.result["canonical_contract"]["primary_geometry"])
        self.assertFalse(self.result["prototype"]["point_cloud_primary"])

    def test_selection_is_same_across_views(self) -> None:
        parity = self.result["selection_parity"]
        self.assertEqual(parity["side_view_selected_id"], parity["linear_view_selected_id"])
        self.assertTrue(parity["automated_identity_and_label_pass"])
        self.assertFalse(parity["focus_panel_present_in_prototype"])
        self.assertFalse(parity["full_selection_parity_pass"])
        self.assertFalse(parity["physical_user_tested"])

    def test_voiceover_remains_open(self) -> None:
        accessibility = self.result["accessibility"]
        self.assertFalse(accessibility["voiceover_physical_tested"])
        self.assertFalse(accessibility["talkback_physical_tested"])
        self.assertTrue(self.result["open_gates"]["voiceover_or_talkback"])

    def test_large_profile_is_not_hidden(self) -> None:
        measurements = self.result["measurements"]
        self.assertLess(measurements["large_profile"]["planet_median_fps"], measurements["small_profile"]["planet_median_fps"])
        self.assertTrue(measurements["large_profile_optimization_required"])

    def test_validator_rejects_acceptance_overclaim(self) -> None:
        errors = self.errors_after(lambda result: result["source_input"].update({"acceptance_claimed": True}))
        self.assertTrue(any("source receipt truth" in error for error in errors))

    def test_validator_rejects_point_cloud_reversion(self) -> None:
        errors = self.errors_after(lambda result: result["prototype"].update({"point_cloud_primary": True}))
        self.assertTrue(any("scope or geometry" in error for error in errors))

    def test_validator_rejects_layer_loss(self) -> None:
        errors = self.errors_after(lambda result: result["canonical_contract"].update({"layer_count": 5}))
        self.assertTrue(any("layer inventory" in error for error in errors))

    def test_validator_rejects_coordinate_invention(self) -> None:
        errors = self.errors_after(lambda result: result["canonical_contract"].update({"invented_coordinates": True}))
        self.assertTrue(any("coordinates" in error for error in errors))

    def test_validator_rejects_broken_shell_ratio(self) -> None:
        errors = self.errors_after(lambda result: result["globe_behavior"].update({"outer_shell_radius_px": 200}))
        self.assertTrue(any("outer shell" in error for error in errors))

    def test_validator_rejects_edge_click_loss(self) -> None:
        errors = self.errors_after(lambda result: result["interaction"].update({"sphere_edge_annulus_opens_side_view": False}))
        self.assertTrue(any("interaction evidence" in error for error in errors))

    def test_validator_rejects_selection_drift(self) -> None:
        errors = self.errors_after(lambda result: result["selection_parity"].update({"linear_view_selected_id": "other"}))
        self.assertTrue(any("parity IDs" in error for error in errors))

    def test_validator_rejects_fake_full_focus_parity(self) -> None:
        errors = self.errors_after(lambda result: result["selection_parity"].update({"full_selection_parity_pass": True}))
        self.assertTrue(any("focus-panel selection parity" in error for error in errors))

    def test_validator_rejects_fake_voiceover(self) -> None:
        errors = self.errors_after(lambda result: result["accessibility"].update({"voiceover_physical_tested": True}))
        self.assertTrue(any("screen-reader physical" in error for error in errors))

    def test_validator_rejects_performance_gate_closure(self) -> None:
        errors = self.errors_after(lambda result: result["measurements"].update({"large_profile_optimization_required": False}))
        self.assertTrue(any("optimization gate" in error for error in errors))

    def test_validator_rejects_public_endpoint(self) -> None:
        errors = self.errors_after(lambda result: result["installed_service"].update({"private_endpoint_published_in_repository": True}))
        self.assertTrue(any("service evidence" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"engine_selected": True}))
        self.assertTrue(any("must not authorize" in error for error in errors))

    def test_validator_rejects_changed_archive_hash(self) -> None:
        errors = self.errors_after(lambda result: result["evidence_artifacts"].update({"archive_sha256": "0" * 64}))
        self.assertTrue(any("artifact hash" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
