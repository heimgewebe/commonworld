import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_device_acceptance_pack import ROOT, load_result, validate_device_acceptance_pack


class DeviceAcceptancePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def mutated_root(self, mutate) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        research = root / "docs" / "research"
        research.mkdir(parents=True)
        result = copy.deepcopy(self.result)
        mutate(result)
        (research / "device-acceptance-pack-v1.result.json").write_text(json.dumps(result, indent=2) + "\n")
        shutil.copy2(ROOT / "docs/research/device-acceptance-pack-v1.md", research / "device-acceptance-pack-v1.md")
        for name in ("index.html", "404.html"):
            source = ROOT / name
            if source.is_file():
                shutil.copy2(source, root / name)
        return temporary, root

    def errors_after(self, mutate) -> list[str]:
        temporary, root = self.mutated_root(mutate)
        try:
            return validate_device_acceptance_pack(root)
        finally:
            temporary.cleanup()

    def test_pack_validates(self) -> None:
        self.assertEqual([], validate_device_acceptance_pack(ROOT))

    def test_virtual_list_is_bounded_at_50000_items(self) -> None:
        linear = self.result["virtualized_linear_view"]
        self.assertEqual(50000, linear["scale_dataset_identities"])
        self.assertEqual(17, linear["maximum_rendered_rows"])
        self.assertLessEqual(linear["maximum_rendered_rows"], linear["maximum_allowed_rows"])
        self.assertTrue(linear["dom_bound_pass"])

    def test_physical_acceptance_remains_pending(self) -> None:
        self.assertEqual("pack_ready_physical_execution_pending", self.result["status"])
        gate = self.result["manual_acceptance_gate"]
        self.assertTrue(gate["all_checks_pending"])
        self.assertFalse(gate["physical_mobile_safari_tested"])
        self.assertFalse(gate["real_voiceover_or_talkback_tested"])

    def test_service_is_private_and_tailnet_only(self) -> None:
        service = self.result["acceptance_package"]["service"]
        self.assertEqual("tailscale_ipv4_only", service["binding_scope"])
        self.assertFalse(service["public_ingress"])
        self.assertFalse(service["loopback_listener"])
        self.assertTrue(service["result_directory_private"])

    def test_pack_never_authorizes_engine_or_architecture(self) -> None:
        decision = self.result["decision"]
        self.assertFalse(decision["engine_selected"])
        self.assertFalse(decision["production_architecture_authorized"])
        receipt = self.result["acceptance_package"]["receipt_contract"]
        self.assertTrue(receipt["engine_authorization_forbidden"])
        self.assertTrue(receipt["production_architecture_authorization_forbidden"])

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"engine_selected": True}))
        self.assertTrue(any("must not select" in error for error in errors))

    def test_validator_rejects_architecture_authorization(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"production_architecture_authorized": True}))
        self.assertTrue(any("must not authorize" in error for error in errors))

    def test_validator_rejects_fake_physical_safari_claim(self) -> None:
        errors = self.errors_after(lambda result: result["manual_acceptance_gate"].update({"physical_mobile_safari_tested": True}))
        self.assertTrue(any("physical_mobile_safari_tested" in error for error in errors))

    def test_validator_rejects_dom_bound_violation(self) -> None:
        errors = self.errors_after(lambda result: result["virtualized_linear_view"].update({"maximum_rendered_rows": 26}))
        self.assertTrue(any("linear-view evidence" in error or "DOM bound" in error for error in errors))

    def test_validator_rejects_real_catalog_overclaim(self) -> None:
        errors = self.errors_after(lambda result: result["virtualized_linear_view"].update({"real_catalog_data_tested": True}))
        self.assertTrue(any("linear-view evidence" in error for error in errors))

    def test_validator_rejects_public_ingress(self) -> None:
        errors = self.errors_after(lambda result: result["acceptance_package"]["service"].update({"public_ingress": True}))
        self.assertTrue(any("tailnet boundary" in error for error in errors))

    def test_validator_rejects_endpoint_publication(self) -> None:
        errors = self.errors_after(lambda result: result["scope"].update({"device_endpoint_published_in_repository": True}))
        self.assertTrue(any("privacy boundary" in error for error in errors))

    def test_validator_rejects_changed_release_hash(self) -> None:
        errors = self.errors_after(lambda result: result["acceptance_package"].update({"release_manifest_sha256": "0" * 64}))
        self.assertTrue(any("release manifest hash" in error for error in errors))

    def test_validator_rejects_changed_archive_hash(self) -> None:
        errors = self.errors_after(lambda result: result["evidence_artifacts"].update({"archive_sha256": "0" * 64}))
        self.assertTrue(any("artifact hash mismatch" in error for error in errors))

    def test_validator_rejects_missing_manual_check(self) -> None:
        def mutate(result: dict) -> None:
            result["manual_acceptance_gate"]["required_checks"].pop()
        errors = self.errors_after(mutate)
        self.assertTrue(any("manual acceptance check inventory" in error for error in errors))

    def test_validator_rejects_physical_fps_overclaim(self) -> None:
        errors = self.errors_after(lambda result: result["preparation_measurement"].update({"relative_not_physical_device_fps": False}))
        self.assertTrue(any("must remain relative" in error for error in errors))

    def test_validator_rejects_disabled_same_origin_guard(self) -> None:
        errors = self.errors_after(lambda result: result["acceptance_package"]["receipt_contract"].update({"same_origin_required": False}))
        self.assertTrue(any("receipt contract" in error for error in errors))

    def test_validator_rejects_unbounded_receipt_files(self) -> None:
        errors = self.errors_after(lambda result: result["acceptance_package"]["receipt_contract"].update({"maximum_receipt_files": 1000000}))
        self.assertTrue(any("receipt contract" in error for error in errors))

    def test_validator_rejects_private_cgnat_endpoint_leak(self) -> None:
        def mutate(result: dict) -> None:
            result["scope"]["debug_endpoint"] = "http://" + ".".join(("100", "64", "0", "1")) + ":4196/"
        errors = self.errors_after(mutate)
        self.assertTrue(any("private endpoint leaked" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
