import json
import re
import unittest
from pathlib import Path
from urllib.parse import urljoin

from scripts.catalog_recovery import PAGE_SIZE, index_relative_path, page_count, page_records, project_relative_path
from scripts.validate_catalog_recovery import ROOT, validate_catalog_recovery


class CatalogRecoveryTests(unittest.TestCase):
    def test_current_recovery_contract_and_artifacts_validate(self) -> None:
        self.assertEqual([], validate_catalog_recovery(ROOT, verify_measurements=False))

    def test_pagination_is_bounded_and_complete(self) -> None:
        records = [{"id": f"project-{index:05d}"} for index in range(10_000)]
        self.assertEqual(417, page_count(len(records)))
        pages = [page_records(records, number) for number in range(1, 418)]
        self.assertTrue(all(1 <= len(page) <= PAGE_SIZE for page in pages))
        self.assertEqual(records, [record for page in pages for record in page])

    def test_recovery_paths_are_locale_explicit_and_identity_stable(self) -> None:
        self.assertEqual(Path("catalog/index.html"), index_relative_path("en", 1))
        self.assertEqual(Path("catalog/pages/2.html"), index_relative_path("en", 2))
        self.assertEqual(Path("catalog/de/index.html"), index_relative_path("de", 1))
        self.assertEqual(Path("catalog/de/pages/2.html"), index_relative_path("de", 2))
        self.assertEqual(Path("catalog/projects/debian.html"), project_relative_path("en", "debian"))
        self.assertEqual(Path("catalog/de/projects/debian.html"), project_relative_path("de", "debian"))

    def test_paginated_index_canonical_and_hreflang_follow_same_page(self) -> None:
        expectations = {
            "en": (ROOT / "catalog/pages/2.html", "/catalog/pages/2.html", "de", "/catalog/de/pages/2.html"),
            "de": (ROOT / "catalog/de/pages/2.html", "/catalog/de/pages/2.html", "en", "/catalog/pages/2.html"),
        }
        for locale, (path, canonical, alternate_locale, alternate) in expectations.items():
            with self.subTest(locale=locale):
                markup = path.read_text(encoding="utf-8")
                self.assertIn(f'<link rel="canonical" href="{canonical}" />', markup)
                self.assertIn(f'<link rel="alternate" hreflang="{alternate_locale}" href="{alternate}" />', markup)

    def test_landing_recovery_links_resolve_inside_the_selected_release(self) -> None:
        for page_name, locale_prefix in (("index.html", "catalog/"), ("de.html", "catalog/de/")):
            with self.subTest(page=page_name):
                markup = (ROOT / page_name).read_text(encoding="utf-8")
                base = re.search(r'<base href="(/releases/[0-9a-f]{20}/)" />', markup)
                self.assertIsNotNone(base)
                release_base = base.group(1)
                fallback = markup.split('id="static-catalog-fallback"', 1)[1]
                pagination = re.search(r'class="recovery-pagination"><a href="([^"]+)"', fallback)
                project_pages = re.findall(r'<a href="([^"]+)">(?:Project page|Projektseite)</a>', fallback)
                project_json = re.findall(r'<a href="([^"]+)" type="application/json">JSON</a>', fallback)
                self.assertIsNotNone(pagination)
                self.assertTrue(project_pages)
                self.assertTrue(project_json)
                self.assertEqual(f"{release_base}{locale_prefix}", urljoin(release_base, pagination.group(1)))
                for href in (*project_pages, *project_json):
                    self.assertTrue(urljoin(release_base, href).startswith(f"{release_base}catalog/"), href)

                selected_snapshot = ROOT / release_base.removeprefix("/") / page_name
                self.assertEqual(markup, selected_snapshot.read_text(encoding="utf-8"))

    def test_project_canonical_and_hreflang_follow_each_locale_direction(self) -> None:
        identifier = "debian"
        expectations = {
            "en": (
                ROOT / f"catalog/projects/{identifier}.html",
                f"/catalog/projects/{identifier}.html",
                "de",
                f"/catalog/de/projects/{identifier}.html",
            ),
            "de": (
                ROOT / f"catalog/de/projects/{identifier}.html",
                f"/catalog/de/projects/{identifier}.html",
                "en",
                f"/catalog/projects/{identifier}.html",
            ),
        }
        for locale, (path, canonical, alternate_locale, alternate) in expectations.items():
            with self.subTest(locale=locale):
                markup = path.read_text(encoding="utf-8")
                self.assertIn(f'<link rel="canonical" href="{canonical}" />', markup)
                self.assertIn(f'<link rel="alternate" hreflang="{alternate_locale}" href="{alternate}" />', markup)

    def test_cutover_authorization_remains_false_in_all_t028_authorities(self) -> None:
        recovery = json.loads((ROOT / "contracts/commonworld/catalog-recovery.contract.json").read_text())
        scale = json.loads((ROOT / "contracts/commonworld/catalog-scale-gates.contract.json").read_text())
        state = json.loads((ROOT / "contracts/commonworld/current-state.contract.json").read_text())
        self.assertFalse(recovery["authorization"]["runtime_catalogue_cutover_authorized"])
        self.assertFalse(scale["current_authorization"]["cutover_authorized"])
        self.assertFalse(state["catalog_delivery"]["runtime_catalogue_cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
