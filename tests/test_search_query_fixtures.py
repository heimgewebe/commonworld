import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_search_query_fixtures import validate_search_query_fixtures


class SearchQueryFixtureTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        shutil.copytree(ROOT / "proofs", tmp_root / "proofs")
        return tmp_root

    def test_search_query_fixtures_validate(self) -> None:
        self.assertEqual([], validate_search_query_fixtures(ROOT))

    def test_search_query_fixtures_reject_wrong_top_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-query-fixtures.sample.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["fixtures"][0]["expected_top_ids"] = ["openstreetmap"]
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_search_query_fixtures(tmp_root)

        self.assertIn(
            "search query fixture repair-finds-repair-circle expected top ids ['openstreetmap'], got ['neighborhood-repair-circle-fixture']",
            errors,
        )

    def test_search_query_fixtures_reject_boundary_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-query-fixtures.sample.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["boundary"]["runtime_dependency"] = "search server"
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_search_query_fixtures(tmp_root)

        self.assertIn("search query fixtures boundary must keep no-runtime/no-authority semantics", errors)

    def test_search_query_fixtures_reject_model_weight_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = tmp_root / "proofs" / "search" / "search.js"
            path.write_text(path.read_text(encoding="utf-8").replace("weight: 40", "weight: 4", 1), encoding="utf-8")

            errors = validate_search_query_fixtures(tmp_root)

        self.assertIn("search query fixtures model drift: JS missing title/Title/40", errors)

    def test_search_query_fixtures_reject_missing_reason_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "search-query-fixtures.sample.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["fixtures"][0]["expected_reason_fields"]["neighborhood-repair-circle-fixture"].append("location")
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_search_query_fixtures(tmp_root)

        self.assertIn(
            "search query fixture repair-finds-repair-circle expected reason fields ['location'] for neighborhood-repair-circle-fixture, got ['title', 'summary', 'aspect', 'source']",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
