import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_map_proof import classify_project, load_projects, proof_dir, validate_map_proof


class MapProofTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for directory_name in ("contracts", "examples", "proofs"):
            shutil.copytree(ROOT / directory_name, tmp_root / directory_name)
        return tmp_root

    def test_static_map_proof_validates(self) -> None:
        self.assertEqual([], validate_map_proof(ROOT))

    def test_hidden_project_is_not_map_renderable(self) -> None:
        projects = {project["id"]: project for project in load_projects(ROOT)}
        projection = classify_project(projects["openstreetmap"])
        self.assertFalse(projection.renderable)
        self.assertEqual("hidden", projection.mode)

    def test_approximate_fixture_is_renderable_with_halo(self) -> None:
        projects = {project["id"]: project for project in load_projects(ROOT)}
        projection = classify_project(projects["neighborhood-repair-circle-fixture"])
        self.assertTrue(projection.renderable)
        self.assertTrue(projection.requires_halo)

    def test_exact_seed_fixture_is_renderable_without_halo(self) -> None:
        projects = {project["id"]: project for project in load_projects(ROOT)}
        projection = classify_project(projects["solidarity-kitchen-fixture"])
        self.assertTrue(projection.renderable)
        self.assertEqual("exact", projection.mode)
        self.assertFalse(projection.requires_halo)

    def test_map_js_labels_exact_and_approximate_privacy_modes(self) -> None:
        js = (proof_dir(ROOT) / "map.js").read_text(encoding="utf-8")
        css = (proof_dir(ROOT) / "map.css").read_text(encoding="utf-8")
        self.assertIn('project.location.mode === "exact"', js)
        self.assertIn('privacy-badge--${project.location.mode}', js)
        self.assertIn('project.location.mode === "exact" ? "Exact" : "Approximate"', js)
        self.assertIn(".privacy-badge--exact", css)

    def test_missing_hidden_filter_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            js_path = proof_dir(tmp_root) / "map.js"
            js_text = js_path.read_text(encoding="utf-8").replace('project.location?.mode !== "hidden"', "true")
            js_path.write_text(js_text, encoding="utf-8")

            errors = validate_map_proof(tmp_root)

        self.assertIn("map proof JS must include an explicit hidden-location filter", errors)

    def test_missing_approximate_halo_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            css_path = proof_dir(tmp_root) / "map.css"
            css_path.write_text(css_path.read_text(encoding="utf-8").replace(".approximate-halo", ".approximate-ring"), encoding="utf-8")

            errors = validate_map_proof(tmp_root)

        self.assertIn("map proof CSS missing .approximate-halo", errors)

    def test_readme_documents_external_map_dependencies(self) -> None:
        readme = (proof_dir(ROOT) / "README.md").read_text(encoding="utf-8")
        self.assertIn("CDN", readme)
        self.assertIn("tile", readme)


    def test_exact_location_classification_renders_without_halo(self) -> None:
        projection = classify_project(
            {
                "id": "exact-example",
                "location": {
                    "mode": "exact",
                    "coordinates": {"lat": 53.5, "lon": 10.0},
                },
            }
        )
        self.assertTrue(projection.renderable)
        self.assertFalse(projection.requires_halo)

    def test_map_marker_requires_finite_coordinates(self) -> None:
        js = (proof_dir(ROOT) / "map.js").read_text(encoding="utf-8")
        self.assertIn("Number.isFinite(coordinates?.lat)", js)
        self.assertIn("Number.isFinite(coordinates?.lon)", js)

    def test_approximate_halo_is_centered_on_marker(self) -> None:
        css = (proof_dir(ROOT) / "map.css").read_text(encoding="utf-8")
        self.assertIn("top: 50%", css)
        self.assertIn("left: 50%", css)
        self.assertIn("transform: translate(-50%, -50%)", css)


    def test_map_proof_ui_discloses_external_dependencies(self) -> None:
        html = (proof_dir(ROOT) / "index.html").read_text(encoding="utf-8")
        self.assertIn("loads MapLibre from a CDN", html)
        self.assertIn("raster map tiles from CARTO", html)


if __name__ == "__main__":
    unittest.main()
