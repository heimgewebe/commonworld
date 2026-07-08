import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generate_catalog_export import build_catalog_export, main, stable_json
from scripts.validate_contracts import ROOT


class CatalogExportGeneratorTests(unittest.TestCase):
    def copy_examples(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_generator_matches_committed_sample(self) -> None:
        export, errors = build_catalog_export(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(
            (ROOT / "examples" / "commonworld" / "catalog-export.sample.json").read_text(encoding="utf-8"),
            stable_json(export),
        )

    def test_generator_tracks_seed_manifest_order(self) -> None:
        export, errors = build_catalog_export(ROOT)
        manifest = json.loads((ROOT / "examples" / "commonworld" / "seed-projects.json").read_text(encoding="utf-8"))

        self.assertEqual([], errors)
        self.assertEqual(
            manifest["project_paths"],
            [entry["project_path"].removeprefix("examples/commonworld/") for entry in export["entries"]],
        )


    def test_check_uses_output_relative_to_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_examples(tmp_dir)

            result = main(["--root", str(tmp_root), "--check"])

        self.assertEqual(0, result)

    def test_check_detects_stale_output_in_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_examples(tmp_dir)
            output_path = tmp_root / "examples" / "commonworld" / "catalog-export.sample.json"
            output_path.write_text("{}\n", encoding="utf-8")

            result = main(["--root", str(tmp_root), "--check"])

        self.assertEqual(1, result)

    def test_generator_rejects_paths_outside_projects_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_examples(tmp_dir)
            manifest_path = tmp_root / "examples" / "commonworld" / "seed-projects.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_paths"] = ["../catalog-export.sample.json"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            _export, errors = build_catalog_export(tmp_root)

        self.assertIn(
            "catalog export source manifest project_paths entries must stay inside examples/commonworld/projects",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
