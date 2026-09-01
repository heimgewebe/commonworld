import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_page_release_manifest import snapshot_files
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
            "assets/commonworld-page-builds.json",
            "contracts/commonworld/digital-sphere.contract.json",
            "docs/evidence/commonworld-current-state.attestation.json",
            "docs/research/public-maplibre-vertical-slice-v1.result.json",
            "LICENSE",
            "LICENSE-DATA.md",
            "SECURITY.md",
            ".well-known/security.txt",
            "_config.yml",
            "scripts/verify_pages_deployment.py",
            ".github/workflows/production-readback.yml",
            ".github/workflows/security-policy-expiry.yml",
        )
        for relative in paths:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return target

    def test_current_state_validates(self) -> None:
        self.assertEqual([], validate_current_state(ROOT))

    def test_current_state_release_binding_is_non_circular(self) -> None:
        release_inputs = {
            path.relative_to(ROOT).as_posix()
            for path in snapshot_files(ROOT, include_manifest=False)
        }
        self.assertNotIn(
            "docs/evidence/commonworld-current-state.attestation.json",
            release_inputs,
        )
        self.assertNotIn("assets/commonworld-page-builds.json", release_inputs)

    def test_current_state_rejects_invalid_current_as_of(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["current_as_of"] = "not-a-date"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state current_as_of must be an ISO date", errors)

    def test_current_state_rejects_contract_change_without_attestation_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["current_as_of"] = "2026-08-31"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state attestation contract binding mismatch", errors)

    def test_current_state_rejects_release_change_without_attestation_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "assets/commonworld-page-builds.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["release_id"] = "0" * 20
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state attestation release binding mismatch", errors)

    def test_current_state_requires_release_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            (root / "docs/evidence/commonworld-current-state.attestation.json").unlink()
            errors = validate_current_state(root)
        self.assertIn(
            "missing current-state dependency: docs/evidence/commonworld-current-state.attestation.json",
            errors,
        )

    def test_current_state_rejects_malformed_release_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "docs/evidence/commonworld-current-state.attestation.json"
            path.write_text("{}\n", encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state attestation schema or kind mismatch", errors)

    def test_current_state_rejects_non_object_release_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "docs/evidence/commonworld-current-state.attestation.json"
            path.write_text("[]\n", encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current-state attestation must be an object", errors)

    def test_security_disclosure_rejects_disabled_private_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["security_disclosure"]["trust_boundary"] = "self_attested"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current security-disclosure truth mismatch", errors)

    def test_security_disclosure_rejects_unconditional_weekly_monitoring_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["security_disclosure"]["expiry_monitoring"] = "weekly_github_actions"
            value["security_disclosure"].pop("scheduled_workflow_inactivity_boundary_days", None)
            value["security_disclosure"].pop("manual_reenable_required_after_automatic_disablement", None)
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current security-disclosure truth mismatch", errors)

    def test_security_disclosure_requires_exact_production_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "scripts/verify_pages_deployment.py"
            path.write_text(path.read_text(encoding="utf-8").replace(".well-known/security.txt", "security.txt"), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current production readback does not include security.txt", errors)


    def test_security_disclosure_requires_live_setting_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / ".github/workflows/production-readback.yml"
            path.write_text(path.read_text(encoding="utf-8").replace("--verify-live-setting", "--skip-live-setting"), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current production readback does not enforce private vulnerability reporting", errors)

    def test_security_disclosure_requires_weekly_expiry_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            path.write_text(path.read_text(encoding="utf-8").replace('cron: "17 5 * * 1"', 'cron: "0 0 1 1 *"'), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("current security-expiry workflow mismatch", errors)

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

    def test_catalog_delivery_rejects_platform_selected_detail_upgrade_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/catalog-platform.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["browser_transition"]["selected_identity_detail"]["mode"] = "shadow_only"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertIn("catalog platform selected-detail public-upgrade truth mismatch", errors)

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

    def test_catalog_delivery_rejects_runtime_detail_cache_retention_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "assets/commonworld-app.js"
            value = path.read_text(encoding="utf-8").replace(
                "const CATALOG_DETAIL_CACHE_LIMIT = 1;",
                "const CATALOG_DETAIL_CACHE_LIMIT = 16;",
            )
            path.write_text(value, encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("CATALOG_DETAIL_CACHE_LIMIT = 1" in error for error in errors))


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
