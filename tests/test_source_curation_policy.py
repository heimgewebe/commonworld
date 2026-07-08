import copy
import unittest

from scripts.validate_contracts import ROOT, iter_project_examples, load_contract_set, load_json, validate_project
from scripts.validate_source_curation_policy import validate_source_curation_policy


def project_examples_by_id():
    projects = {}
    for path in iter_project_examples(ROOT):
        project = load_json(path)
        projects[project["id"]] = project
    return projects


class SourceCurationPolicyTests(unittest.TestCase):
    def validate_example(self, project):
        _, project_schema, registry = load_contract_set(ROOT)
        return validate_project(project, project_schema=project_schema, registry=registry)

    def test_source_curation_policy_doc_validates(self) -> None:
        self.assertEqual([], validate_source_curation_policy(ROOT))

    def test_candidate_requires_review_marker(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"].pop("reviewed_by")
        self.assertIn(
            "candidate, curated and archived entries need reviewed_by and reviewed_at",
            self.validate_example(project),
        )

    def test_candidate_rejects_fixture_provenance(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["provenance"]["sources"] = [
            {"type": "fixture", "label": "Synthetic fixture", "retrieved_at": "2026-07-08"}
        ]
        errors = self.validate_example(project)
        self.assertIn("non-fixture entries must not rely on fixture provenance", errors)
        self.assertIn("candidate, curated and archived entries need non-fixture provenance", errors)

    def test_fixture_rejects_non_fixture_source_mix(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["neighborhood-repair-circle-fixture"])
        project["provenance"]["sources"].append(
            {
                "type": "official-source",
                "label": "Unexpected official source",
                "url": "https://example.org/source",
                "retrieved_at": "2026-07-08",
            }
        )
        self.assertIn(
            "fixture entries must not mix fixture and non-fixture provenance",
            self.validate_example(project),
        )

    def test_official_source_requires_url_and_retrieved_at(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["provenance"]["sources"][0].pop("url")
        self.assertIn(
            "provenance.sources[0]: official-source sources need url and retrieved_at",
            self.validate_example(project),
        )

    def test_manual_and_derived_sources_require_note(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"]["state"] = "curated"
        project["provenance"]["sources"] = [
            {
                "type": "manual-curation",
                "label": "Manual review",
                "retrieved_at": "2026-07-08",
            },
            {
                "type": "derived",
                "label": "Derived signal",
                "retrieved_at": "2026-07-08",
            },
        ]
        errors = self.validate_example(project)
        self.assertIn("provenance.sources[0]: manual-curation sources need note", errors)
        self.assertIn("provenance.sources[1]: derived sources need note", errors)


    def test_aspect_official_evidence_requires_url_and_retrieved_at(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["aspects"][0]["evidence"][0].pop("retrieved_at")
        self.assertIn(
            "aspects[open-data].evidence[0]: official-source sources need url and retrieved_at",
            self.validate_example(project),
        )

    def test_aspect_manual_and_derived_evidence_require_note(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["aspects"][0]["evidence"] = [
            {
                "type": "manual-curation",
                "label": "Manual aspect review",
                "retrieved_at": "2026-07-08",
            },
            {
                "type": "derived",
                "label": "Derived aspect signal",
                "retrieved_at": "2026-07-08",
            },
        ]
        errors = self.validate_example(project)
        self.assertIn("aspects[open-data].evidence[0]: manual-curation sources need note", errors)
        self.assertIn("aspects[open-data].evidence[1]: derived sources need note", errors)

    def test_curated_requires_two_non_fixture_sources(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"]["state"] = "curated"
        project["provenance"]["sources"] = [project["provenance"]["sources"][0]]
        self.assertIn("curated entries need at least two non-fixture sources", self.validate_example(project))

    def test_curated_rejects_derived_only_sources(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"]["state"] = "curated"
        project["provenance"]["sources"] = [
            {"type": "derived", "label": "Derived one", "note": "Derived from internal transform."},
            {"type": "derived", "label": "Derived two", "note": "Derived from second transform."},
        ]
        self.assertIn("curated entries must not rely only on derived sources", self.validate_example(project))

    def test_handoff_requires_curated_entry(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["handoff"] = {
            "enabled": True,
            "system": "weltgewebe",
            "project_id": "osm",
            "action_label": "Open in weltgewebe",
            "url": "https://example.org/weltgewebe/osm",
        }
        self.assertIn("handoff actions require curated curation state", self.validate_example(project))

    def test_archived_entries_do_not_expose_handoff_actions(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"]["state"] = "archived"
        project["handoff"] = {
            "enabled": True,
            "system": "weltgewebe",
            "project_id": "osm",
            "action_label": "Open in weltgewebe",
            "url": "https://example.org/weltgewebe/osm",
        }
        self.assertIn("archived entries must not expose handoff actions", self.validate_example(project))


if __name__ == "__main__":
    unittest.main()
