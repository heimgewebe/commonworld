import hashlib
import json
import unittest

from scripts.smoke_pages_live import (
    EXPECTED_CATALOG_ENTRY_COUNT,
    EXPECTED_CATALOG_PROJECT_FILES,
    EXPECTED_MACHINE_SURFACE,
    EXPECTED_PUBLICATION,
    LiveFetch,
    MIN_BODY_BYTES,
    REQUIRED_TOKENS,
    validate_catalog_fetch,
    validate_live_fetch,
    validate_runtime_asset_fetch,
)


class PagesLiveSmokeTests(unittest.TestCase):
    def valid_body(self) -> str:
        body = "\n".join(REQUIRED_TOKENS)
        return body + (" " * max(0, MIN_BODY_BYTES - len(body.encode("utf-8")) + 10))

    def valid_catalog(self) -> str:
        return json.dumps(
            {
                "schema_version": 1,
                "kind": "commonworld_public_catalog",
                "entry_count": EXPECTED_CATALOG_ENTRY_COUNT,
                "project_files": list(EXPECTED_CATALOG_PROJECT_FILES),
                "publication": EXPECTED_PUBLICATION,
                "machine_surface": EXPECTED_MACHINE_SURFACE,
            }
        )

    def test_canonical_shell_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html; charset=utf-8",
            body=self.valid_body(),
        )
        self.assertEqual([], validate_live_fetch(fetch))

    def test_public_catalog_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json; charset=utf-8",
            body=self.valid_catalog(),
        )
        self.assertEqual([], validate_catalog_fetch(fetch))

    def test_empty_catalog_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body="{}",
        )
        self.assertIn("live catalog must not be empty", validate_catalog_fetch(fetch))

    def test_catalog_boundary_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["publication"]["engine_selected"] = False
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_old_preproduction_boundary_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["publication"]["production_architecture_authorized"] = False
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_missing_production_delivery_boundary_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        del catalog["publication"]["production_delivery"]
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog publication boundary mismatch", validate_catalog_fetch(fetch))

    def test_machine_surface_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["machine_surface"]["write_path"] = True
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn("live catalog machine-readable surface boundary mismatch", validate_catalog_fetch(fetch))

    def test_catalog_count_or_identity_drift_fails(self) -> None:
        catalog = json.loads(self.valid_catalog())
        catalog["project_files"].pop()
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn(
            f"live catalog must contain {EXPECTED_CATALOG_ENTRY_COUNT} entries",
            validate_catalog_fetch(fetch),
        )

        catalog = json.loads(self.valid_catalog())
        catalog["project_files"] = sorted(["projects/not-canonical.json", *catalog["project_files"][1:]])
        fetch = LiveFetch(
            requested_url="https://commonworld.net/catalog/catalog.json",
            final_url="https://commonworld.net/catalog/catalog.json",
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        )
        self.assertIn(
            "live catalog project_files do not match the checked-out canonical catalog",
            validate_catalog_fetch(fetch),
        )

    def test_old_proof_hub_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html",
            body=self.valid_body() + " proof hub ",
        )
        self.assertIn("live Pages contains forbidden delivery token: proof hub", validate_live_fetch(fetch))

    def test_parking_page_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html",
            body=self.valid_body() + " Domain parked. ",
        )
        self.assertIn("live Pages contains forbidden delivery token: Domain parked.", validate_live_fetch(fetch))

    def test_runtime_asset_hash_and_delivery_pass(self) -> None:
        body = "x" * 128
        fetch = LiveFetch(
            requested_url="https://commonworld.net/assets/commonworld-app.js",
            final_url="https://commonworld.net/assets/commonworld-app.js",
            status=200,
            content_type="text/javascript; charset=utf-8",
            body=body,
        )
        self.assertEqual(
            [],
            validate_runtime_asset_fetch(
                fetch,
                minimum_bytes=100,
                allowed_content_types=("javascript",),
                expected_sha256=hashlib.sha256(body.encode()).hexdigest(),
            ),
        )

    def test_runtime_asset_hash_drift_fails(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/assets/commonworld-app.js",
            final_url="https://commonworld.net/assets/commonworld-app.js",
            status=200,
            content_type="text/javascript",
            body="changed runtime",
        )
        errors = validate_runtime_asset_fetch(
            fetch,
            minimum_bytes=1,
            allowed_content_types=("javascript",),
            expected_sha256="0" * 64,
        )
        self.assertTrue(any("hash mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
