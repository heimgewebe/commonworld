import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_seed_baseline import ROOT, validate_public_seed_baseline


class PublicSeedBaselineTests(unittest.TestCase):
    def copy_catalog(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        shutil.copytree(ROOT / "catalog", root / "catalog")
        shutil.copytree(ROOT / "contracts", root / "contracts")
        return root

    def mutate(self, root: Path, identifier: str, mutation) -> None:
        path = root / "catalog" / "projects" / f"{identifier}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        mutation(record)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_seed_baseline_validates(self) -> None:
        self.assertEqual([], validate_public_seed_baseline(ROOT))

    def test_seed_geographic_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_catalog(tmp_dir)
            self.mutate(root, "debian", lambda record: record.setdefault("presence", {}).update({"geographic": [{"mode": "exact", "geometry": {"type": "Point", "coordinates": [0, 0]}}]}))
            errors = validate_public_seed_baseline(root)
        self.assertTrue(any("must remain without geographic locations" in error for error in errors))

    def test_seed_geography_or_relation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_catalog(tmp_dir)
            self.mutate(root, "freifunk", lambda record: record.setdefault("relations", []).append({"target_id": "debian", "type": "cooperates-with", "source_ids": ["freifunk-about"]}))
            errors = validate_public_seed_baseline(root)
        self.assertTrue(any("must remain relation-free" in error for error in errors))

    def test_new_mixed_presence_records_do_not_change_seed_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_catalog(tmp_dir)
            path = root / "catalog" / "projects" / "additional-geographic.json"
            path.write_text('{"id":"additional-geographic"}\n', encoding="utf-8")
            errors = validate_public_seed_baseline(root)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
