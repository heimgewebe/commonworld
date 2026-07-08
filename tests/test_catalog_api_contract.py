import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_catalog_api_contract import validate_catalog_api_contract
from scripts.validate_contracts import ROOT


class CatalogApiContractTests(unittest.TestCase):
    def copy_contract_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        return tmp_root

    def test_catalog_api_contract_validates(self) -> None:
        self.assertEqual([], validate_catalog_api_contract(ROOT))

    def test_routes_must_remain_get_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "catalog-api.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["routes"][0]["method"] = "POST"
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_contract(tmp_root)

        self.assertIn("catalog API contract routes must be GET-only", errors)
        self.assertIn("catalog API contract must not include POST routes", errors)

    def test_routes_must_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "catalog-api.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["routes"][1]["writes"] = True
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_contract(tmp_root)

        self.assertIn("catalog API contract routes must not write", errors)

    def test_routes_must_cover_exact_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "contracts" / "commonworld" / "catalog-api.contract.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["routes"].append(
                {
                    "id": "submit-project",
                    "method": "GET",
                    "path": "/catalog/v1/submit",
                    "description": "Not allowed.",
                    "source": "generated static catalog export",
                    "access": "public-read-only",
                    "auth_required": False,
                    "writes": False,
                    "submissions": False,
                    "response_shape": "not allowed",
                }
            )
            path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_contract(tmp_root)

        self.assertIn("catalog API contract routes must exactly cover the allowed read-only catalog paths in deterministic order", errors)
        self.assertIn("catalog API contract route path is not allowed", errors)

    def test_doc_must_not_enable_server_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "catalog-api-contract.md"
            text = path.read_text(encoding="utf-8") + "\nImplement the server now.\n"
            path.write_text(text, encoding="utf-8")

            errors = validate_catalog_api_contract(tmp_root)

        self.assertIn("catalog API contract doc includes forbidden shortcut: implement the server now", errors)


if __name__ == "__main__":
    unittest.main()
