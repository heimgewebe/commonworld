import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_catalog import ROOT, validate_public_catalog


class PublicCatalogTests(unittest.TestCase):
    def copy_public_catalog(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        shutil.copytree(ROOT / "catalog", root / "catalog")
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copy2(ROOT / "index.html", root / "index.html")
        return root

    def mutate_project(self, root: Path, identifier: str, mutation) -> None:
        path = root / "catalog" / "projects" / f"{identifier}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        mutation(record)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_public_catalog_validates(self) -> None:
        self.assertEqual([], validate_public_catalog(ROOT))

    def test_manifest_must_match_project_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            path = root / "catalog" / "catalog.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["project_files"].pop()
            manifest["entry_count"] -= 1
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = validate_public_catalog(root)

        self.assertIn("public catalog manifest and project file inventory differ", errors)

    def test_non_object_project_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            path = root / "catalog" / "projects" / "debian.json"
            path.write_text("[]\n", encoding="utf-8")

            errors = validate_public_catalog(root)

        self.assertIn("public catalog project debian.json must contain a JSON object", errors)

    def test_candidate_record_cannot_be_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(root, "debian", lambda record: record["curation"].update({"state": "candidate"}))

            errors = validate_public_catalog(root)

        self.assertTrue(any("must be in a public curation state" in error for error in errors))

    def test_unknown_source_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(
                root,
                "freifunk",
                lambda record: record["presence"]["digital"].update({"source_ids": ["missing-source"]}),
            )

            errors = validate_public_catalog(root)

        self.assertTrue(any("unknown provenance sources" in error for error in errors))

    def test_public_shell_identity_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace('data-commonproject-id="debian"', 'data-commonproject-id="debian-missing"'),
                encoding="utf-8",
            )

            errors = validate_public_catalog(root)

        self.assertIn("public shell card identities must match the public catalog once in Text and once in the no-JavaScript fallback", errors)

    def test_manual_presentation_layer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(root, "openstreetmap", lambda record: record.update({"presentation_layer": "mixed_other"}))

            errors = validate_public_catalog(root)

        self.assertTrue(any("must not store presentation or zoom assignments" in error for error in errors))

    def test_public_shell_wrong_layer_label_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Digital · Freie Software und Infrastruktur",
                    "Digital · Falsche Schicht",
                    1,
                ),
                encoding="utf-8",
            )

            errors = validate_public_catalog(root)

        self.assertTrue(any("derived German presentation label" in error for error in errors))

    def test_production_delivery_boundary_cannot_regress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            path = root / "catalog" / "catalog.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["publication"]["production_architecture_authorized"] = False
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = validate_public_catalog(root)

        self.assertIn("public catalog publication boundary mismatch", errors)

    def test_non_official_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(
                root,
                "mastodon",
                lambda record: record["provenance"]["sources"][0].update({"type": "manual-curation"}),
            )

            errors = validate_public_catalog(root)

        self.assertTrue(any("must use official or public-registry sources" in error for error in errors))

    def test_public_registry_source_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(
                root,
                "debian",
                lambda record: record["provenance"]["sources"][0].update({"type": "public-registry"}),
            )

            errors = validate_public_catalog(root)

        self.assertFalse(any("must use official or public-registry sources" in error for error in errors))

    def test_unknown_relation_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(
                root,
                "freifunk-hamburg",
                lambda record: record["relations"][0].update({"target_id": "missing-commonproject"}),
            )

            errors = validate_public_catalog(root)

        self.assertTrue(any("relation target is not a published CommonProject" in error for error in errors))

    def test_semantic_zoom_assignment_is_rejected_from_catalog_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_public_catalog(tmp_dir)
            self.mutate_project(root, "cltb-le-nid", lambda record: record.update({"semantic_zoom": "local"}))

            errors = validate_public_catalog(root)

        self.assertTrue(any("must not store presentation or zoom assignments" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
