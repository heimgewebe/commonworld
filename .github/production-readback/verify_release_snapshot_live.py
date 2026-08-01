#!/usr/bin/env python3
"""Verify every file in the immutable Commonworld release snapshot on production."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_RELATIVE = Path("assets/commonworld-page-builds.json")
RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{20}$")
DEFAULT_RETRY_DELAYS_SECONDS = (0, 30, 90)
DEFAULT_WORKERS = 8


@dataclass(frozen=True)
class RawFetch:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class SnapshotFile:
    relative_path: str
    local_path: Path
    expected_sha256: str
    expected_bytes: int


@dataclass(frozen=True)
class SnapshotFileReceipt:
    relative_path: str
    requested_url: str
    final_url: str | None
    status: int | None
    content_type: str | None
    body_bytes: int | None
    sha256: str | None
    expected_sha256: str
    expected_bytes: int
    matched: bool
    error: str | None


@dataclass(frozen=True)
class SnapshotCycleReceipt:
    cycle: int
    delay_seconds: int
    requested_files: int
    matched_files: int
    remaining_files: int


@dataclass(frozen=True)
class ReleaseSnapshotReceipt:
    schema_version: int
    kind: str
    receipt_id: str
    repository_sha: str
    requested_url: str
    release_id: str
    started_at: str
    completed_at: str
    verdict: str
    total_files: int
    total_requests: int
    cycles: tuple[SnapshotCycleReceipt, ...]
    files: tuple[SnapshotFileReceipt, ...]
    errors: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def load_snapshot_inventory(root: Path = ROOT) -> tuple[str, tuple[SnapshotFile, ...]]:
    """Return the exact committed file inventory for the current release id."""
    manifest_path = root / MANIFEST_RELATIVE
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read release manifest: {error}") from error

    release_id = manifest.get("release_id") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("kind") != "commonworld.release_manifest"
        or manifest.get("schema_version") != 2
        or not isinstance(release_id, str)
        or not RELEASE_ID_PATTERN.fullmatch(release_id)
    ):
        raise RuntimeError("release manifest identity is invalid")

    snapshot_root = root / "releases" / release_id
    if not snapshot_root.is_dir():
        raise RuntimeError(f"release snapshot directory is missing: releases/{release_id}")
    snapshot_manifest = snapshot_root / MANIFEST_RELATIVE
    if not snapshot_manifest.is_file() or snapshot_manifest.read_bytes() != manifest_bytes:
        raise RuntimeError("release snapshot manifest does not match the canonical manifest")

    inventory: list[SnapshotFile] = []
    for path in sorted(
        snapshot_root.rglob("*"),
        key=lambda item: item.relative_to(snapshot_root).as_posix(),
    ):
        if path.is_symlink():
            raise RuntimeError(
                f"release snapshot must not contain symlinks: {path.relative_to(snapshot_root)}"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(snapshot_root).as_posix()
        body = path.read_bytes()
        inventory.append(
            SnapshotFile(
                relative_path=relative,
                local_path=path,
                expected_sha256=hashlib.sha256(body).hexdigest(),
                expected_bytes=len(body),
            )
        )
    if not inventory:
        raise RuntimeError("release snapshot inventory must not be empty")
    return release_id, tuple(inventory)


def fetch_bytes(url: str, timeout_seconds: int) -> RawFetch:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "User-Agent": "commonworld-release-snapshot-readback/1.0",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
            context=ssl.create_default_context(),
        ) as response:
            return RawFetch(
                requested_url=url,
                final_url=response.geturl(),
                status=int(response.status),
                content_type=response.headers.get("content-type", ""),
                body=response.read(),
            )
    except urllib.error.HTTPError as error:
        try:
            body = error.read()
        finally:
            error.close()
        return RawFetch(
            requested_url=url,
            final_url=error.geturl(),
            status=int(error.code),
            content_type=error.headers.get("content-type", "") if error.headers else "",
            body=body,
        )
    except (urllib.error.URLError, OSError) as error:
        raise RuntimeError(
            f"snapshot fetch failed for {url}: {type(error).__name__}: {error}"
        ) from error


def snapshot_url(base_url: str, release_id: str, relative_path: str) -> str:
    root_url = base_url if base_url.endswith("/") else f"{base_url}/"
    encoded = urllib.parse.quote(relative_path, safe="/._-")
    return urllib.parse.urljoin(root_url, f"releases/{release_id}/{encoded}")


def verify_snapshot_file(
    item: SnapshotFile,
    *,
    base_url: str,
    release_id: str,
    timeout_seconds: int,
    fetcher: Callable[[str, int], RawFetch] = fetch_bytes,
) -> SnapshotFileReceipt:
    requested_url = snapshot_url(base_url, release_id, item.relative_path)
    try:
        fetched = fetcher(requested_url, timeout_seconds)
    except RuntimeError as error:
        return SnapshotFileReceipt(
            relative_path=item.relative_path,
            requested_url=requested_url,
            final_url=None,
            status=None,
            content_type=None,
            body_bytes=None,
            sha256=None,
            expected_sha256=item.expected_sha256,
            expected_bytes=item.expected_bytes,
            matched=False,
            error=str(error),
        )

    actual_sha256 = hashlib.sha256(fetched.body).hexdigest()
    matched = (
        fetched.status == 200
        and fetched.final_url == requested_url
        and len(fetched.body) == item.expected_bytes
        and actual_sha256 == item.expected_sha256
    )
    reasons: list[str] = []
    if fetched.status != 200:
        reasons.append(f"status={fetched.status}")
    if fetched.final_url != requested_url:
        reasons.append(f"redirect={fetched.final_url}")
    if len(fetched.body) != item.expected_bytes:
        reasons.append(f"bytes={len(fetched.body)} expected={item.expected_bytes}")
    if actual_sha256 != item.expected_sha256:
        reasons.append("sha256-mismatch")
    return SnapshotFileReceipt(
        relative_path=item.relative_path,
        requested_url=requested_url,
        final_url=fetched.final_url,
        status=fetched.status,
        content_type=fetched.content_type,
        body_bytes=len(fetched.body),
        sha256=actual_sha256,
        expected_sha256=item.expected_sha256,
        expected_bytes=item.expected_bytes,
        matched=matched,
        error=None if matched else ", ".join(reasons),
    )


def verify_snapshot_cycle(
    items: Sequence[SnapshotFile],
    *,
    base_url: str,
    release_id: str,
    timeout_seconds: int,
    workers: int,
    fetcher: Callable[[str, int], RawFetch] = fetch_bytes,
) -> tuple[SnapshotFileReceipt, ...]:
    if not 1 <= workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        receipts = executor.map(
            lambda item: verify_snapshot_file(
                item,
                base_url=base_url,
                release_id=release_id,
                timeout_seconds=timeout_seconds,
                fetcher=fetcher,
            ),
            items,
        )
        return tuple(receipts)


def run_release_snapshot_readback(
    *,
    base_url: str,
    timeout_seconds: int,
    retry_delays_seconds: Sequence[int],
    workers: int,
    repository_sha: str,
    root: Path = ROOT,
    fetcher: Callable[[str, int], RawFetch] = fetch_bytes,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], str] = utc_now,
) -> ReleaseSnapshotReceipt:
    delays = tuple(int(delay) for delay in retry_delays_seconds)
    if not delays or delays[0] != 0 or any(delay < 0 or delay > 600 for delay in delays):
        raise ValueError(
            "retry delays must start with zero and stay between 0 and 600 seconds"
        )
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise ValueError("timeout_seconds must be between 1 and 120")

    started_at = now()
    release_id, inventory = load_snapshot_inventory(root)
    pending = {item.relative_path: item for item in inventory}
    latest: dict[str, SnapshotFileReceipt] = {}
    cycles: list[SnapshotCycleReceipt] = []
    total_requests = 0

    for cycle, delay in enumerate(delays, start=1):
        if delay:
            sleeper(float(delay))
        requested = tuple(pending.values())
        requested_by_path = {item.relative_path: item for item in requested}
        receipts = verify_snapshot_cycle(
            requested,
            base_url=base_url,
            release_id=release_id,
            timeout_seconds=timeout_seconds,
            workers=workers,
            fetcher=fetcher,
        )
        total_requests += len(receipts)
        pending = {}
        for receipt in receipts:
            latest[receipt.relative_path] = receipt
            if not receipt.matched:
                pending[receipt.relative_path] = requested_by_path[receipt.relative_path]
        cycles.append(
            SnapshotCycleReceipt(
                cycle=cycle,
                delay_seconds=delay,
                requested_files=len(requested),
                matched_files=sum(receipt.matched for receipt in receipts),
                remaining_files=len(pending),
            )
        )
        if not pending:
            break

    ordered_receipts = tuple(latest[item.relative_path] for item in inventory)
    errors = tuple(
        f"{receipt.relative_path}: {receipt.error or 'unmatched'}"
        for receipt in ordered_receipts
        if not receipt.matched
    )
    return ReleaseSnapshotReceipt(
        schema_version=1,
        kind="commonworld_release_snapshot_readback",
        receipt_id="commonworld.release-snapshot-readback.v1",
        repository_sha=repository_sha,
        requested_url=base_url,
        release_id=release_id,
        started_at=started_at,
        completed_at=now(),
        verdict="pass" if not errors else "fail",
        total_files=len(inventory),
        total_requests=total_requests,
        cycles=tuple(cycles),
        files=ordered_receipts,
        errors=errors,
    )


def write_receipt(
    path: Path,
    receipt: ReleaseSnapshotReceipt | dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(receipt) if isinstance(receipt, ReleaseSnapshotReceipt) else receipt
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def parse_delays(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "retry delays must be comma-separated integers"
        ) from error


def _write_fixture_snapshot(root: Path, release_id: str, files: dict[str, bytes]) -> None:
    manifest = {
        "kind": "commonworld.release_manifest",
        "pages": {},
        "release_id": release_id,
        "schema_version": 2,
    }
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    canonical_manifest = root / MANIFEST_RELATIVE
    canonical_manifest.parent.mkdir(parents=True, exist_ok=True)
    canonical_manifest.write_bytes(manifest_bytes)
    snapshot_root = root / "releases" / release_id
    snapshot_manifest = snapshot_root / MANIFEST_RELATIVE
    snapshot_manifest.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest.write_bytes(manifest_bytes)
    for relative, body in files.items():
        target = snapshot_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


def run_self_test() -> None:
    release_id = "a" * 20
    repository_sha = "b" * 40
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _write_fixture_snapshot(
            root,
            release_id,
            {
                "index.html": b"index",
                "assets/app.js": b"app",
                "catalog/a b.json": b"{}",
            },
        )
        loaded_release, inventory = load_snapshot_inventory(root)
        assert loaded_release == release_id
        assert {item.relative_path for item in inventory} == {
            "assets/app.js",
            "assets/commonworld-page-builds.json",
            "catalog/a b.json",
            "index.html",
        }
        snapshot_root = root / "releases" / release_id
        calls: dict[str, int] = {}
        sleeps: list[float] = []

        def relative_from_url(url: str) -> str:
            path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
            prefix = f"/releases/{release_id}/"
            assert path.startswith(prefix)
            return path.removeprefix(prefix)

        def flaky_fetcher(url: str, timeout_seconds: int) -> RawFetch:
            assert timeout_seconds == 5
            relative = relative_from_url(url)
            calls[relative] = calls.get(relative, 0) + 1
            expected = (snapshot_root / relative).read_bytes()
            if relative == "assets/app.js" and calls[relative] == 1:
                return RawFetch(url, url, 404, "text/html", b"missing")
            return RawFetch(url, url, 200, "application/octet-stream", expected)

        receipt = run_release_snapshot_readback(
            base_url="https://commonworld.net",
            timeout_seconds=5,
            retry_delays_seconds=(0, 1),
            workers=1,
            repository_sha=repository_sha,
            root=root,
            fetcher=flaky_fetcher,
            sleeper=sleeps.append,
            now=lambda: "2026-08-01T00:00:00Z",
        )
        assert receipt.verdict == "pass"
        assert receipt.total_files == 4
        assert receipt.total_requests == 5
        assert [cycle.requested_files for cycle in receipt.cycles] == [4, 1]
        assert sleeps == [1.0]
        assert calls["assets/app.js"] == 2
        assert calls["index.html"] == 1
        assert calls["assets/commonworld-page-builds.json"] == 1
        assert calls["catalog/a b.json"] == 1
        assert snapshot_url(
            "https://commonworld.net",
            release_id,
            "catalog/a b.json",
        ) == f"https://commonworld.net/releases/{release_id}/catalog/a%20b.json"

        def redirecting_fetcher(url: str, timeout_seconds: int) -> RawFetch:
            relative = relative_from_url(url)
            body = (snapshot_root / relative).read_bytes()
            final_url = f"{url}?redirected=1" if relative == "index.html" else url
            return RawFetch(url, final_url, 200, "application/octet-stream", body)

        redirected = run_release_snapshot_readback(
            base_url="https://commonworld.net/",
            timeout_seconds=5,
            retry_delays_seconds=(0,),
            workers=1,
            repository_sha=repository_sha,
            root=root,
            fetcher=redirecting_fetcher,
            sleeper=lambda _seconds: None,
            now=lambda: "2026-08-01T00:00:00Z",
        )
        assert redirected.verdict == "fail"
        assert any(error.startswith("index.html: redirect=") for error in redirected.errors)

        snapshot_manifest = snapshot_root / MANIFEST_RELATIVE
        snapshot_manifest.write_text("{}\n", encoding="utf-8")
        try:
            load_snapshot_inventory(root)
        except RuntimeError as error:
            assert "release snapshot manifest does not match" in str(error)
        else:
            raise AssertionError("manifest drift must fail closed")

    print("commonworld complete release snapshot self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify every committed file in the current path-keyed release snapshot "
            "on production."
        )
    )
    parser.add_argument("--url", default="https://commonworld.net/")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument(
        "--retry-delays-seconds",
        type=parse_delays,
        default=DEFAULT_RETRY_DELAYS_SECONDS,
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if args.receipt is None:
        parser.error("--receipt is required unless --self-test is used")

    repository_sha = os.environ.get(
        "COMMONWORLD_EXPECTED_SHA",
        os.environ.get("GITHUB_SHA", "unknown"),
    )
    try:
        receipt = run_release_snapshot_readback(
            base_url=args.url,
            timeout_seconds=args.timeout_seconds,
            retry_delays_seconds=args.retry_delays_seconds,
            workers=args.workers,
            repository_sha=repository_sha,
        )
    except (RuntimeError, ValueError, OSError) as error:
        failure = {
            "error": str(error),
            "error_type": type(error).__name__,
            "kind": "commonworld_release_snapshot_readback",
            "receipt_id": "commonworld.release-snapshot-readback.v1",
            "repository_sha": repository_sha,
            "schema_version": 1,
            "verdict": "fail",
        }
        write_receipt(args.receipt, failure)
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 1

    write_receipt(args.receipt, receipt)
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0 if receipt.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
