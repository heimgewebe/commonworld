import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_presence_axes import ROOT, validate_presence_axes


class PresenceAxesTests(unittest.TestCase):
    def copy_slice(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        for directory in ("assets", "catalog", "contracts", "docs"):
            shutil.copytree(ROOT / directory, root / directory)
        shutil.copy2(ROOT / "index.html", root / "index.html")
        shutil.copy2(ROOT / "LICENSE-DATA.md", root / "LICENSE-DATA.md")
        return root

    def mutate(self, root: Path, identifier: str, mutation) -> None:
        path = root / "catalog" / "projects" / f"{identifier}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        mutation(record)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_presence_axes_slice_validates(self) -> None:
        self.assertEqual([], validate_presence_axes(ROOT))

    def test_missing_canonical_odbl_exception_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_slice(tmp_dir)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"] = []
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            errors = validate_presence_axes(root)
        self.assertTrue(any("ODbL geometry exception" in error for error in errors))

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_slice(tmp_dir)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"][0]["source_ids"] = [
                "osm-node-13966522352",
                "osm-way-260066697",
            ]
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            errors = validate_presence_axes(root)
        self.assertTrue(any("ODbL geometry exception" in error for error in errors))

    def test_hidden_router_geometry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_slice(tmp_dir)
            self.mutate(root, "freifunk-hamburg", lambda record: record["presence"]["geographic"][1].update({"geometry": {"type": "Point", "coordinates": [10, 53]} }))
            errors = validate_presence_axes(root)
        self.assertTrue(any("private router locations must remain hidden" in error for error in errors))

    def test_approximate_anchor_must_keep_declared_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_slice(tmp_dir)
            self.mutate(root, "freifunk-hamburg", lambda record: record["presence"]["geographic"][0].update({"uncertainty_meters_min": 250}))
            errors = validate_presence_axes(root)
        self.assertTrue(any("five kilometres" in error for error in errors))

    def test_evidenced_parent_relation_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_slice(tmp_dir)
            self.mutate(root, "freifunk-hamburg", lambda record: record.update({"relations": []}))
            errors = validate_presence_axes(root)
        self.assertTrue(any("chapter-of relation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
