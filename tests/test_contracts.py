import copy
import unittest

from scripts.validate_contracts import (
    ROOT,
    iter_project_examples,
    load_contract_set,
    load_json,
    validate_project,
)


def project_examples_by_id():
    projects = {}
    for path in iter_project_examples(ROOT):
        project = load_json(path)
        projects[project["id"]] = project
    return projects


class CommonProjectContractTests(unittest.TestCase):
    def validate_example(self, project):
        _, project_schema, registry = load_contract_set(ROOT)
        return validate_project(project, project_schema=project_schema, registry=registry)

    def test_seed_examples_validate_against_contract(self) -> None:
        _, project_schema, registry = load_contract_set(ROOT)
        example_paths = list(iter_project_examples(ROOT))

        self.assertGreaterEqual(len(example_paths), 3)

        for path in example_paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                project = load_json(path)
                self.assertEqual(
                    [],
                    validate_project(project, project_schema=project_schema, registry=registry),
                )

    def test_seed_examples_cover_core_privacy_modes_and_spheres(self) -> None:
        projects = [load_json(path) for path in iter_project_examples(ROOT)]

        self.assertIn("digital", {project["sphere"] for project in projects})
        self.assertIn("place", {project["sphere"] for project in projects})
        self.assertIn("hybrid", {project["sphere"] for project in projects})
        self.assertIn("hidden", {project["location"]["mode"] for project in projects})
        self.assertIn("approximate", {project["location"]["mode"] for project in projects})

    def test_seed_examples_cover_projection_cases(self) -> None:
        projects = [load_json(path) for path in iter_project_examples(ROOT)]

        self.assertTrue(all("profile" in project.get("projections", {}) for project in projects))
        self.assertTrue(any("map" in project.get("projections", {}) for project in projects))
        self.assertTrue(any("aether" in project.get("projections", {}) for project in projects))
        self.assertTrue(
            any(
                project["sphere"] == "hybrid"
                and {"map", "aether", "profile"}.issubset(project.get("projections", {}))
                for project in projects
            )
        )

    def test_hidden_projects_do_not_have_map_projection(self) -> None:
        for path in iter_project_examples(ROOT):
            project = load_json(path)
            if project["location"]["mode"] == "hidden":
                with self.subTest(project=project["id"]):
                    self.assertNotIn("map", project.get("projections", {}))

    def test_projection_semantics_reject_invalid_combinations(self) -> None:
        projects = project_examples_by_id()

        digital_with_map = copy.deepcopy(projects["openstreetmap"])
        digital_with_map["projections"]["map"] = {
            "appearance": "local-marker",
            "location_claim": "exact",
        }
        self.assertIn(
            "hidden locations must not expose a map projection",
            self.validate_example(digital_with_map),
        )
        self.assertIn(
            "digital projects must not include a map projection; use hybrid when a map anchor exists",
            self.validate_example(digital_with_map),
        )

        place_with_aether = copy.deepcopy(projects["neighborhood-repair-circle-fixture"])
        place_with_aether["projections"]["aether"] = {
            "appearance": "digital-card",
            "stream": "repair",
            "ortssignal": False,
        }
        self.assertIn(
            "place projects must not include an aether projection; use hybrid when a digital extension exists",
            self.validate_example(place_with_aether),
        )

        approximate_with_exact_claim = copy.deepcopy(projects["neighborhood-repair-circle-fixture"])
        approximate_with_exact_claim["projections"]["map"]["location_claim"] = "exact"
        self.assertIn(
            "approximate locations must use approximate map location_claim",
            self.validate_example(approximate_with_exact_claim),
        )

        disabled_handoff_available = copy.deepcopy(projects["neighborhood-repair-circle-fixture"])
        disabled_handoff_available["projections"]["profile"]["handoff_state"] = "available"
        self.assertIn(
            "disabled handoff must not have available profile handoff_state",
            self.validate_example(disabled_handoff_available),
        )

    def test_enabled_handoff_requires_explicit_url(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
        project["curation"] = {
            "state": "curated",
            "reviewed_by": "commonworld-review",
            "reviewed_at": "2026-07-08",
        }
        project["provenance"]["sources"] = [
            {
                "type": "official-source",
                "label": "OpenStreetMap",
                "url": "https://www.openstreetmap.org/",
                "retrieved_at": "2026-07-08",
            },
            {
                "type": "public-registry",
                "label": "Wikidata",
                "url": "https://www.wikidata.org/wiki/Q936",
                "retrieved_at": "2026-07-08",
            },
        ]
        project["handoff"] = {
            "enabled": True,
            "system": "weltgewebe",
            "project_id": "openstreetmap",
            "action_label": "Open in weltgewebe",
        }
        self.assertTrue(
            any("'url' is a required property" in error for error in self.validate_example(project))
        )

    def test_enabled_handoff_label_must_stay_neutral(self) -> None:
        for action_label in ("Join in weltgewebe", "Coordinate in weltgewebe"):
            with self.subTest(action_label=action_label):
                project = copy.deepcopy(project_examples_by_id()["openstreetmap"])
                project["curation"] = {
                    "state": "curated",
                    "reviewed_by": "commonworld-review",
                    "reviewed_at": "2026-07-08",
                }
                project["provenance"]["sources"] = [
                    {
                        "type": "official-source",
                        "label": "OpenStreetMap",
                        "url": "https://www.openstreetmap.org/",
                        "retrieved_at": "2026-07-08",
                    },
                    {
                        "type": "public-registry",
                        "label": "Wikidata",
                        "url": "https://www.wikidata.org/wiki/Q936",
                        "retrieved_at": "2026-07-08",
                    },
                ]
                project["handoff"] = {
                    "enabled": True,
                    "system": "weltgewebe",
                    "project_id": "openstreetmap",
                    "action_label": action_label,
                    "url": "https://example.org/weltgewebe/projects/openstreetmap",
                }
                self.assertIn(
                    "handoff action_label must stay neutral until authorization is modeled",
                    self.validate_example(project),
                )

    def test_hidden_hybrid_can_keep_aether_without_map(self) -> None:
        project = copy.deepcopy(project_examples_by_id()["osm-hamburg-hybrid-fixture"])
        project["location"] = {
            "mode": "hidden",
            "label": "Hidden local relation",
            "precision": "none",
            "privacy_note": "Local relation is intentionally not shown on the map.",
        }
        project["projections"] = {
            "aether": {
                "appearance": "hybrid-card",
                "stream": "knowledge-data",
                "ortssignal": True,
            },
            "profile": {
                "mode": "focus-state",
                "preserves_previous_projection": True,
                "handoff_state": "locked",
            },
        }

        self.assertEqual([], self.validate_example(project))

    def test_color_is_not_the_only_semantic_carrier(self) -> None:
        for path in iter_project_examples(ROOT):
            project = load_json(path)
            for aspect in project["aspects"]:
                with self.subTest(project=project["id"], aspect=aspect["id"]):
                    self.assertTrue(aspect["label"])
                    self.assertTrue(aspect["icon_token"])
                    self.assertTrue(aspect["evidence"])


if __name__ == "__main__":
    unittest.main()
