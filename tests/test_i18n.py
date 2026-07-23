import json
import unittest
from pathlib import Path

from scripts.commonworld_i18n import localize_records
from scripts.render_public_shell import load_records, render_method, render_shell

ROOT = Path(__file__).resolve().parents[1]


class InternationalizationTests(unittest.TestCase):
    def test_english_overlay_covers_catalog_without_replacing_fact_truth(self) -> None:
        canonical = load_records(ROOT)
        localized = localize_records(canonical, "en", ROOT)
        self.assertEqual([record["id"] for record in canonical], [record["id"] for record in localized])
        self.assertEqual(len(canonical), len(localized))
        for source, translated in zip(canonical, localized, strict=True):
            self.assertEqual(source["id"], translated["id"])
            self.assertEqual(source["curation"], translated["curation"])
            self.assertEqual(source["activity"], translated["activity"])
            self.assertEqual(
                [(entry.get("mode"), entry.get("geometry"), entry.get("uncertainty_meters_min")) for entry in source["presence"]["geographic"]],
                [(entry.get("mode"), entry.get("geometry"), entry.get("uncertainty_meters_min")) for entry in translated["presence"]["geographic"]],
            )
            self.assertEqual(
                [(entry["type"], entry["url"]) for entry in source["links"]],
                [(entry["type"], entry["url"]) for entry in translated["links"]],
            )
            self.assertEqual(
                [entry["url"] for entry in source["provenance"]["sources"]],
                [entry["url"] for entry in translated["provenance"]["sources"]],
            )
            self.assertTrue(translated["summary"].strip())

    def test_locale_overlay_matches_catalog_ids_exactly(self) -> None:
        overlay = json.loads((ROOT / "catalog/locales/en.json").read_text(encoding="utf-8"))
        catalog_ids = {record["id"] for record in load_records(ROOT)}
        self.assertEqual(catalog_ids, set(overlay["projects"]))

    def test_english_is_default_static_surface_and_german_remains_available(self) -> None:
        english = render_shell(ROOT, "en")
        german = render_shell(ROOT, "de")
        self.assertIn('<html lang="en">', english)
        self.assertIn('<title>commonworld — Discover Commons</title>', english)
        self.assertIn('href="./de.html"', english)
        self.assertIn('<html lang="de">', german)
        self.assertIn('<title>commonworld — Commons entdecken</title>', german)
        self.assertIn('href="./"', german)
        self.assertIn('Search Commons', english)
        self.assertIn('Commons suchen', german)

    def test_method_surface_is_localized_without_scripts(self) -> None:
        english = render_method(ROOT, "en")
        german = render_method(ROOT, "de")
        self.assertIn('Method, coverage and privacy', english)
        self.assertIn('Methode, Abdeckung und Datenschutz', german)
        self.assertNotIn('<script', english.casefold())
        self.assertNotIn('<script', german.casefold())


if __name__ == "__main__":
    unittest.main()
