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
            Path("docs/evidence/catalog-platform-scaling-v1.json"),
            Path("scripts/measure_catalog_platform_scaling.py"),
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

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

    def test_cutover_cannot_be_authorized_by_synthetic_evidence(self):
        relative = "contracts/commonworld/catalog-scale-gates.contract.json"
        contract = self.load(relative)
        contract["current_authorization"]["cutover_authorized"] = True
        self.write(relative, contract)
        self.assertIn(
            "catalogue scale contract must not authorize cutover",
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

    def test_100k_stress_warning_cannot_be_silently_glossed_over(self):
        relative = "docs/evidence/catalog-platform-scaling-v1.json"
        evidence = self.load(relative)
        measurement = next(item for item in evidence["measurements"] if item["entry_count"] == 100_000)
        measurement["gate_evaluation"]["shard_gzip"] = "pass"
        self.write(relative, evidence)
        errors = MODULE.validate_catalog_scale_gates(self.root, verify_measurements=False)
        self.assertIn("100000: shard gate does not match measured size", errors)
        self.assertIn("100000: stress tier must preserve the measured prefix-depth warning", errors)

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
