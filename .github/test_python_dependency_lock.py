import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_python_dependency_lock import (
    REGENERATE_COMMAND,
    UV_VERSION,
    expected_header,
    regeneration_argv,
    validation_errors,
    validate_repository,
)


class PythonDependencyLockTests(unittest.TestCase):
    def fixture(self):
        input_text = "jsonschema>=4.23,<5\n"
        lock_text = expected_header(input_text) + "jsonschema==4.26.0 \\\n    --hash=sha256:" + "a" * 64 + "\n"
        workflow_text = (
            "run: python3 .github/validate_python_dependency_lock.py\n"
            "run: python -m pip install --require-hashes -r requirements-dev.txt\n"
        )
        return input_text, lock_text, workflow_text

    def test_repository_contract_passes(self):
        self.assertEqual([], validate_repository())

    def test_unhashed_lock_is_rejected(self):
        source, lock, workflow = self.fixture()
        lock = lock.replace(" \\\n    --hash=sha256:" + "a" * 64, "")
        errors = validation_errors(source, lock, workflow)
        self.assertTrue(any("has no SHA-256 hash" in error for error in errors))

    def test_open_range_lock_is_rejected(self):
        source, lock, workflow = self.fixture()
        lock = lock.replace("jsonschema==4.26.0", "jsonschema>=4.23")
        errors = validation_errors(source, lock, workflow)
        self.assertTrue(any("only exact name==version pins" in error for error in errors))

    def test_missing_direct_dependency_is_rejected(self):
        source, lock, workflow = self.fixture()
        source += "attrs>=25,<27\n"
        lock = expected_header(source) + lock.split("\n", 3)[3]
        errors = validation_errors(source, lock, workflow)
        self.assertTrue(any("direct dependencies missing from lock: attrs" in error for error in errors))

    def test_changed_source_invalidates_existing_lock(self):
        source, lock, workflow = self.fixture()
        source = "jsonschema>=5,<6\n"
        errors = validation_errors(source, lock, workflow)
        self.assertIn(
            "requirements-dev.txt: lock is not bound to the current requirements-dev.in digest",
            errors,
        )

    def test_ci_must_use_require_hashes(self):
        source, lock, workflow = self.fixture()
        workflow = workflow.replace(" --require-hashes", "")
        errors = validation_errors(source, lock, workflow)
        self.assertTrue(any("not installed with --require-hashes" in error for error in errors))
        self.assertTrue(any("unhashed requirements-dev.txt installation remains" in error for error in errors))

    def test_ci_must_validate_lock(self):
        source, lock, workflow = self.fixture()
        workflow = workflow.replace("run: python3 .github/validate_python_dependency_lock.py\n", "")
        errors = validation_errors(source, lock, workflow)
        self.assertIn("validate workflow: dependency lock validator is missing", errors)

    def test_ci_must_validate_before_install(self):
        source, lock, workflow = self.fixture()
        lines = workflow.splitlines(keepends=True)
        workflow = "".join(reversed(lines))
        errors = validation_errors(source, lock, workflow)
        self.assertIn("validate workflow: dependency lock must be validated before installation", errors)

    def test_commented_validator_does_not_satisfy_ci_contract(self):
        source, lock, workflow = self.fixture()
        workflow = workflow.replace(
            "run: python3 .github/validate_python_dependency_lock.py",
            "# run: python3 .github/validate_python_dependency_lock.py",
        )
        errors = validation_errors(source, lock, workflow)
        self.assertIn("validate workflow: dependency lock validator is missing", errors)

    def test_direct_url_source_is_rejected(self):
        source, lock, workflow = self.fixture()
        source = "jsonschema @ https://example.invalid/jsonschema.whl\n"
        lock = expected_header(source) + lock.split("\n", 3)[3]
        errors = validation_errors(source, lock, workflow)
        self.assertTrue(any("unsupported dependency source" in error for error in errors))

    def test_regenerator_is_explicitly_version_bound(self):
        self.assertEqual("0.9.11", UV_VERSION)
        self.assertEqual("python3 .github/validate_python_dependency_lock.py --regenerate", REGENERATE_COMMAND)
        self.assertEqual(
            (
                "uv",
                "pip",
                "compile",
                "requirements-dev.in",
                "--python-version",
                "3.12",
                "--generate-hashes",
                "--no-emit-index-url",
                "--custom-compile-command",
                REGENERATE_COMMAND,
                "--output-file",
                "requirements-dev.txt",
            ),
            regeneration_argv(),
        )


if __name__ == "__main__":
    unittest.main()
