import copy
import json
import unittest

from scripts.validate_contracts import (
    ROOT,
    base_record,
    load_schema,
    representative_records,
    validation_errors,
    validate_contracts,
)


class ContractTests(unittest.TestCase):
    def test_contracts_validate(self) -> None:
        self.assertEqual([], validate_contracts(ROOT))

    def test_case_matrix_covers_required_real_world_shapes(self) -> None:
        records = {record["id"]: record for record in representative_records()}
        self.assertEqual(
            {
                "shared-repair-place",
                "community-forest",
                "protected-seed-library",
                "sheltered-mutual-aid-store",
                "open-knowledge-network",
                "regional-water-cooperative",
                "tool-library-network",
                "local-digital-mapping-network",
                "mapping-chapter",
                "paused-community-kitchen",
            },
            set(records),
        )
        for record in records.values():
            with self.subTest(record=record["id"]):
                self.assertEqual([], validation_errors(record))


    def test_fully_digital_record_uses_no_invented_coordinate(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"] = {
            "geographic": [],
            "digital": {
                "available": True,
                "reach": "global",
                "label": "Available worldwide",
                "source_ids": ["official-website"],
            },
        }
        self.assertEqual([], validation_errors(record))

    def test_hidden_location_rejects_geometry(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0] = {
            "id": "withheld-site",
            "mode": "hidden",
            "label": "Location withheld",
            "privacy_note": "The exact location is not public.",
            "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
            "source_ids": ["official-website"],
        }
        self.assertTrue(validation_errors(record))

    def test_approximate_location_requires_geometry_and_uncertainty(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0] = {
            "id": "approximate-site",
            "mode": "approximate",
            "label": "Approximate district",
            "source_ids": ["official-website"],
        }
        errors = validation_errors(record)
        self.assertTrue(any("geometry" in error for error in errors))
        self.assertTrue(any("uncertainty_meters_min" in error for error in errors))

    def test_approximate_location_rejects_polygon_geometry(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0] = {
            "id": "approximate-area",
            "mode": "approximate",
            "label": "Approximate public area",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[9.9, 53.4], [10.1, 53.4], [10.1, 53.6], [9.9, 53.4]]],
            },
            "uncertainty_meters_min": 1000,
            "source_ids": ["official-website"],
        }
        self.assertTrue(any("Point" in error for error in validation_errors(record)))

    def test_multiple_geographic_anchors_validate_as_one_identity(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"].append(
            {
                "id": "second-site",
                "mode": "exact",
                "label": "Second public site",
                "geometry": {"type": "Point", "coordinates": [9.9, 53.6]},
                "source_ids": ["official-website"],
            }
        )
        self.assertEqual([], validation_errors(record))

    def test_relation_requires_known_provenance_source(self) -> None:
        record = copy.deepcopy(base_record())
        record["relations"] = [
            {
                "target_id": "another-commons",
                "type": "cooperates-with",
                "source_ids": ["missing-source"],
            }
        ]
        errors = validation_errors(record)
        self.assertTrue(any("unknown provenance sources" in error for error in errors))

    def test_digital_presence_requires_known_provenance_source(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["digital"]["source_ids"] = ["missing-source"]
        self.assertTrue(any("digital presence references unknown" in error for error in validation_errors(record)))

    def test_activity_requires_known_provenance_source(self) -> None:
        record = copy.deepcopy(base_record())
        record["activity"]["source_ids"] = ["missing-source"]
        self.assertTrue(any("activity references unknown" in error for error in validation_errors(record)))

    def test_polygon_rings_must_be_closed(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0]["geometry"] = {
            "type": "Polygon",
            "coordinates": [[[9.9, 53.4], [10.1, 53.4], [10.1, 53.6], [9.8, 53.5]]],
        }
        self.assertTrue(any("unclosed polygon ring" in error for error in validation_errors(record)))

    def test_exact_location_rejects_uncertainty_radius(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0]["uncertainty_meters_min"] = 100
        self.assertTrue(any("uncertainty_meters_min" in error for error in validation_errors(record)))

    def test_hidden_location_requires_privacy_explanation(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0] = {
            "id": "withheld-site",
            "mode": "hidden",
            "label": "Location withheld",
            "source_ids": ["official-website"],
        }
        self.assertTrue(any("privacy_note" in error for error in validation_errors(record)))

    def test_coordinates_must_stay_inside_world_bounds(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"][0]["geometry"]["coordinates"] = [181.0, 53.5]
        self.assertTrue(validation_errors(record))

    def test_temporal_evidence_order_is_coherent(self) -> None:
        record = copy.deepcopy(base_record())
        record["activity"]["observed_at"] = "2026-07-02"
        self.assertTrue(any("activity observed_at" in error for error in validation_errors(record)))
        record = copy.deepcopy(base_record())
        record["curation"]["next_review_at"] = "2026-06-30"
        self.assertTrue(any("next_review_at" in error for error in validation_errors(record)))

    def test_semantic_validation_never_crashes_on_schema_invalid_shapes(self) -> None:
        record = copy.deepcopy(base_record())
        record["presence"]["geographic"] = [None]
        record["activity"]["source_ids"] = None
        record["relations"] = [None]
        self.assertTrue(validation_errors(record))

    def test_paused_activity_is_independent_from_stale_curation(self) -> None:
        record = copy.deepcopy(base_record())
        record["activity"]["status"] = "paused"
        record["curation"].update({"state": "stale", "reviewed_by": "Editorial review"})
        self.assertEqual([], validation_errors(record))

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
