import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_mixed_node_proof import (
    build_segments,
    load_projects,
    proof_dir,
    validate_proof,
)
from scripts.validate_seed_manifest import expected_seed_paths, seed_manifest_path
from scripts.proof_shared import SHARED_JS_REL


class MixedNodeProofTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for directory_name in ("contracts", "examples", "proofs"):
            shutil.copytree(ROOT / directory_name, tmp_root / directory_name)
        return tmp_root

    def test_static_mixed_node_proof_validates(self) -> None:
        self.assertEqual([], validate_proof(ROOT))

    def test_validate_proof_uses_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertEqual([], validate_proof(self.copy_valid_root(tmp_dir)))

    def test_validate_proof_reports_contract_errors_without_projection_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            project_path = tmp_root / "examples" / "commonworld" / "projects" / "openstreetmap.json"
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["aspects"][0]["weight"] = 0.99
            project_path.write_text(json.dumps(project), encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertTrue(any("aspect weights must sum to 1.0" in error for error in errors))


    def test_seed_manifest_lives_in_shared_examples_area(self) -> None:
        self.assertEqual(
            ROOT / "examples" / "commonworld" / "seed-projects.json",
            seed_manifest_path(ROOT),
        )
        self.assertFalse((proof_dir(ROOT) / "seed-projects.json").exists())

    def test_missing_shared_seed_manifest_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            seed_manifest_path(tmp_root).unlink()

            errors = validate_proof(tmp_root)

        self.assertIn("missing shared seed manifest: examples/commonworld/seed-projects.json", errors)

    def test_seed_manifest_schema_version_is_current(self) -> None:
        manifest = json.loads(seed_manifest_path(ROOT).read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["schema_version"])

    def test_seed_manifest_exactly_lists_seed_files(self) -> None:
        manifest = json.loads(seed_manifest_path(ROOT).read_text(encoding="utf-8"))
        self.assertEqual(expected_seed_paths(ROOT), manifest["project_paths"])

    def test_seed_manifest_references_existing_seed_files(self) -> None:
        manifest = json.loads(seed_manifest_path(ROOT).read_text(encoding="utf-8"))
        for project_path in manifest["project_paths"]:
            with self.subTest(project_path=project_path):
                self.assertTrue((seed_manifest_path(ROOT).parent / project_path).resolve().is_file())

    def test_segment_order_is_deterministic(self) -> None:
        projects = {project["id"]: project for project in load_projects(ROOT)}

        self.assertEqual(
            ["open-data", "community-mapping", "public-infrastructure"],
            [segment.aspect_id for segment in build_segments(projects["openstreetmap"])],
        )
        self.assertEqual(
            ["repair", "education", "mutual-aid"],
            [segment.aspect_id for segment in build_segments(projects["neighborhood-repair-circle-fixture"])],
        )

    def test_segment_spans_use_contract_weights_without_overlap(self) -> None:
        for project in load_projects(ROOT):
            with self.subTest(project=project["id"]):
                segments = build_segments(project)
                aspects_by_id = {aspect["id"]: aspect for aspect in project["aspects"]}
                self.assertAlmostEqual(0.0, segments[0].start, places=3)
                self.assertAlmostEqual(1.0, segments[-1].end, places=3)

                previous_end = 0.0
                for segment in segments:
                    self.assertGreaterEqual(segment.start, previous_end - 0.001)
                    self.assertAlmostEqual(previous_end, segment.start, places=3)
                    self.assertAlmostEqual(
                        aspects_by_id[segment.aspect_id]["weight"],
                        segment.span,
                        places=3,
                    )
                    previous_end = segment.end

    def test_aspect_cards_have_non_color_semantics(self) -> None:
        for project in load_projects(ROOT):
            for segment in build_segments(project):
                with self.subTest(project=project["id"], aspect=segment.aspect_id):
                    self.assertTrue(segment.label)
                    self.assertTrue(segment.icon_token.startswith("icon."))
                    self.assertGreaterEqual(segment.evidence_count, 1)
                    self.assertGreaterEqual(segment.confidence, 0)
                    self.assertLessEqual(segment.confidence, 1)

    def test_detail_surface_and_js_keep_a11y_anchors(self) -> None:
        directory = proof_dir(ROOT)
        html = (directory / "index.html").read_text(encoding="utf-8")
        js = (directory / "mixed-node.js").read_text(encoding="utf-8")

        for token in ('id="project-detail"', "data-detail-surface", 'aria-live="polite"', 'tabindex="-1"'):
            with self.subTest(html_token=token):
                self.assertIn(token, html)

        for token in ("aria-controls", "project-detail", "aria-expanded", "closeDetail", "Escape", "activeNodeButton.focus"):
            with self.subTest(js_token=token):
                self.assertIn(token, js)

    def test_fixture_projects_are_visibly_marked(self) -> None:
        projects = load_projects(ROOT)
        self.assertTrue(any(project["curation"]["state"] == "fixture" for project in projects))

        # The fixture label is produced by the shared curationBadgeLabel helper; the
        # proof supplies the badge rendering surface (.node-badge) and the wiring.
        shared_js = (ROOT / SHARED_JS_REL).read_text(encoding="utf-8")
        js = (proof_dir(ROOT) / "mixed-node.js").read_text(encoding="utf-8")
        css = (proof_dir(ROOT) / "mixed-node.css").read_text(encoding="utf-8")
        self.assertIn("Synthetic fixture", shared_js)
        self.assertIn("curationBadgeLabel", js)
        self.assertIn(".node-badge", css)

    def test_fixture_marker_is_required_when_fixture_seed_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            shared_path = tmp_root / SHARED_JS_REL
            shared_path.write_text(shared_path.read_text(encoding="utf-8").replace("Synthetic fixture", "Synthetic sample"), encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("shared curationStateLabel must render the Synthetic fixture label", errors)

    def test_token_coverage_requires_css_custom_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            css_path = proof_dir(tmp_root) / "mixed-node.css"
            css_text = css_path.read_text(encoding="utf-8").replace("--aspect-data:", "--aspectdatum:")
            css_path.write_text(css_text, encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("proof CSS variable missing --aspect-data", errors)

    def test_invalid_seed_manifest_json_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            seed_manifest_path(tmp_root).write_text("{not json", encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertTrue(any(error.startswith("seed-projects.json is not valid JSON") for error in errors))

    def test_token_coverage_requires_js_icon_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            shared_path = tmp_root / SHARED_JS_REL
            shared_text = shared_path.read_text(encoding="utf-8").replace("  \"icon.map\": \"⌖\",\n", "")
            shared_path.write_text(shared_text, encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("shared aspect module ICON_GLYPHS missing icon.map", errors)

    def test_token_coverage_requires_exact_color_mapping_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            shared_path = tmp_root / SHARED_JS_REL
            shared_text = shared_path.read_text(encoding="utf-8").replace("\"aspect.data\": \"var(--aspect-data)\"", "\"aspect.data\": \"var(--aspect-repair)\"")
            shared_path.write_text(shared_text, encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("shared aspect module ASPECT_COLORS missing aspect.data", errors)

    def test_detail_surface_motion_contract_is_visible(self) -> None:
        directory = proof_dir(ROOT)
        html = (directory / "index.html").read_text(encoding="utf-8")
        css = (directory / "mixed-node.css").read_text(encoding="utf-8")
        js = (directory / "mixed-node.js").read_text(encoding="utf-8")

        for token in ('data-state="closed"', 'aria-hidden="true"', "data-sheet-grip"):
            with self.subTest(html_token=token):
                self.assertIn(token, html)

        for token in ("--sheet-drag-y", 'data-open="true"', 'data-state="dragging"', "translate3d", "touch-action: none"):
            with self.subTest(css_token=token):
                self.assertIn(token, css)

        for token in (
            "requestAnimationFrame",
            "transitionend",
            'event.propertyName !== "transform"',
            'event.target.closest("[data-close-detail]")',
            "pointerdown",
            "pointermove",
            "setPointerCapture",
            "swipeCloseThreshold",
        ):
            with self.subTest(js_token=token):
                self.assertIn(token, js)

    def test_motion_contract_requires_swipe_handler_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            js_path = proof_dir(tmp_root) / "mixed-node.js"
            js_path.write_text(js_path.read_text(encoding="utf-8").replace("pointermove", "pointerdrag"), encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("proof JS missing motion behavior token pointermove", errors)

    def test_motion_contract_requires_sheet_transform_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            css_path = proof_dir(tmp_root) / "mixed-node.css"
            css_path.write_text(css_path.read_text(encoding="utf-8").replace("translate3d", "translate"), encoding="utf-8")

            errors = validate_proof(tmp_root)

        self.assertIn("proof CSS missing motion behavior token translate3d", errors)


if __name__ == "__main__":
    unittest.main()
