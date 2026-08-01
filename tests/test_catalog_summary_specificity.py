import copy
import unittest

from scripts.catalog_summary_specificity import (
    load_contract,
    specificity_errors,
    validate_contract,
)
from scripts.commonworld_i18n import SUPPORTED_LOCALES


class CatalogSummarySpecificityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_current_contract_covers_every_released_locale(self) -> None:
        self.assertEqual(validate_contract(self.contract, SUPPORTED_LOCALES), [])

    def test_every_declared_phrase_reports_project_locale_rule_and_match(self) -> None:
        policies = self.contract["locale_policies"]
        for locale in SUPPORTED_LOCALES:
            for rule in policies[locale]["rules"]:
                for phrase in rule["phrases"]:
                    with self.subTest(locale=locale, rule=rule["id"], phrase=phrase):
                        record = {
                            "id": "specificity-fixture",
                            "summary": f"Prefix {phrase.upper()} suffix.",
                        }
                        errors = specificity_errors(record, locale, self.contract)
                        self.assertEqual(len(errors), 1)
                        self.assertIn("project specificity-fixture", errors[0])
                        self.assertIn(f"locale={locale}", errors[0])
                        self.assertIn(f"rule={rule['id']}", errors[0])
                        self.assertIn(f"matched={phrase!r}", errors[0])

    def test_concrete_collective_governance_examples_remain_allowed(self) -> None:
        policies = self.contract["locale_policies"]
        for locale in SUPPORTED_LOCALES:
            for index, summary in enumerate(policies[locale]["allowed_examples"]):
                with self.subTest(locale=locale, example=index):
                    self.assertEqual(
                        specificity_errors(
                            {"id": "allowed-fixture", "summary": summary},
                            locale,
                            self.contract,
                        ),
                        [],
                    )

    def test_forbidden_phrase_cannot_supply_its_own_mechanism(self) -> None:
        cases = (
            (
                "en",
                "A community-maintained knowledge base for communities.",
                "en-generic-community-maintained",
            ),
            (
                "de",
                "Eine gemeinschaftlich gepflegte Wissenssammlung für Gemeinschaften.",
                "de-generic-community-maintained",
            ),
        )
        for locale, summary, rule_id in cases:
            with self.subTest(locale=locale):
                errors = specificity_errors(
                    {"id": "self-exemption-fixture", "summary": summary},
                    locale,
                    self.contract,
                )
                self.assertEqual(len(errors), 1)
                self.assertIn(f"rule={rule_id}", errors[0])

    def test_independent_actor_and_mechanism_can_justify_similar_wording(self) -> None:
        summary = (
            "A community-maintained package archive whose volunteers publish "
            "signed security updates through a documented process."
        )
        self.assertEqual(
            specificity_errors(
                {"id": "independent-context-fixture", "summary": summary},
                "en",
                self.contract,
            ),
            [],
        )

    def test_specificity_marker_lists_must_not_be_empty(self) -> None:
        for marker_kind in ("actor_patterns", "mechanism_patterns"):
            contract = copy.deepcopy(self.contract)
            contract["locale_policies"]["en"]["specificity_markers"][
                marker_kind
            ] = []
            with self.subTest(marker_kind=marker_kind):
                self.assertIn(
                    f"summary specificity locale en {marker_kind} must be a non-empty string list",
                    validate_contract(contract, SUPPORTED_LOCALES),
                )

    def test_released_locale_without_policy_fails_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        del contract["locale_policies"]["en"]
        errors = validate_contract(contract, SUPPORTED_LOCALES)
        self.assertIn(
            "summary specificity policy missing for released locale en",
            errors,
        )

    def test_normalization_duplicate_phrase_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        phrases = contract["locale_policies"]["en"]["rules"][0]["phrases"]
        phrases.append("  COMMUNITY-DRIVEN  ")
        errors = validate_contract(contract, SUPPORTED_LOCALES)
        self.assertTrue(
            any(
                "en-generic-community-developed phrases must be unique after normalization"
                in error
                for error in errors
            )
        )

    def test_every_rule_requires_a_bound_rejected_example(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_policies"]["de"]["rejected_examples"] = []
        errors = validate_contract(contract, SUPPORTED_LOCALES)
        self.assertTrue(
            any(
                "locale de rule de-generic-community-developed needs at least 1 rejected examples"
                in error
                for error in errors
            )
        )
        self.assertTrue(
            any(
                "locale de rule de-generic-community-maintained needs at least 1 rejected examples"
                in error
                for error in errors
            )
        )

    def test_planned_locale_policy_is_not_required_before_promotion(self) -> None:
        self.assertEqual(validate_contract(self.contract, ("en", "de")), [])
        errors = validate_contract(self.contract, ("en", "de", "es"))
        self.assertIn(
            "summary specificity policy missing for released locale es",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
