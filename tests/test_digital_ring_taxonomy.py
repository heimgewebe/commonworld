import json
import unittest
from pathlib import Path

from scripts.digital_taxonomy import derive_project_path, load_taxonomy, normalize_path
from scripts.validate_digital_ring_taxonomy import ROOT, validate_digital_ring_taxonomy


class DigitalRingTaxonomyTest(unittest.TestCase):
    def setUp(self):
        self.taxonomy = load_taxonomy(ROOT)

    def test_current_taxonomy_contract_validates(self):
        self.assertEqual(validate_digital_ring_taxonomy(ROOT), [])

    def test_derivation_cases_are_semantic_not_order_based(self):
        base = {"id": "case", "presence": {"digital": {"available": True}}}
        self.assertEqual(
            derive_project_path({**base, "themes": ["free-software"]}, self.taxonomy)["path_key"],
            "sphere/software_tools_production/free_software",
        )
        self.assertEqual(
            derive_project_path({**base, "themes": ["education", "knowledge"]}, self.taxonomy)["path_key"],
            "sphere/knowledge_learning_culture/knowledge_learning_bridge",
        )
        self.assertEqual(
            derive_project_path({**base, "themes": ["open-source", "open-data"]}, self.taxonomy)["path_key"],
            "sphere/software_tools_production/knowledge_software_bridge",
        )
        unknown = derive_project_path({**base, "themes": ["future-theme"]}, self.taxonomy)
        self.assertEqual(unknown["status"], "unclassified")
        self.assertEqual(unknown["unknown_themes"], ["future-theme"])
        self.assertIsNone(derive_project_path({**base, "presence": {"digital": {"available": False}}}, self.taxonomy))

    def test_legacy_aliases_and_invalid_paths_fail_closed(self):
        aliases = {entry["alias"]: entry["target_path"] for entry in self.taxonomy["legacy_layer_aliases"]}
        self.assertEqual(set(aliases), {
            "knowledge_data",
            "software_infrastructure",
            "media_culture",
            "learning_education",
            "communication_networks",
            "mixed_other",
        })
        self.assertEqual(aliases["mixed_other"], ["sphere"])
        self.assertTrue(normalize_path("sphere/communication_networks/community_networks", self.taxonomy)["valid"])
        self.assertEqual(normalize_path("sphere/../catalog", self.taxonomy)["path"], ["sphere"])
        self.assertFalse(normalize_path("sphere/../catalog", self.taxonomy)["valid"])

    def test_normalize_path_matches_shared_fail_closed_parity_fixtures(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures/digital-path-parity.json").read_text(encoding="utf-8"))
        for fixture in fixtures:
            with self.subTest(fixture["name"]):
                normalized = normalize_path(fixture["value"], self.taxonomy)
                self.assertEqual(normalized["valid"], fixture["valid"])
                self.assertEqual(normalized["path"], fixture["path"])


if __name__ == "__main__":
    unittest.main()
