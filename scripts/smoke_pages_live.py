#!/usr/bin/env python3
"""Read-only live delivery smoke for the canonical Commonworld public shell."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL_ENV = "COMMONWORLD_PAGES_URL"
MIN_BODY_BYTES = 2_000

REQUIRED_TOKENS = (
    "<title>commonworld — Commons entdecken</title>",
    "Commons weltweit entdecken",
    "Die gemeinsame Welt wird sichtbar.",
    'class="globe-stage"',
    'class="digital-sphere"',
    "Der kanonische Globus wird aufgebaut.",
)

FORBIDDEN_TOKENS = (
    "Domain parked.",
    "INWX",
    "domainparking",
    "proof hub",
    "fixture",
    "Aether",
    "<script",
    "<form",
    "method=\"post\"",
    "login",
    "signup",
    "/api/",
)


@dataclass(frozen=True)
class LiveFetch:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body: str


@dataclass(frozen=True)
class PagesLiveSmokeReceipt:
    smoke_id: str
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body_bytes: int
    required_tokens: tuple[str, ...]
    forbidden_tokens_absent: tuple[str, ...]


def default_url(root: Path = ROOT) -> str:
    configured = os.environ.get(URL_ENV)
    if configured:
        return configured
    cname = root / "CNAME"
    if cname.is_file():
        host = cname.read_text(encoding="utf-8").strip().splitlines()[0]
        return f"https://{host}/"
    return "https://heimgewebe.github.io/commonworld/"


def fetch_live_url(url: str, timeout_seconds: int = 20, insecure: bool = False) -> LiveFetch:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "commonworld-pages-live-smoke/2.0", "Accept": "text/html,application/xhtml+xml"},
    )
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context) as response:
            raw = response.read()
            return LiveFetch(
                requested_url=url,
                final_url=response.geturl(),
                status=int(response.status),
                content_type=response.headers.get("content-type", ""),
                body=raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace"),
            )
    except urllib.error.URLError as error:
        raise RuntimeError(f"live Pages fetch failed for {url}: {error}") from error


def validate_live_fetch(fetch: LiveFetch) -> list[str]:
    errors: list[str] = []
    body_lower = fetch.body.casefold()
    if fetch.status != 200:
        errors.append(f"live Pages status must be 200, got {fetch.status}")
    if "text/html" not in fetch.content_type.casefold():
        errors.append(f"live Pages content-type must include text/html, got {fetch.content_type!r}")
    if len(fetch.body.encode("utf-8")) < MIN_BODY_BYTES:
        errors.append(f"live Pages body too small: expected at least {MIN_BODY_BYTES} bytes")
    for token in REQUIRED_TOKENS:
        if token not in fetch.body:
            errors.append(f"live Pages missing canonical-shell token: {token}")
    for token in FORBIDDEN_TOKENS:
        if token.casefold() in body_lower:
            errors.append(f"live Pages contains forbidden delivery token: {token}")
    return errors


def run_live_smoke(url: str | None = None, timeout_seconds: int = 20, insecure: bool = False) -> PagesLiveSmokeReceipt:
    fetch = fetch_live_url(url or default_url(ROOT), timeout_seconds=timeout_seconds, insecure=insecure)
    errors = validate_live_fetch(fetch)
    if errors:
        raise RuntimeError("live Pages smoke failed:\n- " + "\n- ".join(errors))
    return PagesLiveSmokeReceipt(
        smoke_id="commonworld.pages-live.canonical-shell.v2",
        requested_url=fetch.requested_url,
        final_url=fetch.final_url,
        status=fetch.status,
        content_type=fetch.content_type,
        body_bytes=len(fetch.body.encode("utf-8")),
        required_tokens=REQUIRED_TOKENS,
        forbidden_tokens_absent=FORBIDDEN_TOKENS,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that the public Pages URL serves the canonical Commonworld shell.")
    parser.add_argument("--url", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()
    try:
        receipt = run_live_smoke(args.url, timeout_seconds=args.timeout_seconds, insecure=args.insecure)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
