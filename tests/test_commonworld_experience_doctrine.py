import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_commonworld_experience_doctrine import validate_commonworld_experience_doctrine
from scripts.validate_contracts import ROOT


class CommonworldExperienceDoctrineTests(unittest.TestCase):
    def copy_docs(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        return tmp_root

    def test_experience_doctrine_validates(self) -> None:
        self.assertEqual([], validate_commonworld_experience_doctrine(ROOT))

    def test_experience_doctrine_requires_familiar_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_docs(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "commonworld-experience-doctrine.md"
            path.write_text(path.read_text(encoding="utf-8").replace("must not require WASD", "may require specialist controls"), encoding="utf-8")

            errors = validate_commonworld_experience_doctrine(tmp_root)

        self.assertIn("experience doctrine missing required token: must not require WASD", errors)

    def test_experience_doctrine_requires_linear_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_docs(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "commonworld-experience-doctrine.md"
            path.write_text(path.read_text(encoding="utf-8").replace("semantically ordered linear equivalent", "spatial-only route"), encoding="utf-8")

            errors = validate_commonworld_experience_doctrine(tmp_root)

        self.assertIn("experience doctrine missing required token: semantically ordered linear equivalent", errors)

    def test_experience_doctrine_rejects_gamification_shortcut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_docs(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "commonworld-experience-doctrine.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nLeaderboards are allowed.\n", encoding="utf-8")

            errors = validate_commonworld_experience_doctrine(tmp_root)

        self.assertIn("experience doctrine contains forbidden token: leaderboards are allowed", errors)


if __name__ == "__main__":
    unittest.main()
