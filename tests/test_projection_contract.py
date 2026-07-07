import unittest

from scripts.validate_contracts import ROOT, iter_project_examples, load_json
from scripts.validate_projection_contract import validate_projection_contract


def project_examples_by_id():
    projects = {}
    for path in iter_project_examples(ROOT):
        project = load_json(path)
        projects[project["id"]] = project
    return projects


class ProjectionContractTests(unittest.TestCase):
    def test_projection_contract_doc_validates(self) -> None:
        self.assertEqual([], validate_projection_contract(ROOT))

    def test_project_examples_cover_projection_contract_matrix(self) -> None:
        projects = project_examples_by_id()

        self.assertIn("map", projects["neighborhood-repair-circle-fixture"]["projections"])
        self.assertIn("aether", projects["openstreetmap"]["projections"])
        self.assertTrue(
            {"map", "aether", "profile"}.issubset(
                projects["osm-hamburg-hybrid-fixture"]["projections"]
            )
        )

    def test_projection_contract_preserves_identity(self) -> None:
        text = (ROOT / "docs/blueprints/commonproject-projection-contract.md").read_text(encoding="utf-8")
        self.assertIn("projection metadata must not create a second project identity", text)


if __name__ == "__main__":
    unittest.main()
