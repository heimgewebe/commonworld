import http.client
import io
import json
import urllib.error
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate_security_policy import PrivateReportingFetch, ROOT, github_api_get_private_reporting, validate_security_policy, verify_live_private_reporting, write_json_receipt


class SecurityPolicyTests(unittest.TestCase):
    REQUIRED = ("SECURITY.md", ".well-known/security.txt", "_config.yml", ".github/workflows/validate.yml", ".github/workflows/production-readback.yml", ".github/workflows/security-policy-expiry.yml")
    NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)

    def copy_surface(self, directory: str) -> Path:
        root = Path(directory)
        for relative in self.REQUIRED:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def test_current_surface_validates(self) -> None:
        self.assertEqual([], validate_security_policy(ROOT, now=self.NOW))

    def test_expired_or_nearly_expired_security_txt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            text = path.read_text(encoding="utf-8").replace(
                "Expires: 2027-06-30T00:00:00Z",
                "Expires: 2026-08-01T00:00:00Z",
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must remain more than 30 days in the future", errors)

    def test_overlong_expiry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            text = path.read_text(encoding="utf-8").replace(
                "Expires: 2027-06-30T00:00:00Z",
                "Expires: 2028-06-30T00:00:00Z",
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must be no more than 366 days in the future", errors)

    def test_non_rfc3339_expiry_grammar_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text(encoding="utf-8").replace("Expires: 2027-06-30T00:00:00Z", "Expires: 20270630T000000+0000"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must be strict RFC 3339", errors)

    def test_public_issue_or_invented_email_contact_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            security = root / ".well-known/security.txt"
            security.write_text(
                security.read_text(encoding="utf-8").replace(
                    "https://github.com/heimgewebe/commonworld/security/advisories/new",
                    "mailto:security@example.invalid",
                ),
                encoding="utf-8",
            )
            policy = root / "SECURITY.md"
            policy.write_text(
                policy.read_text(encoding="utf-8").replace("Do not use public issues", "Public issues are acceptable"),
                encoding="utf-8",
            )
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Contact must equal" in error for error in errors))
        self.assertIn("security disclosure surface must not invent an email contact", errors)
        self.assertTrue(any("Do not use public issues" in error for error in errors))

    def test_unreviewed_field_and_broad_nojekyll_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text(encoding="utf-8") + "Hiring: https://example.invalid/jobs\n", encoding="utf-8")
            (root / ".nojekyll").write_text("", encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt field is not reviewed: Hiring", errors)
        self.assertIn(".nojekyll would publish an unnecessarily broad dotfile surface", errors)

    def test_jekyll_include_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            (root / "_config.yml").write_text("include:\n  - .well-known\n  - .github\n", encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("Jekyll configuration must expose only the reviewed .well-known directory", errors)

    def test_live_private_reporting_receipt_passes_only_when_enabled(self) -> None:
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "a" * 40,
            api_get=lambda: PrivateReportingFetch("https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", 200, {"enabled": True}),
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("pass", receipt["verdict"])
        self.assertTrue(receipt["enabled"])

    def test_live_private_reporting_disabled_fails_and_writes_receipt(self) -> None:
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "b" * 40,
            api_get=lambda: PrivateReportingFetch("https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", 200, {"enabled": False}),
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertIn("private vulnerability reporting must be enabled before publication", receipt["errors"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json_receipt(path, receipt)
            stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt, stored)

    def test_live_private_reporting_malformed_response_fails(self) -> None:
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "c" * 40,
            api_get=lambda: PrivateReportingFetch("https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", 200, {"enabled": "yes"}),
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertIn("private vulnerability reporting response must contain boolean enabled", receipt["errors"])

    def test_private_reporting_redirect_or_status_fails(self) -> None:
        redirected = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "e" * 40,
            api_get=lambda: PrivateReportingFetch("https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", "https://api.github.com/redirected", 200, {"enabled": True}),
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", redirected["verdict"])
        self.assertIn("private vulnerability reporting endpoint redirected or mismatched", redirected["errors"])
        wrong_status = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "f" * 40,
            api_get=lambda: PrivateReportingFetch("https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting", 206, {"enabled": True}),
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertIn("private vulnerability reporting status must be 200, got 206", wrong_status["errors"])

    def test_malformed_repository_still_produces_failed_receipt(self) -> None:
        receipt = verify_live_private_reporting(
            "heimgewebe/common world",
            "a" * 40,
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertIsNone(receipt["endpoint"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json_receipt(path, receipt)
            self.assertEqual(receipt, json.loads(path.read_text(encoding="utf-8")))

    def test_security_txt_requires_exact_field_grammar_and_terminal_lf(self) -> None:
        mutations = (
            ("Contact: https://", "Contact:https://"),
            ("Contact: https://", " Contact: https://"),
        )
        for old, new in mutations:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any("exact 'Field: value' grammar" in error for error in errors))
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_bytes(path.read_bytes().rstrip(b"\n"))
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt must end with LF", errors)

    def test_future_leap_second_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text(encoding="utf-8").replace("2027-06-30T00:00:00Z", "2027-06-30T00:00:60Z"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must be strict RFC 3339", errors)

    def test_premerge_workflow_requires_exact_head_live_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/validate.yml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("--verify-live-setting\n", "--offline-only\n", 1)
            text += "\n# --verify-live-setting\n"
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Verify private vulnerability reporting before merge" in error and "command mismatch" in error for error in errors))

    def test_production_marker_relocation_does_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/production-readback.yml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("--verify-live-setting\n", "--offline-only\n", 1)
            text += "\n# --verify-live-setting\n"
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Verify private vulnerability reporting setting" in error and "command mismatch" in error for error in errors))

    def test_expiry_workflow_requires_schedule_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            start = text.index("- name: Verify private vulnerability reporting remains enabled")
            end = text.index("- name: Upload scheduled security receipt", start)
            block = text[start:end].replace("python3 scripts/validate_security_policy.py", "true")
            path.write_text(text[:start] + block + text[end:], encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Verify private vulnerability reporting remains enabled" in error and "command mismatch" in error for error in errors))

    def test_non_rfc3339_expiry_separator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text(encoding="utf-8").replace("Expires: 2027-06-30T00:00:00Z", "Expires: 2027-06-30 00:00:00Z"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must be strict RFC 3339", errors)

    def test_non_rfc3339_expiry_spellings_fail(self) -> None:
        invalid_values = (
            "2027-06-30 00:00:00Z",
            "20270630T000000Z",
            "2027-W26-3T00:00:00Z",
            "2027-06-30T00:00:00+0000",
            "2027-06-30T00:00:00+00:00:30",
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(path.read_text(encoding="utf-8").replace("2027-06-30T00:00:00Z", invalid), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertIn("security.txt Expires must be strict RFC 3339", errors)

    def test_rfc3339_fractional_offset_and_lowercase_tz_pass(self) -> None:
        for valid in ("2027-06-30T01:30:00.250+01:30", "2027-06-30t00:00:00z"):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".well-known/security.txt"
                path.write_text(path.read_text(encoding="utf-8").replace("2027-06-30T00:00:00Z", valid), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertEqual([], errors)

    def test_expiry_workflow_requires_live_setting_and_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            path.write_text(path.read_text(encoding="utf-8").replace("--verify-live-setting", "--offline-only").replace("steps.security_setting.outcome != 'success'", "false"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Verify private vulnerability reporting remains enabled" in error and "command mismatch" in error for error in errors))
        self.assertTrue(any("Enforce live reporting result" in error and "field 'if'" in error for error in errors))


    def test_workflows_keep_private_reporting_readback_tokenless(self) -> None:
        production = (ROOT / ".github/workflows/production-readback.yml").read_text(encoding="utf-8")
        security_step = production.split("- name: Verify private vulnerability reporting setting", 1)[1].split("- name: Upload production readback receipts", 1)[0]
        scheduled = (ROOT / ".github/workflows/security-policy-expiry.yml").read_text(encoding="utf-8")
        self.assertNotIn("GITHUB_TOKEN", security_step)
        self.assertNotIn("github.token", security_step)
        self.assertNotIn("GITHUB_TOKEN", scheduled)
        self.assertNotIn("github.token", scheduled)


    def test_live_private_reporting_transport_timeout_becomes_failed_receipt(self) -> None:
        def timed_out():
            raise RuntimeError("private vulnerability reporting readback failed: socket timeout")

        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "d" * 40,
            api_get=timed_out,
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertIn("private vulnerability reporting readback failed: socket timeout", receipt["errors"])

    def test_public_status_body_timeout_is_wrapped(self) -> None:
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                raise TimeoutError("socket timeout")

        from unittest.mock import patch
        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(RuntimeError, "socket timeout"):
                github_api_get_private_reporting("heimgewebe/commonworld")

    def test_expiry_live_readback_runs_even_when_policy_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            path.write_text(path.read_text(encoding="utf-8").replace("        id: security_setting\n        if: always()\n", "        id: security_setting\n"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Verify private vulnerability reporting remains enabled" in error and "field 'if'" in error for error in errors))

    def test_http_error_preserves_endpoint_and_status_metadata(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"
        error = urllib.error.HTTPError(
            endpoint,
            429,
            "rate limited",
            {},
            io.BytesIO(b'{"message":"rate limited"}'),
        )
        from unittest.mock import patch
        with patch("urllib.request.urlopen", side_effect=error):
            fetch = github_api_get_private_reporting("heimgewebe/commonworld")
        self.assertEqual(endpoint, fetch.requested_url)
        self.assertEqual(endpoint, fetch.final_url)
        self.assertEqual(429, fetch.status)
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "9" * 40,
            api_get=lambda: fetch,
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertEqual(429, receipt["status"])
        self.assertEqual(endpoint, receipt["requested_url"])
        self.assertEqual(endpoint, receipt["final_url"])

    def test_structural_workflow_validation_rejects_false_always_condition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            start = text.index("- name: Upload scheduled security receipt")
            end = text.index("- name: Enforce live reporting result", start)
            block = text[start:end].replace("if: always()", "if: always() && false")
            path.write_text(text[:start] + block + text[end:], encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Upload scheduled security receipt" in error and "field 'if'" in error for error in errors))


    def test_multiline_plain_condition_cannot_hide_false_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            expected = "        if: always() && steps.security_setting.outcome != 'success'\n"
            replacement = expected.rstrip("\n") + "\n          && false\n"
            path.write_text(text.replace(expected, replacement, 1), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Enforce live reporting result" in error and "field 'if'" in error for error in errors))

    def test_literal_run_newlines_cannot_masquerade_as_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            start = text.index("- name: Enforce live reporting result")
            block = text[start:].replace("        run: exit 1", "        run: |\n          exit\n          1", 1)
            path.write_text(text[:start] + block, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Enforce live reporting result" in error and "command mismatch" in error for error in errors))

    def test_enforcement_step_rejects_continue_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            marker = "      - name: Enforce live reporting result\n"
            replacement = marker + "        continue-on-error: true\n"
            path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Enforce live reporting result" in error and "must not define field 'continue-on-error'" in error for error in errors))

    def test_relocated_cron_text_does_not_restore_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            text = text.replace('  schedule:\n    - cron: "17 5 * * 1"\n', "")
            text += '\n# inert marker: - cron: "17 5 * * 1"\n'
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security expiry workflow must define exactly one on.schedule", errors)

    def test_http_error_incomplete_body_retains_response_metadata(self) -> None:
        endpoint = "https://api.github.com/repos/heimgewebe/commonworld/private-vulnerability-reporting"

        class IncompleteBody:
            def read(self, *args, **kwargs):
                raise http.client.IncompleteRead(b"{", 10)

            def close(self):
                return None

        error = urllib.error.HTTPError(endpoint, 503, "unavailable", {}, IncompleteBody())
        from unittest.mock import patch
        with patch("urllib.request.urlopen", side_effect=error):
            fetch = github_api_get_private_reporting("heimgewebe/commonworld")
        self.assertEqual(endpoint, fetch.requested_url)
        self.assertEqual(endpoint, fetch.final_url)
        self.assertEqual(503, fetch.status)
        self.assertIsNone(fetch.payload)


    def test_folded_run_comment_cannot_masquerade_as_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            start = text.index("- name: Enforce live reporting result")
            block = text[start:].replace("        run: exit 1", "        run: >-\n          exit\n          # comment\n          1", 1)
            path.write_text(text[:start] + block, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Enforce live reporting result" in error and "command mismatch" in error for error in errors))

    def test_duplicate_cron_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8").replace(
                '    - cron: "17 5 * * 1"\n',
                '    - cron: "17 5 * * 1"\n      cron: "0 0 * * *"\n',
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("cron item must not contain duplicate" in error for error in errors))

    def test_conflicting_contents_permission_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8").replace(
                "  contents: read\n",
                "  contents: read\n  contents: write\n",
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security expiry workflow permissions must contain exactly contents: read and no conflicting keys", errors)


    def test_runtime_workflows_install_yaml_dependency(self) -> None:
        for relative, label in (
            (".github/workflows/production-readback.yml", "production readback workflow"),
            (".github/workflows/security-policy-expiry.yml", "security expiry workflow"),
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "python -m pip install -r requirements-dev.txt",
                        "true",
                        1,
                    ),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "Install security validation dependencies" in error and "command mismatch" in error for error in errors),
                errors,
            )

    def test_runtime_dependency_install_cannot_be_conditional(self) -> None:
        for relative, label in (
            (".github/workflows/production-readback.yml", "production readback workflow"),
            (".github/workflows/security-policy-expiry.yml", "security expiry workflow"),
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                text = path.read_text(encoding="utf-8")
                marker = "      - name: Install security validation dependencies\n"
                self.assertEqual(1, text.count(marker))
                path.write_text(text.replace(marker, marker + "        if: false\n", 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "Install security validation dependencies" in error and "must not define field 'if'" in error for error in errors),
                errors,
            )

    def test_inline_duplicate_schedule_mapping_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8").replace(
                "  workflow_dispatch:\n",
                '  workflow_dispatch:\n  schedule: [{cron: "0 0 1 1 *"}]\n',
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("duplicate on field: schedule" in error for error in errors))

    def test_scalar_duplicate_permissions_mapping_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8").replace(
                "  contents: read\n\n",
                "  contents: read\npermissions: write-all\n\n",
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("duplicate top-level field: permissions" in error for error in errors))

    def test_second_with_mapping_with_disjoint_keys_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            marker = "          retention-days: 30\n"
            replacement = marker + "        with:\n          compression-level: 9\n"
            self.assertEqual(1, text.count(marker))
            path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("duplicate step field: with" in error for error in errors))

    def test_folded_run_blank_line_preserves_shell_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "        run: exit 1\n",
                "        run: >-\n          exit\n\n          1\n",
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(any("Enforce live reporting result" in error and "command mismatch" in error for error in errors))

    def test_enforcement_rejects_shell_override_and_spaced_duplicate_run(self) -> None:
        for injected, expected in (
            ("        shell: bash {0} || true\n", "must not define field 'shell'"),
            ("        run : exit 0\n", "duplicate step field: run"),
        ):
            with self.subTest(injected=injected), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".github/workflows/security-policy-expiry.yml"
                text = path.read_text(encoding="utf-8")
                marker = "      - name: Enforce live reporting result\n"
                path.write_text(text.replace(marker, marker + injected, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any(expected in error for error in errors), errors)


    def test_security_jobs_cannot_be_skipped_or_soft_failed(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "  contracts:\n", "validate workflow"),
            (".github/workflows/production-readback.yml", "  verify-exact-pages-deployment:\n", "production readback workflow"),
            (".github/workflows/security-policy-expiry.yml", "  validate-security-policy-expiry:\n", "security expiry workflow"),
        )
        for relative, marker, label in cases:
            for field in ("if: false", "continue-on-error: true"):
                with self.subTest(relative=relative, field=field), tempfile.TemporaryDirectory() as directory:
                    root = self.copy_surface(directory)
                    path = root / relative
                    source = path.read_text(encoding="utf-8")
                    self.assertEqual(1, source.count(marker))
                    path.write_text(source.replace(marker, marker + f"    {field}\n", 1), encoding="utf-8")
                    errors = validate_security_policy(root, now=self.NOW)
                key = field.split(":", 1)[0]
                self.assertTrue(
                    any(label in error and "job" in error and f"field '{key}'" in error for error in errors),
                    errors,
                )

    def test_security_jobs_reject_inherited_shell_overrides(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "  contracts:\n", "validate workflow"),
            (".github/workflows/production-readback.yml", "  verify-exact-pages-deployment:\n", "production readback workflow"),
            (".github/workflows/security-policy-expiry.yml", "  validate-security-policy-expiry:\n", "security expiry workflow"),
        )
        for relative, job_marker, label in cases:
            with self.subTest(relative=relative, scope="workflow"), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                path.write_text(
                    source.replace(
                        "jobs:\n",
                        "defaults:\n  run:\n    shell: bash {0} || true\n\njobs:\n",
                        1,
                    ),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "workflow must not define defaults.run.shell" in error for error in errors),
                errors,
            )

            with self.subTest(relative=relative, scope="job"), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(job_marker))
                path.write_text(
                    source.replace(
                        job_marker,
                        job_marker + "    defaults:\n      run:\n        shell: bash {0} || true\n",
                        1,
                    ),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "job" in error and "must not define defaults.run.shell" in error for error in errors),
                errors,
            )

    def test_exact_pages_readback_step_is_structurally_bound(self) -> None:
        mutations = (
            (
                "        shell: bash {0} || true\n",
                "must not define field 'shell'",
            ),
            (
                "        if: false\n",
                "must not define field 'if'",
            ),
        )
        marker = "      - name: Verify exact Pages deployment and public content\n"
        for injected, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".github/workflows/production-readback.yml"
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(marker))
                path.write_text(source.replace(marker, marker + injected, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(
                    "Verify exact Pages deployment and public content" in error and expected in error
                    for error in errors
                ),
                errors,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/production-readback.yml"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "          --deployment-timeout-seconds 600\n",
                    "          --deployment-timeout-seconds 0\n",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_security_policy(root, now=self.NOW)
        self.assertTrue(
            any(
                "Verify exact Pages deployment and public content" in error
                and "command mismatch" in error
                for error in errors
            ),
            errors,
        )

    def test_security_receipt_uploads_cannot_soft_fail(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "Upload pre-merge security receipt", "validate workflow"),
            (
                ".github/workflows/production-readback.yml",
                "Upload production readback receipts",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "Upload scheduled security receipt",
                "security expiry workflow",
            ),
        )
        for relative, step_name, label in cases:
            marker = f"      - name: {step_name}\n"
            for field in ("continue-on-error: true", "shell: bash {0} || true"):
                with self.subTest(relative=relative, field=field), tempfile.TemporaryDirectory() as directory:
                    root = self.copy_surface(directory)
                    path = root / relative
                    source = path.read_text(encoding="utf-8")
                    self.assertEqual(1, source.count(marker))
                    path.write_text(
                        source.replace(marker, marker + f"        {field}\n", 1),
                        encoding="utf-8",
                    )
                    errors = validate_security_policy(root, now=self.NOW)
                key = field.split(":", 1)[0]
                self.assertTrue(
                    any(
                        label in error
                        and step_name in error
                        and f"must not define field '{key}'" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_security_jobs_reject_skipping_needs_chains(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "  contracts:\n", "validate workflow"),
            (
                ".github/workflows/production-readback.yml",
                "  verify-exact-pages-deployment:\n",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "  validate-security-policy-expiry:\n",
                "security expiry workflow",
            ),
        )
        for relative, marker, label in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(marker))
                source = source.replace(marker, marker + "    needs: suppressed-security\n", 1)
                source = (
                    source.rstrip()
                    + "\n\n  suppressed-security:\n"
                    + "    if: false\n"
                    + "    runs-on: ubuntu-latest\n"
                    + "    steps:\n"
                    + "      - run: true\n"
                )
                path.write_text(source, encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "must not define field 'needs'" in error for error in errors),
                errors,
            )

    def test_expiry_validation_step_is_exact_and_unconditional(self) -> None:
        mutations = (
            (
                "        run: python3 scripts/validate_security_policy.py\n",
                "        run: true\n",
                "command mismatch",
            ),
            (
                "      - name: Validate disclosure policy and expiry\n",
                "      - name: Validate disclosure policy and expiry\n        if: false\n",
                "must not define field 'if'",
            ),
            (
                "      - name: Validate disclosure policy and expiry\n",
                "      - name: Validate disclosure policy and expiry\n        continue-on-error: true\n",
                "must not define field 'continue-on-error'",
            ),
            (
                "      - name: Validate disclosure policy and expiry\n",
                "      - name: Validate disclosure policy and expiry\n        shell: bash {0} || true\n",
                "must not define field 'shell'",
            ),
        )
        for old, new, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / ".github/workflows/security-policy-expiry.yml"
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(old))
                path.write_text(source.replace(old, new, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(
                    "Validate disclosure policy and expiry" in error and expected in error
                    for error in errors
                ),
                errors,
            )

    def test_security_critical_steps_cannot_move_to_a_suppressed_sibling_job(self) -> None:
        cases = (
            (
                ".github/workflows/validate.yml",
                "Upload pre-merge security receipt",
                "validate workflow",
            ),
            (
                ".github/workflows/production-readback.yml",
                "Verify private vulnerability reporting setting",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "Verify private vulnerability reporting remains enabled",
                "security expiry workflow",
            ),
        )

        def relocate_step(source: str, step_name: str) -> str:
            marker = f"      - name: {step_name}\n"
            self.assertEqual(1, source.count(marker))
            start = source.index(marker)
            end = source.find("      - name: ", start + len(marker))
            if end == -1:
                end = len(source)
            block = source[start:end]
            without = source[:start] + source[end:]
            return (
                without.rstrip()
                + "\n\n  suppressed-security:\n"
                + "    if: false\n"
                + "    runs-on: ubuntu-latest\n"
                + "    steps:\n"
                + block.rstrip()
                + "\n"
            )

        for relative, step_name, label in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                path.write_text(
                    relocate_step(path.read_text(encoding="utf-8"), step_name),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(
                    label in error
                    and "security-critical steps must belong to the same executable job" in error
                    for error in errors
                ),
                errors,
            )

    def test_security_critical_steps_require_the_reviewed_job_name(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "  contracts:\n", "validate workflow", "contracts"),
            (
                ".github/workflows/production-readback.yml",
                "  verify-exact-pages-deployment:\n",
                "production readback workflow",
                "verify-exact-pages-deployment",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "  validate-security-policy-expiry:\n",
                "security expiry workflow",
                "validate-security-policy-expiry",
            ),
        )
        for relative, marker, label, expected_job in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(marker))
                path.write_text(
                    source.replace(marker, "  renamed-security-job:\n", 1),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(
                    label in error
                    and f"must belong to job '{expected_job}'" in error
                    for error in errors
                ),
                errors,
            )

    def test_security_workflow_digests_bind_triggers_and_all_predecessors(self) -> None:
        mutations = (
            (
                ".github/workflows/validate.yml",
                "  pull_request:\n",
                "  workflow_dispatch:\n",
            ),
            (
                ".github/workflows/production-readback.yml",
                "      - main\n",
                "      - never-run\n",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "    steps:\n",
                "    steps:\n      - name: Unreviewed predecessor\n        run: echo attacker >> \"$GITHUB_PATH\"\n",
            ),
        )
        for relative, old, new in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(old))
                path.write_text(source.replace(old, new, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(
                    "security workflow bytes changed without reviewed digest update" in error
                    and relative in error
                    for error in errors
                ),
                errors,
            )

    def test_security_workflow_and_job_field_inventories_are_exact(self) -> None:
        cases = (
            (".github/workflows/validate.yml", "  contracts:\n", "validate workflow"),
            (
                ".github/workflows/production-readback.yml",
                "  verify-exact-pages-deployment:\n",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "  validate-security-policy-expiry:\n",
                "security expiry workflow",
            ),
        )
        for relative, job_marker, label in cases:
            with self.subTest(relative=relative, scope="workflow"), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                path.write_text(
                    source.replace("jobs:\n", "env:\n  PYTHONPATH: attacker\n\njobs:\n", 1),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any(label in error and "workflow fields must equal" in error for error in errors), errors)

            with self.subTest(relative=relative, scope="job"), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(job_marker))
                path.write_text(
                    source.replace(job_marker, job_marker + "    env:\n      PYTHONPATH: attacker\n", 1),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any(label in error and "job" in error and "fields must equal" in error for error in errors), errors)

    def test_security_steps_reject_unreviewed_fields(self) -> None:
        cases = (
            (
                ".github/workflows/validate.yml",
                "Verify private vulnerability reporting before merge",
                "validate workflow",
            ),
            (
                ".github/workflows/production-readback.yml",
                "Verify exact Pages deployment and public content",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "Validate disclosure policy and expiry",
                "security expiry workflow",
            ),
        )
        for relative, step_name, label in cases:
            marker = f"      - name: {step_name}\n"
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(marker))
                path.write_text(
                    source.replace(marker, marker + "        working-directory: attacker\n", 1),
                    encoding="utf-8",
                )
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and step_name in error and "unreviewed field 'working-directory'" in error for error in errors),
                errors,
            )

    def test_security_critical_steps_are_consecutive_and_ordered(self) -> None:
        cases = (
            (
                ".github/workflows/validate.yml",
                "      - name: Upload pre-merge security receipt\n",
                "validate workflow",
            ),
            (
                ".github/workflows/production-readback.yml",
                "      - name: Verify private vulnerability reporting setting\n",
                "production readback workflow",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "      - name: Verify private vulnerability reporting remains enabled\n",
                "security expiry workflow",
            ),
        )
        injected = "      - name: Interposed unreviewed step\n        run: true\n\n"
        for relative, marker, label in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(marker))
                path.write_text(source.replace(marker, injected + marker, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(
                any(label in error and "must be consecutive and in reviewed order" in error for error in errors),
                errors,
            )

    def test_quoted_mapping_key_whitespace_is_not_normalized(self) -> None:
        mutations = (
            (
                ".github/workflows/security-policy-expiry.yml",
                "        run: exit 1\n",
                '        "run ": exit 1\n',
                "Enforce live reporting result",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                '    - cron: "17 5 * * 1"\n',
                '    - "cron ": "17 5 * * 1"\n',
                "on.schedule",
            ),
            (
                ".github/workflows/security-policy-expiry.yml",
                "  contents: read\n",
                '  "contents ": read\n',
                "permissions",
            ),
        )
        for relative, old, new, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = self.copy_surface(directory)
                path = root / relative
                source = path.read_text(encoding="utf-8")
                self.assertEqual(1, source.count(old))
                path.write_text(source.replace(old, new, 1), encoding="utf-8")
                errors = validate_security_policy(root, now=self.NOW)
            self.assertTrue(any(expected in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
