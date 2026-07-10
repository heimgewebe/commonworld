import json
import os
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from scripts.smoke_map_proof_browser import parse_result, run_browser_smoke, validate_result
from scripts.smoke_proof_hub_browser import BROWSER_ENV
from scripts.validate_contracts import ROOT


GOOD_RESULT = {
    "markerCount": 2,
    "loadState": "Map ready. 2 location-safe nodes rendered. 1 non-map project skipped.",
    "openElapsedMs": 32.0,
    "openSnapshot": {
        "hidden": False,
        "opacity": "1",
        "transform": "none",
        "transitionDuration": "0s",
        "willChange": "auto",
        "inViewport": True,
    },
    "closed": True,
    "reopened": True,
}


def write_fake_browser(path: Path, result: dict) -> None:
    payload = json.dumps(result).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    path.write_text(
        textwrap.dedent(
            f'''\
            #!/usr/bin/env python3
            print('<html><body><pre id="result">{payload}</pre></body></html>')
            '''
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class MapProofBrowserSmokeTests(unittest.TestCase):
    def test_parse_result_reads_browser_payload(self) -> None:
        dom = '<html><pre id="result">' + json.dumps(GOOD_RESULT) + "</pre></html>"
        self.assertEqual(GOOD_RESULT, parse_result(dom))

    def test_valid_result_has_no_errors(self) -> None:
        self.assertEqual([], validate_result(GOOD_RESULT))

    def test_inherited_opacity_and_motion_fail(self) -> None:
        result = json.loads(json.dumps(GOOD_RESULT))
        result["openSnapshot"]["opacity"] = "0"
        result["openSnapshot"]["transitionDuration"] = "0.18s, 0.26s"
        errors = validate_result(result)
        self.assertIn("map detail panel opacity must be 1, got 0", errors)
        self.assertTrue(any("must not inherit proof transitions" in error for error in errors))

    def test_fake_browser_produces_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            browser = Path(tmp_dir) / "fake-browser"
            write_fake_browser(browser, GOOD_RESULT)
            with mock.patch.dict(os.environ, {BROWSER_ENV: str(browser)}, clear=False):
                receipt = run_browser_smoke(ROOT, timeout_seconds=2)
        self.assertEqual("commonworld.map-proof.browser-interaction-smoke.v1", receipt.smoke_id)
        self.assertEqual(2, receipt.marker_count)
        self.assertTrue(receipt.panel_closed)
        self.assertTrue(receipt.panel_reopened)
        self.assertEqual("none", receipt.panel_transform)

    def test_harness_error_is_actionable(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "map browser harness failed"):
            parse_result('<pre id="result">{"error":"boom"}</pre>')

    def test_harness_runs_directly_in_map_document(self) -> None:
        from scripts.smoke_map_proof_browser import HARNESS

        self.assertIn('document.querySelector("[data-detail-surface]")', HARNESS)
        self.assertNotIn("iframe", HARNESS)


if __name__ == "__main__":
    unittest.main()
