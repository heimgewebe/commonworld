import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_canonical_plan import ROOT, validate_canonical_plan


class CanonicalPlanTests(unittest.TestCase):
    def copy_repository_core(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for name in ("README.md", "AGENTS.md", "requirements-dev.txt"):
            shutil.copy2(ROOT / name, tmp_root / name)
        for directory in ("docs", "contracts", ".github"):
            source = ROOT / directory
            if source.exists():
                shutil.copytree(source, tmp_root / directory)
        for directory in ("scripts", "tests"):
            source = ROOT / directory
            shutil.copytree(source, tmp_root / directory)
        shutil.copy2(ROOT / "package.json", tmp_root / "package.json")
        return tmp_root

    def test_canonical_plan_validates(self) -> None:
        self.assertEqual([], validate_canonical_plan(ROOT))

    def test_semantic_zoom_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / "docs" / "blueprints" / "commonworld-masterplan.md"
            path.write_text(path.read_text(encoding="utf-8").replace("## Semantischer Zoom", "## Maßstab"), encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertIn("canonical globe plan missing required token: ## Semantischer Zoom", errors)

    def test_commit_bound_production_readback_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / "docs" / "blueprints" / "commonworld-masterplan.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "### Commitgebundener Produktions-Readback v1",
                    "### Ungebundene Produktionsprüfung",
                ),
                encoding="utf-8",
            )

            errors = validate_canonical_plan(root)

        self.assertIn(
            "canonical globe plan missing required token: ### Commitgebundener Produktions-Readback v1",
            errors,
        )

    def test_parallel_blueprint_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            (root / "docs" / "blueprints" / "second-plan.md").write_text("# competing plan\n", encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertTrue(any(error.startswith("active blueprint inventory mismatch") for error in errors))

    def test_required_check_catalog_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            (root / ".github" / "grabowski-required-checks.json").unlink()

            errors = validate_canonical_plan(root)

        self.assertIn("missing Grabowski required-check catalog", errors)

    def test_required_check_catalog_must_match_workflow_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / ".github" / "grabowski-required-checks.json"
            path.write_text('{"schema_version": 1, "required_checks": ["validate"]}\n', encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertIn(
            "Grabowski required-check catalog must require exactly the contracts check",
            errors,
        )

    def test_browser_smoke_command_must_use_bound_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / "package.json"
            package = json.loads(path.read_text(encoding="utf-8"))
            package["scripts"]["smoke:browser"] = "node scripts/smoke_public_browser.mjs"
            path.write_text(json.dumps(package), encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertIn("package.json must expose the bound browser smoke runner", errors)

    def test_browser_smoke_runner_must_validate_fresh_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / "scripts" / "run_browser_smoke.py"
            path.write_text(
                path.read_text(encoding="utf-8").replace("'--smoke-result', str(actual)", "str(actual)"),
                encoding="utf-8",
            )

            errors = validate_canonical_plan(root)

        self.assertIn("bound browser smoke runner steps or order mismatch", errors)

    def test_browser_smoke_runner_must_keep_step_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / "scripts" / "run_browser_smoke.py"
            source = path.read_text(encoding="utf-8")
            first = "run(['node', 'scripts/smoke_proposal_browser.mjs'])"
            second = "run(['node', 'scripts/smoke_focus_overlay_browser.mjs'])"
            path.write_text(source.replace(first, '__SWAP__').replace(second, first).replace('__SWAP__', second), encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertIn("bound browser smoke runner steps or order mismatch", errors)

    def test_validation_workflow_must_keep_contracts_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            path = root / ".github" / "workflows" / "validate.yml"
            path.write_text(path.read_text(encoding="utf-8").replace("  contracts:\n", "  renamed:\n"), encoding="utf-8")

            errors = validate_canonical_plan(root)

        self.assertIn("validation workflow must expose the required contracts job", errors)

    def test_obsolete_proof_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_repository_core(tmp_dir)
            (root / "proofs").mkdir()

            errors = validate_canonical_plan(root)

        self.assertIn("obsolete active path must be removed: proofs", errors)


if __name__ == "__main__":
    unittest.main()
