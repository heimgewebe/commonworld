import json
import tempfile
import unittest
from pathlib import Path

from scripts.measure_catalog_delivery import measure
from scripts.validate_catalog_delivery_budget import ROOT, validate, validate_actual_smoke


class CatalogDeliveryBudgetTests(unittest.TestCase):
    def test_current_delivery_stays_within_contract(self) -> None:
        self.assertEqual([], validate(ROOT))

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
            root = Path(tmp)
            for relative in (
                'assets/commonworld-app.js',
                'assets/commonworld-bootstrap-catalog.mjs',
                'catalog/catalog.json',
                'index.html',
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            for source in (ROOT / 'catalog/projects').glob('*.json'):
                target = root / 'catalog/projects' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            bootstrap_path = root / 'assets/commonworld-bootstrap-catalog.mjs'
            bootstrap = bootstrap_path.read_text(encoding='utf-8')
            bootstrap_path.write_text(bootstrap.replace('Commons', 'Veraltete Projektion', 1), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'do not match canonical CommonProject content'):
                measure(root)

    def test_validator_rejects_browser_smoke_catalogue_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            for source in (ROOT / 'catalog/projects').glob('*.json'):
                target = root / 'catalog/projects' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            smoke_path = root / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json'
            smoke = json.loads(smoke_path.read_text(encoding='utf-8'))
            next(item for item in smoke['scenarios'] if item['id'] == 'catalogue-failure')['blockedCatalogRequests'] = 1
            smoke_path.write_text(json.dumps(smoke), encoding='utf-8')
            errors = validate(root)
        self.assertIn('public browser smoke observed a runtime catalogue request', errors)

    def test_fresh_smoke_result_rejects_missing_scenario_and_catalogue_request(self) -> None:
        expected = json.loads(
            (ROOT / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json').read_text(encoding='utf-8')
        )
        actual = json.loads(json.dumps(expected))
        actual.pop('binding', None)
        actual['scenarios'].pop()
        next(item for item in actual['scenarios'] if item['id'] == 'catalogue-failure')['blockedCatalogRequests'] = 1
        errors = validate_actual_smoke(actual, expected)
        self.assertIn(
            'fresh public browser smoke scenario order or membership differs from committed evidence',
            errors,
        )
        self.assertIn('fresh public browser smoke observed a runtime catalogue request', errors)

    def test_validator_rejects_runtime_catalogue_refetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            for source in (ROOT / 'catalog/projects').glob('*.json'):
                target = root / 'catalog/projects' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            app = root / 'assets/commonworld-app.js'
            app.write_text(app.read_text(encoding='utf-8') + '\nasync function loadRecords() {}\n', encoding='utf-8')
            errors = validate(root)
        self.assertTrue(any('must not refetch' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
