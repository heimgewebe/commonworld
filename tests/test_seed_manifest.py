import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_seed_manifest import (
    expected_seed_paths,
    path_is_relative_to,
    seed_manifest_path,
    validate_seed_manifest,
)


class SeedManifestContractTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for directory_name in ("contracts", "examples"):
            shutil.copytree(ROOT / directory_name, tmp_root / directory_name)
        return tmp_root

    def test_shared_seed_manifest_validates(self) -> None:
        self.assertEqual([], validate_seed_manifest(ROOT))

    def test_path_is_relative_to_uses_explicit_relative_check(self) -> None:
        parent = ROOT / "examples" / "commonworld" / "projects"
        self.assertTrue(path_is_relative_to(parent / "openstreetmap.json", parent))
        self.assertFalse(path_is_relative_to(ROOT / "examples" / "commonworld" / "seed-projects.json", parent))

    def test_seed_manifest_exactly_lists_project_examples(self) -> None:
        manifest = json.loads(seed_manifest_path(ROOT).read_text(encoding="utf-8"))
        self.assertEqual(expected_seed_paths(ROOT), manifest["project_paths"])

    def test_missing_manifest_reports_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            seed_manifest_path(tmp_root).unlink()

            errors = validate_seed_manifest(tmp_root)

        self.assertEqual(["missing shared seed manifest: examples/commonworld/seed-projects.json"], errors)

    def test_seed_manifest_rejects_parent_directory_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            manifest_path = seed_manifest_path(tmp_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_paths"] = ["../outside.json"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            errors = validate_seed_manifest(tmp_root)

        self.assertIn("seed-projects.json project_paths entries must stay inside examples/commonworld", errors)

    def test_seed_manifest_rejects_non_project_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            manifest_path = seed_manifest_path(tmp_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_paths"] = ["seed-projects.json"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            errors = validate_seed_manifest(tmp_root)

        self.assertIn(
            "seed-projects.json project_paths entries must point into examples/commonworld/projects",
            errors,
        )

    def test_seed_manifest_rejects_non_string_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            manifest_path = seed_manifest_path(tmp_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_paths"] = [42]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            errors = validate_seed_manifest(tmp_root)

        self.assertIn("seed-projects.json project_paths entries must be strings", errors)


if __name__ == "__main__":
    unittest.main()
