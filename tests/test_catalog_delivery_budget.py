import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.measure_catalog_delivery import measure
from scripts.validate_catalog_delivery_budget import (
    CATALOGUE_NETWORK_BLOCKED_SCENARIO,
    ROOT,
    validate,
    validate_actual_smoke,
)


class CatalogDeliveryBudgetTests(unittest.TestCase):
    def copy_delivery_tree(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        for relative in (
            'assets/commonworld-app.js',
            'assets/commonworld-bootstrap-catalog.mjs',
            'catalog/catalog.json',
            'index.html',
            'contracts/commonworld/catalog-delivery-budget.contract.json',
            'docs/evidence/catalog-delivery-benchmark-v1.json',
            'docs/evidence/catalog-delivery-public-browser-smoke-v1.json',
            'docs/catalog-delivery-options.md',
            'scripts/smoke_public_browser.mjs',
            'scripts/run_browser_smoke.py',
            'scripts/browser_smoke_plan.py',
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        shutil.copytree(ROOT / 'catalog/projects', root / 'catalog/projects')
        benchmark = json.loads(
            (ROOT / 'docs/evidence/catalog-delivery-benchmark-v1.json').read_text(encoding='utf-8')
        )
        for profile in benchmark['optimized']['browser']['profiles']:
            for request_path in profile['first_party_requests']:
                relative = 'index.html' if request_path == '/' else request_path.lstrip('/')
                source = ROOT / relative
                target = root / relative
                if source.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        return root

    def fresh_smoke(self) -> dict:
        value = json.loads(
            (ROOT / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json').read_text(
                encoding='utf-8'
            )
        )
        value.pop('binding', None)
        return value

    def test_current_delivery_stays_within_contract(self) -> None:
        warnings: list[str] = []
        self.assertEqual([], validate(ROOT, warnings))
        self.assertEqual([], warnings)

    def test_static_measurement_preserves_single_truth_and_no_startup_refetch(self) -> None:
        metrics = measure(ROOT)
        manifest = json.loads((ROOT / 'catalog/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['entry_count'], metrics['entry_count'])
        self.assertEqual(0, metrics['runtime_verification_fetch']['project_request_count'])
        self.assertEqual(0, metrics['runtime_verification_fetch']['duplicate_identity_payload_count'])
        self.assertEqual(metrics['entry_count'] * 2, metrics['html']['catalog_card_instances'])
        self.assertEqual(1, metrics['html']['noscript_catalogs'])

    def test_measure_rejects_stale_bootstrap_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_delivery_tree(tmp)
            bootstrap_path = root / 'assets/commonworld-bootstrap-catalog.mjs'
            bootstrap = bootstrap_path.read_text(encoding='utf-8')
            bootstrap_path.write_text(
                bootstrap.replace('Commons', 'Veraltete Projektion', 1), encoding='utf-8'
            )
            with self.assertRaisesRegex(ValueError, 'do not match canonical CommonProject content'):
                measure(root)

    def test_validator_rejects_committed_smoke_catalogue_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_delivery_tree(tmp)
            smoke_path = root / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json'
            smoke = json.loads(smoke_path.read_text(encoding='utf-8'))
            next(
                item for item in smoke['scenarios']
                if item['id'] == CATALOGUE_NETWORK_BLOCKED_SCENARIO
            )['blockedCatalogRequests'] = 1
            smoke_path.write_text(json.dumps(smoke), encoding='utf-8')
            errors = validate(root)
        self.assertIn('public browser smoke observed 1 runtime catalogue request(s)', errors)

    def test_fresh_smoke_reports_missing_scenario_without_false_request_claim(self) -> None:
        expected = self.fresh_smoke()
        actual = json.loads(json.dumps(expected))
        actual['scenarios'] = [
            item for item in actual['scenarios']
            if item['id'] != CATALOGUE_NETWORK_BLOCKED_SCENARIO
        ]
        errors = validate_actual_smoke(actual, expected)
        self.assertIn(
            f'fresh public browser smoke missing required scenario: {CATALOGUE_NETWORK_BLOCKED_SCENARIO}',
            errors,
        )
        self.assertFalse(any('observed' in error and 'catalogue request' in error for error in errors))

    def test_fresh_smoke_reports_missing_blocked_request_field(self) -> None:
        expected = self.fresh_smoke()
        actual = json.loads(json.dumps(expected))
        scenario = next(
            item for item in actual['scenarios']
            if item['id'] == CATALOGUE_NETWORK_BLOCKED_SCENARIO
        )
        scenario.pop('blockedCatalogRequests')
        errors = validate_actual_smoke(actual, expected)
        self.assertIn(
            'fresh public browser smoke scenario catalogue-network-blocked missing blockedCatalogRequests',
            errors,
        )

    def test_fresh_smoke_rejects_boolean_negative_and_noninteger_request_counts(self) -> None:
        expected = self.fresh_smoke()
        for invalid in (True, -1, 0.5):
            with self.subTest(invalid=invalid):
                actual = json.loads(json.dumps(expected))
                next(
                    item for item in actual['scenarios']
                    if item['id'] == CATALOGUE_NETWORK_BLOCKED_SCENARIO
                )['blockedCatalogRequests'] = invalid
                errors = validate_actual_smoke(actual, expected)
                self.assertIn(
                    'fresh public browser smoke scenario catalogue-network-blocked '
                    'blockedCatalogRequests must be a nonnegative integer',
                    errors,
                )

    def test_fresh_smoke_rejects_observed_catalogue_request(self) -> None:
        expected = self.fresh_smoke()
        actual = json.loads(json.dumps(expected))
        next(
            item for item in actual['scenarios']
            if item['id'] == CATALOGUE_NETWORK_BLOCKED_SCENARIO
        )['blockedCatalogRequests'] = 2
        errors = validate_actual_smoke(actual, expected)
        self.assertIn('fresh public browser smoke observed 2 runtime catalogue request(s)', errors)

    def test_validator_rejects_deliberate_bootstrap_budget_breach(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_delivery_tree(tmp)
            contract_path = root / 'contracts/commonworld/catalog-delivery-budget.contract.json'
            contract = json.loads(contract_path.read_text(encoding='utf-8'))
            contract['budgets']['warn_bootstrap_gzip_bytes'] = 19000
            contract['budgets']['max_bootstrap_gzip_bytes'] = 20000
            contract_path.write_text(json.dumps(contract), encoding='utf-8')
            errors = validate(root)
        self.assertTrue(
            any(
                error.startswith('bootstrap gzip bytes exceeds budget: actual=20526, warn=19000, max=20000')
                for error in errors
            )
        )

    def test_validator_warns_without_failing_inside_warning_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_delivery_tree(tmp)
            contract_path = root / 'contracts/commonworld/catalog-delivery-budget.contract.json'
            contract = json.loads(contract_path.read_text(encoding='utf-8'))
            contract['budgets']['warn_bootstrap_gzip_bytes'] = 20000
            contract_path.write_text(json.dumps(contract), encoding='utf-8')
            benchmark_path = root / 'docs/evidence/catalog-delivery-benchmark-v1.json'
            benchmark = json.loads(benchmark_path.read_text(encoding='utf-8'))
            benchmark['budget_binding']['warn_bootstrap_gzip_bytes'] = 20000
            benchmark_path.write_text(json.dumps(benchmark), encoding='utf-8')
            warnings: list[str] = []
            errors = validate(root, warnings)
        self.assertEqual([], errors)
        self.assertEqual(
            ['bootstrap gzip bytes entered warning range: actual=20526, warn=20000, max=32768'],
            warnings,
        )

    def test_validator_rejects_runtime_catalogue_refetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_delivery_tree(tmp)
            app = root / 'assets/commonworld-app.js'
            app.write_text(
                app.read_text(encoding='utf-8') + '\nasync function loadRecords() {}\n',
                encoding='utf-8',
            )
            errors = validate(root)
        self.assertTrue(any('must not refetch' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
