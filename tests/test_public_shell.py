import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_shell import ROOT, validate_public_shell


class PublicShellTests(unittest.TestCase):
    def copy_shell(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        shutil.copy2(ROOT / "index.html", root / "index.html")
        shutil.copy2(ROOT / "index.css", root / "index.css")
        return root

    def test_public_shell_validates(self) -> None:
        self.assertEqual([], validate_public_shell(ROOT))

    def test_public_shell_rejects_old_proof_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8") + "\n<p>Proof hub</p>\n", encoding="utf-8")

            errors = validate_public_shell(root)

        self.assertIn("public shell contains obsolete or unsafe token: proof", errors)

    def test_public_shell_requires_digital_sphere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8").replace('class="digital-sphere"', 'class="orbit"'), encoding="utf-8")

            errors = validate_public_shell(root)

        self.assertIn('public shell missing required token: class="digital-sphere"', errors)

    def test_public_shell_has_no_script_or_form(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8").casefold()
        self.assertNotIn("<script", html)
        self.assertNotIn("<form", html)


if __name__ == "__main__":
    unittest.main()
