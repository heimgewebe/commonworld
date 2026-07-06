import json
import unittest

from scripts.validate_contracts import ROOT
from scripts.validate_map_proof import proof_dir


class MapSourceConfigTests(unittest.TestCase):
    def test_map_source_config_declares_proof_mode(self) -> None:
        map_source = json.loads((proof_dir(ROOT) / "map-source.json").read_text(encoding="utf-8"))
        self.assertEqual(1, map_source["schema_version"])
        self.assertEqual("proof", map_source["mode"])
        self.assertIn("script_url", map_source["library"])
        self.assertIn("css_url", map_source["library"])
        self.assertIn("style", map_source["basemap"])

    def test_provider_details_are_centralized_in_config(self) -> None:
        html = (proof_dir(ROOT) / "index.html").read_text(encoding="utf-8")
        js = (proof_dir(ROOT) / "map.js").read_text(encoding="utf-8")
        map_source = (proof_dir(ROOT) / "map-source.json").read_text(encoding="utf-8")
        for fragment in ("maplibre-gl@", "carto-dark-matter"):
            self.assertNotIn(fragment, html)
            self.assertNotIn(fragment, js)
        self.assertIn("maplibre-gl.js", map_source)
        self.assertIn("carto-dark-matter", map_source)


if __name__ == "__main__":
    unittest.main()
