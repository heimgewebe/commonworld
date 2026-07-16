from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_proposal_path", ROOT / "scripts/validate_proposal_path.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ProposalPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads((ROOT / "contracts/commonworld/proposal.schema.json").read_text(encoding="utf-8"))
        self.valid = json.loads((ROOT / "tests/fixtures/proposals/valid.json").read_text(encoding="utf-8"))

    def test_complete_surface_contract_is_valid(self) -> None:
        self.assertEqual(MODULE.validate(ROOT), [])

    def test_unknown_fields_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.valid)
        candidate["project"]["unreviewed"] = True
        errors = MODULE.validate_fixture(candidate, self.schema)
        self.assertTrue(any("Additional properties" in error for error in errors), errors)

    def test_missing_source_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.valid)
        candidate["project"]["sources"] = []
        self.assertTrue(MODULE.validate_fixture(candidate, self.schema))

    def test_javascript_url_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.valid)
        candidate["project"]["official_website"] = "javascript:alert(1)"
        self.assertTrue(MODULE.validate_fixture(candidate, self.schema))

    def test_private_coordinates_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.valid)
        candidate["project"]["region"] = "52.5200, 13.4050"
        self.assertTrue(MODULE.validate_fixture(candidate, self.schema))

    def test_proposal_never_mutates_catalog_inventory(self) -> None:
        manifest = json.loads((ROOT / "catalog/catalog.json").read_text(encoding="utf-8"))
        proposal_ids = {path.stem for path in (ROOT / "tests/fixtures/proposals").glob("*.json")}
        published_ids = {Path(item).stem for item in manifest["project_files"]}
        self.assertTrue(proposal_ids.isdisjoint(published_ids))


if __name__ == "__main__":
    unittest.main()
