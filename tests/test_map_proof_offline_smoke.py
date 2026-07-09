import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.smoke_map_proof_offline import expected_markers, smoke_report, validate_offline_map_smoke
from scripts.validate_contracts import ROOT


class MapProofOfflineSmokeTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for directory_name in ("contracts", "examples", "proofs"):
            shutil.copytree(ROOT / directory_name, tmp_root / directory_name)
        return tmp_root

    def test_offline_smoke_validates_current_map_proof(self) -> None:
        self.assertEqual([], validate_offline_map_smoke(ROOT))

    def test_offline_smoke_reports_exact_and_approximate_markers(self) -> None:
        report = smoke_report(ROOT)
        markers = {marker.project_id: marker for marker in report.renderable_markers}
        self.assertEqual("offline-stubbed", report.network_mode)
        self.assertIn("maplibre-gl", report.external_dependencies_stubbed)
        self.assertIn("carto-raster-tiles", report.external_dependencies_stubbed)
        self.assertFalse(markers["solidarity-kitchen-fixture"].has_approximate_halo)
        self.assertTrue(markers["neighborhood-repair-circle-fixture"].has_approximate_halo)
        self.assertIn("openstreetmap", report.skipped_project_ids)

    def test_missing_marker_creation_fails_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_valid_root(tmp_dir)
            js_path = root / "proofs/map/map.js"
            js_path.write_text(
                js_path.read_text(encoding="utf-8").replace(
                    "new maplibre.Marker({ element: createMapMarkerElement(project) })",
                    "new maplibre.Marker()",
                ),
                encoding="utf-8",
            )
            errors = validate_offline_map_smoke(root)
        self.assertIn(
            "map proof JS missing token: new maplibre.Marker({ element: createMapMarkerElement(project) })",
            errors,
        )

    def test_expected_markers_are_deterministically_ordered(self) -> None:
        ids = [marker.project_id for marker in expected_markers(ROOT)]
        self.assertEqual(sorted(ids), ids)


if __name__ == "__main__":
    unittest.main()
