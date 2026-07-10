import json
import tempfile
import unittest
from pathlib import Path

from scripts.smoke_map_proof_browser import prepare_tree, receipt_from_result, validate_result
from scripts.validate_contracts import ROOT


GOOD_RESULT = {
    "markerCount": 2,
    "loadState": "Map ready. 2 location-safe nodes rendered. 1 non-map project skipped.",
    "openElapsedMs": 32.0,
    "openSnapshot": {
        "hidden": False,
        "opacity": "1",
        "transform": "none",
        "transitionDuration": "0s",
        "willChange": "auto",
        "inViewport": True,
    },
    "closed": True,
    "reopened": True,
}


class MapProofBrowserSmokeTests(unittest.TestCase):
    def test_valid_result_has_no_errors(self) -> None:
        self.assertEqual([], validate_result(GOOD_RESULT))

    def test_inherited_opacity_and_motion_fail(self) -> None:
        result = json.loads(json.dumps(GOOD_RESULT))
        result["openSnapshot"]["opacity"] = "0"
        result["openSnapshot"]["transitionDuration"] = "0.18s, 0.26s"
        errors = validate_result(result)
        self.assertIn("map detail panel opacity must be 1, got 0", errors)
        self.assertTrue(any("must not inherit proof transitions" in error for error in errors))

    def test_receipt_from_valid_result(self) -> None:
        receipt = receipt_from_result("Chromium test", GOOD_RESULT)
        self.assertEqual("commonworld.map-proof.browser-interaction-smoke.v1", receipt.smoke_id)
        self.assertEqual("Chromium test", receipt.browser_version)
        self.assertEqual(2, receipt.marker_count)
        self.assertTrue(receipt.panel_closed)
        self.assertTrue(receipt.panel_reopened)

    def test_prepare_tree_uses_local_maplibre_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            destination = Path(tmp_dir) / "tree"
            prepare_tree(ROOT, destination)
            source = json.loads(
                (destination / "proofs" / "map" / "map-source.json").read_text(encoding="utf-8")
            )
            self.assertEqual("/test-assets/dist/maplibre-gl.js", source["library"]["script_url"])
            self.assertEqual("/test-assets/dist/maplibre-gl.css", source["library"]["css_url"])
            self.assertTrue((destination / "test-assets" / "dist" / "maplibre-gl.js").is_file())


if __name__ == "__main__":
    unittest.main()
