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
