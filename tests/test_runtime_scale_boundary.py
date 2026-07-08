import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_runtime_scale_boundary import validate_runtime_scale_boundary


class RuntimeScaleBoundaryTests(unittest.TestCase):
    def copy_docs(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        return tmp_root

    def test_runtime_scale_boundary_validates(self) -> None:
        self.assertEqual([], validate_runtime_scale_boundary(ROOT))

    def test_boundary_requires_plan_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_docs(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "runtime-scale-boundary.md"
            text = path.read_text(encoding="utf-8").replace("plan-before-build", "build-first")
            path.write_text(text, encoding="utf-8")

            errors = validate_runtime_scale_boundary(tmp_root)

        self.assertIn("runtime scale boundary missing required phrase: plan-before-build", errors)

    def test_boundary_rejects_backend_shortcut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_docs(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "runtime-scale-boundary.md"
            text = path.read_text(encoding="utf-8") + "\nImplement the API now. Automatic publication is allowed.\n"
            path.write_text(text, encoding="utf-8")

            errors = validate_runtime_scale_boundary(tmp_root)

        self.assertIn("runtime scale boundary includes forbidden shortcut: implement the api now", errors)
        self.assertIn("runtime scale boundary includes forbidden shortcut: automatic publication is allowed", errors)

    def test_boundary_keeps_runtime_read_only(self) -> None:
        text = (ROOT / "docs" / "blueprints" / "runtime-scale-boundary.md").read_text(encoding="utf-8")
        self.assertIn("read-only catalog API", text)
        self.assertIn("import candidate preview, not automatic publication", text)
        self.assertIn("weltgewebe write path", text)


if __name__ == "__main__":
    unittest.main()
