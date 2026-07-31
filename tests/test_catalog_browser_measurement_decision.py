from __future__ import annotations

import unittest
from copy import deepcopy

from scripts.evaluate_catalog_browser_measurements import (
    build_decision_evidence,
    validate_decision_evidence,
)


class CatalogBrowserMeasurementDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.budgets = {
            "max_startup_project_json_requests": 0,
            "max_browser_dom_nodes": 2500,
            "max_runtime_ready_ms_at_4x_cpu": 5000,
            "max_script_duration_ms_at_4x_cpu": 3000,
            "max_task_duration_ms_at_4x_cpu": 3000,
            "max_bootstrap_compile_p95_ms_at_4x_cpu": 100,
        }
        self.budget_hash = "b" * 64

    @staticmethod
    def measurement(
        *,
        surface_hash: str = "a" * 64,
        task_duration_ms: float = 1200.0,
    ) -> dict:
        profiles = []
        for name in ("mobile-low-power", "desktop-low-power"):
            profiles.append(
                {
                    "profile": name,
                    "viewport": {"width": 390, "height": 844},
                    "cpu_throttle_rate": 4,
                    "runtime_ready_ms": 900,
                    "dom_node_count": 1200,
                    "runtime_ready": True,
                    "runtime_failed": False,
                    "script_duration_ms": 500.0,
                    "task_duration_ms": task_duration_ms,
                    "bootstrap_compile": {"p95_ms": 5.0},
                    "first_party_requests": ["/", "/assets/commonworld-app.js"],
                    "first_party_surface_sha256": surface_hash,
                    "project_json_request_count": 0,
                }
            )
        return {
            "schema_version": 1,
            "kind": "commonworld_catalog_delivery_browser_metrics",
            "measured_at": "2026-07-31T12:00:00Z",
            "cpu_throttle_rate": 4,
            "profiles": profiles,
        }

    def build(self, *measurements: dict) -> dict:
        evidence, errors = build_decision_evidence(
            list(measurements),
            self.budgets,
            budget_contract_sha256=self.budget_hash,
        )
        self.assertEqual(errors, [])
        self.assertIsNotNone(evidence)
        return evidence or {}

    def validate(self, evidence: dict, *, terminal: bool = True) -> list[str]:
        return validate_decision_evidence(
            evidence,
            self.budgets,
            budget_contract_sha256=self.budget_hash,
            require_terminal_pass=terminal,
        )

    def test_first_attempt_pass_is_terminal_and_preserved(self) -> None:
        first = self.measurement()
        evidence = self.build(first)
        self.assertEqual(evidence["decision"], "pass")
        self.assertEqual(evidence["attempt_count"], 1)
        self.assertEqual(evidence["selected_attempt"], 1)
        self.assertEqual(evidence["attempts"][0]["measurement"], first)
        self.assertEqual(self.validate(evidence), [])

    def test_first_breach_requires_exactly_one_confirmation(self) -> None:
        evidence = self.build(self.measurement(task_duration_ms=3500.0))
        self.assertEqual(evidence["decision"], "confirmation-required")
        self.assertEqual(evidence["gate_verdict"], "pending")
        self.assertEqual(evidence["profiles"], [])
        errors = self.validate(evidence)
        self.assertTrue(any("not a terminal pass" in error for error in errors))

    def test_breach_then_pass_preserves_both_as_variance(self) -> None:
        first = self.measurement(task_duration_ms=3500.0)
        second = self.measurement(task_duration_ms=1700.0)
        evidence = self.build(first, second)
        self.assertEqual(evidence["decision"], "variance-observed")
        self.assertEqual(evidence["attempt_count"], 2)
        self.assertEqual(evidence["selected_attempt"], 2)
        self.assertEqual(evidence["attempts"][0]["verdict"], "breach")
        self.assertEqual(evidence["attempts"][1]["verdict"], "pass")
        self.assertEqual(evidence["attempts"][0]["measurement"], first)
        self.assertEqual(evidence["attempts"][1]["measurement"], second)
        self.assertEqual(self.validate(evidence), [])

    def test_two_consecutive_breaches_block_and_require_architecture_review(self) -> None:
        evidence = self.build(
            self.measurement(task_duration_ms=3500.0),
            self.measurement(task_duration_ms=4200.0),
        )
        self.assertEqual(evidence["decision"], "consecutive-breach")
        self.assertEqual(evidence["gate_verdict"], "block")
        self.assertTrue(evidence["architecture_review_required"])
        self.assertEqual(evidence["profiles"], [])
        errors = self.validate(evidence)
        self.assertTrue(any("not a terminal pass" in error for error in errors))

    def test_mismatched_attempt_surface_is_rejected(self) -> None:
        evidence, errors = build_decision_evidence(
            [
                self.measurement(surface_hash="a" * 64, task_duration_ms=3500.0),
                self.measurement(surface_hash="c" * 64),
            ],
            self.budgets,
            budget_contract_sha256=self.budget_hash,
        )
        self.assertIsNone(evidence)
        self.assertTrue(any("same first-party surface" in error for error in errors))

    def test_second_attempt_after_first_pass_is_rejected(self) -> None:
        evidence, errors = build_decision_evidence(
            [self.measurement(), self.measurement()],
            self.budgets,
            budget_contract_sha256=self.budget_hash,
        )
        self.assertIsNone(evidence)
        self.assertTrue(any("only permitted" in error for error in errors))

    def test_manipulated_attempt_or_decision_is_detected(self) -> None:
        evidence = self.build(
            self.measurement(task_duration_ms=3500.0),
            self.measurement(task_duration_ms=1700.0),
        )
        manipulated_attempt = deepcopy(evidence)
        manipulated_attempt["attempts"][0]["measurement"]["profiles"][0][
            "task_duration_ms"
        ] = 1000.0
        self.assertTrue(
            any(
                "does not match its embedded attempts" in error
                for error in self.validate(manipulated_attempt)
            )
        )

        manipulated_decision = deepcopy(evidence)
        manipulated_decision["decision"] = "pass"
        self.assertTrue(
            any(
                "does not match its embedded attempts" in error
                for error in self.validate(manipulated_decision)
            )
        )


if __name__ == "__main__":
    unittest.main()
