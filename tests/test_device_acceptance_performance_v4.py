import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_device_acceptance_performance_v4 import (
    ROOT,
    load_result,
    validate_device_acceptance_performance_v4,
)


class DeviceAcceptancePerformanceV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load_result()

    def errors_after(self, mutate, report_suffix: str = "") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            research = root / "docs/research"
            research.mkdir(parents=True)
            result = copy.deepcopy(self.result)
            mutate(result)
            (research / "device-acceptance-performance-v4.result.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            report = (ROOT / "docs/research/device-acceptance-performance-v4.md").read_text()
            (research / "device-acceptance-performance-v4.md").write_text(report + report_suffix)
            for name in ("index.html", "404.html"):
                source = ROOT / name
                if source.is_file():
                    shutil.copy2(source, root / name)
            return validate_device_acceptance_performance_v4(root)

    def test_proof_validates(self) -> None:
        self.assertEqual([], validate_device_acceptance_performance_v4(ROOT))

    def test_physical_v3_remains_incomplete(self) -> None:
        physical = self.result["physical_v3_receipt"]
        self.assertEqual(1, physical["automatic_runs_completed"])
        self.assertEqual(3, physical["automatic_runs_required"])
        self.assertEqual("incomplete", physical["overall_verdict"])

    def test_render_counts_do_not_claim_idle_loop(self) -> None:
        interpretation = self.result["physical_v3_receipt"]["interpretation"]
        self.assertFalse(interpretation["continuous_idle_rendering_proven"])
        self.assertTrue(interpretation["render_counts_include_benchmark_work"])

    def test_same_workload_ab_improves_both_profiles(self) -> None:
        ab = self.result["same_workload_ab"]
        self.assertGreater(ab["v4"]["planet_fps"], ab["v3"]["planet_fps"])
        self.assertGreater(ab["v4"]["local_fps"], ab["v3"]["local_fps"])
        self.assertEqual(0, ab["v4"]["overlay_geometry_writes"])
        self.assertEqual(3, ab["v4"]["navigation_state_writes"])

    def test_installed_v4_software_gate_passes(self) -> None:
        installed = self.result["v4_installed_proof"]
        self.assertTrue(installed["performance_gate_pass"])
        self.assertGreaterEqual(installed["planet_median_fps"], 30)
        self.assertGreaterEqual(installed["local_median_fps"], 30)
        self.assertFalse(installed["physical_device_tested"])

    def test_physical_v4_and_accessibility_remain_open(self) -> None:
        gates = self.result["open_gates"]
        self.assertTrue(gates["physical_apple_webkit_v4_three_runs"])
        self.assertTrue(gates["physical_android_chrome_v4_three_runs"])
        self.assertTrue(gates["voiceover_or_talkback"])

    def test_validator_rejects_fake_three_run_physical_receipt(self) -> None:
        errors = self.errors_after(
            lambda result: result["physical_v3_receipt"].update({"automatic_runs_completed": 3})
        )
        self.assertTrue(any("one of three runs" in error for error in errors))

    def test_validator_rejects_idle_loop_overclaim(self) -> None:
        errors = self.errors_after(
            lambda result: result["physical_v3_receipt"]["interpretation"].update(
                {"continuous_idle_rendering_proven": True}
            )
        )
        self.assertTrue(any("interpretation" in error for error in errors))

    def test_validator_rejects_direct_v3_v4_comparability(self) -> None:
        errors = self.errors_after(
            lambda result: result["physical_v3_receipt"]["interpretation"].update(
                {"directly_comparable_to_v4_measurement": True}
            )
        )
        self.assertTrue(any("interpretation" in error for error in errors))

    def test_validator_rejects_unconfirmed_map_render(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_changes"].update({"map_render_event_confirmed": False})
        )
        self.assertTrue(any("benchmark or optimization" in error for error in errors))

    def test_validator_rejects_unaligned_browser_frame(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_changes"].update({"browser_frame_aligned": False})
        )
        self.assertTrue(any("benchmark or optimization" in error for error in errors))

    def test_validator_rejects_uncoalesced_navigation_state(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_changes"].update({"navigation_state_write_debounce_ms": 0})
        )
        self.assertTrue(any("benchmark or optimization" in error for error in errors))

    def test_validator_rejects_ab_regression(self) -> None:
        errors = self.errors_after(
            lambda result: result["same_workload_ab"]["v4"].update({"planet_fps": 10})
        )
        self.assertTrue(any("outperform" in error or "ratio" in error for error in errors))

    def test_validator_handles_zero_baseline_without_crashing(self) -> None:
        errors = self.errors_after(
            lambda result: result["same_workload_ab"]["v3"].update({"planet_fps": 0})
        )
        self.assertTrue(any("invalid v3 A/B measurement" in error for error in errors))

    def test_validator_handles_zero_state_write_baseline_without_crashing(self) -> None:
        errors = self.errors_after(
            lambda result: result["same_workload_ab"]["v3"].update({"navigation_state_writes": 0})
        )
        self.assertTrue(any("navigation-state-write evidence" in error for error in errors))

    def test_validator_rejects_idle_rendering(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_installed_proof"].update({"idle_overlay_render_delta": 1})
        )
        self.assertTrue(any("idle deltas" in error for error in errors))

    def test_validator_rejects_physical_claim_for_software_proof(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_installed_proof"].update({"physical_device_tested": True})
        )
        self.assertTrue(any("non-physical" in error for error in errors))

    def test_validator_rejects_below_gate_installed_proof(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_installed_proof"].update({"planet_median_fps": 29})
        )
        self.assertTrue(any("below the declared 30 FPS" in error for error in errors))

    def test_validator_rejects_public_endpoint(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_installed_proof"].update(
                {"private_endpoint_in_repository": True}
            )
        )
        self.assertTrue(any("network privacy" in error for error in errors))

    def test_validator_rejects_continuous_health_claim(self) -> None:
        errors = self.errors_after(
            lambda result: result["v4_installed_proof"].update(
                {"continuous_health_not_claimed": False}
            )
        )
        self.assertTrue(any("continuous health" in error for error in errors))

    def test_validator_rejects_closed_physical_gate(self) -> None:
        errors = self.errors_after(
            lambda result: result["open_gates"].update(
                {"physical_apple_webkit_v4_three_runs": False}
            )
        )
        self.assertTrue(any("open-gate inventory" in error for error in errors))

    def test_validator_rejects_engine_selection(self) -> None:
        errors = self.errors_after(
            lambda result: result["decision"].update({"engine_selected": True})
        )
        self.assertTrue(any("decision boundary" in error for error in errors))

    def test_validator_rejects_changed_archive_hash(self) -> None:
        errors = self.errors_after(
            lambda result: result["evidence_artifacts"].update({"archive_sha256": "0" * 64})
        )
        self.assertTrue(any("evidence hash" in error for error in errors))

    def test_validator_rejects_private_tailnet_address(self) -> None:
        address = ".".join(("100", "64", "0", "1"))
        errors = self.errors_after(lambda result: None, f"\nPrivate endpoint {address}\n")
        self.assertTrue(any("private physical receipt material" in error for error in errors))

    def test_validator_rejects_raw_user_agent(self) -> None:
        user_agent = "Mozilla" + "/" + "5.0 private raw header"
        errors = self.errors_after(lambda result: None, f"\n{user_agent}\n")
        self.assertTrue(any("private physical receipt material" in error for error in errors))

    def test_validator_rejects_raw_session_key(self) -> None:
        errors = self.errors_after(lambda result: None, '\n{"session_id": "private"}\n')
        self.assertTrue(any("private physical receipt material" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
