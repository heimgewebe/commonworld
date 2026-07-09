import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_proof_hub import (
    extract_project_preview_cards,
    extract_proof_cards,
    extract_proof_links,
    load_catalog_snapshot_metrics,
    load_project_preview_entries,
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
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_proof_hub_links_all_registered_surfaces(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for surface in load_proof_surfaces(ROOT):
            with self.subTest(proof_id=surface["id"]):
                self.assertIn(f'data-proof-link="{surface["id"]}"', html)
                self.assertIn(f'href="{surface["href"]}"', html)
                self.assertIn(f'data-proof-role="{surface["role"]}"', html)
                self.assertIn(f'Role: {surface["role"]}', html)

    def test_extract_proof_links_pairs_data_proof_link_and_href(self) -> None:
        html = '<a data-proof-link="map" href="./proofs/map/"></a>'
        links, duplicates = extract_proof_links(html)
        self.assertEqual({"map": "./proofs/map/"}, links)
        self.assertEqual(set(), duplicates)

    def test_extract_proof_cards_reads_href_role_and_visible_text(self) -> None:
        html = (
            '<a data-proof-link="map" data-proof-role="render location-safe CommonProjects" href="./proofs/map/">'
            '<h2>Map</h2><p>Role: render location-safe CommonProjects</p></a>'
        )
        cards, duplicates = extract_proof_cards(html)
        self.assertEqual(set(), duplicates)
        self.assertEqual("./proofs/map/", cards["map"].href)
        self.assertEqual("render location-safe CommonProjects", cards["map"].role)
        self.assertEqual("Map", cards["map"].heading_text)
        self.assertIn("Map", cards["map"].visible_text)
        self.assertIn("render location-safe CommonProjects", cards["map"].visible_text)

    def test_hub_rejects_swapped_surface_hrefs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace('href="./proofs/map/"', 'href="./proofs/aether/"', 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub href mismatch for map: expected ./proofs/map/, got ./proofs/aether/", errors)

    def test_hub_rejects_swapped_surface_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace(
                'data-proof-role="render location-safe CommonProjects"',
                'data-proof-role="focus digital, hidden-location and hybrid Aether projections"',
                1,
            )
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn(
            "proof hub role mismatch for map: expected render location-safe CommonProjects, got focus digital, hidden-location and hybrid Aether projections",
            errors,
        )

    def test_hub_rejects_missing_visible_surface_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace("Role: render location-safe CommonProjects", "Registry-backed surface", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn(
            "proof hub visible role missing for map: expected render location-safe CommonProjects",
            errors,
        )

    def test_hub_rejects_heading_drift_even_when_title_appears_elsewhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace("<h2>Aether</h2>", "<h2>Digital surface</h2>", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub heading mismatch for aether: expected Aether, got Digital surface", errors)

    def test_hub_rejects_unregistered_proof_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            anchor = '      <section class="trust-panel"'
            extra_card = (
                '<a class="proof-card" href="./proofs/extra/" '
                'data-proof-link="extra" data-proof-role="extra">'
                '<h2>Extra</h2><p>Role: extra</p></a>'
            )
            self.assertIn(anchor, html)
            html = html.replace(anchor, f"        {extra_card}{anchor}", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub unregistered data-proof-link: extra", errors)

    def test_hub_rejects_duplicate_data_proof_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8")
            html = html.replace('data-proof-link="aether"', 'data-proof-link="map"')
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub duplicate data-proof-link: map", errors)

    def test_hub_requires_surface_taxonomy_panel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("Surface taxonomy", "Surface overview", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub HTML missing Surface taxonomy", errors)

    def test_hub_requires_card_surface_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("<dt>Surface type</dt>", "<dt>Surface class</dt>", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub surface type missing for project-profile", errors)

    def test_hub_requires_card_evidence_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("<dt>Evidence mode</dt>", "<dt>Evidence source</dt>", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub evidence mode missing for project-profile", errors)

    def test_catalog_snapshot_metrics_match_static_export(self) -> None:
        metrics = load_catalog_snapshot_metrics(ROOT)
        self.assertEqual(4, metrics["entries"])
        self.assertEqual(3, metrics["curation.fixture"])
        self.assertEqual(1, metrics["curation.candidate"])
        self.assertEqual(0, metrics["curation.curated"])
        self.assertEqual(0, metrics["curation.archived"])
        self.assertEqual(2, metrics["location.approximate"])
        self.assertEqual(1, metrics["location.exact"])
        self.assertEqual(1, metrics["location.hidden"])

    def test_hub_rejects_catalog_snapshot_count_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace(
                'data-catalog-metric="entries">4</dd>',
                'data-catalog-metric="entries">5</dd>',
                1,
            )
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub catalog metric mismatch for entries: expected 4 in 2 places, got 1", errors)

    def test_hub_rejects_missing_catalog_snapshot_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("not a live API, ranking system or publication queue", "not dynamic", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub catalog snapshot boundary missing", errors)

    def test_hub_rejects_catalog_snapshot_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace(
                'data-catalog-source="examples/commonworld/catalog-export.sample.json"',
                'data-catalog-source="/api/catalog"',
                1,
            )
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub catalog snapshot source missing or drifted", errors)

    def test_project_preview_cards_match_search_index_input(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        cards, duplicates = extract_project_preview_cards(html)
        entries = load_project_preview_entries(ROOT)
        self.assertEqual(set(), duplicates)
        self.assertEqual([entry["id"] for entry in entries], list(cards))
        for entry in entries:
            with self.subTest(project_id=entry["id"]):
                card = cards[entry["id"]]
                self.assertEqual(entry["curation_state"], card.attrs["data-project-curation"])
                self.assertEqual(entry["location_mode"], card.attrs["data-project-location-mode"])
                self.assertEqual(entry["project_path"], card.attrs["data-project-path"])
                self.assertIn(entry["title"], card.visible_text)
                self.assertIn(entry["summary"], card.visible_text)
                self.assertIn(entry["location_label"], card.visible_text)

    def test_hub_rejects_project_preview_title_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("OpenStreetMap", "Open Mapping Network", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub project preview visible token missing for openstreetmap: OpenStreetMap", errors)

    def test_hub_rejects_project_preview_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace(
                'data-project-preview-source="examples/commonworld/search-index-input.sample.json"',
                'data-project-preview-source="/api/projects"',
                1,
            )
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn("proof hub project preview source missing or drifted", errors)

    def test_hub_rejects_project_preview_order_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace(
                'data-project-id="neighborhood-repair-circle-fixture"',
                'data-project-id="solidarity-kitchen-fixture"',
                1,
            )
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertTrue(any(error.startswith("proof hub project preview order mismatch") for error in errors))

    def test_hub_requires_visual_hierarchy_sections(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="proof-surfaces"', html)
        self.assertIn('class="section-heading"', html)
        self.assertIn('id="proof-surfaces-title"', html)
        self.assertIn("Inspect the proofs before reading the catalog.", html)
        self.assertIn("Readable examples, not action cards.", html)

    def test_hub_rejects_missing_project_preview_hierarchy_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_valid_root(tmp_dir)
            html_path = tmp_root / "index.html"
            html = html_path.read_text(encoding="utf-8").replace("They do not join, submit, manage or publish anything.", "They are examples.", 1)
            html_path.write_text(html, encoding="utf-8")

            errors = validate_proof_hub(tmp_root)

        self.assertIn(
            "proof hub project preview hierarchy token missing: They do not join, submit, manage or publish anything.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
