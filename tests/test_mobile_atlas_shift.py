import unittest

from scripts.validate_contracts import ROOT
from scripts.validate_mobile_atlas_shift import validate_mobile_atlas_shift


class MobileAtlasShiftTests(unittest.TestCase):
    def test_mobile_atlas_shift_validates(self) -> None:
        self.assertEqual([], validate_mobile_atlas_shift(ROOT))

    def test_projection_switch_has_two_modes(self) -> None:
        html = (ROOT / "proofs/mobile-atlas-shift/index.html").read_text(encoding="utf-8")
        for mode in ("map", "aether"):
            with self.subTest(mode=mode):
                self.assertIn(f'data-mode-target="{mode}"', html)

    def test_hybrid_commons_appears_in_map_and_aether(self) -> None:
        html = (ROOT / "proofs/mobile-atlas-shift/index.html").read_text(encoding="utf-8")
        self.assertIn("code-pillar", html)
        self.assertIn("OSM Hamburg · Ortssignal", html)


if __name__ == "__main__":
    unittest.main()
