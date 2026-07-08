import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_search_proof import validate_search_proof


class StaticSearchProofTests(unittest.TestCase):
    def copy_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "proofs", tmp_root / "proofs")
        return tmp_root

    def test_static_search_proof_validates(self) -> None:
        self.assertEqual([], validate_search_proof(ROOT))

    def test_search_proof_rejects_submit_button(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "proofs" / "search" / "index.html"
            path.write_text(path.read_text(encoding="utf-8") + '\n<button type="submit">Submit</button>\n', encoding="utf-8")

            errors = validate_search_proof(tmp_root)

        self.assertIn("search proof HTML must not include forbidden token: type=\"submit\"", errors)

    def test_search_proof_rejects_runtime_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "proofs" / "search" / "search.js"
            path.write_text(path.read_text(encoding="utf-8") + '\nfetch("/api/search", {method: "POST"});\n', encoding="utf-8")

            errors = validate_search_proof(tmp_root)

        self.assertIn("search proof JS must not include forbidden token: fetch(\"/", errors)

    def test_search_proof_requires_static_sample_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "proofs" / "search" / "search.js"
            path.write_text(path.read_text(encoding="utf-8").replace("../../examples/commonworld/search-index-input.sample.json", "../../examples/commonworld/catalog-export.sample.json"), encoding="utf-8")

            errors = validate_search_proof(tmp_root)

        self.assertIn(
            "search proof JS missing required token: ../../examples/commonworld/search-index-input.sample.json",
            errors,
        )

    def test_search_proof_requires_traceable_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_surface(tmp_dir)
            path = tmp_root / "proofs" / "search" / "index.html"
            path.write_text(path.read_text(encoding="utf-8").replace("data-card-path", "data-card-source", 1), encoding="utf-8")

            errors = validate_search_proof(tmp_root)

        self.assertIn("search proof must expose source project_path for traceability", errors)


if __name__ == "__main__":
    unittest.main()
