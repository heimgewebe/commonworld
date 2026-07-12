import json
import unittest

from scripts.smoke_pages_live import (
    EXPECTED_CATALOG_ENTRY_COUNT,
    EXPECTED_PUBLICATION,
    LiveFetch,
    MIN_BODY_BYTES,
    REQUIRED_TOKENS,
    validate_catalog_fetch,
    validate_live_fetch,
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
                "project_files": [f"projects/project-{index:02d}.json" for index in range(EXPECTED_CATALOG_ENTRY_COUNT)],
                "publication": EXPECTED_PUBLICATION,
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

    def test_catalog_count_drift_fails(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
