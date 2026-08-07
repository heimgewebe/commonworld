from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import build_page_release_manifest as release_builder
from scripts import validate_release_snapshot_lifecycle as lifecycle_validator
from scripts.measure_release_snapshot_lifecycle import build_evidence
from scripts.validate_release_snapshot_lifecycle import (
    ROOT,
    reproduce_append_only_merge,
    reproduce_legacy_conflict,
    validate,
)


class ReleaseSnapshotBuilderTests(unittest.TestCase):
    def test_new_release_retains_common_ancestor_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "index.html"
            second = root / "assets" / "payload.js"
            second.parent.mkdir(parents=True)
            first.write_text("first release\n", encoding="utf-8")
            second.write_text("shared payload\n", encoding="utf-8")
            sources = (first, second)
            old_release = "a" * 20
            new_release = "b" * 20
            with mock.patch.object(release_builder, "snapshot_files", return_value=sources):
                release_builder.build_snapshot(root, old_release)
                first.write_text("second release\n", encoding="utf-8")
                release_builder.build_snapshot(root, new_release)

            self.assertEqual(
                "first release\n",
                (root / "releases" / old_release / "index.html").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "second release\n",
                (root / "releases" / new_release / "index.html").read_text(encoding="utf-8"),
            )

    def test_existing_content_addressed_release_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "index.html"
            source.write_text("canonical\n", encoding="utf-8")
            release_id = "c" * 20
            with mock.patch.object(release_builder, "snapshot_files", return_value=(source,)):
                snapshot = release_builder.build_snapshot(root, release_id)
                (snapshot / "index.html").write_text("corrupted\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "immutable release snapshot content drift"):
                    release_builder.build_snapshot(root, release_id)

    def test_existing_release_with_extra_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "index.html"
            source.write_text("canonical\n", encoding="utf-8")
            release_id = "d" * 20
            with mock.patch.object(release_builder, "snapshot_files", return_value=(source,)):
                snapshot = release_builder.build_snapshot(root, release_id)
                (snapshot / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "immutable release snapshot file set drift"):
                    release_builder.build_snapshot(root, release_id)


class ReleaseConflictModelTests(unittest.TestCase):
    def test_legacy_replace_model_reproduces_conflicts(self) -> None:
        conflict, unmerged = reproduce_legacy_conflict()
        self.assertTrue(conflict)
        self.assertGreater(unmerged, 0)

    def test_append_only_model_merges_cleanly(self) -> None:
        clean, unmerged = reproduce_append_only_merge()
        self.assertTrue(clean)
        self.assertEqual(0, unmerged)

    def test_repository_release_lifecycle_validates(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_generated_evidence_matches_repository_binding(self) -> None:
        bound = json.loads(
            (ROOT / "docs/evidence/release-snapshot-lifecycle-v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(bound, build_evidence(ROOT))

    def test_changed_proposed_head_input_invalidates_evidence(self) -> None:
        original = lifecycle_validator.file_sha256

        def changed_hash(path: Path) -> str:
            digest = original(path)
            if path.name == "build_page_release_manifest.py":
                return "0" * 64
            return digest

        with mock.patch.object(lifecycle_validator, "file_sha256", side_effect=changed_hash):
            errors = lifecycle_validator.validate(ROOT)
        self.assertTrue(
            any("proposed-head input digests are stale" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
