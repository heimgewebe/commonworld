import tempfile
import unittest
from pathlib import Path

from scripts.proof_shared import (
    ROOT,
    SHARED_JS_REL,
    assert_shared_imports,
    imported_shared_names,
    validate_shared_module,
)


class SharedAspectModuleTests(unittest.TestCase):
    def _tmp_root_with_shared(self, tmp_dir: str, source: str) -> Path:
        tmp_root = Path(tmp_dir)
        shared = tmp_root / SHARED_JS_REL
        shared.parent.mkdir(parents=True, exist_ok=True)
        shared.write_text(source, encoding="utf-8")
        return tmp_root

    def test_real_shared_module_validates(self) -> None:
        self.assertEqual([], validate_shared_module(ROOT))

    def test_all_three_proofs_import_from_shared_module(self) -> None:
        for proof, relative in (
            ("mixed-node", "proofs/mixed-node/mixed-node.js"),
            ("map", "proofs/map/map.js"),
            ("aether", "proofs/aether/aether.js"),
        ):
            js = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("loadSeedProjects", imported_shared_names(js), proof)

    def test_confidence_output_is_unified_via_shared_format_percent(self) -> None:
        # Every proof must route confidence through the shared formatConfidence so
        # the sub-10% rendering cannot drift apart again.
        for relative in (
            "proofs/mixed-node/mixed-node.js",
            "proofs/map/map.js",
            "proofs/aether/aether.js",
        ):
            js = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("formatConfidence", imported_shared_names(js), relative)

    def test_format_confidence_must_compose_format_percent(self) -> None:
        source = (ROOT / SHARED_JS_REL).read_text(encoding="utf-8")
        broken = source.replace(
            "export function formatConfidence(value) {\n  return `${formatPercent(value)} confidence`;\n}",
            "export function formatConfidence(value) {\n  return `${Math.round(value * 100)}% confidence`;\n}",
        )
        self.assertNotEqual(source, broken)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self._tmp_root_with_shared(tmp_dir, broken)
            errors = validate_shared_module(tmp_root)
        self.assertIn(
            "shared formatConfidence must compose formatPercent so confidence output stays unified",
            errors,
        )

    def test_missing_export_is_reported(self) -> None:
        source = (ROOT / SHARED_JS_REL).read_text(encoding="utf-8")
        without_gradient = source.replace("export function gradientFor", "function gradientFor")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self._tmp_root_with_shared(tmp_dir, without_gradient)
            errors = validate_shared_module(tmp_root)
        self.assertIn("shared aspect module must export function gradientFor", errors)

    def test_missing_shared_module_reports_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            errors = validate_shared_module(Path(tmp_dir))
        self.assertEqual([f"missing shared aspect module: {SHARED_JS_REL}"], errors)

    def test_assert_shared_imports_flags_missing_and_unexported(self) -> None:
        js = 'import { formatPercent, bogus } from "../shared/aspects.js";\n'
        errors = assert_shared_imports(js, ("formatPercent", "gradientFor"), "sample proof")
        self.assertIn("sample proof must import gradientFor from proofs/shared/aspects.js", errors)
        self.assertIn(
            "sample proof imports bogus, which the shared aspect module does not export",
            errors,
        )
        self.assertNotIn("sample proof must import formatPercent from proofs/shared/aspects.js", errors)

    def test_assert_shared_imports_requires_the_import(self) -> None:
        errors = assert_shared_imports("const x = 1;\n", ("formatPercent",), "sample proof")
        self.assertEqual(
            [f"sample proof must import shared aspect helpers from {SHARED_JS_REL}"],
            errors,
        )


if __name__ == "__main__":
    unittest.main()
