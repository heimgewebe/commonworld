import hashlib
import http.client
import io
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from scripts.smoke_pages_live import (
    EXPECTED_CATALOG_ENTRY_COUNT,
    EXPECTED_CATALOG_PROJECT_FILES,
    EXPECTED_MACHINE_SURFACE,
    EXPECTED_PUBLICATION,
    LiveFetch,
    LiveFetchError,
    MIN_BODY_BYTES,
    PROPOSAL_REQUIRED_TOKENS,
    REQUIRED_TOKENS,
    fetch_live_url,
    validate_catalog_fetch,
    validate_live_fetch,
    validate_proposal_fetch,
    validate_runtime_asset_fetch,
)


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        body: bytes = b"ok",
    ) -> None:
        self.status = status
        self._url = url
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url


def http_error(url: str, status: int) -> urllib.error.HTTPError:
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"
    return urllib.error.HTTPError(url, status, f"HTTP {status}", headers, io.BytesIO(b"temporary"))


class FailingReadResponse(FakeResponse):
    def read(self) -> bytes:
        raise http.client.IncompleteRead(b"partial", 100)


class PagesLiveSmokeTests(unittest.TestCase):
    def valid_body(self) -> str:
        body = "\n".join(REQUIRED_TOKENS)
        return body + (" " * max(0, MIN_BODY_BYTES - len(body.encode("utf-8")) + 10))

    def valid_catalog(self) -> str:
        return json.dumps(
            {
                "schema_version": 1,
                "kind": "commonworld_public_catalog",
                "entry_count": EXPECTED_CATALOG_ENTRY_COUNT,
                "project_files": list(EXPECTED_CATALOG_PROJECT_FILES),
                "publication": EXPECTED_PUBLICATION,
                "machine_surface": EXPECTED_MACHINE_SURFACE,
            }
        )

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_retryable_503_then_success_is_transparent(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.side_effect = [
            http_error(url, 503),
            FakeResponse(url=url, body=b"recovered"),
        ]

        fetch = fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual("recovered", fetch.body)
        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(0.01)
        self.assertEqual(
            [(1, "http_error", 503, True), (2, "success", 200, False)],
            [(attempt.attempt, attempt.outcome, attempt.status, attempt.retryable) for attempt in fetch.attempts],
        )

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_persistent_503_fails_after_exactly_one_retry(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.side_effect = [http_error(url, 503), http_error(url, 503)]

        with self.assertRaises(LiveFetchError) as raised:
            fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(0.01)
        self.assertEqual([503, 503], [attempt.status for attempt in raised.exception.attempts])
        self.assertTrue(all(attempt.retryable for attempt in raised.exception.attempts))
        self.assertIn('"status":503', str(raised.exception))

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_nonretryable_404_fails_without_retry(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/missing"
        urlopen.side_effect = http_error(url, 404)

        with self.assertRaises(LiveFetchError) as raised:
            fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual(1, urlopen.call_count)
        sleep.assert_not_called()
        self.assertEqual(1, len(raised.exception.attempts))
        self.assertEqual(404, raised.exception.attempts[0].status)
        self.assertFalse(raised.exception.attempts[0].retryable)

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_transport_error_then_success_is_transparent(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.side_effect = [
            urllib.error.URLError("temporary route failure"),
            FakeResponse(url=url, body=b"recovered"),
        ]

        fetch = fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(0.01)
        self.assertEqual("transport_error", fetch.attempts[0].outcome)
        self.assertIsNone(fetch.attempts[0].status)
        self.assertTrue(fetch.attempts[0].retryable)
        self.assertEqual("success", fetch.attempts[1].outcome)

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_incomplete_body_read_then_success_is_transparent(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.side_effect = [
            FailingReadResponse(url=url),
            FakeResponse(url=url, body=b"recovered"),
        ]

        fetch = fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(0.01)
        self.assertEqual("transport_error", fetch.attempts[0].outcome)
        self.assertEqual("IncompleteRead", fetch.attempts[0].error_type)
        self.assertEqual("success", fetch.attempts[1].outcome)

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_decode_error_is_not_retried(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.return_value = FakeResponse(
            url=url,
            content_type="text/html; charset=utf-8",
            body=b"\xff",
        )

        with self.assertRaises(LiveFetchError) as raised:
            fetch_live_url(url, retry_delay_seconds=0.01)

        self.assertEqual(1, urlopen.call_count)
        sleep.assert_not_called()
        self.assertEqual("decode_error", raised.exception.attempts[0].outcome)
        self.assertFalse(raised.exception.attempts[0].retryable)

    @patch("scripts.smoke_pages_live.time.sleep")
    @patch("scripts.smoke_pages_live.urllib.request.urlopen")
    def test_retry_count_zero_disables_retry(self, urlopen, sleep) -> None:
        url = "https://commonworld.net/"
        urlopen.side_effect = http_error(url, 503)

        with self.assertRaises(LiveFetchError) as raised:
            fetch_live_url(url, retry_count=0, retry_delay_seconds=0.01)

        self.assertEqual(1, urlopen.call_count)
        sleep.assert_not_called()
        self.assertEqual(1, len(raised.exception.attempts))

    def test_retry_policy_is_bounded_to_zero_or_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "retry_count must be 0 or 1"):
            fetch_live_url("https://commonworld.net/", retry_count=2)

    def test_canonical_shell_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html; charset=utf-8",
            body=self.valid_body(),
        )
        self.assertEqual([], validate_live_fetch(fetch))

    def test_public_proposal_page_passes(self) -> None:
        body = "\n".join(PROPOSAL_REQUIRED_TOKENS)
        body += " " * max(0, 8_010 - len(body.encode("utf-8")))
        fetch = LiveFetch(
            requested_url="https://commonworld.net/propose.html",
            final_url="https://commonworld.net/propose.html",
            status=200,
            content_type="text/html; charset=utf-8",
            body=body,
        )
        self.assertEqual([], validate_proposal_fetch(fetch))

    def test_public_proposal_page_missing_no_auto_publish_fails(self) -> None:
        body = "\n".join(token for token in PROPOSAL_REQUIRED_TOKENS if token != "nicht automatisch veröffentlicht")
        body += " " * max(0, 8_010 - len(body.encode("utf-8")))
        fetch = LiveFetch(
            requested_url="https://commonworld.net/propose.html",
            final_url="https://commonworld.net/propose.html",
            status=200,
            content_type="text/html; charset=utf-8",
            body=body,
        )
        self.assertIn("live proposal page missing token: nicht automatisch veröffentlicht", validate_proposal_fetch(fetch))

    def test_public_catalog_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json; charset=utf-8",
            body=self.valid_catalog(),
        )
        self.assertEqual([], validate_catalog_fetch(fetch))

    def test_empty_catalog_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body="{}",
        )
        self.assertIn("live catalog must not be empty", validate_catalog_fetch(fetch))

    def test_catalog_boundary_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["publication"]["engine_selected"] = False
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_old_preproduction_boundary_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["publication"]["production_architecture_authorized"] = False
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_missing_production_delivery_boundary_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        del catalog["publication"]["production_delivery"]
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_machine_surface_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["machine_surface"]["write_path"] = True
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog machine-readable surface boundary mismatch", validate_catalog_fetch(fetch))

    def test_catalog_count_or_identity_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["project_files"].pop()
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn(
            f"live catalog must contain {EXPECTED_CATALOG_ENTRY_COUNT} entries",
            validate_catalog_fetch(fetch),
        )

        catalog = json.loads(self.valid_catalog())
        catalog["project_files"] = sorted(["projects/not-canonical.json", *catalog["project_files"][1:]])
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn(
            "live catalog project_files do not match the checked-out canonical catalog",
            validate_catalog_fetch(fetch),
        )

    def test_old_proof_hub_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html",
            body=self.valid_body() + " proof hub ",
        )
        self.assertIn("live Pages contains forbidden delivery token: proof hub", validate_live_fetch(fetch))

    def test_parking_page_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html",
            body=self.valid_body() + " Domain parked. ",
        )
        self.assertIn("live Pages contains forbidden delivery token: Domain parked.", validate_live_fetch(fetch))

    def test_runtime_asset_hash_and_delivery_pass(self) -> None:
        body = "x" * 128
        fetch = LiveFetch(
            requested_url="https://commonworld.net/assets/commonworld-app.js",
            final_url="https://commonworld.net/assets/commonworld-app.js",
            status=200,
            content_type="text/javascript; charset=utf-8",
            body=body,
        )
        self.assertEqual(
            [],
            validate_runtime_asset_fetch(
                fetch,
                minimum_bytes=100,
                allowed_content_types=("javascript",),
                expected_sha256=hashlib.sha256(body.encode()).hexdigest(),
            ),
        )

    def test_runtime_asset_hash_drift_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/assets/commonworld-app.js",
            final_url="https://commonworld.net/assets/commonworld-app.js",
            status=200,
            content_type="text/javascript",
            body="changed runtime",
        )
        errors = validate_runtime_asset_fetch(
            fetch,
            minimum_bytes=1,
            allowed_content_types=("javascript",),
            expected_sha256="0" * 64,
        )
        self.assertTrue(any("hash mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
