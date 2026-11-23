"""Proof that public regional contexts cannot be confused with locations."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_regional_context import (  # noqa: E402
    INDEX, SCHEMA, project_index, read_json, validation_errors
)


class RegionalContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_json(ROOT / INDEX)
        cls.schema = read_json(ROOT / SCHEMA)
        cls.projects = project_index(ROOT)

    def errors(self, manifest: dict) -> list[str]:
        return validation_errors(manifest, self.projects, self.schema, current_date=date(2026, 11, 23))

    def test_three_public_contexts_and_stable_canonical_ids(self) -> None:
        self.assertEqual(self.errors(self.manifest), [])
        contexts = self.manifest["contexts"]
        self.assertEqual({c["project_id"] for c in contexts}, {
            "berkshares", "great-lakes-commons", "coopcycle"
        })
        self.assertEqual({c["reference"]["kind"] for c in contexts}, {
            "named_region", "bioregion", "distributed_network"
        })

    def test_all_three_sources_are_independent_of_hidden_location_text(self) -> None:
        for entry in self.manifest["contexts"]:
            project = self.projects[entry["project_id"]]
            sources = {s["id"]: s for s in project["provenance"]["sources"]}
            self.assertTrue(all(sources[s]["type"] == "official-source" for s in entry["source_ids"]))
            self.assertTrue(all(x["mode"] == "hidden" and "geometry" not in x
                                for x in project["presence"]["geographic"]))
            self.assertEqual(entry["coverage_claim"], "none")

    def test_adding_geometry_or_private_coordinates_is_schema_error(self) -> None:
        for field, value in (
            ("geometry", {"type": "Point", "coordinates": [-73.2, 42.4]}),
            ("coordinates", [-73.2, 42.4]),
            ("member_addresses", ["private address"]),
        ):
            with self.subTest(field=field):
                item = copy.deepcopy(self.manifest)
                item["contexts"][0][field] = value
                self.assertTrue(self.errors(item))

    def test_unknown_project_and_unbound_source_are_rejected(self) -> None:
        item = copy.deepcopy(self.manifest)
        item["contexts"][1]["project_id"] = "not-a-published-project"
        self.assertIn("unknown canonical project", " ".join(self.errors(item)))
        item = copy.deepcopy(self.manifest)
        item["contexts"][0]["source_ids"] = ["berkshares-berkshire-region"]
        self.assertIn("unknown official source", " ".join(self.errors(item)))

    def test_duplicate_id_and_pair_rejected(self) -> None:
        item = copy.deepcopy(self.manifest)
        item["contexts"].append(copy.deepcopy(item["contexts"][0]))
        errors = " ".join(self.errors(item))
        self.assertIn("duplicate context id", errors)
        self.assertIn("duplicate project/reference", errors)

    def test_future_review_and_extent_claim_rejected(self) -> None:
        item = copy.deepcopy(self.manifest)
        item["contexts"][0]["source_reviewed_at"] = "2099-01-01"
        self.assertIn("source reviewed in the future", " ".join(self.errors(item)))
        item = copy.deepcopy(self.manifest)
        item["contexts"][0]["coverage_claim"] = "full"
        self.assertTrue(self.errors(item))

    def test_reference_has_no_geographic_centroid_or_inferred_membership(self) -> None:
        for entry in self.manifest["contexts"]:
            self.assertEqual(set(entry["reference"]), {"id", "kind", "labels"})
            self.assertEqual(set(entry["reference"]["labels"]), {"de", "en"})
            self.assertEqual(set(entry["public_notes"]), {"de", "en"})
            self.assertNotIn("geometry", json.dumps(entry))
            self.assertNotIn("longitude", json.dumps(entry))
            self.assertNotIn("latitude", json.dumps(entry))
            self.assertNotIn("country_codes", json.dumps(entry))


if __name__ == "__main__":
    unittest.main()
