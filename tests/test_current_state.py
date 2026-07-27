import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_current_state import ROOT, validate_current_state


class CurrentStateTests(unittest.TestCase):
    def copy_current_state(self, directory: str) -> Path:
        target = Path(directory)
        shutil.copytree(ROOT / "catalog", target / "catalog")
        paths = (
            "contracts/commonworld/current-state.contract.json",
            "contracts/commonworld/public-maplibre-vertical-slice.contract.json",
            "contracts/commonworld/digital-ring-taxonomy.contract.json",
            "contracts/commonworld/production-delivery-provider.contract.json",
            "contracts/commonworld/catalog-platform.contract.json",
            "contracts/commonworld/renderer-selection.contract.json",
            "assets/commonworld-app.js",
            "contracts/commonworld/digital-sphere.contract.json",
            "docs/research/public-maplibre-vertical-slice-v1.result.json",
            "LICENSE",
            "LICENSE-DATA.md",
        )
        for relative in paths:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return target

    def test_current_state_validates(self) -> None:
        self.assertEqual([], validate_current_state(ROOT))

    def test_current_state_rejects_date_before_ring_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["current_as_of"] = "2026-07-18"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state date does not cover the selected catalog shard shadow truth", errors)

    def test_catalog_delivery_declares_selected_shard_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["catalog_delivery"]["runtime_catalogue_parity_check"] = False
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current catalog-delivery truth mismatch", errors)
        self.assertIn("catalog platform and current state disagree on runtime catalogue parity", errors)

    def test_catalog_delivery_declares_generation_bound_detail_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["catalog_delivery"]["runtime_catalogue_detail_loading"] = False
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current catalog-delivery truth mismatch", errors)
        self.assertIn("catalog platform and current state disagree on detail loading", errors)

    def test_catalog_delivery_rejects_platform_shadow_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["browser_transition"]["shadow_runtime_observation"]["selected_identity_detail"] = False
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform shadow-observation truth mismatch", errors)
        self.assertIn("catalog platform and current state disagree on detail loading", errors)

    def test_catalog_delivery_rejects_incompatible_detail_parity_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["browser_transition"]["selected_detail_parity"] = "unbound_detail"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform selected-detail parity boundary mismatch", errors)

    def test_catalog_delivery_rejects_runtime_implementation_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(path.read_text(encoding="utf-8").replace("function loadCatalogDetailOnce(", "function removedCatalogDetailOnce("), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("loadCatalogDetailOnce" in error for error in errors))

    def test_catalog_delivery_rejects_cache_limit_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["runtime_cache"]["details_max_entries"] = 128
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform and current state disagree on runtime catalogue cache limits", errors)


    def test_catalog_delivery_rejects_retry_policy_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["runtime_cache"]["explicit_retry_refresh"] = "reuse_cached_promises"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform and current state disagree on fresh retry policy", errors)

    def test_catalog_delivery_rejects_cutover_without_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["browser_transition"]["cutover_authorized"] = True
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform and current state disagree on bootstrap cutover authorization", errors)

    def test_dynamic_digital_count_has_precise_error_without_static_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["digital_ring_taxonomy"]["current_digital_identity_count"] += 1
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current catalog digital identity count does not match current state", errors)
        self.assertFalse(any("static truth mismatch" in error for error in errors))

    def test_digital_ring_state_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["digital_ring_taxonomy"]["legacy_count"] = 25
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current digital ring taxonomy field inventory mismatch", errors)

    def test_activity_status_policy_is_current_operational_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["activity_status_policy"]["unknown_review_max_days"] = 90
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current public activity-status policy mismatch", errors)

    def test_rejects_regression_to_unapproved_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["production"]["architecture_authorized"] = False
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("production truth" in error for error in errors))

    def test_rejects_historical_contract_as_current_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["precedence"]["current_operational_truth"] = "renderer-selection.contract.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("precedence" in error for error in errors))

    def test_rejects_rewritten_historical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "docs/research/public-maplibre-vertical-slice-v1.result.json"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("historical evidence was rewritten" in error for error in errors))

    def test_rejects_missing_odbl_catalogue_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"] = []
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("licensing truth" in error for error in errors))

        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"][0]["source_ids"] = [
                "osm-node-13966522352",
                "osm-way-260066697",
            ]
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("licensing truth" in error for error in errors))

    def test_rejects_missing_data_licence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            (root / "LICENSE-DATA.md").unlink()
            errors = validate_current_state(root)
        self.assertTrue(any("licences must exist" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
