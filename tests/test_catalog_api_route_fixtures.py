import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generate_catalog_api_route_fixtures import build_catalog_api_route_fixtures
from scripts.validate_catalog_api_route_fixtures import validate_catalog_api_route_fixtures
from scripts.validate_contracts import ROOT


class CatalogApiRouteFixtureTests(unittest.TestCase):
    def copy_fixture_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_catalog_api_route_fixtures_validate(self) -> None:
        self.assertEqual([], validate_catalog_api_route_fixtures(ROOT))

    def test_generator_matches_committed_fixture(self) -> None:
        generated, errors = build_catalog_api_route_fixtures(ROOT)
        self.assertEqual([], errors)
        fixture_path = ROOT / "examples" / "commonworld" / "catalog-api-route-fixtures.sample.json"
        committed = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(committed, generated)

    def test_fixture_rejects_write_route_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_fixture_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-api-route-fixtures.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["fixtures"][0]["method"] = "POST"
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_route_fixtures(tmp_root)

        self.assertIn("catalog API route fixture catalog-export must remain GET-only", errors)
        self.assertIn("catalog API route fixture catalog-export must not include POST routes", errors)

    def test_fixture_rejects_writes_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_fixture_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-api-route-fixtures.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["fixtures"][1]["writes"] = True
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_route_fixtures(tmp_root)

        self.assertIn("catalog API route fixture catalog-project-list must not write", errors)

    def test_fixture_rejects_extra_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_fixture_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-api-route-fixtures.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["fixtures"].append(
                {
                    "id": "submit-project",
                    "method": "GET",
                    "route_path_template": "/catalog/v1/submit",
                    "request_path": "/catalog/v1/submit",
                    "status": 200,
                    "access": "public-read-only",
                    "auth_required": False,
                    "writes": False,
                    "submissions": False,
                    "source": "generated static catalog export",
                    "response_shape": "not allowed",
                    "body": {},
                }
            )
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_route_fixtures(tmp_root)

        self.assertIn("catalog API route fixtures must exactly cover the T012 route ids in deterministic order", errors)
        self.assertIn("catalog API route fixture id must match a known contract route", errors)

    def test_fixture_rejects_stale_project_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_fixture_surface(tmp_dir)
            path = tmp_root / "examples" / "commonworld" / "catalog-api-route-fixtures.sample.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["fixtures"][1]["body"]["count"] = 999
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_catalog_api_route_fixtures(tmp_root)

        self.assertIn("catalog-project-list route fixture count must match the static catalog export entries", errors)
        self.assertIn("catalog API route fixture sample is stale", errors)

    def test_doc_must_not_enable_server_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_fixture_surface(tmp_dir)
            path = tmp_root / "docs" / "blueprints" / "catalog-api-route-fixtures.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nImplement the server now.\n", encoding="utf-8")

            errors = validate_catalog_api_route_fixtures(tmp_root)

        self.assertIn("catalog API route fixture doc includes forbidden shortcut: implement the server now", errors)


if __name__ == "__main__":
    unittest.main()
