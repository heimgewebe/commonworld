import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate_security_policy import ROOT, validate_security_policy


class SecurityPolicyTests(unittest.TestCase):
    REQUIRED = ("SECURITY.md", ".well-known/security.txt", "_config.yml")
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


if __name__ == "__main__":
    unittest.main()
