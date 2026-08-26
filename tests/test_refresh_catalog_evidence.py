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
    def _init_repo(self, root: Path, files: dict[str, str]) -> None:
        subprocess.run(("git", "init", "-q"), cwd=root, check=True)
        subprocess.run(("git", "config", "user.email", "tests@example.invalid"), cwd=root, check=True)
        subprocess.run(("git", "config", "user.name", "Commonworld Tests"), cwd=root, check=True)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(("git", "add", "."), cwd=root, check=True)
        subprocess.run(("git", "commit", "-qm", "fixture"), cwd=root, check=True)

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
            self._init_repo(root, {"tracked.txt": "one\n"})
            first = refresh_catalog_evidence.workspace_snapshot(root)

            (root / "tracked.txt").write_text("two\n", encoding="utf-8")
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

    def test_refresh_in_place_refuses_protected_evidence_mutation(self) -> None:
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
                mock.patch.object(refresh_catalog_evidence, "_verify_in_place", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence._refresh_in_place(root, builders={}))
            verify.assert_not_called()

    def test_refresh_in_place_runs_safe_steps_in_order_before_verification(self) -> None:
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
                mock.patch.object(refresh_catalog_evidence, "_verify_in_place", return_value=0) as verify,
            ):
                self.assertEqual(0, refresh_catalog_evidence._refresh_in_place(root, builders={}))

        self.assertEqual(
            [step.name for step in refresh_catalog_evidence.SAFE_REFRESH_STEPS],
            seen,
        )
        verify.assert_called_once_with(root, builders={})

    def test_check_mutation_is_confined_to_isolated_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._init_repo(root, {"tracked.txt": "original\n"})

            def mutate_isolated(isolated: Path, mode: str):
                self.assertEqual("--check", mode)
                (isolated / "tracked.txt").write_text("mutated\n", encoding="utf-8")
                (isolated / "new.txt").write_text("new\n", encoding="utf-8")
                return subprocess.CompletedProcess(["check"], 1, "", "simulated mutation\n")

            with mock.patch.object(
                refresh_catalog_evidence,
                "_run_isolated_mode",
                side_effect=mutate_isolated,
            ):
                self.assertEqual(1, refresh_catalog_evidence.verify(root))

            self.assertEqual("original\n", (root / "tracked.txt").read_text(encoding="utf-8"))
            self.assertFalse((root / "new.txt").exists())

    def test_public_refresh_does_not_publish_when_safe_steps_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_relative = "docs/evidence/catalog-recovery-scale-v1.json"
            self._init_repo(root, {evidence_relative: '{"value":1}\n'})

            def fail_safe_steps(isolated: Path) -> bool:
                (isolated / evidence_relative).write_text('{"value":2}\n', encoding="utf-8")
                return False

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=fail_safe_steps,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_not_called()
            self.assertEqual('{"value":1}\n', (root / evidence_relative).read_text(encoding="utf-8"))

    def test_machine_refresh_check_runs_only_machine_derived_validators(self) -> None:
        seen: list[str] = []

        def run_step(step, *, root: Path) -> bool:
            seen.append(step.name)
            return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "workspace_snapshot",
                    return_value="same",
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "check_deterministic_outputs",
                    return_value=[],
                ),
                mock.patch.object(refresh_catalog_evidence, "_run_step", side_effect=run_step),
            ):
                self.assertEqual(
                    0,
                    refresh_catalog_evidence._verify_machine_refresh_outputs_in_place(root),
                )

        self.assertEqual(
            [
                step.name
                for step in refresh_catalog_evidence.VERIFY_STEPS
                if step.evidence_class == "machine-derived"
            ],
            seen,
        )

    def test_machine_refresh_check_failure_prevents_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_relative = "docs/evidence/catalog-recovery-scale-v1.json"
            self._init_repo(root, {evidence_relative: '{"value":1}\n'})

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / evidence_relative).write_text('{"value":2}\n', encoding="utf-8")
                return True

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(
                        ["machine-check"], 1, "", "machine validation failed\n"
                    ),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_not_called()
            self.assertEqual('{"value":1}\n', (root / evidence_relative).read_text(encoding="utf-8"))

    def test_successful_refresh_publishes_allowed_machine_outputs_before_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_relative = "docs/evidence/catalog-recovery-scale-v1.json"
            self._init_repo(root, {evidence_relative: '{"value":1}\n'})

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / evidence_relative).write_text('{"value":2}\n', encoding="utf-8")
                (isolated / "index.html").write_text("<main>generated</main>\n", encoding="utf-8")
                return True

            def verify_source(source: Path) -> int:
                self.assertEqual('{"value":2}\n', (source / evidence_relative).read_text(encoding="utf-8"))
                self.assertEqual("<main>generated</main>\n", (source / "index.html").read_text(encoding="utf-8"))
                return 0

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "verify",
                    side_effect=verify_source,
                ) as verify,
            ):
                self.assertEqual(0, refresh_catalog_evidence.refresh(root))

            verify.assert_called_once_with(root)

    def test_stale_observational_verify_keeps_published_machine_outputs_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_relative = "docs/evidence/catalog-recovery-scale-v1.json"
            self._init_repo(root, {evidence_relative: '{"value":1}\n'})

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / evidence_relative).write_text('{"value":2}\n', encoding="utf-8")
                return True

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=1) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_called_once_with(root)
            self.assertEqual('{"value":2}\n', (root / evidence_relative).read_text(encoding="utf-8"))

    def test_refresh_refuses_unexpected_output_path_without_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unexpected = "scripts/unexpected.py"
            self._init_repo(root, {unexpected: "before\n"})

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / unexpected).write_text("after\n", encoding="utf-8")
                return True

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_not_called()
            self.assertEqual("before\n", (root / unexpected).read_text(encoding="utf-8"))

    def test_refresh_refuses_rewrite_of_preexisting_untracked_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._init_repo(root, {"tracked.txt": "base\n"})
            untracked = root / "index.html"
            untracked.write_text("mine\n", encoding="utf-8")

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / "index.html").write_text("generated\n", encoding="utf-8")
                return True

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_not_called()
            self.assertEqual("mine\n", untracked.read_text(encoding="utf-8"))

    def test_refresh_refuses_publication_after_concurrent_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_relative = "docs/evidence/catalog-recovery-scale-v1.json"
            self._init_repo(root, {"tracked.txt": "before\n", evidence_relative: '{"value":1}\n'})

            def mutate_isolated(isolated: Path) -> bool:
                (isolated / evidence_relative).write_text('{"value":2}\n', encoding="utf-8")
                (root / "tracked.txt").write_text("concurrent\n", encoding="utf-8")
                return True

            with (
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_safe_refresh_steps",
                    side_effect=mutate_isolated,
                ),
                mock.patch.object(
                    refresh_catalog_evidence,
                    "_run_isolated_mode",
                    return_value=subprocess.CompletedProcess(["machine-check"], 0, "", ""),
                ),
                mock.patch.object(refresh_catalog_evidence, "verify", return_value=0) as verify,
            ):
                self.assertEqual(1, refresh_catalog_evidence.refresh(root))

            verify.assert_not_called()
            self.assertEqual("concurrent\n", (root / "tracked.txt").read_text(encoding="utf-8"))
            self.assertEqual('{"value":1}\n', (root / evidence_relative).read_text(encoding="utf-8"))

    def test_refresh_output_allowlist_is_explicit(self) -> None:
        self.assertTrue(refresh_catalog_evidence._is_allowed_refresh_output("index.html"))
        self.assertTrue(refresh_catalog_evidence._is_allowed_refresh_output("catalog/pages/2.html"))
        self.assertTrue(refresh_catalog_evidence._is_allowed_refresh_output("catalog/runtime/manifest.v2.json"))
        self.assertTrue(refresh_catalog_evidence._is_allowed_refresh_output("releases/abc/index.html"))
        self.assertTrue(
            refresh_catalog_evidence._is_allowed_refresh_output(
                "assets/map/commonworld-country-boundaries.geojson"
            )
        )
        self.assertTrue(
            refresh_catalog_evidence._is_allowed_refresh_output(
                "docs/evidence/catalog-recovery-scale-v1.json"
            )
        )
        self.assertFalse(refresh_catalog_evidence._is_allowed_refresh_output("catalog/projects/example.json"))
        self.assertFalse(refresh_catalog_evidence._is_allowed_refresh_output("scripts/validate_catalog.py"))
        self.assertFalse(
            refresh_catalog_evidence._is_allowed_refresh_output(
                "docs/evidence/catalog-delivery-benchmark-v1.json"
            )
        )


if __name__ == "__main__":
    unittest.main()
