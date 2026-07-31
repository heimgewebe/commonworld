from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path

from scripts.validate_commons_admission import validate


class CommonsAdmissionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for directory in (
            "contracts/commonworld",
            "catalog/projects",
            "catalog/commons-bases",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        source_root = Path(__file__).resolve().parents[1]
        for relative in (
            "contracts/commonworld/commons-definition.contract.json",
            "contracts/commonworld/commons-basis.schema.json",
            "catalog/commons-bases/retroreview-policy.json",
        ):
            target = self.root / relative
            target.write_text(
                (source_root / relative).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def project(
        project_id: str,
        *,
        catalogued_at: str = "2026-07-31",
        reviewed_at: str = "2026-07-31",
        next_review_at: str = "2026-10-31",
        state: str = "listed",
    ) -> dict:
        return {
            "id": project_id,
            "provenance": {
                "sources": [
                    {"id": "official-source"},
                ]
            },
            "curation": {
                "state": state,
                "catalogued_at": catalogued_at,
                "reviewed_at": reviewed_at,
                "next_review_at": next_review_at,
            },
        }

    @staticmethod
    def basis(project_id: str, reviewed_at: str = "2026-07-31") -> dict:
        criterion = {
            "status": "supported",
            "statement": "Primary-near evidence supports this required Commons dimension.",
            "source_ids": ["official-source"],
        }
        return {
            "schema_version": 1,
            "kind": "commonworld_commons_basis",
            "project_id": project_id,
            "classification": "common",
            "decision": "include",
            "reviewed_at": reviewed_at,
            "reviewer": "Test editorial review",
            "criteria": {
                key: deepcopy(criterion)
                for key in (
                    "shared_resource",
                    "community",
                    "commoning_practice",
                    "rules_and_responsibility",
                    "common_benefit",
                )
            },
            "confidence": 0.8,
            "limitations": [],
        }

    def write_case(self, projects: list[dict], bases: list[dict]) -> None:
        project_files = []
        for project in projects:
            filename = f"projects/{project['id']}.json"
            project_files.append(filename)
            (self.root / "catalog" / filename).write_text(
                json.dumps(project),
                encoding="utf-8",
            )
        manifest = {
            "entry_count": len(project_files),
            "project_files": sorted(project_files),
        }
        (self.root / "catalog/catalog.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        basis_files = []
        for basis in bases:
            filename = f"{basis['project_id']}.json"
            basis_files.append(filename)
            (self.root / "catalog/commons-bases" / filename).write_text(
                json.dumps(basis),
                encoding="utf-8",
            )
        index = {
            "entry_count": len(basis_files),
            "basis_files": sorted(basis_files),
        }
        (self.root / "catalog/commons-bases/index.json").write_text(
            json.dumps(index),
            encoding="utf-8",
        )

    def test_new_record_with_source_bound_basis_passes(self) -> None:
        self.write_case([self.project("new-common")], [self.basis("new-common")])
        self.assertEqual(validate(self.root, today=date(2026, 7, 31)), [])

    def test_new_record_without_basis_fails_closed(self) -> None:
        self.write_case([self.project("new-common")], [])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(any("lacks Commons basis" in error for error in errors))

    def test_unknown_dimension_may_record_an_honest_empty_source_gap(self) -> None:
        project = self.project("unclear-common", state="candidate")
        basis = self.basis("unclear-common")
        basis["classification"] = "undetermined"
        basis["decision"] = "needs_information"
        basis["criteria"]["community"] = {
            "status": "unknown",
            "statement": "No primary-near source currently establishes a participating community.",
            "source_ids": [],
        }
        self.write_case([project], [basis])
        self.assertEqual(validate(self.root, today=date(2026, 7, 31)), [])

    def test_include_cannot_use_undetermined_classification(self) -> None:
        project = self.project("new-common")
        basis = self.basis("new-common")
        basis["classification"] = "undetermined"
        self.write_case([project], [basis])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(
            any(
                "classification" in error
                and "commons-infrastructure" in error
                for error in errors
            )
        )

    def test_needs_information_requires_an_unresolved_dimension(self) -> None:
        project = self.project("unclear-common", state="candidate")
        basis = self.basis("unclear-common")
        basis["classification"] = "undetermined"
        basis["decision"] = "needs_information"
        self.write_case([project], [basis])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(
            any(
                "needs_information requires at least one partial or unknown dimension" in error
                for error in errors
            )
        )

    def test_reject_requires_an_unsupported_dimension(self) -> None:
        project = self.project("rejected-common", state="archived")
        basis = self.basis("rejected-common")
        basis["classification"] = "undetermined"
        basis["decision"] = "reject"
        self.write_case([project], [basis])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(
            any(
                "reject requires at least one unsupported dimension" in error
                for error in errors
            )
        )

    def test_supported_dimension_requires_at_least_one_source(self) -> None:
        project = self.project("new-common")
        basis = self.basis("new-common")
        basis["criteria"]["community"]["source_ids"] = []
        self.write_case([project], [basis])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(
            any(
                "criteria.community.source_ids" in error
                and "non-empty" in error
                for error in errors
            )
        )

    def test_legacy_record_is_queued_until_effective_deadline(self) -> None:
        legacy = self.project(
            "legacy-common",
            catalogued_at="2026-07-12",
            reviewed_at="2026-07-12",
            next_review_at="2026-08-15",
        )
        self.write_case([legacy], [])
        self.assertEqual(validate(self.root, today=date(2026, 8, 15)), [])

    def test_unknown_basis_source_fails(self) -> None:
        project = self.project("new-common")
        basis = self.basis("new-common")
        basis["criteria"]["community"]["source_ids"] = ["invented-source"]
        self.write_case([project], [basis])
        errors = validate(self.root, today=date(2026, 7, 31))
        self.assertTrue(any("unknown project sources" in error for error in errors))

    def test_overdue_legacy_listing_fails_after_migration_grace(self) -> None:
        legacy = self.project(
            "legacy-common",
            catalogued_at="2026-07-12",
            reviewed_at="2026-07-12",
            next_review_at="2026-07-20",
        )
        self.write_case([legacy], [])
        errors = validate(self.root, today=date(2026, 9, 1))
        self.assertTrue(any("review overdue" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
