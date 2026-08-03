import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_catalog_scale_gates",
    ROOT / "scripts" / "validate_catalog_scale_gates.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CatalogScaleGateValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        for relative in (
            Path("contracts/commonworld/catalog-scale-gates.contract.json"),
            Path("contracts/commonworld/current-state.contract.json"),
            Path("contracts/commonworld/project.schema.json"),
            Path("docs/evidence/catalog-platform-scaling-v1.json"),
            Path("scripts/__init__.py"),
            Path("scripts/measure_catalog_platform_scaling.py"),
            Path("scripts/catalog_scale_fixtures.py"),
            Path("scripts/validate_contracts.py"),
            Path("catalog/catalog.json"),
            Path("catalog/locales/en.json"),
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        shutil.copytree(ROOT / "catalog" / "projects", self.root / "catalog" / "projects")

    def tearDown(self):
        self.temp_directory.cleanup()

    def load(self, relative: str) -> dict:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def write(self, relative: str, value: dict) -> None:
        (self.root / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_current_scale_gate_contract_passes_with_fresh_recomputation(self):
        self.assertEqual(MODULE.validate_catalog_scale_gates(self.root), [])

    def test_committed_measurements_cannot_be_fabricated_with_valid_gate_labels(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        for measurement in evidence["measurements"]:
            measurement["world_index"]["raw_bytes"] += 1
            measurement["shards"]["gzip_total_bytes"] += 1
        self.write(relative, evidence)
        self.assertIn(
            "catalogue scaling evidence deterministic measurement drift",
            MODULE.validate_catalog_scale_gates(self.root),
        )

    def test_measurement_generator_path_cannot_drift(self):
        relative = "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = self.load(relative)
        contract["measurement"]["generator"] = "scripts/ambient_scale_measurement.py"
        self.write(relative, contract)
        self.assertIn(
            "catalogue scale contract generator path mismatch",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_obsolete_synthetic_marker_cannot_replace_representative_fixture_disclosure(self):
        relative = "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = self.load(relative)
        contract["measurement"].pop("representative_fixture_only")
        contract["measurement"]["synthetic_only"] = True
        self.write(relative, contract)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertIn("catalogue scale contract must disclose representative-fixture-only evidence", errors)
        self.assertIn("catalogue scale contract must not retain the obsolete synthetic-only model", errors)

    def test_cutover_cannot_be_authorized_by_representative_fixture_evidence(self):
        relative = "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = self.load(relative)
        contract["current_authorization"]["cutover_authorized"] = True
        self.write(relative, contract)
        self.assertIn(
            "catalogue scale contract must not authorize cutover",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_fixture_source_digest_is_bound_to_the_exact_catalogue(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        evidence["fixture_model"]["source_catalog_sha256"] = "0" * 64
        self.write(relative, evidence)
        self.assertIn(
            "catalogue scaling fixture source digest drift",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_fixture_project_set_digest_is_bound_to_project_contents(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        evidence["fixture_model"]["source_project_set_sha256"] = "0" * 64
        self.write(relative, evidence)
        self.assertIn(
            "catalogue scaling fixture project-set digest drift",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_fixture_english_overlay_digest_is_bound_to_overlay_contents(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        evidence["fixture_model"]["source_english_overlay_sha256"] = "0" * 64
        self.write(relative, evidence)
        self.assertIn(
            "catalogue scaling fixture English overlay digest drift",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_malformed_source_project_inventory_fails_closed_without_exception(self):
        relative = "catalog/catalog.json"
        catalog = self.load(relative)
        catalog["project_files"] = "not-a-list"
        self.write(relative, catalog)
        self.assertIn(
            "catalogue scaling source project inventory must be a list",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_source_project_path_escape_fails_closed(self):
        relative = "catalog/catalog.json"
        catalog = self.load(relative)
        catalog["project_files"][0] = "../catalog.json"
        self.write(relative, catalog)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertTrue(
            any(error.startswith("catalogue scaling source project set is invalid:") for error in errors),
            errors,
        )

    def test_full_schema_tier_must_cover_every_released_english_identity(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 1_000)
        measurement["coverage"]["english_overlay_project_count"] -= 1
        self.write(relative, evidence)
        self.assertIn(
            "1000: fixture English overlay coverage incomplete",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_10k_cutover_tier_cannot_cross_shard_warning(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 10_000)
        measurement["shards"]["gzip_max_bytes"] = evidence["budgets"]["shard_warn_gzip_bytes"]
        measurement["gate_evaluation"]["shard_gzip"] = "warning"
        self.write(relative, evidence)
        self.assertIn(
            "10000: cutover scale tier must remain below shard warning budget",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_100k_hard_failure_cannot_be_silently_glossed_over(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 100_000)
        measurement["gate_evaluation"]["shard_gzip"] = "pass"
        self.write(relative, evidence)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertIn("100000: shard gate does not match measured size", errors)
        self.assertIn("100000: fixed two-hex stress tier must preserve the measured hard-budget failure", errors)

    def test_100k_stress_projection_cannot_claim_materialized_locales(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 100_000)
        measurement["coverage"]["stress_projection"]["locale_overlays_materialized"] = True
        measurement["coverage"]["english_overlay_project_count"] = 100_000
        self.write(relative, evidence)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertIn("100000: stress projection must disclose unmaterialized locale overlays", errors)
        self.assertIn("100000: compact stress projection must not claim generated English overlays", errors)

    def test_100k_stress_projection_metadata_must_be_an_object(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 100_000)
        measurement["coverage"]["stress_projection"] = "not-an-object"
        self.write(relative, evidence)
        self.assertIn(
            "100000: stress projection metadata must be an object",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_100k_prefix_migration_candidate_must_restore_headroom(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 100_000)
        measurement["prefix_migration_candidate"]["gate_evaluation"]["shard_gzip"] = "fail"
        self.write(relative, evidence)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertIn("100000: prefix migration shard gate does not match measured size", errors)
        self.assertIn("100000: three-hex prefix migration candidate must restore shard headroom", errors)

    def test_unpublished_fixture_task_cannot_be_asserted_as_registry_truth(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        evidence["decision"]["fixture_task"] = "COMMONWORLD-PUBLIC-GLOBE-V1-T039"
        self.write(relative, evidence)
        self.assertIn(
            "catalogue scaling evidence must not assert an unpublished fixture task",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )

    def test_backend_escalation_cannot_become_default(self):
        relative = "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = self.load(relative)
        contract["decision_policy"]["backend_by_default"] = True
        self.write(relative, contract)
        self.assertIn(
            "catalogue scale contract must remain measurement-first, not backend-first",
            MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False),
        )


if __name__ == "__main__":
    unittest.main()
