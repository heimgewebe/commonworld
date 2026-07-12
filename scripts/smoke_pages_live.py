#!/usr/bin/env python3
"""Read-only live delivery smoke for the Commonworld shell and public catalog."""

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
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
URL_ENV = "COMMONWORLD_PAGES_URL"
MIN_BODY_BYTES = 2_000
CATALOG_RELATIVE_URL = "catalog/catalog.json"
EXPECTED_CATALOG_ENTRY_COUNT = 10

REQUIRED_TOKENS = (
    "<title>commonworld — Commons entdecken</title>",
    "Commons weltweit entdecken",
    "Die gemeinsame Welt wird sichtbar.",
    'class="globe-stage"',
    'class="digital-sphere"',
    "Die Globe-Engine steht fest.",
    "MapLibre GL JS wird den Globus",
    "10 geprüfte Startdatensätze",
    'id="catalog"',
    './catalog/catalog.json',
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

EXPECTED_PUBLICATION = {
    "public": True,
    "source_policy": "official-sources-only",
    "curation_state": "listed",
    "engine_selected": True,
    "production_architecture_authorized": False,
    "selected_engine": "maplibre_gl_js",
    "public_runtime_uses_selected_engine": False,
}


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
    catalog_requested_url: str
    catalog_final_url: str
    catalog_status: int
    catalog_content_type: str
    catalog_kind: str
    catalog_entry_count: int
    catalog_project_files: tuple[str, ...]
    catalog_publication: dict[str, object]


def default_url(root: Path = ROOT) -> str:
    configured = os.environ.get(URL_ENV)
    if configured:
        return configured
    cname = root / "CNAME"
    if cname.is_file():
        host = cname.read_text(encoding="utf-8").strip().splitlines()[0]
        return f"https://{host}/"
    return "https://heimgewebe.github.io/commonworld/"


def fetch_live_url(
    url: str,
    timeout_seconds: int = 20,
    insecure: bool = False,
    accept: str = "text/html,application/xhtml+xml",
) -> LiveFetch:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "commonworld-pages-live-smoke/3.0", "Accept": accept},
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


def parse_catalog(fetch: LiveFetch) -> tuple[dict, list[str]]:
    errors: list[str] = []
    if fetch.status != 200:
        errors.append(f"live catalog status must be 200, got {fetch.status}")
    if "application/json" not in fetch.content_type.casefold():
        errors.append(f"live catalog content-type must include application/json, got {fetch.content_type!r}")
    try:
        catalog = json.loads(fetch.body)
    except json.JSONDecodeError as error:
        return {}, errors + [f"live catalog must be valid JSON: {error}"]
    if not isinstance(catalog, dict):
        return {}, errors + ["live catalog must be a JSON object"]
    return catalog, errors


def validate_catalog_fetch(fetch: LiveFetch) -> list[str]:
    catalog, errors = parse_catalog(fetch)
    if not catalog:
        if not errors:
            errors.append("live catalog must not be empty")
        return errors
    if catalog.get("schema_version") != 1:
        errors.append("live catalog schema_version must be 1")
    if catalog.get("kind") != "commonworld_public_catalog":
        errors.append("live catalog kind mismatch")
    files = catalog.get("project_files")
    if not isinstance(files, list):
        errors.append("live catalog project_files must be a list")
        files = []
    if files != sorted(files) or len(files) != len(set(files)):
        errors.append("live catalog project_files must be sorted and unique")
    if catalog.get("entry_count") != EXPECTED_CATALOG_ENTRY_COUNT or len(files) != EXPECTED_CATALOG_ENTRY_COUNT:
        errors.append(f"live catalog must contain {EXPECTED_CATALOG_ENTRY_COUNT} entries")
    if catalog.get("publication") != EXPECTED_PUBLICATION:
        errors.append("live catalog publication boundary mismatch")
    return errors


def run_live_smoke(url: str | None = None, timeout_seconds: int = 20, insecure: bool = False) -> PagesLiveSmokeReceipt:
    page = fetch_live_url(url or default_url(ROOT), timeout_seconds=timeout_seconds, insecure=insecure)
    errors = validate_live_fetch(page)

    catalog_url = urljoin(page.final_url, CATALOG_RELATIVE_URL)
    catalog_fetch = fetch_live_url(
        catalog_url,
        timeout_seconds=timeout_seconds,
        insecure=insecure,
        accept="application/json",
    )
    errors.extend(validate_catalog_fetch(catalog_fetch))
    if errors:
        raise RuntimeError("live Pages smoke failed:\n- " + "\n- ".join(errors))

    catalog, parse_errors = parse_catalog(catalog_fetch)
    if parse_errors:
        raise RuntimeError("live Pages smoke failed:\n- " + "\n- ".join(parse_errors))
    return PagesLiveSmokeReceipt(
        smoke_id="commonworld.pages-live.public-catalog.v3",
        requested_url=page.requested_url,
        final_url=page.final_url,
        status=page.status,
        content_type=page.content_type,
        body_bytes=len(page.body.encode("utf-8")),
        required_tokens=REQUIRED_TOKENS,
        forbidden_tokens_absent=FORBIDDEN_TOKENS,
        catalog_requested_url=catalog_fetch.requested_url,
        catalog_final_url=catalog_fetch.final_url,
        catalog_status=catalog_fetch.status,
        catalog_content_type=catalog_fetch.content_type,
        catalog_kind=str(catalog["kind"]),
        catalog_entry_count=int(catalog["entry_count"]),
        catalog_project_files=tuple(catalog["project_files"]),
        catalog_publication=dict(catalog["publication"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the public Commonworld shell and catalog.")
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
