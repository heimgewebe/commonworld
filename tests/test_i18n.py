import copy
import json
import re
import unittest
from pathlib import Path

from scripts.commonworld_i18n import SUPPORTED_LOCALES, load_locale, localize_records, replace_exact, validate_catalog_overlay
from scripts.render_proposal_page import render as render_proposal
from scripts.render_public_shell import load_records, render_method, render_shell

ROOT = Path(__file__).resolve().parents[1]
WAVE1_LOCALES = tuple(json.loads((ROOT / "docs/architecture/locale-release.contract.json").read_text(encoding="utf-8"))["rollout"]["wave_1"])


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

    def test_released_locale_overlays_match_catalog_ids_exactly(self) -> None:
        catalog_ids = {record["id"] for record in load_records(ROOT)}
        for locale in SUPPORTED_LOCALES:
            if locale == "de":
                continue
            overlay = json.loads((ROOT / f"catalog/locales/{locale}.json").read_text(encoding="utf-8"))
            with self.subTest(locale=locale):
                self.assertEqual(catalog_ids, set(overlay["projects"]))

    def test_wave1_catalog_content_is_localized_and_content_locale_is_exact(self) -> None:
        canonical = load_records(ROOT)
        english = {record["id"]: record for record in localize_records(canonical, "en", ROOT)}
        for locale in WAVE1_LOCALES:
            localized = {record["id"]: record for record in localize_records(canonical, locale, ROOT)}
            for project_id in ("mundraub", "common-voice"):
                with self.subTest(locale=locale, project=project_id):
                    self.assertEqual(locale, localized[project_id]["_content_locale"] )
                    self.assertEqual(english[project_id].get("_title_locale"), localized[project_id]["_title_locale"] )
                    self.assertEqual(english[project_id]["title"], localized[project_id]["title"] )
                    self.assertNotEqual(english[project_id]["summary"], localized[project_id]["summary"] )
                    self.assertNotEqual(english[project_id]["presence"]["digital"]["label"], localized[project_id]["presence"]["digital"]["label"] )
            if locale == "ar":
                self.assertRegex(localized["mundraub"]["summary"], r"[\u0600-\u06ff]")
            if locale == "zh-Hans":
                self.assertRegex(localized["mundraub"]["summary"], r"[\u4e00-\u9fff]")
                zh_overlay = json.loads((ROOT / "catalog/locales/zh-Hans.json").read_text(encoding="utf-8"))
                self.assertEqual(zh_overlay["projects"]["libreoffice"]["digital_label"], "自由办公套件和开放的参与路径")
                self.assertEqual(localized["reprap"]["summary"], "一个围绕自由记录、可制造自身大部分零件的 3D 打印机展开的全球开放硬件项目；其设计可由社区协作构建、调整和改进。")

    def test_canonical_title_without_explicit_english_overlay_has_no_false_language(self) -> None:
        canonical = load_records(ROOT)
        for locale in ("en", *WAVE1_LOCALES):
            localized = {record["id"]: record for record in localize_records(canonical, locale, ROOT)}
            with self.subTest(locale=locale):
                self.assertIsNone(localized["akiba-mashinani-trust"]["_title_locale"])

    def test_catalog_overlay_validation_rejects_extra_fields_and_wrong_digital_shape(self) -> None:
        canonical = load_records(ROOT)
        overlay = load_locale("es", ROOT)
        broken = copy.deepcopy(overlay)
        broken["projects"]["mundraub"]["canonical_url"] = "https://example.invalid/"
        with self.assertRaisesRegex(ValueError, "unexpected project fields"):
            validate_catalog_overlay(broken, canonical, "es")
        broken = copy.deepcopy(overlay)
        unavailable = next(record for record in canonical if record["presence"]["digital"]["available"] is not True)
        broken["projects"][unavailable["id"]]["digital_label"] = "must not exist"
        with self.assertRaisesRegex(ValueError, "must not contain digital label"):
            validate_catalog_overlay(broken, canonical, "es")

    def test_arabic_catalog_prose_has_arabic_without_glued_mixed_script(self) -> None:
        overlay = json.loads((ROOT / "catalog/locales/ar.json").read_text(encoding="utf-8"))
        for project_id, translation in overlay["projects"].items():
            text = " ".join([translation["summary"], *translation["geographic_labels"].values(), translation.get("digital_label", "")])
            with self.subTest(project=project_id):
                self.assertRegex(text, r"[\u0600-\u06ff]")
                self.assertNotRegex(text, r"[\u0621-\u063A\u0641-\u064A][A-Za-z]|[A-Za-z][\u0621-\u063A\u0641-\u064A]")

    def test_geographic_overlay_is_bound_to_stable_location_ids(self) -> None:
        canonical = load_records(ROOT)
        target = next(record for record in canonical if record["id"] == "fucvam")
        target["presence"]["geographic"] = list(reversed(target["presence"]["geographic"]))
        localized = localize_records(canonical, "en", ROOT)
        translated = next(record for record in localized if record["id"] == "fucvam")
        labels = {location["id"]: location["label"] for location in translated["presence"]["geographic"]}
        overlay = json.loads((ROOT / "catalog/locales/en.json").read_text(encoding="utf-8"))
        self.assertEqual(labels, overlay["projects"]["fucvam"]["geographic_labels"])

    def test_english_overlay_preserves_meaningful_source_labels(self) -> None:
        canonical = load_records(ROOT)
        localized = localize_records(canonical, "en", ROOT)
        debian = next(record for record in localized if record["id"] == "debian")
        self.assertTrue(debian["provenance"]["sources"][0]["label"].startswith("About Debian · "))

    def test_english_is_default_static_surface_and_german_remains_available(self) -> None:
        english = render_shell(ROOT, "en")
        german = render_shell(ROOT, "de")
        self.assertIn('<html lang="en">', english)
        self.assertIn('<title>commonworld — Discover Commons</title>', english)
        self.assertIn('href="./de.html?ui_lang=de"', english)
        self.assertIn('<html lang="de">', german)
        self.assertIn('<title>commonworld — Commons entdecken</title>', german)
        self.assertIn('href="./?ui_lang=en"', german)
        for markup in (english, german):
            self.assertIn('data-locale-choice="auto"', markup)
            self.assertIn('data-locale-choice="en"', markup)
            self.assertIn('data-locale-choice="de"', markup)
            self.assertIn('data-locale-effective', markup)
        self.assertIn('Search Commons', english)
        self.assertIn('Commons suchen', german)

    def test_english_static_surfaces_do_not_retain_known_german_ui_strings(self) -> None:
        english_shell = render_shell(ROOT, "en")
        english_proposal = render_proposal("en")
        for marker in (
            "Commons suchen",
            "Filter zurücksetzen",
            "Zur Textansicht springen",
            "Digitale Sphäre",
            "Meinen Standort verwenden",
            "Commons vorschlagen",
        ):
            with self.subTest(surface="index", marker=marker):
                self.assertNotIn(marker, english_shell)
        for marker in (
            "Ein Commons vorschlagen",
            "Was danach passiert",
            "Grobe Region oder Ort",
            "Validiertes JSON herunterladen",
        ):
            with self.subTest(surface="proposal", marker=marker):
                self.assertNotIn(marker, english_proposal)

    def test_exact_replacement_contract_fails_closed_on_template_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "locale replacement contract drift"):
            replace_exact("<p>changed template</p>", {"<p>expected template</p>": "<p>translated</p>"}, surface="test")

    def test_method_surface_is_localized_with_only_locale_runtime(self) -> None:
        english = render_method(ROOT, "en")
        german = render_method(ROOT, "de")
        self.assertIn('Method, coverage and privacy', english)
        self.assertIn('Methode, Abdeckung und Datenschutz', german)
        for markup in (english, german):
            self.assertEqual(1, markup.casefold().count('<script'))
            self.assertIn('commonworld-locale.mjs?v=', markup)
            self.assertIn('data-locale-choice="auto"', markup)


if __name__ == "__main__":
    unittest.main()
