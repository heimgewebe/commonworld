from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_proposal_path", ROOT / "scripts/validate_proposal_path.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ProposalPathTests(unittest.TestCase):
    def copy_repo(self, tmp_dir: str) -> Path:
        """Return a full working-tree copy of the repo without .git/node_modules."""
        root = Path(tmp_dir) / "repo"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "node_modules"))
        return root

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

    def test_validator_accepts_attribute_varied_stylesheet_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repo(tmp_dir)
            path = root / "propose.html"
            html = path.read_text(encoding="utf-8")
            # Reordered attributes, single quotes and extra rel tokens must stay valid.
            html = html.replace(
                '<link rel="stylesheet" href="./index.css" />',
                "<link data-x='1' href='./index.css' rel='stylesheet preload'>",
            )
            html = html.replace(
                '<link rel="stylesheet" href="./assets/proposal.css" />',
                '<link href="./assets/proposal.css" rel="Stylesheet" />',
            )
            path.write_text(html, encoding="utf-8")
            self.assertEqual([], MODULE.validate(root))

    def test_validator_reports_missing_body_proposal_page_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repo(tmp_dir)
            path = root / "assets/proposal.css"
            css = path.read_text(encoding="utf-8")
            # Rename the real body rule so no exact body.proposal-page block remains.
            css = css.replace("body.proposal-page {", "body.proposal-page-alt {", 1)
            path.write_text(css, encoding="utf-8")
            errors = MODULE.validate(root)
            self.assertIn("assets/proposal.css must style body.proposal-page", errors)

    def test_validator_ignores_braces_in_leading_css_comment_and_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repo(tmp_dir)
            path = root / "assets/proposal.css"
            css = path.read_text(encoding="utf-8")
            decoy = '/* stray braces } { */\n.decoy::before { content: "} {"; }\n\n'
            path.write_text(decoy + css, encoding="utf-8")
            self.assertEqual([], MODULE.validate(root))


if __name__ == "__main__":
    unittest.main()
