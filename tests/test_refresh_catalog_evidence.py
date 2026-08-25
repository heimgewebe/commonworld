from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_catalog_evidence.py"
SPEC = importlib.util.spec_from_file_location("refresh_catalog_evidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
refresh_catalog_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh_catalog_evidence
SPEC.loader.exec_module(refresh_catalog_evidence)


class RefreshCatalogEvidenceTests(unittest.TestCase):
    def test_cli_requires_exactly_one_mode(self) -> None:
        with self.assertRaises(SystemExit):
            refresh_catalog_evidence.parse_args([])
        self.assertTrue(refresh_catalog_evidence.parse_args(["--check"]).check)
        self.assertTrue(refresh_catalog_evidence.parse_args(["--refresh"]).refresh)
        with self.assertRaises(SystemExit):
            refresh_catalog_evidence.parse_args(["--check", "--refresh"])

    def test_refresh_inventory_excludes_observational_and_review_writers(self) -> None:
        commands = "\n".join(" ".join(step.argv) for step in refresh_catalog_evidence.SAFE_REFRESH_STEPS)
        self.assertNotIn("generate_locale_release_evidence.py", commands)
        self.assertNotIn("measure_catalog_delivery_browser.mjs", commands)
        self.assertNotIn("measure_catalog_platform_scaling.py", commands)
        self.assertIn("measure_catalog_recovery.py", commands)
        self.assertIn("measure_catalog_hierarchy_v2.py", commands)
        self.assertIn("measure_release_snapshot_lifecycle.py", commands)
        self.assertEqual(
            [
                "public-build",
                "catalog-recovery-evidence",
                "catalog-hierarchy-evidence",
                "release-snapshot-lifecycle-evidence",
            ],
            [step.name for step in refresh_catalog_evidence.SAFE_REFRESH_STEPS],
        )

    def test_verify_inventory_includes_canonical_scale_masterplan_check(self) -> None:
        self.assertIn(
            "catalog-scale-masterplan",
            [step.name for step in refresh_catalog_evidence.VERIFY_STEPS],
        )

    def test_protected_snapshot_detects_file_and_tree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "docs/evidence/catalog-delivery-benchmark-v1.json"
            tree_path = root / "docs/evidence/locale-releases"
            file_path.parent.mkdir(parents=True)
            tree_path.mkdir(parents=True)
            file_path.write_text("{}\n", encoding="utf-8")
            (tree_path / "es.json").write_text('{"locale":"es"}\n', encoding="utf-8")

            first = refresh_catalog_evidence.protected_snapshot(root)
            file_path.write_text('{"changed":true}\n', encoding="utf-8")
            (tree_path / "es.json").write_text('{"locale":"es","changed":true}\n', encoding="utf-8")
            second = refresh_catalog_evidence.protected_snapshot(root)

            self.assertNotEqual(
                first["docs/evidence/catalog-delivery-benchmark-v1.json"],
                second["docs/evidence/catalog-delivery-benchmark-v1.json"],
            )
            self.assertNotEqual(
                first["docs/evidence/locale-releases"],
                second["docs/evidence/locale-releases"],
            )

    def test_workspace_snapshot_detects_tracked_and_untracked_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(("git", "init", "-q"), cwd=root, check=True)
            tracked = root / "tracked.txt"
            tracked.write_text("one\n", encoding="utf-8")
            subprocess.run(("git", "add", "tracked.txt"), cwd=root, check=True)
            first = refresh_catalog_evidence.workspace_snapshot(root)

            tracked.write_text("two\n", encoding="utf-8")
            second = refresh_catalog_evidence.workspace_snapshot(root)
            self.assertNotEqual(first, second)

            untracked = root / "untracked.txt"
            untracked.write_text("three\n", encoding="utf-8")
            third = refresh_catalog_evidence.workspace_snapshot(root)
            self.assertNotEqual(second, third)

            untracked.write_text("four\n", encoding="utf-8")
            fourth = refresh_catalog_evidence.workspace_snapshot(root)
            self.assertNotEqual(third, fourth)

    def test_deterministic_output_check_is_object_based_and_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = {
                "catalog-recovery": {"kind": "recovery", "value": 1},
                "catalog-hierarchy": {"kind": "hierarchy", "value": 2},
                "release-snapshot-lifecycle": {"kind": "lifecycle", "value": 3},
            }
            builders = {
                name: (lambda payload=payload: payload)
                for name, payload in expected.items()
            }
            for name, relative in refresh_catalog_evidence.DETERMINISTIC_OUTPUTS.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(expected[name], indent=2) + "\n", encoding="utf-8")

            self.assertEqual(
                [],
                refresh_catalog_evidence.check_deterministic_outputs(root, builders=builders),
            )

            drift_path = root / refresh_catalog_evidence.DETERMINISTIC_OUTPUTS["catalog-hierarchy"]
            drift_path.write_text('{"kind":"hierarchy","value":999}\n', encoding="utf-8")
            failures = refresh_catalog_evidence.check_deterministic_outputs(root, builders=builders)
            self.assertEqual(["catalog-hierarchy: deterministic evidence drift"], failures)

    def test_refresh_refuses_unexpected_protected_evidence_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protected = root / "docs/evidence/catalog-delivery-benchmark-v1.json"
            protected.parent.mkdir(parents=True)
            protected.write_text("{}\n", encoding="utf-8")
            call_count = 0

            def run_step(_step, *, root: Path) -> bool:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    protected.write_text('{"unexpected":true}\n', encoding="utf-8")
                return True

            with (
                mock.patch.object(refresh_catalog_evidence, "_run_step", side_effect=run_step),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root, builders={}))
            verify.assert_not_called()

    def test_refresh_runs_safe_steps_in_order_before_verification(self) -> None:
        seen: list[str] = []

        def run_step(step, *, root: Path) -> bool:
            seen.append(step.name)
            return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(refresh_catalog_evidence, "_run_step", side_effect=run_step),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "protected_snapshot",
                    return_value={"protected": "same"},
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(0, refresh_catalog_evidence.refresh(root, builders={}))

        self.assertEqual(
            [step.name for step in refresh_catalog_evidence.SAFE_REFRESH_STEPS],
            seen,
        )
        verify.assert_called_once_with(root, builders={})


if __name__ == "__main__":
    unittest.main()
