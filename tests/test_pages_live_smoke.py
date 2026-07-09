import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.smoke_pages_live import (
    FORBIDDEN_TOKENS,
    LiveFetch,
    REQUIRED_TOKENS,
    URL_ENV,
    default_url,
    run_live_smoke,
    validate_live_fetch,
)


def valid_body() -> str:
    visible = "\n".join(REQUIRED_TOKENS)
    return "<!doctype html><html><head><title>commonworld proof hub</title></head><body>" + visible + ("\nstatic proof hub" * 600) + "</body></html>"


class PagesLiveSmokeTests(unittest.TestCase):
    def test_default_url_prefers_env(self) -> None:
        with mock.patch.dict(os.environ, {URL_ENV: "https://example.test/"}, clear=False):
            self.assertEqual("https://example.test/", default_url(Path(tempfile.mkdtemp())))

    def test_default_url_uses_cname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "CNAME").write_text("commonworld.net\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual("https://commonworld.net/", default_url(root))

    def test_valid_live_fetch_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html; charset=utf-8",
            body=valid_body(),
        )
        self.assertEqual([], validate_live_fetch(fetch))

    def test_parking_page_fails_with_specific_tokens(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="http://commonworld.net/",
            status=200,
            content_type="text/html; charset=UTF-8",
            body="<html><title>commonworld.net</title><body><h1>Domain parked.</h1><script src='http://commonworld.net/assets/js/script.js'></script>INWX</body></html>",
        )
        errors = validate_live_fetch(fetch)
        self.assertIn("live Pages contains forbidden delivery token: Domain parked.", errors)
        self.assertIn("live Pages contains forbidden delivery token: INWX", errors)
        self.assertIn("live Pages contains forbidden delivery token: <script", errors)
        self.assertTrue(any(error.startswith("live Pages missing required proof-hub token") for error in errors))

    def test_github_pages_https_redirect_to_http_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://heimgewebe.github.io/commonworld/",
            final_url="http://commonworld.net/",
            status=200,
            content_type="text/html",
            body=valid_body(),
        )
        self.assertIn(
            "live Pages redirected from HTTPS GitHub Pages URL to insecure HTTP URL: http://commonworld.net/",
            validate_live_fetch(fetch),
        )

    def test_run_live_smoke_receipt_uses_fetcher(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html; charset=utf-8",
            body=valid_body(),
        )
        with mock.patch("scripts.smoke_pages_live.fetch_live_url", return_value=fetch):
            receipt = run_live_smoke("https://commonworld.net/")
        self.assertEqual("commonworld.pages-live.delivery-smoke.v1", receipt.smoke_id)
        self.assertEqual("https://commonworld.net/", receipt.final_url)
        self.assertEqual(tuple(REQUIRED_TOKENS), receipt.required_tokens)
        self.assertEqual(tuple(FORBIDDEN_TOKENS), receipt.forbidden_tokens_absent)
        self.assertIn("no deploy, DNS, Pages, GitHub or INWX mutation", receipt.boundary)


if __name__ == "__main__":
    unittest.main()
