import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_proof_hub import (
    extract_proof_links,
    validate_proof_hub,
)
from scripts.validate_proof_surfaces import load_proof_surfaces


class ProofHubTests(unittest.TestCase):
    def test_static_proof_hub_validates(self) -> None:
        self.assertEqual([], validate_proof_hub(ROOT))

    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for path in ("index.html", "index.css"):
            shutil.copy2(ROOT / path, tmp_root / path)
        shutil.copytree(ROOT / "proofs", tmp_root / "proofs")
        return tmp_root

    def test_proof_hub_links_all_registered_surfaces(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for surface in load_proof_surfaces(ROOT):
            with self.subTest(proof_id=surface["id"]):
                self.assertIn(f'data-proof-link="{surface["id"]}"', html)
                self.assertIn(f'href="{surface["href"]}"', html)

    def test_extract_proof_links_pairs_data_proof_link_and_href(self) -> None:
        html = '<a data-proof-link="map" href="./proofs/map/"></a>'
        links, duplicates = extract_proof_links(html)
        self.assertEqual({"map": "./proofs/map/"}, links)
        self.assertEqual(set(), duplicates)

    def test_hub_rejects_swapped_surface_hrefs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace('href="./proofs/map/" data-proof-link="map"', 'href="./proofs/aether/" data-proof-link="map"')
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub href mismatch for map: expected ./proofs/map/, got ./proofs/aether/", errors)

    def test_hub_rejects_duplicate_data_proof_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace('data-proof-link="aether"', 'data-proof-link="map"')
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub duplicate data-proof-link: map", errors)


if __name__ == "__main__":
    unittest.main()
