import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_maplibre_vertical_slice import (
    CONTRACT_PATH,
    REQUIRED_FILES,
    ROOT,
    _javascript_function_source,
    validate_public_maplibre_vertical_slice,
)


class PublicMapLibreVerticalSliceTests(unittest.TestCase):
    def copy_slice(self, temporary_directory: str) -> Path:
        target_root = Path(temporary_directory)
        paths = set(REQUIRED_FILES) | {
            Path("scripts/render_public_shell.py"),
            Path("scripts/__init__.py"),
        }
        manifest = json.loads((ROOT / "catalog/catalog.json").read_text(encoding="utf-8"))
        paths.update(Path("catalog") / relative for relative in manifest["project_files"])
        for relative in paths:
            source = ROOT / relative
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return target_root

    @staticmethod
    def mutate_json(root: Path, relative: str | Path, mutation) -> None:
        path = root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        mutation(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_vertical_slice_validates(self) -> None:
        self.assertEqual([], validate_public_maplibre_vertical_slice(ROOT))

    def test_javascript_function_extraction_ignores_non_code_delimiters(self) -> None:
        javascript = r'''
const stringDecoy = "function target() { return 'wrong'; }";
const templateDecoy = `function target() { return "template wrong"; }`;
const regexDecoy = /function target\(\) \{ return false; \}/u;
// function target() { return "line-comment wrong"; }
/* function target() { return "also wrong"; } */
function
  target(
    value = ")",
    pattern = /[(){}]/u
  ) {
  const singleQuoted = '}';
  const doubleQuoted = "{";
  // A comment with a closing brace must not end the function: }
  /* Nor may a block comment with both delimiters: { } */
  const template = `raw } ${ { nested: `inner ${"}"}` } } tail {`;
  return { value, pattern, template };
}
function after() { return false; }
'''

        extracted = _javascript_function_source(javascript, "target")

        self.assertTrue(extracted.startswith("function\n  target("))
        self.assertIn("return { value, pattern, template };", extracted)
        self.assertNotIn("function after", extracted)
        self.assertEqual("function after() { return false; }", _javascript_function_source(javascript, "after"))

    def test_javascript_function_extraction_handles_source_start_and_declaration_comments(self) -> None:
        javascript = "function /* declaration */ target(value = ')') /* body */ { const ratio = object.return / 2; const braces = /[{}]/u; return { ratio, braces }; } function after() {}"

        self.assertEqual(
            "function /* declaration */ target(value = ')') /* body */ { const ratio = object.return / 2; const braces = /[{}]/u; return { ratio, braces }; }",
            _javascript_function_source(javascript, "target"),
        )

    def test_javascript_function_extraction_fails_closed_on_unterminated_body(self) -> None:
        self.assertEqual("", _javascript_function_source("function target() { const value = '}';", "target"))

    def test_rejects_floating_maplibre_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(root, "package.json", lambda value: value["dependencies"].update({"maplibre-gl": "^5.24.0"}))
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("exactly pinned" in error for error in errors))

    def test_rejects_lockfile_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "package-lock.json",
                lambda value: value["packages"]["node_modules/maplibre-gl"].update({"version": "5.25.0"}),
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("resolve maplibre-gl exactly" in error for error in errors))

    def test_rejects_changed_vendored_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/vendor/maplibre-gl.js"
            path.write_bytes(path.read_bytes() + b"\n// changed\n")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("vendored MapLibre asset hash mismatch" in error for error in errors))


    def test_rejects_changed_maplibre_license(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/vendor/MAPLIBRE-LICENSE.txt"
            path.write_text(path.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("license hash mismatch" in error for error in errors))

    def test_rejects_external_script_cdn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "./assets/vendor/maplibre-gl.js",
                    "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js",
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("forbidden dependency" in error or "CDN" in error for error in errors))

    def test_rejects_fabricated_geographic_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "catalog/projects/debian.json",
                lambda value: value["presence"].update(
                    {"geographic": [{"id": "invented", "mode": "exact", "coordinates": [8.0, 51.0]}]}
                ),
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("must not contain geographic coordinates" in error for error in errors))

    def test_rejects_unapproved_map_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "assets/map/openfreemap-liberty.json",
                lambda value: value["sources"]["openmaptiles"].update({"url": "https://example.invalid/planet"}),
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("style snapshot hash mismatch" in error or "unapproved external URL" in error for error in errors))

    def test_rejects_missing_worker_csp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8").replace("worker-src 'self' blob:; ", ""), encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("CSP missing token" in error for error in errors))

    def test_rejects_runtime_publication_false(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "catalog/catalog.json",
                lambda value: value["publication"].update({"public_runtime_uses_selected_engine": False}),
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("publication boundary mismatch" in error for error in errors))

    def test_rejects_hardcoded_catalog_identity_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(path.read_text(encoding="utf-8") + "\nconst forbiddenIdentity = 'debian';\n", encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("hardcodes catalog identity" in error for error in errors))

    def test_rejects_bypassing_text_ribbon_lane_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "  renderSphereRibbons(runtime.records);",
                    "  elements.sphereStreams.replaceChildren();",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("text-ribbon lane architecture" in error for error in errors))

    def test_rejects_cooperative_gestures_that_block_one_finger_touch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "    renderWorldCopies: false,\n",
                    "    cooperativeGestures: true,\n    renderWorldCopies: false,\n",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("one-finger touch movement" in error for error in errors))

    def test_rejects_raw_subpixel_sphere_visuals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "`${quantizeSpherePixel(geometry.x)}px`",
                    "String(geometry.x) + 'px'",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("quantize subpixel geometry" in error for error in errors))

    def test_rejects_duplicate_sphere_geometry_style_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "  runtime.sphereMetrics.globeDiameter = geometry.globeDiameter;",
                    "  setStylePropertyIfChanged(elements.sphere, '--sphere-x', x);\n  runtime.sphereMetrics.globeDiameter = geometry.globeDiameter;",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("without duplicate writes" in error for error in errors))

    def test_rejects_raw_sphere_diagnostic_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "setDatasetIfChanged(elements.stage, 'sphereX', quantizeSpherePixel(geometry.x));",
                    "setDatasetIfChanged(elements.stage, 'sphereX', geometry.x);",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("publish quantized geometry" in error for error in errors))

    def test_rejects_sphere_metric_dom_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "runtime.sphereMetrics.globeDiameter",
                    "Number(elements . stage . dataset [ 'globeDiameter' ] ?? 0)",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("runtime metrics instead of reading diagnostic DOM state" in error for error in errors))

    def test_accepts_equivalent_sphere_validator_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            baseline_errors = validate_public_maplibre_vertical_slice(root)
            path = root / "assets/commonworld-app.js"
            source = path.read_text(encoding="utf-8")
            source = source.replace(
                "quantizeSpherePixel(geometry.x)",
                "quantizeSpherePixel( geometry . x )",
                1,
            )
            source = source.replace(
                "runtime.sphereMetrics.globeViewportRatio = globeViewportRatio;",
                "runtime . sphereMetrics . globeViewportRatio=globeViewportRatio ;",
                1,
            )
            source = source.replace(
                "Number(runtime.sphereMetrics.globeViewportRatio.toFixed(4))",
                "Number( runtime . sphereMetrics . globeViewportRatio . toFixed( 4 ) )",
                1,
            )
            source = source.replace(
                "sampledDiagnosticPublicationDue(",
                "sampledDiagnosticPublicationDue (",
                1,
            )
            path.write_text(source, encoding="utf-8")
            app_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            index_path = root / "index.html"
            index_html = index_path.read_text(encoding="utf-8")
            index_html = re.sub(
                r'(commonworld-app\.js\?v=)[0-9a-f]{12}',
                rf'\g<1>{app_hash}',
                index_html,
                count=1,
            )
            index_path.write_text(index_html, encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertEqual(errors, baseline_errors)

    def test_rejects_detached_sphere_viewport_ratio_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Number(runtime.sphereMetrics.globeViewportRatio.toFixed(4))",
                    "Number(globeViewportRatio.toFixed(4))",
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("read the runtime viewport ratio" in error for error in errors))

    def test_rejects_inline_sphere_diagnostic_modulo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            source = path.read_text(encoding="utf-8")
            start = source.index("  const publishDiagnostics = sampledDiagnosticPublicationDue(")
            end = source.index("  updateSphereGeometry({ publishDiagnostics });", start)
            source = source[:start] + "  const publishDiagnostics = runtime.mapGeometrySampleCount % MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL === 0;\n" + source[end:]
            path.write_text(source, encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("admitted-sample helper" in error for error in errors))

    def test_rejects_nondeterministic_shell_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8").replace("Commons direkt durchsuchen", "Andere Überschrift", 1), encoding="utf-8")
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("deterministic catalog-derived shell" in error for error in errors))

    def test_android_and_screenreader_nonclaims_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                CONTRACT_PATH,
                lambda value: value["release_gates"].update(
                    {"physical_android_chrome_current_globe_first_surface": "pass", "screen_reader_product_support": "pass"}
                ),
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("Android Chrome" in error for error in errors))
        self.assertTrue(any("screen-reader" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
