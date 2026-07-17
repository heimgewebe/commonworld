import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_maplibre_phase2_proof import (
    ROOT,
    load_result,
    validate_maplibre_phase2_proof,
)


class MapLibrePhase2ProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def mutated_root(self, mutate) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        target = root / "docs" / "research"
        target.mkdir(parents=True)
        result = copy.deepcopy(self.result)
        mutate(result)
        (target / "maplibre-phase2-globe-proof.result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(
            ROOT / "docs" / "research" / "maplibre-phase2-globe-proof.md",
            target / "maplibre-phase2-globe-proof.md",
        )
        for public_file in ("index.html", "404.html"):
            source = ROOT / public_file
            if source.is_file():
                shutil.copy2(source, root / public_file)
        return temporary, root

    def errors_after(self, mutate) -> list[str]:
        temporary, root = self.mutated_root(mutate)
        try:
            return validate_maplibre_phase2_proof(root)
        finally:
            temporary.cleanup()

    def test_proof_validates(self) -> None:
        self.assertEqual([], validate_maplibre_phase2_proof(ROOT))

    def test_local_gates_pass_but_physical_acceptance_is_blocked(self) -> None:
        self.assertEqual(
            "local_gates_pass_physical_acceptance_blocked", self.result["status"]
        )
        self.assertFalse(self.result["decision"]["engine_selected"])
        self.assertFalse(
            self.result["decision"]["production_architecture_authorized"]
        )
        self.assertFalse(
            self.result["limitations"]["physical_mobile_devices_tested"]
        )

    def test_geographic_and_digital_channels_share_identity_truth(self) -> None:
        evidence = self.result["gate_results"]["identity_deduplication"]["evidence"]
        self.assertEqual(5000, evidence["unique_identities"])
        self.assertEqual(4000, evidence["geographic_representations"])
        self.assertEqual(2000, evidence["digital_representations"])
        # Historical benchmark field name retained for evidence compatibility.
        self.assertEqual(1000, evidence["hybrid_identities"])
        self.assertEqual(5000, evidence["union_identities"])

    def test_maplibre_native_digital_sphere_is_projection_free(self) -> None:
        gate = self.result["gate_results"]["maplibre_native_abstract_digital_sphere"]
        self.assertEqual("pass", gate["status"])
        self.assertEqual(
            "custom_gl_clip_space_ephemeral_vectors_not_map_projection_or_catalog_coordinates",
            gate["boundary"],
        )

    def test_overlay_has_no_geographic_or_persisted_coordinates(self) -> None:
        evidence = self.result["gate_results"]["maplibre_native_abstract_digital_sphere"][
            "evidence"
        ]
        self.assertFalse(evidence["usesMapProjection"])
        self.assertFalse(evidence["usesGeographicCoordinates"])
        self.assertFalse(evidence["placementPersistedToCatalog"])
        self.assertTrue(evidence["sharesIdentityIds"])

    def test_vector_tiles_and_semantic_layers_are_proven(self) -> None:
        gates = self.result["gate_results"]
        self.assertEqual(
            "coverage-partial-hatch",
            gates["coverage_partial_broken_hatch"]["evidence"]["pattern"],
        )
        self.assertEqual(
            "coverage-unassessed-dots",
            gates["coverage_unassessed_dot_grid"]["evidence"]["pattern"],
        )
        self.assertGreater(
            gates["approximate_location_boundary_and_halo"]["evidence"][
                "rendered_features"
            ],
            0,
        )
        self.assertEqual(
            [1, 2, 3, 4, 5, 6],
            gates["realistic_vector_tile_path"]["evidence"]["zooms"],
        )

    def test_state_accessibility_idle_and_reduced_motion_are_proven(self) -> None:
        gates = self.result["gate_results"]
        restoration = gates["deep_link_state_restoration"]["evidence"]
        self.assertEqual(restoration["before"], restoration["after"])
        self.assertEqual(
            {"mapRenderDelta": 0, "overlayRenderDelta": 0},
            gates["idle_render_pause"]["evidence"],
        )
        self.assertEqual(
            0, gates["reduced_motion_state_equivalence"]["evidence"]["duration"]
        )
        self.assertTrue(
            gates["accessibility_tree_structure"]["evidence"]["hasLastIdentity"]
        )

    def test_validator_rejects_premature_engine_selection(self) -> None:
        errors = self.errors_after(
            lambda result: result["decision"].update({"engine_selected": True})
        )
        self.assertTrue(any("must not select" in error for error in errors))

    def test_validator_rejects_production_architecture_authorization(self) -> None:
        errors = self.errors_after(
            lambda result: result["decision"].update(
                {"production_architecture_authorized": True}
            )
        )
        self.assertTrue(any("must not authorize" in error for error in errors))

    def test_validator_rejects_fake_physical_mobile_claim(self) -> None:
        errors = self.errors_after(
            lambda result: result["limitations"].update(
                {"physical_mobile_devices_tested": True}
            )
        )
        self.assertTrue(any("limitations" in error for error in errors))

    def test_validator_rejects_digital_coordinate_use(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["maplibre_native_abstract_digital_sphere"]["evidence"][
                "usesGeographicCoordinates"
            ] = True

        errors = self.errors_after(mutate)
        self.assertTrue(any("native digital sphere" in error for error in errors))

    def test_validator_rejects_identity_duplication(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["identity_deduplication"]["evidence"][
                "union_identities"
            ] = 6000

        errors = self.errors_after(mutate)
        self.assertTrue(any("deduplicate" in error for error in errors))

    def test_validator_rejects_state_restoration_drift(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["deep_link_state_restoration"]["evidence"][
                "after"
            ]["z"] = 9

        errors = self.errors_after(mutate)
        self.assertTrue(any("restored exactly" in error for error in errors))

    def test_validator_rejects_missing_coverage_pattern(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["coverage_partial_broken_hatch"]["evidence"][
                "pattern"
            ] = "solid"

        errors = self.errors_after(mutate)
        self.assertTrue(any("hatch evidence" in error for error in errors))

    def test_validator_rejects_missing_vector_tile_path(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["realistic_vector_tile_path"]["status"] = "blocked"

        errors = self.errors_after(mutate)
        self.assertTrue(any("gate status mismatch" in error for error in errors))

    def test_validator_rejects_changed_evidence_hash(self) -> None:
        def mutate(result: dict) -> None:
            result["evidence_artifacts"]["archive_sha256"] = "0" * 64

        errors = self.errors_after(mutate)
        self.assertTrue(any("evidence hash changed" in error for error in errors))

    def test_validator_rejects_changed_version(self) -> None:
        def mutate(result: dict) -> None:
            result["versions"]["maplibre_gl_js"] = "next"

        errors = self.errors_after(mutate)
        self.assertTrue(any("versions must remain" in error for error in errors))

    def test_validator_rejects_screen_reader_overclaim(self) -> None:
        def mutate(result: dict) -> None:
            result["gate_results"]["accessibility_tree_structure"][
                "real_screen_reader_session"
            ] = "pass"

        errors = self.errors_after(mutate)
        self.assertTrue(any("real screen-reader proof" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
