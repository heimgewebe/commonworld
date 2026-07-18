import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_production_delivery_provider import ROOT, validate_production_delivery_provider


class ProductionDeliveryProviderTests(unittest.TestCase):
    REQUIRED = (
        "contracts/commonworld/production-delivery-provider.contract.json",
        "contracts/commonworld/public-maplibre-vertical-slice.contract.json",
        "docs/research/production-delivery-provider-v1.result.json",
        "assets/map/openfreemap-liberty.json",
        "catalog/catalog.json",
        "docs/ops/pages-dns.md",
        ".github/workflows/production-readback.yml",
        "scripts/verify_pages_deployment.py",
        "docs/research/evidence/public-maplibre-vertical-slice-v1.catalog.json",
    )

    def copy_contract(self, directory: str) -> Path:
        root = Path(directory)
        for relative in self.REQUIRED:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def mutate_json(self, root: Path, relative: str, mutation) -> None:
        path = root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_contract_validates(self) -> None:
        self.assertEqual([], validate_production_delivery_provider(ROOT))

    def test_sla_cannot_be_invented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(root, self.REQUIRED[0], lambda value: value["basemap"].update({"service_level_agreement_claimed": True}))
            errors = validate_production_delivery_provider(root)
        self.assertIn("basemap provider boundary mismatch: service_level_agreement_claimed", errors)

    def test_catalog_authorization_cannot_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(root, "catalog/catalog.json", lambda value: value["publication"].update({"production_architecture_authorized": False}))
            errors = validate_production_delivery_provider(root)
        self.assertIn("public catalog does not publish bounded production authorization", errors)

    def test_linear_catalog_is_required_during_provider_outage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(root, self.REQUIRED[0], lambda value: value["failure_contract"].update({"provider_outage": "map_unavailable"}))
            errors = validate_production_delivery_provider(root)
        self.assertIn("provider outage must preserve the linear catalog", errors)

    def test_production_readback_must_remain_exact_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(
                root,
                self.REQUIRED[0],
                lambda value: value["monitoring"]["pages_production_readback"].update(
                    {"commit_binding": "latest_successful", "automatic_rollback": True}
                ),
            )
            errors = validate_production_delivery_provider(root)
        self.assertIn("production readback boundary mismatch: commit_binding", errors)
        self.assertIn("production readback boundary mismatch: automatic_rollback", errors)

    def test_production_readback_retry_schedule_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(
                root,
                self.REQUIRED[0],
                lambda value: value["monitoring"]["pages_production_readback"].update(
                    {"live_retry_delays_seconds": [0, 30, 90, 180]}
                ),
            )
            errors = validate_production_delivery_provider(root)
        self.assertIn("production readback boundary mismatch: live_retry_delays_seconds", errors)

    def test_migration_requires_separate_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(root, self.REQUIRED[0], lambda value: value["migration"].update({"authorized": True}))
            errors = validate_production_delivery_provider(root)
        self.assertIn("production decision must not implicitly authorize migration", errors)

    def test_unreviewed_runtime_origin_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            self.mutate_json(root, "assets/map/openfreemap-liberty.json", lambda value: value.update({"glyphs": "https://example.invalid/fonts/{fontstack}/{range}.pbf"}))
            errors = validate_production_delivery_provider(root)
        self.assertTrue(any("style runtime origins differ" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
