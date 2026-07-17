import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import validation_errors
from scripts.validate_digital_sphere_real_surface import (
    FOCUS_ID,
    LAYER_ORDER,
    ROOT,
    VISIBLE_NAME_LIMIT_PER_LAYER,
    build_layer_coverage,
    build_name_presentation,
    camera_transition,
    contains_coordinate_material,
    derive_digital_layer,
    focus_panel,
    focus_panel_hash,
    load_records,
    load_reference_set,
    load_result,
    selection_paths,
    unique_orbit_labels,
    validate_digital_sphere_real_surface,
    visible_records_for_layer,
)


class DigitalSphereRealSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = load_records()
        self.result = load_result()

    def copy_real_surface_core(self, directory: str) -> Path:
        root = Path(directory)
        (root / "docs/research").mkdir(parents=True)
        (root / "tests/cases").mkdir(parents=True)
        (root / "contracts/commonworld").mkdir(parents=True)
        shutil.copy2(
            ROOT / "docs/research/digital-sphere-real-surface-v1.result.json",
            root / "docs/research/digital-sphere-real-surface-v1.result.json",
        )
        shutil.copy2(
            ROOT / "docs/research/digital-sphere-real-surface-v1.md",
            root / "docs/research/digital-sphere-real-surface-v1.md",
        )
        shutil.copy2(
            ROOT / "docs/research/device-acceptance-performance-v4.result.json",
            root / "docs/research/device-acceptance-performance-v4.result.json",
        )
        shutil.copy2(
            ROOT / "tests/cases/digital-sphere.reference-projects.json",
            root / "tests/cases/digital-sphere.reference-projects.json",
        )
        shutil.copy2(
            ROOT / "docs/research/digital-sphere-real-surface-v1.reference-projects.json",
            root / "docs/research/digital-sphere-real-surface-v1.reference-projects.json",
        )
        shutil.copy2(
            ROOT / "contracts/commonworld/digital-sphere.contract.json",
            root / "contracts/commonworld/digital-sphere.contract.json",
        )
        shutil.copy2(
            ROOT / "contracts/commonworld/project.schema.json",
            root / "contracts/commonworld/project.schema.json",
        )
        shutil.copy2(ROOT / "index.html", root / "index.html")
        return root

    def errors_after_result(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_real_surface_core(directory)
            result_path = root / "docs/research/digital-sphere-real-surface-v1.result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            mutate(result)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return validate_digital_sphere_real_surface(root)

    def errors_after_reference_set(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_real_surface_core(directory)
            reference_path = root / "tests/cases/digital-sphere.reference-projects.json"
            reference_set = json.loads(reference_path.read_text(encoding="utf-8"))
            mutate(reference_set)
            reference_path.write_text(json.dumps(reference_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return validate_digital_sphere_real_surface(root)

    def test_real_surface_proof_validates(self) -> None:
        self.assertEqual([], validate_digital_sphere_real_surface(ROOT))

    def test_twelve_references_validate_against_commonproject_v4(self) -> None:
        self.assertEqual(12, len(self.records))
        for record in self.records:
            with self.subTest(record=record["id"]):
                self.assertEqual([], validation_errors(record))

    def test_all_six_layers_are_covered_by_reference_records(self) -> None:
        coverage = build_layer_coverage(self.records)
        self.assertEqual(list(LAYER_ORDER), [item["id"] for item in coverage])
        self.assertTrue(all(item["count"] > 0 for item in coverage))
        self.assertEqual(12, sum(item["count"] for item in coverage))

    def test_unique_topic_score_and_tie_fallback_are_deterministic(self) -> None:
        by_id = {record["id"]: record for record in self.records}
        self.assertEqual("knowledge_data", derive_digital_layer(by_id["wikipedia-reference"]))
        self.assertEqual("software_infrastructure", derive_digital_layer(by_id["debian-reference"]))
        self.assertEqual("mixed_other", derive_digital_layer(by_id["openstreetmap-reference"]))
        self.assertEqual("mixed_other", derive_digital_layer(by_id["meta-wiki-reference"]))

    def test_missing_or_unmapped_digital_presence_rules(self) -> None:
        no_digital = copy.deepcopy(self.records[0])
        no_digital["presence"]["digital"] = {"available": False, "source_ids": ["wikimedia-projects"]}
        self.assertIsNone(derive_digital_layer(no_digital))

        unmapped = copy.deepcopy(self.records[0])
        unmapped["themes"] = ["unmapped-topic"]
        self.assertEqual("mixed_other", derive_digital_layer(unmapped))

    def test_no_geographic_coordinates_are_created_for_digital_references(self) -> None:
        for record in self.records:
            with self.subTest(record=record["id"]):
                self.assertEqual([], record["presence"]["geographic"])
                self.assertFalse(contains_coordinate_material(record["presence"]["geographic"]))

    def test_visible_names_are_bounded_and_keep_accessible_full_text(self) -> None:
        presentation = build_name_presentation(self.records)
        for layer in presentation["visible_by_layer"]:
            self.assertLessEqual(layer["visible_name_count"], VISIBLE_NAME_LIMIT_PER_LAYER)
            for item in layer["visible_names"]:
                self.assertTrue(item["visible_text"])
                self.assertTrue(item["accessible_full_text"])
        self.assertEqual(
            "Meta-Wiki Community Coordination and Documentation",
            presentation["meta_wiki_accessible_full_text"],
        )
        self.assertLessEqual(len(presentation["meta_wiki_visible_text"]), 18)

    def test_different_long_names_never_reuse_the_same_visible_short_text(self) -> None:
        records = [
            {"id": "meta-one", "title": "Meta-Wiki Community Coordination and Documentation"},
            {"id": "meta-two", "title": "Meta-Wiki Community Collaboration and Documentation"},
        ]
        labels = unique_orbit_labels(records)
        self.assertNotEqual(labels["meta-one"]["visible_text"], labels["meta-two"]["visible_text"])
        self.assertEqual(records[0]["title"], labels["meta-one"]["accessible_full_text"])
        self.assertEqual(records[1]["title"], labels["meta-two"]["accessible_full_text"])

    def test_synthetic_load_identities_do_not_displace_reference_names(self) -> None:
        synthetic = []
        for index in range(20):
            record = copy.deepcopy(self.records[0])
            record.update(
                {
                    "id": f"benchmark-{index:04d}",
                    "title": f"Virtual identity {index}",
                    "_source_backed_reference": False,
                }
            )
            synthetic.append(record)
        visible = visible_records_for_layer(self.records + synthetic, "knowledge_data")
        self.assertEqual(["wikipedia-reference", "wikidata-reference"], [record["id"] for record in visible])

    def test_focus_panel_is_derived_from_the_same_identity(self) -> None:
        record = next(item for item in self.records if item["id"] == FOCUS_ID)
        panel = focus_panel(record)
        self.assertEqual(record["title"], panel["full_name"])
        self.assertEqual(record["summary"], panel["summary"])
        self.assertEqual(record["presence"]["digital"], panel["digital_presence"])
        self.assertFalse(panel["has_geographic_presence"])
        self.assertTrue(panel["has_digital_presence"])
        self.assertNotIn("commons_kind", panel)
        self.assertEqual(focus_panel_hash(record), focus_panel_hash(copy.deepcopy(record)))

    def test_selection_paths_share_the_same_focus_panel(self) -> None:
        paths = selection_paths(self.records)
        self.assertEqual({FOCUS_ID}, {path["selected_id"] for path in paths})
        self.assertEqual(1, len({path["focus_panel_hash"] for path in paths}))
        self.assertTrue(all(path["active_focus_count"] == 1 for path in paths))

    def test_validator_rejects_manual_or_unbound_layer_derivation(self) -> None:
        errors = self.errors_after_result(
            lambda result: result["layer_derivation"].update(
                {"source_identity": "manual-layer", "manual_catalog_layer_field": True}
            )
        )
        self.assertTrue(any("source identity" in error for error in errors))
        self.assertTrue(any("manual catalog layer" in error for error in errors))

    def test_side_camera_uses_maplibre_target_and_exact_restore(self) -> None:
        transition = camera_transition(reduced_motion=False)
        self.assertEqual("maplibre.easeTo", transition["maplibre_command"])
        self.assertEqual(260, transition["duration_ms"])
        self.assertNotEqual(transition["source_state"]["bearing"], transition["target_state"]["bearing"])
        self.assertNotEqual(transition["source_state"]["pitch"], transition["target_state"]["pitch"])
        self.assertNotEqual(transition["source_state"]["zoom"], transition["target_state"]["zoom"])
        self.assertNotEqual(transition["source_state"]["padding"], transition["target_state"]["padding"])
        self.assertEqual(transition["source_state"], transition["restored_state_after_close"])
        self.assertTrue(transition["restored_exact"])
        self.assertEqual(transition["source_state"], transition["restored_state_after_browser_back"])
        self.assertTrue(transition["browser_back_restored_exact"])

    def test_reduced_motion_reaches_same_target_in_zero_ms(self) -> None:
        normal = camera_transition(reduced_motion=False)
        reduced = camera_transition(reduced_motion=True)
        self.assertEqual("maplibre.jumpTo", reduced["maplibre_command"])
        self.assertEqual(0, reduced["duration_ms"])
        self.assertEqual(normal["target_state"], reduced["target_state"])
        self.assertEqual(normal["url"], reduced["url"])
        self.assertEqual(normal["selected_id"], reduced["selected_id"])
        self.assertEqual(normal["focus_id"], reduced["focus_id"])

    def test_no_continuous_idle_rendering_and_v4_floor_is_preserved(self) -> None:
        performance = self.result["rendering_performance"]
        self.assertFalse(performance["continuous_idle_rendering"])
        self.assertEqual(0, performance["idle_overlay_render_delta"])
        self.assertLessEqual(performance["idle_map_render_delta"], 2)
        self.assertTrue(performance["v4_software_profile_floor"]["performance_gate_pass"])
        self.assertTrue(performance["new_browser_fps_claimed"])
        proof = performance["private_v6_browser_proof"]
        self.assertEqual("pass", proof["browser_test_status"])
        self.assertEqual(260, proof["camera"]["animated_duration_ms"])
        self.assertEqual(0, proof["camera"]["reduced_motion_duration_ms"])
        self.assertTrue(proof["camera"]["animated_exact_restore"])
        self.assertTrue(proof["camera"]["browser_back_exact_restore"])
        self.assertEqual(50000, proof["virtual_list"]["total_items"])
        self.assertTrue(proof["performance"]["gate_pass"])
        self.assertEqual([], proof["console_errors"])
        self.assertFalse(proof["physical_device_tested"])


    def test_validator_rejects_private_v6_manifest_drift(self) -> None:
        def mutate(result: dict) -> None:
            result["rendering_performance"]["private_v6_browser_proof"]["release_manifest_sha256"] = "0" * 64

        errors = self.errors_after_result(mutate)
        self.assertTrue(any("private v6 browser proof" in error for error in errors))

    def test_public_shell_contains_no_reference_fixture_data(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for record in self.records:
            self.assertNotIn(record["id"], html)
            self.assertNotIn(record["summary"], html)
            self.assertNotIn(record["activity"]["note"], html)
            self.assertNotIn(record["curation"]["notes"], html)

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after_result(lambda result: result["decision"].update({"engine_selected": True}))
        self.assertTrue(any("engine and production architecture" in error for error in errors))

    def test_validator_rejects_selection_drift(self) -> None:
        def mutate(result: dict) -> None:
            result["selection_parity"]["paths"][2]["selected_id"] = "wikidata-reference"

        errors = self.errors_after_result(mutate)
        self.assertTrue(any("selection parity paths" in error for error in errors))

    def test_validator_rejects_reduced_motion_animation(self) -> None:
        def mutate(result: dict) -> None:
            result["side_camera"]["reduced_motion_transition"]["duration_ms"] = 260

        errors = self.errors_after_result(mutate)
        self.assertTrue(any("reduced-motion transition" in error or "0 ms" in error for error in errors))

    def test_validator_rejects_fabricated_digital_coordinates(self) -> None:
        def mutate(reference_set: dict) -> None:
            reference_set["records"][0]["presence"]["geographic"] = [
                {
                    "id": "invented-point",
                    "mode": "exact",
                    "label": "Invented point",
                    "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
                    "source_ids": ["wikimedia-projects"],
                }
            ]

        errors = self.errors_after_reference_set(mutate)
        self.assertTrue(any("must not contain a geographic anchor" in error or "digital" in error for error in errors))

    def test_validator_rejects_reference_publication_overclaim(self) -> None:
        errors = self.errors_after_result(
            lambda result: result["acceptance_boundaries"].update(
                {"source_backed_reference_projects_are_published_catalog": True}
            )
        )
        self.assertTrue(any("publication" in error or "acceptance boundaries" in error for error in errors))

    def test_reference_set_visibility_flags_are_preserved(self) -> None:
        reference_set = load_reference_set()
        self.assertTrue(reference_set["visibility"]["excluded_from_public_shell"])
        self.assertTrue(reference_set["visibility"]["not_catalog_truth"])


if __name__ == "__main__":
    unittest.main()
