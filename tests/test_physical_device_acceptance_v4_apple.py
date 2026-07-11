import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_physical_device_acceptance_v4_apple import (
    ROOT,
    load_result,
    validate_physical_device_acceptance_v4_apple,
)


class PhysicalDeviceAcceptanceV4AppleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def errors_after(self, mutate, report_suffix: str = "") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            research = root / "docs/research"
            research.mkdir(parents=True)
            result = copy.deepcopy(self.result)
            mutate(result)
            (research / "physical-device-acceptance-v4-apple.result.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            report = (ROOT / "docs/research/physical-device-acceptance-v4-apple.md").read_text()
            (research / "physical-device-acceptance-v4-apple.md").write_text(report + report_suffix)
            for name in ("index.html", "404.html"):
                source = ROOT / name
                if source.is_file():
                    shutil.copy2(source, root / name)
            return validate_physical_device_acceptance_v4_apple(root)

    def test_result_validates(self) -> None:
        self.assertEqual([], validate_physical_device_acceptance_v4_apple(ROOT))

    def test_physical_performance_passes(self) -> None:
        automatic = self.result["automatic"]
        self.assertEqual(3, automatic["runs"])
        self.assertGreater(automatic["planet_median_fps"], 50)
        self.assertGreater(automatic["local_median_fps"], 50)
        self.assertTrue(automatic["performance_gate_pass"])

    def test_raw_receipt_remains_incomplete(self) -> None:
        self.assertEqual("incomplete", self.result["raw_receipt"]["overall_verdict"])
        self.assertEqual(["assistive_technology", "reduced_motion"], self.result["manual_raw"]["not_run"])

    def test_screenreader_is_waived_not_passed(self) -> None:
        assistive = self.result["policy_evaluation"]["assistive_technology"]
        self.assertEqual("waived_by_product_owner", assistive["status"])
        self.assertFalse(assistive["screen_reader_product_support_claimed"])
        self.assertEqual("voiceover_not_required_for_non_public_prototype", assistive["waiver_normalized"])
        self.assertEqual("waived_not_passed", self.result["normalized_verdict"]["assistive_technology"])

    def test_reduced_motion_gap_is_disclosed(self) -> None:
        raw = self.result["manual_raw"]
        reduced = self.result["policy_evaluation"]["reduced_motion"]
        self.assertIsNone(raw["reduced_motion_last_motion_duration_ms"])
        self.assertTrue(reduced["raw_machine_duration_missing"])
        self.assertTrue(reduced["product_owner_attested_working"])
        self.assertEqual("movement_reduction_works", reduced["attestation_normalized"])

    def test_android_remains_open(self) -> None:
        self.assertEqual("open", self.result["remaining_gates"]["physical_android_chrome_v5"])

    def test_validator_rejects_raw_verdict_rewrite(self) -> None:
        errors = self.errors_after(lambda result: result["raw_receipt"].update({"overall_verdict": "complete_pending_repository_review"}))
        self.assertTrue(any("raw receipt" in error for error in errors))

    def test_validator_rejects_missing_run(self) -> None:
        errors = self.errors_after(lambda result: result["automatic"].update({"runs": 2}))
        self.assertTrue(any("three v4 physical" in error for error in errors))

    def test_validator_rejects_performance_regression(self) -> None:
        errors = self.errors_after(lambda result: result["automatic"].update({"planet_median_fps": 20}))
        self.assertTrue(any("performance value" in error for error in errors))

    def test_validator_rejects_idle_rendering(self) -> None:
        errors = self.errors_after(lambda result: result["automatic"].update({"idle_overlay_render_delta": 1}))
        self.assertTrue(any("idle delta" in error for error in errors))

    def test_validator_rejects_short_background(self) -> None:
        errors = self.errors_after(lambda result: result["manual_raw"].update({"background_longest_hidden_ms": 9000}))
        self.assertTrue(any("background duration" in error for error in errors))

    def test_validator_rejects_invented_machine_duration(self) -> None:
        errors = self.errors_after(lambda result: result["manual_raw"].update({"reduced_motion_last_motion_duration_ms": 0}))
        self.assertTrue(any("must not be invented" in error for error in errors))

    def test_validator_rejects_missing_attestation(self) -> None:
        errors = self.errors_after(lambda result: result["policy_evaluation"]["reduced_motion"].update({"product_owner_attested_working": False}))
        self.assertTrue(any("attestation boundary" in error for error in errors))

    def test_validator_rejects_changed_attestation_source(self) -> None:
        errors = self.errors_after(lambda result: result["policy_evaluation"]["reduced_motion"].update({"attestation_source": "unknown"}))
        self.assertTrue(any("attestation boundary" in error for error in errors))

    def test_validator_rejects_changed_waiver_source(self) -> None:
        errors = self.errors_after(lambda result: result["policy_evaluation"]["assistive_technology"].update({"waiver_source": "unknown"}))
        self.assertTrue(any("support overclaim" in error for error in errors))

    def test_validator_rejects_screenreader_support_claim(self) -> None:
        errors = self.errors_after(lambda result: result["policy_evaluation"]["assistive_technology"].update({"screen_reader_product_support_claimed": True}))
        self.assertTrue(any("support overclaim" in error for error in errors))

    def test_validator_rejects_closed_android_gate(self) -> None:
        errors = self.errors_after(lambda result: result["remaining_gates"].update({"physical_android_chrome_v5": "closed"}))
        self.assertTrue(any("remaining gate" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"engine_selected": True}))
        self.assertTrue(any("decision boundary" in error for error in errors))

    def test_validator_rejects_wrong_v5_manifest(self) -> None:
        errors = self.errors_after(lambda result: result["acceptance_v5_release"].update({"installed_manifest_sha256": "0" * 64}))
        self.assertTrue(any("v5 evidence" in error for error in errors))

    def test_validator_rejects_raw_session_key(self) -> None:
        errors = self.errors_after(lambda result: None, '\n{"session_id": "private"}\n')
        self.assertTrue(any("private raw receipt" in error for error in errors))

    def test_validator_rejects_raw_user_agent_key(self) -> None:
        errors = self.errors_after(lambda result: None, '\n{"userAgent": "private"}\n')
        self.assertTrue(any("private raw receipt" in error for error in errors))

    def test_validator_rejects_private_tailnet_address(self) -> None:
        address = ".".join(("100", "64", "0", "1"))
        errors = self.errors_after(lambda result: None, f"\n{address}\n")
        self.assertTrue(any("private raw receipt" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
