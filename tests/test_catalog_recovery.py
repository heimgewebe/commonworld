import json
import unittest
from pathlib import Path

from scripts.catalog_recovery import PAGE_SIZE, index_relative_path, page_count, page_records, project_relative_path
from scripts.validate_catalog_recovery import ROOT, validate_catalog_recovery


class CatalogRecoveryTests(unittest.TestCase):
    def test_current_recovery_contract_and_artifacts_validate(self) -> None:
        self.assertEqual([], validate_catalog_recovery(ROOT, verify_measurements=False))

    def test_pagination_is_bounded_and_complete(self) -> None:
        records = [{"id": f"project-{index:05d}"} for index in range(10_000)]
        self.assertEqual(417, page_count(len(records)))
        pages = [page_records(records, number) for number in range(1, 418)]
        self.assertTrue(all(1 <= len(page) <= PAGE_SIZE for page in pages))
        self.assertEqual(records, [record for page in pages for record in page])

    def test_recovery_paths_are_locale_explicit_and_identity_stable(self) -> None:
        self.assertEqual(Path("catalog/index.html"), index_relative_path("en", 1))
        self.assertEqual(Path("catalog/pages/2.html"), index_relative_path("en", 2))
        self.assertEqual(Path("catalog/de/index.html"), index_relative_path("de", 1))
        self.assertEqual(Path("catalog/de/pages/2.html"), index_relative_path("de", 2))
        self.assertEqual(Path("catalog/projects/debian.html"), project_relative_path("en", "debian"))
        self.assertEqual(Path("catalog/de/projects/debian.html"), project_relative_path("de", "debian"))

    def test_cutover_authorization_remains_false_in_all_t028_authorities(self) -> None:
        recovery = json.loads((ROOT / "contracts/commonworld/catalog-recovery.contract.json").read_text())
        scale = json.loads((ROOT / "contracts/commonworld/catalog-scale-gates.contract.json").read_text())
        state = json.loads((ROOT / "contracts/commonworld/current-state.contract.json").read_text())
        self.assertFalse(recovery["authorization"]["runtime_catalogue_cutover_authorized"])
        self.assertFalse(scale["current_authorization"]["cutover_authorized"])
        self.assertFalse(state["catalog_delivery"]["runtime_catalogue_cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
