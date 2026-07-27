import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate_security_policy import ROOT, validate_security_policy, verify_live_private_reporting, write_json_receipt


class SecurityPolicyTests(unittest.TestCase):
    REQUIRED = ("SECURITY.md", ".well-known/security.txt", "_config.yml", ".github/workflows/production-readback.yml", ".github/workflows/security-policy-expiry.yml")
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
            "token-value",
            api_get=lambda: {"enabled": True},
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("pass", receipt["verdict"])
        self.assertTrue(receipt["enabled"])
        self.assertNotIn("token-value", json.dumps(receipt))

    def test_live_private_reporting_disabled_fails_and_writes_receipt(self) -> None:
        receipt = verify_live_private_reporting(
            "heimgewebe/commonworld",
            "b" * 40,
            "token-value",
            api_get=lambda: {"enabled": False},
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
            "token-value",
            api_get=lambda: {"enabled": "yes"},
            now=lambda: "2026-07-27T20:00:00Z",
        )
        self.assertEqual("fail", receipt["verdict"])
        self.assertIn("private vulnerability reporting response must contain boolean enabled", receipt["errors"])

    def test_expiry_workflow_requires_schedule_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".github/workflows/security-policy-expiry.yml"
            path.write_text(path.read_text(encoding="utf-8").replace("python3 scripts/validate_security_policy.py", "true"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security expiry workflow is incomplete: python3 scripts/validate_security_policy.py", errors)

    def test_non_rfc3339_expiry_separator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_surface(directory)
            path = root / ".well-known/security.txt"
            path.write_text(path.read_text(encoding="utf-8").replace("Expires: 2027-06-30T00:00:00Z", "Expires: 2027-06-30 00:00:00Z"), encoding="utf-8")
            errors = validate_security_policy(root, now=self.NOW)
        self.assertIn("security.txt Expires must be strict RFC 3339", errors)


if __name__ == "__main__":
    unittest.main()
