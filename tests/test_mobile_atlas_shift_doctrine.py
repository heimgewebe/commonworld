import unittest

from scripts.validate_contracts import ROOT
from scripts.validate_mobile_atlas_shift_doctrine import validate_mobile_atlas_shift_doctrine


class MobileAtlasShiftDoctrineTests(unittest.TestCase):
    def test_mobile_atlas_shift_doctrine_validates(self) -> None:
        self.assertEqual([], validate_mobile_atlas_shift_doctrine(ROOT))

    def test_horizon_is_not_navigation(self) -> None:
        text = (ROOT / "docs/blueprints/mobile-atlas-shift-interaction-model.md").read_text(encoding="utf-8")
        self.assertIn("`Horizont` is not a selectable mode", text)
        self.assertIn("no Horizont button", text)

    def test_common_project_has_projections(self) -> None:
        text = (ROOT / "docs/blueprints/mobile-atlas-shift-interaction-model.md").read_text(encoding="utf-8")
        self.assertIn("CommonProject", text)
        self.assertIn("map projection", text)
        self.assertIn("aether projection", text)
        self.assertIn("profile focus", text)


if __name__ == "__main__":
    unittest.main()
