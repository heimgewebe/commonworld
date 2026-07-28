from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.public_cache import page_build_metadata, stamp_page_build, version_page_links, versioned_page_href
from scripts.validate_cache_coherence import ROOT, validate


class PublicCacheMetadataTests(unittest.TestCase):
    def test_page_build_is_deterministic_and_content_bound(self) -> None:
        source = '<!doctype html>\n<html><head>\n    <meta charset="utf-8" />\n</head><body>one</body></html>\n'
        first = stamp_page_build(source, "index.html")
        second = stamp_page_build(source, "index.html")
        changed = stamp_page_build(source.replace("one", "two"), "index.html")
        self.assertEqual(first, second)
        self.assertNotEqual(page_build_metadata(first)[1], page_build_metadata(changed)[1])
        self.assertEqual(("index.html", page_build_metadata(first)[1]), page_build_metadata(first))

    def test_page_build_rejects_duplicate_metadata(self) -> None:
        source = '<!doctype html>\n<html><head>\n    <meta charset="utf-8" />\n<meta name="commonworld-page" content="index.html" /></head></html>'
        with self.assertRaises(ValueError):
            stamp_page_build(source, "index.html")

    def test_versioned_page_links_bind_rendered_target_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            method = stamp_page_build(
                '<!doctype html>\n<html><head>\n    <meta charset="utf-8" />\n</head><body>method</body></html>\n',
                "method.html",
            )
            (root / "method.html").write_text(method, encoding="utf-8")
            build = page_build_metadata(method)[1]
            self.assertEqual(f"./method.html?cw_release={build}", versioned_page_href("method.html", root))
            rendered = version_page_links('<a href="./method.html">Method</a>', ("method.html",), root)
            self.assertEqual(f'<a href="./method.html?cw_release={build}">Method</a>', rendered)


class CacheCoherenceValidationTests(unittest.TestCase):
    def test_repository_cache_coherence_validates(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_validator_rejects_stale_page_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "assets/commonworld-page-builds.json",
                "assets/commonworld-release-check.js",
                "assets/commonworld-mark.svg",
                "assets/vendor/maplibre-gl.css",
                "assets/vendor/maplibre-gl.js",
                "assets/ipad-layout.css",
                "assets/commonworld-app.js",
                "assets/commonworld-proposal.js",
                "assets/proposal.css",
                "assets/map/commonworld-country-boundaries.geojson",
                "assets/map/openfreemap-liberty.json",
                "index.css",
                "package.json",
            ):
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            for relative in ("index.html", "de.html", "method.html", "method.de.html", "propose.html", "propose.de.html"):
                source = ROOT / relative
                target = root / relative
                target.write_bytes(source.read_bytes())
            manifest = root / "assets/commonworld-page-builds.json"
            manifest.write_text('{"kind":"commonworld.page_build_manifest","pages":{},"schema_version":1}\n', encoding="utf-8")
            self.assertIn("public page-build manifest does not match rendered pages", validate(root))


if __name__ == "__main__":
    unittest.main()
