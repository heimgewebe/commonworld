import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_search_index_input_contract import validate_search_index_input_contract


class SearchIndexInputContractTests(unittest.TestCase):
    def copy_contract_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        return tmp_root

    def test_search_index_input_contract_validates(self) -> None:
        self.assertEqual([], validate_search_index_input_contract(ROOT))

    def test_fields_must_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "search-index-input.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["fields"][0]["writes"] = True
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input_contract(tmp_root)

        self.assertIn("search index input contract fields must not write", errors)

    def test_fields_must_reject_private_review_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "search-index-input.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["fields"].append(
                {
                    "id": "private_review_notes",
                    "source": "CommonProject",
                    "description": "Not allowed.",
                    "indexable": True,
                    "writes": False,
                    "submissions": False,
                    "private_review_data": True,
                }
            )
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input_contract(tmp_root)

        self.assertIn("search index input contract fields must exactly cover the allowed input fields in deterministic order", errors)
        self.assertIn("search index input contract fields must not include private review data", errors)

    def test_rebuild_policy_must_not_depend_on_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "search-index-input.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["rebuild_policy"]["runtime_dependency"] = "search server"
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input_contract(tmp_root)

        self.assertIn("search index input contract rebuild_policy runtime_dependency must be none", errors)

    def test_forbidden_list_must_include_vector_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "search-index-input.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["forbidden"].remove("vector database")
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input_contract(tmp_root)

        self.assertIn("search index input contract forbidden list missing: vector database", errors)

    def test_doc_must_not_enable_search_runtime_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "search-index-input-contract.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nImplement search now.\n", encoding="utf-8")

            errors = validate_search_index_input_contract(tmp_root)

        self.assertIn("search index input contract doc includes forbidden shortcut: implement search now", errors)


if __name__ == "__main__":
    unittest.main()
