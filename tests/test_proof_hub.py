import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_proof_hub import (
    extract_proof_links,
    load_proof_surfaces,
    proof_surfaces_path,
    target_index_for_href,
    validate_proof_hub,
    validate_proof_surface_registry,
)


class ProofHubTests(unittest.TestCase):
    def test_static_proof_hub_validates(self) -> None:
        self.assertEqual([], validate_proof_hub(ROOT))

    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for path in ("index.html", "index.css"):
            shutil.copy2(ROOT / path, tmp_root / path)
        shutil.copytree(ROOT / "proofs", tmp_root / "proofs")
        return tmp_root

    def test_proof_surface_registry_validates(self) -> None:
        self.assertEqual([], validate_proof_surface_registry(ROOT))

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

    def test_target_index_for_href_maps_surface_href_to_index(self) -> None:
        self.assertEqual("proofs/map/index.html", target_index_for_href("./proofs/map/"))

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

    def test_registry_missing_file_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            proof_surfaces_path(tmp_root).unlink()

            errors = validate_proof_surface_registry(tmp_root)

        self.assertEqual(["missing proof surface registry: proofs/proof-surfaces.json"], errors)

    def test_registry_rejects_href_outside_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = proof_surfaces_path(tmp_root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["surfaces"][0]["href"] = "./outside/"
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_proof_surface_registry(tmp_root)

        self.assertIn("proof surface registry project-profile href must stay under ./proofs/", errors)

    def test_registry_rejects_duplicate_surface_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = proof_surfaces_path(tmp_root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["surfaces"].append(dict(data["surfaces"][0]))
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_proof_surface_registry(tmp_root)

        self.assertIn("proof surface registry duplicate id: project-profile", errors)

    def test_registry_rejects_href_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = proof_surfaces_path(tmp_root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["surfaces"][1]["target_index"] = "proofs/aether/index.html"
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_proof_surface_registry(tmp_root)

        self.assertIn(
            "proof surface registry map target_index must match href target: proofs/map/index.html",
            errors,
        )

    def test_registry_rejects_targets_outside_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            path = proof_surfaces_path(tmp_root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["surfaces"][0]["target_index"] = "index.html"
            path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_proof_surface_registry(tmp_root)

        self.assertIn("proof surface registry project-profile target_index must stay under proofs/", errors)


if __name__ == "__main__":
    unittest.main()
