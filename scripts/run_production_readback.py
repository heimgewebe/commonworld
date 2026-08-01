#!/usr/bin/env python3
"""Wait for and prove the exact Commonworld release served by production."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, TypeVar
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_page_release_manifest import (  # noqa: E402
    MANIFEST_RELATIVE,
    PUBLIC_PAGES,
    build_manifest,
    compute_release_id,
)
from scripts.public_cache import page_build_metadata, page_release_id  # noqa: E402
from scripts.smoke_pages_live import (  # noqa: E402
    PagesLiveSmokeReceipt,
    default_url,
    fetch_live_url,
    run_live_smoke,
)

READBACK_ID = "commonworld.production-readback.path-keyed-release.v1"
DEFAULT_ATTEMPTS = 24
DEFAULT_DELAY_SECONDS = 15.0
T = TypeVar("T")


@dataclass(frozen=True)
class AttemptFailure:
    attempt: int
    error_type: str
    message: str
    elapsed_ms: int


@dataclass(frozen=True)
class PageReadbackReceipt:
    page: str
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body_bytes: int
    page_build: str
    release_id: str


@dataclass(frozen=True)
class SurfaceReadbackReceipt:
    requested_base_url: str
    final_base_url: str
    smoke_id: str
    catalog_entry_count: int
    manifest_url: str
    manifest_sha256: str
    page_receipts: tuple[PageReadbackReceipt, ...]
    runtime_asset_sha256: dict[str, str]


@dataclass(frozen=True)
class ProductionReadbackReceipt:
    readback_id: str
    expected_sha: str
    release_id: str
    manifest_sha256: str
    successful_attempt: int
    elapsed_ms: int
    prior_failures: tuple[AttemptFailure, ...]
    root_surface: SurfaceReadbackReceipt
    snapshot_surface: SurfaceReadbackReceipt


class ReadbackAttemptsExhausted(RuntimeError):
    def __init__(self, failures: tuple[AttemptFailure, ...]) -> None:
        self.failures = failures
        super().__init__(
            "production readback did not converge: "
            + json.dumps([asdict(failure) for failure in failures], sort_keys=True)
        )


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def load_local_manifest(root: Path = ROOT) -> dict[str, object]:
    """Load and recompute the checked-out release manifest before touching production."""
    path = root / MANIFEST_RELATIVE
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("local release manifest must be a JSON object")

    release_id = compute_release_id(root)
    recomputed = build_manifest(root, release_id)
    if manifest != recomputed:
        raise ValueError("local release manifest does not match the checked-out public snapshot")
    return manifest


def retry_operation(
    operation: Callable[[int], T],
    *,
    attempts: int,
    delay_seconds: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[T, int, tuple[AttemptFailure, ...]]:
    """Run a bounded operation and retain every failed attempt as evidence."""
    if not 1 <= attempts <= 60:
        raise ValueError("attempts must be between 1 and 60")
    if not 0 <= delay_seconds <= 300:
        raise ValueError("delay_seconds must be between 0 and 300")

    failures: list[AttemptFailure] = []
    for attempt in range(1, attempts + 1):
        started_at = time.monotonic()
        try:
            result = operation(attempt)
        except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as error:
            failures.append(
                AttemptFailure(
                    attempt=attempt,
                    error_type=type(error).__name__,
                    message=str(error),
                    elapsed_ms=max(0, round((time.monotonic() - started_at) * 1000)),
                )
            )
            if attempt < attempts:
                sleep_fn(delay_seconds)
                continue
            raise ReadbackAttemptsExhausted(tuple(failures)) from error
        return result, attempt, tuple(failures)

    raise AssertionError("bounded production readback loop exhausted unexpectedly")


def _validate_live_manifest(
    *,
    base_url: str,
    timeout_seconds: int,
    expected_manifest: dict[str, object],
) -> tuple[str, str]:
    manifest_url = urljoin(base_url, MANIFEST_RELATIVE)
    fetched = fetch_live_url(
        manifest_url,
        timeout_seconds=timeout_seconds,
        accept="application/json",
        retry_count=1,
    )
    if fetched.status != 200:
        raise RuntimeError(f"release manifest status must be 200, got {fetched.status}")
    if "application/json" not in fetched.content_type.casefold():
        raise RuntimeError(
            "release manifest content-type must include application/json, "
            f"got {fetched.content_type!r}"
        )
    live_manifest = json.loads(fetched.body)
    if live_manifest != expected_manifest:
        raise RuntimeError(
            "live release manifest does not match the checked-out release: "
            f"expected={canonical_json(expected_manifest)} actual={canonical_json(live_manifest)}"
        )
    return fetched.final_url, hashlib.sha256(fetched.body.encode("utf-8")).hexdigest()


def _validate_live_pages(
    *,
    base_url: str,
    timeout_seconds: int,
    expected_manifest: dict[str, object],
) -> tuple[PageReadbackReceipt, ...]:
    expected_release = str(expected_manifest["release_id"])
    expected_pages = expected_manifest["pages"]
    if not isinstance(expected_pages, dict):
        raise ValueError("release manifest pages must be an object")

    receipts: list[PageReadbackReceipt] = []
    for page in PUBLIC_PAGES:
        fetched = fetch_live_url(
            urljoin(base_url, page),
            timeout_seconds=timeout_seconds,
            accept="text/html,application/xhtml+xml",
            retry_count=1,
        )
        if fetched.status != 200:
            raise RuntimeError(f"public page status must be 200 for {page}, got {fetched.status}")
        if "text/html" not in fetched.content_type.casefold():
            raise RuntimeError(
                f"public page content-type must include text/html for {page}, got {fetched.content_type!r}"
            )
        declared_page, build = page_build_metadata(fetched.body)
        release = page_release_id(fetched.body)
        if declared_page != page:
            raise RuntimeError(f"public page identity mismatch: requested {page}, got {declared_page}")
        if build != expected_pages.get(page):
            raise RuntimeError(
                f"public page build mismatch for {page}: expected {expected_pages.get(page)!r}, got {build!r}"
            )
        if release != expected_release:
            raise RuntimeError(
                f"public page release mismatch for {page}: expected {expected_release}, got {release}"
            )
        receipts.append(
            PageReadbackReceipt(
                page=page,
                requested_url=fetched.requested_url,
                final_url=fetched.final_url,
                status=fetched.status,
                content_type=fetched.content_type,
                body_bytes=len(fetched.body.encode("utf-8")),
                page_build=build,
                release_id=release,
            )
        )
    return tuple(receipts)


def _summarize_smoke(
    smoke: PagesLiveSmokeReceipt,
    *,
    requested_base_url: str,
    manifest_url: str,
    manifest_sha256: str,
    page_receipts: tuple[PageReadbackReceipt, ...],
) -> SurfaceReadbackReceipt:
    return SurfaceReadbackReceipt(
        requested_base_url=requested_base_url,
        final_base_url=smoke.final_url,
        smoke_id=smoke.smoke_id,
        catalog_entry_count=smoke.catalog_entry_count,
        manifest_url=manifest_url,
        manifest_sha256=manifest_sha256,
        page_receipts=page_receipts,
        runtime_asset_sha256={
            asset.relative_url: asset.sha256 for asset in smoke.runtime_assets
        },
    )


def readback_once(
    *,
    root_url: str,
    timeout_seconds: int,
    expected_sha: str,
    expected_manifest: dict[str, object],
) -> ProductionReadbackReceipt:
    """Read root and path-keyed release surfaces against one checked-out manifest."""
    release_id = str(expected_manifest["release_id"])
    manifest_sha256 = hashlib.sha256(
        ((ROOT / MANIFEST_RELATIVE).read_bytes())
    ).hexdigest()

    root_smoke = run_live_smoke(
        root_url,
        timeout_seconds=timeout_seconds,
        retry_count=1,
    )
    root_manifest_url, root_manifest_sha256 = _validate_live_manifest(
        base_url=root_smoke.final_url,
        timeout_seconds=timeout_seconds,
        expected_manifest=expected_manifest,
    )
    root_pages = _validate_live_pages(
        base_url=root_smoke.final_url,
        timeout_seconds=timeout_seconds,
        expected_manifest=expected_manifest,
    )

    snapshot_url = urljoin(root_smoke.final_url, f"releases/{release_id}/")
    snapshot_smoke = run_live_smoke(
        snapshot_url,
        timeout_seconds=timeout_seconds,
        retry_count=1,
    )
    snapshot_manifest_url, snapshot_manifest_sha256 = _validate_live_manifest(
        base_url=snapshot_smoke.final_url,
        timeout_seconds=timeout_seconds,
        expected_manifest=expected_manifest,
    )
    snapshot_pages = _validate_live_pages(
        base_url=snapshot_smoke.final_url,
        timeout_seconds=timeout_seconds,
        expected_manifest=expected_manifest,
    )

    return ProductionReadbackReceipt(
        readback_id=READBACK_ID,
        expected_sha=expected_sha,
        release_id=release_id,
        manifest_sha256=manifest_sha256,
        successful_attempt=0,
        elapsed_ms=0,
        prior_failures=(),
        root_surface=_summarize_smoke(
            root_smoke,
            requested_base_url=root_url,
            manifest_url=root_manifest_url,
            manifest_sha256=root_manifest_sha256,
            page_receipts=root_pages,
        ),
        snapshot_surface=_summarize_smoke(
            snapshot_smoke,
            requested_base_url=snapshot_url,
            manifest_url=snapshot_manifest_url,
            manifest_sha256=snapshot_manifest_sha256,
            page_receipts=snapshot_pages,
        ),
    )


def run_production_readback(
    *,
    root_url: str,
    timeout_seconds: int,
    attempts: int,
    delay_seconds: float,
    expected_sha: str,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ProductionReadbackReceipt:
    expected_manifest = load_local_manifest(ROOT)
    started_at = time.monotonic()

    result, successful_attempt, failures = retry_operation(
        lambda _attempt: readback_once(
            root_url=root_url,
            timeout_seconds=timeout_seconds,
            expected_sha=expected_sha,
            expected_manifest=expected_manifest,
        ),
        attempts=attempts,
        delay_seconds=delay_seconds,
        sleep_fn=sleep_fn,
    )
    return replace(
        result,
        successful_attempt=successful_attempt,
        elapsed_ms=max(0, round((time.monotonic() - started_at) * 1000)),
        prior_failures=failures,
    )


def _write_receipt(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wait for the exact checked-out Commonworld release on the root and path-keyed production surfaces."
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()

    expected_sha = os.environ.get("COMMONWORLD_EXPECTED_SHA", "unknown")
    try:
        receipt = run_production_readback(
            root_url=args.url or default_url(ROOT),
            timeout_seconds=args.timeout_seconds,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
            expected_sha=expected_sha,
        )
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        payload: dict[str, object] = {
            "error": str(error),
            "error_type": type(error).__name__,
            "expected_sha": expected_sha,
            "readback_id": READBACK_ID,
            "status": "failure",
        }
        if isinstance(error, ReadbackAttemptsExhausted):
            payload["attempts"] = [asdict(failure) for failure in error.failures]
        _write_receipt(args.receipt, payload)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    payload = asdict(receipt)
    payload["status"] = "success"
    _write_receipt(args.receipt, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
