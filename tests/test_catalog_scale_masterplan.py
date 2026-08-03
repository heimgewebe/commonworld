import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_catalog_scale_masterplan",
    ROOT / "scripts" / "validate_catalog_scale_masterplan.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CatalogScaleMasterplanValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        for relative in (
            Path("contracts/commonworld/catalog-scale-gates.contract.json"),
            Path("docs/evidence/catalog-platform-scaling-v1.json"),
            Path("docs/blueprints/commonworld-masterplan.md"),
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_current_masterplan_matches_executable_scale_gates(self):
        self.assertEqual(MODULE.validate_catalog_scale_masterplan(self.root), [])

    def test_stale_100k_baseline_is_rejected(self):
        path = self.root / "docs/blueprints/commonworld-masterplan.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("9.844.462 Byte gzip", "1.541.423 Byte gzip", 1)
        path.write_text(text, encoding="utf-8")
        errors = MODULE.validate_catalog_scale_masterplan(self.root)
        self.assertIn(
            "canonical catalogue scale plan retains stale fragment: 1.541.423 Byte gzip",
            errors,
        )
        self.assertIn(
            "canonical catalogue scale plan misses current fragment: 9.844.462 Byte gzip",
            errors,
        )

    def test_contract_cannot_point_to_an_ambient_plan(self):
        path = self.root / "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        contract["canonical_plan"] = "docs/architecture/catalog-platform-v1.md"
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.assertIn(
            "catalogue scale contract canonical plan path mismatch",
            MODULE.validate_catalog_scale_masterplan(self.root),
        )


if __name__ == "__main__":
    unittest.main()
