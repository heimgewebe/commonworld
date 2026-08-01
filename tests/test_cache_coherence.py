from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_page_release_manifest import compute_release_id, snapshot_files
from scripts.public_cache import (
    RELEASE_ID_PLACEHOLDER,
    finalize_page_release,
    page_build_metadata,
    page_release_id,
    stamp_page_build,
)
from scripts.validate_cache_coherence import ROOT, validate


SOURCE = '<!doctype html>\n<html><head>\n    <meta charset="utf-8" />\n</head><body>one</body></html>\n'


class PublicCacheMetadataTests(unittest.TestCase):
    def test_page_build_is_deterministic_and_content_bound(self) -> None:
        first = stamp_page_build(SOURCE, "index.html")
        second = stamp_page_build(SOURCE, "index.html")
        changed = stamp_page_build(SOURCE.replace("one", "two"), "index.html")
        self.assertEqual(first, second)
        self.assertNotEqual(page_build_metadata(first)[1], page_build_metadata(changed)[1])
        self.assertEqual(RELEASE_ID_PLACEHOLDER, page_release_id(first))

    def test_release_self_reference_does_not_change_page_build(self) -> None:
        stamped = stamp_page_build(SOURCE, "index.html")
        before = page_build_metadata(stamped)[1]
        finalized = finalize_page_release(stamped, "a" * 20)
        self.assertEqual(before, page_build_metadata(finalized)[1])
        self.assertEqual("a" * 20, page_release_id(finalized))
        self.assertIn('<base href="/releases/aaaaaaaaaaaaaaaaaaaa/" />', finalized)

    def test_final_html_drift_is_rejected_even_when_metadata_is_unchanged(self) -> None:
        finalized = finalize_page_release(stamp_page_build(SOURCE, "method.html"), "b" * 20)
        drifted = finalized.replace("one", "changed after stamping", 1)
        with self.assertRaisesRegex(ValueError, "does not match final HTML bytes"):
            page_build_metadata(drifted)

    def test_page_build_rejects_duplicate_cache_metadata(self) -> None:
        source = SOURCE.replace(
            '<meta charset="utf-8" />',
            '<meta charset="utf-8" />\n<meta name="commonworld-page" content="index.html" />',
        )
        with self.assertRaises(ValueError):
            stamp_page_build(source, "index.html")


class CacheCoherenceValidationTests(unittest.TestCase):
    def test_repository_cache_coherence_validates(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_release_bound_pages_use_base_safe_fragment_links(self) -> None:
        expected = {
            "index.html": 'href="/#static-catalog-fallback"',
            "de.html": 'href="/de.html#static-catalog-fallback"',
            "propose.html": 'href="/propose.html#commons-proposal-form"',
            "propose.de.html": 'href="/propose.de.html#commons-proposal-form"',
        }
        for relative, token in expected.items():
            with self.subTest(relative=relative):
                page = (ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn('href="#', page)
                self.assertEqual(1, page.count(token))

    def test_release_checker_survives_removal_of_the_page_snapshot(self) -> None:
        manifest = json.loads((ROOT / "assets/commonworld-page-builds.json").read_text(encoding="utf-8"))
        release_id = manifest["release_id"]
        expected = '<script type="module" src="/assets/commonworld-release-check.js?v='
        forbidden = '<script type="module" src="./assets/commonworld-release-check.js?v='
        for relative in ("index.html", "de.html", "propose.html", "propose.de.html"):
            with self.subTest(relative=relative):
                canonical = (ROOT / relative).read_text(encoding="utf-8")
                snapshot = (ROOT / "releases" / release_id / relative).read_text(encoding="utf-8")
                self.assertIn(expected, canonical)
                self.assertIn(expected, snapshot)
                self.assertNotIn(forbidden, canonical)
                self.assertNotIn(forbidden, snapshot)

    def test_release_identity_changes_when_public_asset_changes(self) -> None:
        current = compute_release_id(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in snapshot_files(ROOT, include_manifest=False):
                relative = source.relative_to(ROOT)
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            asset = root / "assets/commonworld-mark.svg"
            asset.write_text(f"{asset.read_text(encoding='utf-8')}\n", encoding="utf-8")
            self.assertNotEqual(current, compute_release_id(root))

    def test_validator_rejects_stale_final_page_bytes_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_source = ROOT / "docs/architecture/locale-release.contract.json"
            contract_target = root / "docs/architecture/locale-release.contract.json"
            contract_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(contract_source, contract_target)
            manifest = json.loads((ROOT / "assets/commonworld-page-builds.json").read_text(encoding="utf-8"))
            release_id = manifest["release_id"]
            for source in snapshot_files(ROOT, include_manifest=True):
                relative = source.relative_to(ROOT)
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                snapshot_target = root / "releases" / release_id / relative
                snapshot_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, snapshot_target)
            for relative in ("404.html", "package.json"):
                shutil.copy2(ROOT / relative, root / relative)
            method = root / "method.html"
            method.write_text(method.read_text(encoding="utf-8").replace("Method, coverage and privacy", "Undeclared drift", 1), encoding="utf-8")
            errors = validate(root)
            self.assertTrue(any("final HTML bytes" in error for error in errors), errors)

    def test_validator_rejects_snapshot_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_source = ROOT / "docs/architecture/locale-release.contract.json"
            contract_target = root / "docs/architecture/locale-release.contract.json"
            contract_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(contract_source, contract_target)
            manifest = json.loads((ROOT / "assets/commonworld-page-builds.json").read_text(encoding="utf-8"))
            release_id = manifest["release_id"]
            for source in snapshot_files(ROOT, include_manifest=True):
                relative = source.relative_to(ROOT)
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                snapshot_target = root / "releases" / release_id / relative
                snapshot_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, snapshot_target)
            for relative in ("404.html", "package.json"):
                shutil.copy2(ROOT / relative, root / relative)
            snapshot_method = root / "releases" / release_id / "method.html"
            snapshot_method.write_text(snapshot_method.read_text(encoding="utf-8").replace("Method, coverage and privacy", "Snapshot drift", 1), encoding="utf-8")
            errors = validate(root)
            self.assertTrue(any("snapshot file differs" in error for error in errors), errors)

    def test_validator_rejects_noncanonical_404_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_source = ROOT / "docs/architecture/locale-release.contract.json"
            contract_target = root / "docs/architecture/locale-release.contract.json"
            contract_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(contract_source, contract_target)
            manifest = json.loads((ROOT / "assets/commonworld-page-builds.json").read_text(encoding="utf-8"))
            release_id = manifest["release_id"]
            for source in snapshot_files(ROOT, include_manifest=True):
                relative = source.relative_to(ROOT)
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                snapshot_target = root / "releases" / release_id / relative
                snapshot_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, snapshot_target)
            shutil.copy2(ROOT / "package.json", root / "package.json")
            not_found = (ROOT / "404.html").read_text(encoding="utf-8").replace('"schema_version":2', '"schema_version":1', 1)
            (root / "404.html").write_text(not_found, encoding="utf-8")
            self.assertIn("custom 404 release marker does not exactly match canonical manifest", validate(root))


if __name__ == "__main__":
    unittest.main()
