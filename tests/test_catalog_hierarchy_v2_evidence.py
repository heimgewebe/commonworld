import copy
import json
import unittest
from pathlib import Path

from scripts.validate_catalog_hierarchy_v2 import validate_evidence

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "catalog-hierarchy-v2.json"


class CatalogHierarchyV2EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_committed_evidence_is_valid(self):
        validate_evidence(self.evidence)

    def test_budget_regression_fails_closed(self):
        mutated = copy.deepcopy(self.evidence)
        mutated["measurements"][-1]["metrics"]["shard_indexes"]["gzip_max_bytes"] = 32_769
        with self.assertRaisesRegex(ValueError, "shard_indexes budget"):
            validate_evidence(mutated)

    def test_cutover_claim_fails_closed(self):
        mutated = copy.deepcopy(self.evidence)
        mutated["migration_guard"]["cutover_authorized"] = True
        with self.assertRaisesRegex(ValueError, "cutover guard"):
            validate_evidence(mutated)

    def test_implementation_digest_drift_fails_closed(self):
        mutated = copy.deepcopy(self.evidence)
        path = next(iter(mutated["implementation_sha256"]))
        mutated["implementation_sha256"][path] = "0" * 64
        with self.assertRaisesRegex(ValueError, "implementation digest mismatch"):
            validate_evidence(mutated)


if __name__ == "__main__":
    unittest.main()
