import copy
import json
import unittest

from scripts.validate_contracts import ROOT, base_record, load_schema, representative_records, validation_errors, validate_contracts


class ContractTests(unittest.TestCase):
    def test_contracts_validate(self) -> None:
        self.assertEqual([], validate_contracts(ROOT))

    def test_representative_geographic_digital_and_hybrid_records_validate(self) -> None:
        for record in representative_records():
            with self.subTest(record=record["id"]):
                self.assertEqual([], validation_errors(record))

    def test_digital_record_rejects_exact_geographic_geometry(self) -> None:
        record = copy.deepcopy(base_record())
        record["kind"] = "digital"
        record["presence"]["digital"] = {
            "available": True,
            "reach": "global",
            "label": "Available worldwide",
        }

        errors = validation_errors(record)

        self.assertTrue(errors)

    def test_hidden_location_rejects_geometry(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"] = {
            "mode": "hidden",
            "label": "Location withheld",
            "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
        }

        errors = validation_errors(record)

        self.assertTrue(errors)

    def test_relation_requires_evidence_url(self) -> None:
        record = copy.deepcopy(base_record())
        record["relations"] = [{"target_id": "another-commons", "type": "cooperates-with"}]

        errors = validation_errors(record)

        self.assertTrue(any("source_url" in error for error in errors))

    def test_contract_contains_no_presentation_truth(self) -> None:
        properties = load_schema()["properties"]
        for forbidden in ("aspects", "projections", "marker_style", "animation", "zoom_level"):
            with self.subTest(property=forbidden):
                self.assertNotIn(forbidden, properties)

    def test_schema_is_json_roundtrippable(self) -> None:
        schema = load_schema()
        self.assertEqual(schema, json.loads(json.dumps(schema)))


if __name__ == "__main__":
    unittest.main()
