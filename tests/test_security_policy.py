import http.client
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.validate_security_policy import (
    PrivateReportingFetch,
    ROOT,
    github_api_get_private_reporting,
    validate_security_policy,
    verify_live_private_reporting,
    write_json_receipt,
)


class SecurityPolicyTests(unittest.TestCase):
    NOW = datetime(2026, 7, 28, tzinfo=timezone.utc)

    def copy_surface(self, directory: str) -> Path:
        root = Path(directory)
        for relative in (
            "SECURITY.md",
            ".well-known/security.txt",
            "_config.yml",
            ".github/workflows/production-readback.yml",
            ".github/workflows/security-policy-expiry.yml",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        return root

    def test_current_surface_validates(self) -> None:
        self.assertEqual([], validate_security_policy(ROOT, now=self.NOW))

    def test_expiry_window_and_strict_timestamp_fail_closed(self) -> None:
        cases = (
            ("2026-08-01T00:00:00Z", "more than 30 days"),
            ("2028-06-30T00:00:00Z", "no more than 366 days"),
            ("2027-06-30 00:00:00Z", "strict RFC 3339"),
            ("2027-06-30T00:00:60Z", "strict RFC 3339"),
        )
        for value, expected in cases:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(path.read_text().replace("2027-06-30T00:00:00Z", value))
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any(expected in error for error in errors), errors)

    def test_only_lf_is_accepted_as_line_separator(self) -> None:
        separators = ("\x0b", "\x0c", "\x85", "\u2028", "\u2029")
        for separator in separators:
            with self.subTest(separator=ascii(separator)), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                text = path.read_text(encoding="utf-8").replace("\nExpires:", separator + "Expires:", 1)
                path.write_text(text, encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertIn("security.txt may use only LF line separators", errors)

    def test_comment_grammar_rejects_controls_and_out_of_range_unicode(self) -> None:
        invalid_comments = (
            "#\x00bad",
            "#\x1fbad",
            "#\x7fbad",
            "#\x80bad",
            "#\x9fbad",
            "#\U00100000bad",
        )
        for comment in invalid_comments:
            with self.subTest(comment=ascii(comment)), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(comment + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any("comment line 1 contains a forbidden character" in error for error in errors), errors)

    def test_net_unicode_rejects_non_nfc_unassigned_and_bom(self) -> None:
        cases = (
            ("# a\u0308\n", "security.txt must use Net-Unicode NFC normalization"),
            ("# unassigned: \u0378\n", "security.txt must not contain unassigned Unicode code points"),
            ("\ufeff", "security.txt must not begin with a Unicode BOM"),
        )
        for prefix, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(prefix + path.read_text(encoding="utf-8"), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertIn(expected, errors)

    def test_comment_grammar_accepts_reviewed_visible_unicode_and_blank_wsp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            prefix = "# Reviewed ASCII, tab\tand Unicode: ä and NBSP:\u00a0\n \t \n"
            path.write_text(prefix + path.read_text(encoding="utf-8"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertEqual([], errors)

    def test_exact_field_grammar_and_terminal_lf_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text().replace("Contact: https://", "Contact:https://"))
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("exact 'Field: value' grammar" in error for error in errors))
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_bytes(path.read_bytes().rstrip(b"\n"))
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt must end with LF", errors)

    def test_public_or_invented_contact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            security = root / ".well-known/security.txt"
            security.write_text(security.read_text().replace(
                "https://github.com/heimgewebe/commonworld/security/advisories/new",
                "mailto:security@example.invalid",
            ))
            policy = root / "SECURITY.md"
            policy.write_text(policy.read_text().replace("Do not use public issues", "Public issues are accepted"))
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Contact must equal" in error for error in errors))
        self.assertIn("security disclosure surface must not invent an email contact", errors)
        self.assertTrue(any("Do not use public issues" in error for error in errors))

    def test_jekyll_scope_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            (root / "_config.yml").write_text("include:\n  - .well-known\n  - .github\n")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("Jekyll configuration must expose only the reviewed .well-known directory", errors)

    def test_live_private_reporting_passes_only_for_exact_enabled_endpoint(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "a" * 40,
            api_get=lambda: PrivateReportingFetch(endpoint, endpoint, 200, {"enabled": True}),
            now=lambda: "2026-07-28T06:00:00Z",
        )
        self.assertEqual("pass", receipt["verdict"])
        self.assertTrue(receipt["enabled"])
        self.assertIn("workflow trust or branch protection", receipt["does_not_establish"])

    def test_disabled_redirected_malformed_and_non_200_responses_fail(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"
        cases = (
            (PrivateReportingFetch(endpoint, endpoint, 200, {"enabled": False}), "must be enabled"),
            (PrivateReportingFetch(endpoint, endpoint + "/redirect", 200, {"enabled": True}), "redirected"),
            (PrivateReportingFetch(endpoint, endpoint, 429, {"enabled": True}), "HTTP 200"),
            (PrivateReportingFetch(endpoint, endpoint, 200, {"enabled": "yes"}), "boolean enabled"),
        )
        for fetch, expected in cases:
            with self.subTest(expected=expected):
                receipt = verify_live_private_reporting(
                    "heimgewebe/commonworld", "b" * 40, api_get=lambda fetch=fetch: fetch,
                    now=lambda: "2026-07-28T06:00:00Z",
                )
            self.assertEqual("fail", receipt["verdict"])
            self.assertTrue(any(expected in error for error in receipt["errors"]), receipt)

    def test_transport_failure_is_generic_and_receipt_is_written(self) -> None:
        def fail():
            raise RuntimeError("private vulnerability reporting transport failed: TimeoutError")
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld", "c" * 40, api_get=fail,
            now=lambda: "2026-07-28T06:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertNotIn("secret", json.dumps(receipt).casefold())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json_receipt(path, receipt)
            self.assertEqual(receipt, json.loads(path.read_text()))

    def test_http_error_preserves_status_without_exposing_body(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"
        error = urllib.error.HTTPError(endpoint, 429, "limited", {}, io.BytesIO(b'{"message":"private detail"}'))
        with patch("urllib.request.urlopen", side_effect=error):
            fetch = github_api_get_private_reporting("heimgewebe/commonworld")
        self.assertEqual(429, fetch.status)
        self.assertEqual(endpoint, fetch.requested_url)

    def test_incomplete_http_error_body_keeps_metadata(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"
        class Body:
            def read(self):
                raise http.client.IncompleteRead(b"{", 4)
            def close(self):
                return None
        error = urllib.error.HTTPError(endpoint, 503, "unavailable", {}, Body())
        with patch("urllib.request.urlopen", side_effect=error):
            fetch = github_api_get_private_reporting("heimgewebe/commonworld")
        self.assertEqual(503, fetch.status)
        self.assertIsNone(fetch.payload)

    def test_workflow_markers_are_operational_checks_not_trust_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/production-readback.yml"
            path.write_text(path.read_text().replace("--verify-live-setting", "--offline-only"))
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("production readback" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
