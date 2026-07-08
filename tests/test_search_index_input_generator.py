import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generate_search_index_input import build_search_index_input
from scripts.validate_contracts import ROOT
from scripts.validate_search_index_input import validate_search_index_input


class SearchIndexInputGeneratorTests(unittest.TestCase):
    def copy_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_search_index_input_validates(self) -> None:
        self.assertEqual([], validate_search_index_input(ROOT))

    def test_generator_matches_committed_sample(self) -> None:
        generated, errors = build_search_index_input(ROOT)
        self.assertEqual([], errors)
        committed = json.loads((ROOT / "examples" / "commonworld" / "search-index-input.sample.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, generated)

    def test_entries_only_use_allowed_fields(self) -> None:
        generated, errors = build_search_index_input(ROOT)
        self.assertEqual([], errors)
        for entry in generated["entries"]:
            self.assertEqual(
                [
                    "id",
                    "title",
                    "summary",
                    "aspects",
                    "curation_state",
                    "location_label",
                    "location_mode",
                    "project_path",
                    "profile_handoff_state",
                ],
                list(entry),
            )
            self.assertNotIn("coordinates", entry)
            self.assertNotIn("provenance", entry)
            self.assertNotIn("private_review_notes", entry)

    def test_stale_sample_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-index-input.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["entry_count"] = 999
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input(tmp_root)

        self.assertIn("search index input sample entry_count must match entries length", errors)
        self.assertIn("search index input sample is stale", errors)

    def test_private_review_notes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-index-input.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["entries"][0]["private_review_notes"] = "not allowed"
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input(tmp_root)

        self.assertIn("search index input entry 0 fields must exactly match the T014 allowed fields", errors)
        self.assertIn("search index input entry 0 must not include forbidden field: private_review_notes", errors)

    def test_aspects_must_only_expose_id_and_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-index-input.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["entries"][0]["aspects"][0]["confidence"] = 0.5
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_search_index_input(tmp_root)

        self.assertIn("search index input entry 0 aspects must only expose id and label", errors)


if __name__ == "__main__":
    unittest.main()
