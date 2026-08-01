import copy
import unittest
from pathlib import Path

from scripts.locale_registry import match_registry_locale
from scripts.validate_locale_release import load_contract, validate_contract

ROOT = Path(__file__).resolve().parents[1]


class LocaleReleaseContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract(ROOT / "docs/architecture/locale-release.contract.json")

    def test_current_runtime_and_released_surfaces_match_contract(self) -> None:
        self.assertEqual(validate_contract(self.contract, ROOT), [])

    def test_candidate_locale_cannot_be_published_without_release_evidence(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["released_locales"].append("es")
        errors = validate_contract(contract, ROOT)
        self.assertTrue(
            any("candidate locale es must not be released" == error for error in errors)
        )
        self.assertTrue(any("runtime released locales" in error for error in errors))
        self.assertIn(
            "summary specificity policy missing for released locale es",
            errors,
        )

    def test_release_gate_requires_locale_specific_summary_policy(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["release_gate"][
            "catalog_summary_specificity_policy_required"
        ] = False
        errors = validate_contract(contract, ROOT)
        self.assertIn(
            "release gate must require a locale-aware catalog summary specificity policy",
            errors,
        )

    def test_primary_subtag_matches_region_specific_candidate(self) -> None:
        self.assertEqual(
            match_registry_locale(["pt-PT"], statuses=("candidate",), root=ROOT),
            "pt-BR",
        )
        self.assertEqual(
            match_registry_locale(["pt"], statuses=("candidate",), root=ROOT),
            "pt-BR",
        )

    def test_location_based_language_inference_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["automatic_selection"]["geolocation_must_not_influence_locale"] = False
        self.assertTrue(any("geolocation" in error for error in validate_contract(contract, ROOT)))

    def test_partial_translation_cannot_pass_the_release_gate(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["release_gate"]["translation_coverage_ratio"] = 0.99
        contract["release_gate"]["untranslated_ui_markers_max"] = 1
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("100%" in error for error in errors))
        self.assertTrue(any("markers" in error for error in errors))

    def test_rollout_waves_are_disjoint_and_not_yet_selectable(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["rollout"]["wave_2"].append("es")
        self.assertTrue(any("duplicate" in error for error in validate_contract(contract, ROOT)))

    def test_arabic_keeps_rtl_as_an_early_architecture_gate(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["ar"]["direction"] = "ltr"
        self.assertTrue(any("Arabic" in error for error in validate_contract(contract, ROOT)))

    def test_content_languages_remain_independent_from_interface_languages(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["content_language_policy"]["independent_from_interface_locales"] = False
        self.assertTrue(any("independent_from_interface_locales" in error for error in validate_contract(contract, ROOT)))

    def test_malformed_locale_lists_fail_closed_without_exception(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["released_locales"] = ["en", {}]
        contract["rollout"]["wave_1"] = ["es", {}]
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("released_locales" in error for error in errors))
        self.assertTrue(any("Wave 1" in error or "rollout waves" in error for error in errors))

    def test_registry_requires_stable_native_and_english_names(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["pt-BR"]["native_name"] = " "
        contract["locale_registry"]["ar"]["english_name"] = ""
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("pt-BR" in error and "native_name" in error for error in errors))
        self.assertTrue(any("ar" in error and "english_name" in error for error in errors))

    def test_default_and_fallback_locales_must_be_released(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["default_locale"] = "es"
        contract["decision"]["fallback_locale"] = "fr"
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("default_locale must be released" == error for error in errors))
        self.assertTrue(any("fallback_locale must be released" == error for error in errors))


if __name__ == "__main__":
    unittest.main()
