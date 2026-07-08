import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_map_source_strategy import validate_map_source_strategy


class MapSourceStrategyTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        return tmp_root

    def test_map_source_strategy_validates(self) -> None:
        self.assertEqual([], validate_map_source_strategy(ROOT))

    def test_strategy_requires_no_second_tile_infrastructure_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "map-source-strategy.md"
            text = path.read_text(encoding="utf-8").replace(
                "commonworld must not operate a second tile infrastructure",
                "commonworld may operate an extra tile infrastructure",
            )
            path.write_text(text, encoding="utf-8")

            errors = validate_map_source_strategy(tmp_root)

        self.assertIn(
            "map source strategy missing required phrase: commonworld must not operate a second tile infrastructure",
            errors,
        )

    def test_strategy_requires_three_source_modes(self) -> None:
        text = (ROOT / "docs" / "blueprints" / "map-source-strategy.md").read_text(encoding="utf-8")
        for heading in ("### proof", "### staging", "### production"):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_strategy_excludes_commonworld_basemap_operations(self) -> None:
        text = (ROOT / "docs" / "blueprints" / "map-source-strategy.md").read_text(encoding="utf-8")
        self.assertIn("Tile generation", text)
        self.assertIn("Tile cache operations", text)
        self.assertIn("A separate operational map service", text)

    def test_strategy_records_t005_static_config_implementation(self) -> None:
        text = (ROOT / "docs" / "blueprints" / "map-source-strategy.md").read_text(encoding="utf-8")
        self.assertIn("COMMONWORLD-ATLAS-V1-T005 is implemented by `proofs/map/map-source.json`", text)
        self.assertIn("single replaceable boundary", text)
        self.assertIn("still avoids backend work, tile hosting, public write paths and weltgewebe handoff logic", text)


if __name__ == "__main__":
    unittest.main()
