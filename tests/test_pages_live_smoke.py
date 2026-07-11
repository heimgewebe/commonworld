import unittest

from scripts.smoke_pages_live import LiveFetch, MIN_BODY_BYTES, REQUIRED_TOKENS, validate_live_fetch


class PagesLiveSmokeTests(unittest.TestCase):
    def valid_body(self) -> str:
        body = "\n".join(REQUIRED_TOKENS)
        return body + (" " * max(0, MIN_BODY_BYTES - len(body.encode("utf-8")) + 10))

    def test_canonical_shell_passes(self) -> None:
        fetch = LiveFetch(
            requested_url="https://commonworld.net/",
            final_url="https://commonworld.net/",
            status=200,
            content_type="text/html; charset=utf-8",
            body=self.valid_body(),
        )
        self.assertEqual([], validate_live_fetch(fetch))

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
