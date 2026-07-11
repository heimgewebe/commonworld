import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_device_acceptance_rerun import ROOT, load_result, validate_device_acceptance_rerun


class DeviceAcceptanceRerunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def mutated_root(self, mutate) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        research = root / "docs" / "research"
        research.mkdir(parents=True)
        result = copy.deepcopy(self.result)
        mutate(result)
        (research / "device-acceptance-rerun-v2.result.json").write_text(json.dumps(result, indent=2) + "\n")
        shutil.copy2(ROOT / "docs/research/device-acceptance-rerun-v2.md", research / "device-acceptance-rerun-v2.md")
        for name in ("index.html", "404.html"):
            source = ROOT / name
            if source.is_file():
                shutil.copy2(source, root / name)
        return temporary, root

    def errors_after(self, mutate) -> list[str]:
        temporary, root = self.mutated_root(mutate)
        try:
            return validate_device_acceptance_rerun(root)
        finally:
            temporary.cleanup()

    def test_rerun_evidence_validates(self) -> None:
        self.assertEqual([], validate_device_acceptance_rerun(ROOT))

    def test_first_run_remains_rejected(self) -> None:
        self.assertFalse(self.result["first_physical_run"]["accepted"])
        self.assertEqual(0, self.result["first_physical_run"]["automatic_performance_runs"])
        self.assertFalse(self.result["first_physical_run"]["reduced_motion_active"])

    def test_finding_severities_match_review(self) -> None:
        severities = {item["id"]: item["severity"] for item in self.result["findings"]}
        self.assertEqual("blocking", severities["digital_sphere_screen_fixed"])
        self.assertEqual("nonblocking", severities["background_interval_not_machine_bound"])

    def test_validator_rejects_background_severity_escalation(self) -> None:
        def mutate(result: dict) -> None:
            result["findings"][-1]["severity"] = "blocking"
        errors = self.errors_after(mutate)
        self.assertTrue(any("finding inventory" in error for error in errors))

    def test_v2_sphere_is_globe_relative(self) -> None:
        remediation = self.result["remediation_v2"]
        self.assertTrue(remediation["digital_sphere_globe_relative"])
        self.assertAlmostEqual(1.2, remediation["overview_shell_radius_px"] / remediation["overview_earth_radius_px"])
        self.assertTrue(remediation["local_sphere_hidden"])

    def test_v2_receipt_is_fail_closed(self) -> None:
        remediation = self.result["remediation_v2"]
        self.assertEqual(3, remediation["automatic_runs_required"])
        self.assertEqual(10000, remediation["background_minimum_hidden_ms"])
        self.assertTrue(remediation["reduced_motion_runtime_evidence_required"])
        self.assertTrue(remediation["incomplete_save_blocked"])

    def test_validator_rejects_accepting_first_run(self) -> None:
        errors = self.errors_after(lambda result: result["first_physical_run"].update({"accepted": True}))
        self.assertTrue(any("first physical-run evidence" in error for error in errors))

    def test_validator_rejects_missing_run_overclaim(self) -> None:
        errors = self.errors_after(lambda result: result["first_physical_run"].update({"automatic_performance_runs": 3}))
        self.assertTrue(any("first physical-run evidence" in error for error in errors))

    def test_validator_rejects_reduced_motion_overclaim(self) -> None:
        errors = self.errors_after(lambda result: result["first_physical_run"].update({"reduced_motion_active": True}))
        self.assertTrue(any("first physical-run evidence" in error for error in errors))

    def test_validator_rejects_lost_sphere_defect(self) -> None:
        errors = self.errors_after(lambda result: result["first_physical_run"].update({"digital_sphere_observation": "passed"}))
        self.assertTrue(any("first physical-run evidence" in error for error in errors))

    def test_validator_rejects_non_globe_relative_v2(self) -> None:
        errors = self.errors_after(lambda result: result["remediation_v2"].update({"digital_sphere_globe_relative": False}))
        self.assertTrue(any("remediation evidence" in error for error in errors))

    def test_validator_rejects_wrong_shell_ratio(self) -> None:
        errors = self.errors_after(lambda result: result["remediation_v2"].update({"overview_shell_ratio": 1.0}))
        self.assertTrue(any("remediation evidence" in error or "globe-relative" in error for error in errors))

    def test_validator_rejects_incomplete_save_weakening(self) -> None:
        errors = self.errors_after(lambda result: result["remediation_v2"].update({"incomplete_save_blocked": False}))
        self.assertTrue(any("remediation evidence" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"engine_selected": True}))
        self.assertTrue(any("must not select" in error for error in errors))

    def test_validator_rejects_architecture_authorization(self) -> None:
        errors = self.errors_after(lambda result: result["decision"].update({"production_architecture_authorized": True}))
        self.assertTrue(any("must not authorize" in error for error in errors))

    def test_validator_rejects_closed_apple_rerun_gate(self) -> None:
        errors = self.errors_after(lambda result: result["rerun_gate"].update({"apple_webkit_rerun_pending": False}))
        self.assertTrue(any("gates must remain pending" in error for error in errors))

    def test_validator_rejects_changed_archive_hash(self) -> None:
        errors = self.errors_after(lambda result: result["evidence_artifacts"].update({"v2_archive_sha256": "0" * 64}))
        self.assertTrue(any("artifact hash mismatch" in error for error in errors))

    def test_validator_rejects_private_endpoint_leak(self) -> None:
        def mutate(result: dict) -> None:
            result["scope"]["debug_endpoint"] = "http://" + ".".join(("100", "64", "0", "1"))
        errors = self.errors_after(mutate)
        self.assertTrue(any("private endpoint leaked" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
