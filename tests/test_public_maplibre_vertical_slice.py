import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_maplibre_vertical_slice import (
    CONTRACT_PATH,
    REQUIRED_FILES,
    ROOT,
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

    def test_rejects_bypassing_identity_preserving_sphere_label_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            path = root / "assets/commonworld-app.js"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "sphereLabelLayout(layerIndex, recordIndex, records.length)",
                    "{ overviewX: 320, overviewY: 320, overviewRotation: 0, sideX: 320, sideY: 320 }",
                ),
                encoding="utf-8",
            )
            errors = validate_public_maplibre_vertical_slice(root)
        self.assertTrue(any("identity-preserving sphere-label layout helper" in error for error in errors))

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
