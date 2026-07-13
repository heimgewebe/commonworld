import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_renderer_spike import ROOT, load_result, validate_renderer_spike


class RendererSpikeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def mutated_root(self, mutate) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        result_path = root / "docs" / "research" / "renderer-engine-spike.result.json"
        report_path = root / "docs" / "research" / "renderer-engine-spike.md"
        result_path.parent.mkdir(parents=True)
        result = copy.deepcopy(self.result)
        mutate(result)
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(ROOT / "docs" / "research" / "renderer-engine-spike.md", report_path)
        for public_file in ("index.html", "404.html"):
            source = ROOT / public_file
            if source.is_file():
                shutil.copy2(source, root / public_file)
        return temporary, root

    def test_renderer_spike_validates(self) -> None:
        self.assertEqual([], validate_renderer_spike(ROOT))

    def test_maplibre_is_fastest_but_not_selected(self) -> None:
        measurements = self.result["measurements"]
        for profile in ("desktop", "mobile_emulated"):
            maplibre = measurements["maplibre_gl_js"][profile]["fps"]
            others = [measurements[name][profile]["fps"] for name in ("cesium_js", "three_js", "deck_gl")]
            self.assertGreater(maplibre, max(others))
        recommendation = self.result["recommendation"]
        self.assertFalse(recommendation["engine_selected"])
        self.assertEqual("maplibre_gl_js", recommendation["primary_candidate"])

    def test_physical_mobile_and_hardware_gpu_are_not_claimed(self) -> None:
        limitations = self.result["method"]["limitations"]
        self.assertFalse(limitations["physical_mobile_device_tested"])
        self.assertFalse(limitations["hardware_gpu_tested"])
        self.assertTrue(limitations["software_webgl_results_are_relative_not_production_fps"])

    def test_color_only_semantics_are_rejected(self) -> None:
        color = self.result["color_vision_check"]
        self.assertEqual("family_color_alone_is_not_reliable", color["conclusion"])
        self.assertLess(color["deutan_minimum_delta_e"], 5)
        self.assertEqual(
            {"family_glyph", "explicit_text_label", "geometry_or_list_context"},
            set(color["required_non_color_channels"]),
        )

    def test_candidate_dispositions_remain_bounded(self) -> None:
        assessment = self.result["capability_assessment"]
        self.assertEqual("conditional_primary_candidate", assessment["maplibre_gl_js"]["current_disposition"])
        self.assertEqual("specialist_overlay_or_fallback_candidate", assessment["three_js"]["current_disposition"])
        self.assertEqual(
            "reject_for_current_phase_cost_and_workload_mismatch",
            assessment["cesium_js"]["current_disposition"],
        )
        self.assertEqual(
            "reject_as_primary_until_globe_contract_matures",
            assessment["deck_gl"]["current_disposition"],
        )

    def test_validator_rejects_changed_base_binding(self) -> None:
        temporary, root = self.mutated_root(
            lambda result: result.update({"repository_base_commit": "0" * 40})
        )
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("measured base commit" in error for error in errors))

    def test_validator_rejects_changed_evidence_hash(self) -> None:
        def mutate(result: dict) -> None:
            result["evidence_artifacts"]["archive_sha256"] = "0" * 64

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("evidence hash" in error for error in errors))

    def test_validator_rejects_changed_candidate_version(self) -> None:
        def mutate(result: dict) -> None:
            result["method"]["candidate_versions"]["maplibre_gl_js"] = "next"

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("versions must remain exactly bound" in error for error in errors))

    def test_validator_rejects_premature_engine_commitment(self) -> None:
        temporary, root = self.mutated_root(
            lambda result: result["recommendation"].update({"engine_selected": True})
        )
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("must not select" in error for error in errors))

    def test_validator_rejects_missing_physical_mobile_limit(self) -> None:
        temporary, root = self.mutated_root(
            lambda result: result["method"]["limitations"].update({"physical_mobile_device_tested": True})
        )
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("must not claim a physical mobile test" in error for error in errors))

    def test_validator_rejects_maplibre_no_longer_fastest(self) -> None:
        def mutate(result: dict) -> None:
            result["measurements"]["maplibre_gl_js"]["desktop"]["fps"] = 1

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("fastest measured candidate" in error for error in errors))

    def test_validator_rejects_weakened_color_vision_boundary(self) -> None:
        temporary, root = self.mutated_root(
            lambda result: result["color_vision_check"].update(
                {"conclusion": "color_is_sufficient"}
            )
        )
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("color-only" in error for error in errors))

    def test_validator_rejects_missing_commitment_condition(self) -> None:
        def mutate(result: dict) -> None:
            result["recommendation"]["conditions_before_engine_commitment"].pop()

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("conditions are incomplete" in error for error in errors))

    def test_validator_rejects_mature_deck_gl_claim(self) -> None:
        def mutate(result: dict) -> None:
            result["capability_assessment"]["deck_gl"][
                "globe_and_geographic_semantic_zoom"
            ] = "production_ready"

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("GlobeView limitations" in error for error in errors))

    def test_validator_rejects_fatal_candidate_error(self) -> None:
        def mutate(result: dict) -> None:
            result["measurements"]["cesium_js"]["fatal_runtime_errors"] = 1

        temporary, root = self.mutated_root(mutate)
        try:
            errors = validate_renderer_spike(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("fatal runtime errors" in error for error in errors))

    def test_raw_spike_harness_is_not_in_repository(self) -> None:
        evidence = self.result["evidence_artifacts"]
        self.assertFalse(evidence["repository_contains_raw_harness"])
        self.assertFalse(evidence["repository_contains_screenshots"])
        for name in ("screenshots", "spikes"):
            self.assertFalse((ROOT / name).exists())
        self.assertTrue((ROOT / "package.json").is_file())
        self.assertTrue((ROOT / "package-lock.json").is_file())


if __name__ == "__main__":
    unittest.main()
