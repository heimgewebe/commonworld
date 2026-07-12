import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_renderer_selection import (
    CONTRACT_PATH,
    EVIDENCE_PATHS,
    REPORT_PATH,
    RESULT_PATH,
    ROOT,
    validate_renderer_selection,
)


class RendererSelectionTests(unittest.TestCase):
    def copy_selection_core(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        paths = set(EVIDENCE_PATHS) | {
            str(RESULT_PATH),
            str(REPORT_PATH),
            "index.html",
        }
        for relative in paths:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        manifest = json.loads((root / "catalog/catalog.json").read_text(encoding="utf-8"))
        for relative in manifest["project_files"]:
            source = ROOT / "catalog" / relative
            target = root / "catalog" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def mutate_json(self, root: Path, relative: str | Path, mutation) -> None:
        path = root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        mutation(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_renderer_selection_validates(self) -> None:
        self.assertEqual([], validate_renderer_selection(ROOT))

    def test_maplibre_is_selected_but_production_is_not_authorized(self) -> None:
        contract = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
        decision = contract["decision_boundary"]
        self.assertTrue(decision["engine_selected"])
        self.assertEqual("maplibre_gl_js", contract["selected_engine"]["id"])
        self.assertFalse(decision["production_architecture_authorized"])
        self.assertFalse(decision["public_runtime_uses_selected_engine"])

    def test_non_object_contract_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            (root / CONTRACT_PATH).write_text("[]\n", encoding="utf-8")

            errors = validate_renderer_selection(root)

        self.assertTrue(any("must contain JSON objects" in error for error in errors))

    def test_validator_rejects_alternative_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(root, CONTRACT_PATH, lambda value: value["selected_engine"].update({"id": "three_js"}))

            errors = validate_renderer_selection(root)

        self.assertTrue(any("must choose MapLibre" in error for error in errors))

    def test_validator_rejects_production_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                CONTRACT_PATH,
                lambda value: value["decision_boundary"].update({"production_architecture_authorized": True}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("decision boundary" in error for error in errors))

    def test_validator_rejects_public_runtime_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                RESULT_PATH,
                lambda value: value["selection"].update({"public_runtime_uses_selected_engine": True}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("static public shell" in error for error in errors))

    def test_malformed_nested_spike_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                "docs/research/renderer-engine-spike.result.json",
                lambda value: value.update({"method": []}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(errors)
        self.assertTrue(any("evidence hash mismatch" in error or "candidate versions" in error for error in errors))

    def test_validator_rejects_changed_evidence_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                RESULT_PATH,
                lambda value: value["evidence_bindings"][0].update({"sha256": "0" * 64}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("evidence hash mismatch" in error for error in errors))

    def test_validator_rejects_removed_csp_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                RESULT_PATH,
                lambda value: value["open_gates"].pop("csp_and_worker_delivery"),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("open release gates" in error for error in errors))

    def test_validator_rejects_changed_engine_responsibilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                RESULT_PATH,
                lambda value: value["selection"]["primary_responsibilities"].pop(),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("primary responsibilities" in error for error in errors))

    def test_validator_rejects_android_pass_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                RESULT_PATH,
                lambda value: value["open_gates"].update({"physical_android_chrome_hardware": "pass"}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("open release gates" in error for error in errors))

    def test_validator_rejects_catalog_geographic_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                "catalog/projects/debian.json",
                lambda value: value["presence"].update(
                    {"geographic": [{"id": "invented", "mode": "hidden", "label": "invented", "source_ids": ["debian-about"]}]}
                ),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("must not gain geographic presence" in error for error in errors))

    def test_validator_rejects_three_js_runtime_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                CONTRACT_PATH,
                lambda value: value["integration_model"].update({"three_js_runtime_dependency_authorized": True}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("integration model" in error for error in errors))

    def test_validator_rejects_floating_version_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            self.mutate_json(
                root,
                CONTRACT_PATH,
                lambda value: value["version_policy"].update({"cdn_floating_version_forbidden": False}),
            )

            errors = validate_renderer_selection(root)

        self.assertTrue(any("version policy" in error for error in errors))

    def test_validator_rejects_runtime_dependency_in_decision_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_selection_core(tmp_dir)
            (root / "package.json").write_text('{"dependencies":{"maplibre-gl":"5.24.0"}}\n', encoding="utf-8")

            errors = validate_renderer_selection(root)

        self.assertTrue(any("must not introduce runtime dependency yet" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
