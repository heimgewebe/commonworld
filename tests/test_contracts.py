import unittest

from scripts.validate_contracts import (
    ROOT,
    iter_project_examples,
    load_contract_set,
    load_json,
    validate_project,
)


class CommonProjectContractTests(unittest.TestCase):
    def test_seed_examples_validate_against_contract(self) -> None:
        _, project_schema, registry = load_contract_set(ROOT)
        example_paths = list(iter_project_examples(ROOT))

        self.assertGreaterEqual(len(example_paths), 2)

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
        self.assertIn("hidden", {project["location"]["mode"] for project in projects})
        self.assertIn("approximate", {project["location"]["mode"] for project in projects})

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
