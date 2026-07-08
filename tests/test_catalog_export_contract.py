import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_catalog_export_contract import validate_catalog_export_contract
from scripts.validate_contracts import ROOT


class CatalogExportContractTests(unittest.TestCase):
    def copy_contract_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_catalog_export_contract_validates(self) -> None:
        self.assertEqual([], validate_catalog_export_contract(ROOT))

    def test_doc_must_keep_static_export_first_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "catalog-export-contract.md"
            text = path.read_text(encoding="utf-8").replace("static export first", "api first")
            path.write_text(text, encoding="utf-8")

            errors = validate_catalog_export_contract(tmp_root)

        self.assertIn("catalog export contract missing required phrase: static export first", errors)

    def test_sample_entries_must_track_seed_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-export.sample.json"
            sample = json.loads(path.read_text(encoding="utf-8"))
            sample["entries"] = list(reversed(sample["entries"]))
            path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_export_contract(tmp_root)

        self.assertIn(
            "catalog export sample entries must deterministically mirror seed manifest project order and public metadata",
            errors,
        )


    def test_source_manifest_paths_must_stay_inside_projects_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "seed-projects.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["project_paths"] = ["../catalog-export.sample.json"]
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_export_contract(tmp_root)

        self.assertIn(
            "catalog export source manifest project_paths entries must stay inside examples/commonworld/projects",
            errors,
        )

    def test_public_scope_requires_curated_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-export.sample.json"
            sample = json.loads(path.read_text(encoding="utf-8"))
            sample["scope"] = "public"
            path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_export_contract(tmp_root)

        self.assertIn("public catalog exports must contain only curated entries", errors)

    def test_boundary_rejects_write_shortcut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "catalog-export-contract.md"
            text = path.read_text(encoding="utf-8") + "\nA write endpoint may be added here.\n"
            path.write_text(text, encoding="utf-8")

            errors = validate_catalog_export_contract(tmp_root)

        self.assertIn("catalog export contract includes forbidden shortcut: write endpoint", errors)


if __name__ == "__main__":
    unittest.main()
