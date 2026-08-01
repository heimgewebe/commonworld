import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse

from scripts.verify_release_snapshot_live import (
    RawFetch,
    load_snapshot_inventory,
    run_release_snapshot_readback,
    snapshot_url,
)

RELEASE_ID = "a" * 20
SHA = "b" * 40


def build_snapshot(root: Path, files: dict[str, bytes]) -> None:
    manifest = {
        "kind": "commonworld.release_manifest",
        "pages": {},
        "release_id": RELEASE_ID,
        "schema_version": 2,
    }
    manifest_bytes = (
        json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    canonical_manifest = root / "assets/commonworld-page-builds.json"
    canonical_manifest.parent.mkdir(parents=True, exist_ok=True)
    canonical_manifest.write_bytes(manifest_bytes)

    snapshot_root = root / "releases" / RELEASE_ID
    snapshot_manifest = snapshot_root / "assets/commonworld-page-builds.json"
    snapshot_manifest.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest.write_bytes(manifest_bytes)
    for relative, body in files.items():
        target = snapshot_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


def relative_from_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    prefix = f"/releases/{RELEASE_ID}/"
    if not path.startswith(prefix):
        raise AssertionError(f"unexpected snapshot URL: {url}")
    return path.removeprefix(prefix)


class ReleaseSnapshotLiveTests(unittest.TestCase):
    def test_inventory_contains_every_snapshot_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_snapshot(
                root,
                {
                    "index.html": b"index",
                    "assets/app.js": b"app",
                    "catalog/project.json": b"{}",
                },
            )
            release_id, inventory = load_snapshot_inventory(root)

        self.assertEqual(RELEASE_ID, release_id)
        self.assertEqual(
            {
                "assets/app.js",
                "assets/commonworld-page-builds.json",
                "catalog/project.json",
                "index.html",
            },
            {item.relative_path for item in inventory},
        )
        for item in inventory:
            self.assertEqual(
                hashlib.sha256(item.local_path.read_bytes()).hexdigest(),
                item.expected_sha256,
            )

    def test_inventory_rejects_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_snapshot(root, {"index.html": b"index"})
            snapshot_manifest = (
                root
                / "releases"
                / RELEASE_ID
                / "assets/commonworld-page-builds.json"
            )
            snapshot_manifest.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "release snapshot manifest does not match",
            ):
                load_snapshot_inventory(root)

    def test_readback_retries_only_unmatched_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_snapshot(
                root,
                {
                    "index.html": b"index",
                    "assets/app.js": b"app",
                },
            )
            snapshot_root = root / "releases" / RELEASE_ID
            calls: dict[str, int] = {}
            sleeps: list[float] = []

            def fetcher(url: str, timeout_seconds: int) -> RawFetch:
                relative = relative_from_url(url)
                calls[relative] = calls.get(relative, 0) + 1
                expected = (snapshot_root / relative).read_bytes()
                if relative == "assets/app.js" and calls[relative] == 1:
                    return RawFetch(url, url, 404, "text/html", b"missing")
                return RawFetch(url, url, 200, "application/octet-stream", expected)

            receipt = run_release_snapshot_readback(
                base_url="https://commonworld.net/",
                timeout_seconds=5,
                retry_delays_seconds=(0, 1),
                workers=1,
                repository_sha=SHA,
                root=root,
                fetcher=fetcher,
                sleeper=sleeps.append,
                now=lambda: "2026-08-01T00:00:00Z",
            )

        self.assertEqual("pass", receipt.verdict)
        self.assertEqual(3, receipt.total_files)
        self.assertEqual(4, receipt.total_requests)
        self.assertEqual([1.0], sleeps)
        self.assertEqual([3, 1], [cycle.requested_files for cycle in receipt.cycles])
        self.assertEqual(2, calls["assets/app.js"])
        self.assertEqual(1, calls["index.html"])
        self.assertEqual(1, calls["assets/commonworld-page-builds.json"])

    def test_redirect_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_snapshot(root, {"index.html": b"index"})
            snapshot_root = root / "releases" / RELEASE_ID

            def fetcher(url: str, timeout_seconds: int) -> RawFetch:
                relative = relative_from_url(url)
                body = (snapshot_root / relative).read_bytes()
                final_url = url + "?redirected=1" if relative == "index.html" else url
                return RawFetch(url, final_url, 200, "application/octet-stream", body)

            receipt = run_release_snapshot_readback(
                base_url="https://commonworld.net/",
                timeout_seconds=5,
                retry_delays_seconds=(0,),
                workers=1,
                repository_sha=SHA,
                root=root,
                fetcher=fetcher,
                sleeper=lambda _seconds: None,
                now=lambda: "2026-08-01T00:00:00Z",
            )

        self.assertEqual("fail", receipt.verdict)
        self.assertTrue(any(error.startswith("index.html: redirect=") for error in receipt.errors))

    def test_snapshot_url_preserves_path_and_encodes_spaces(self) -> None:
        self.assertEqual(
            f"https://commonworld.net/releases/{RELEASE_ID}/catalog/a%20b.json",
            snapshot_url(
                "https://commonworld.net/",
                RELEASE_ID,
                "catalog/a b.json",
            ),
        )


if __name__ == "__main__":
    unittest.main()
