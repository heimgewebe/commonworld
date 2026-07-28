#!/usr/bin/env python3
"""Deterministic cache-coherence helpers for public Commonworld pages."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PAGE_BUILD_PLACEHOLDER = "0" * 16
PAGE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,79}$")
PAGE_BUILD_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_PAGE_META_PATTERN = re.compile(r'<meta name="commonworld-page" content="([^"]+)" />')
_BUILD_META_PATTERN = re.compile(r'<meta name="commonworld-page-build" content="([0-9a-f]{16})" />')


def asset_version(relative_path: str, root: Path) -> str:
    """Return a compact deterministic content version for one public asset."""
    return hashlib.sha256((root / relative_path).read_bytes()).hexdigest()[:12]


def stamp_page_build(markup: str, page_name: str) -> str:
    """Insert page identity/build metadata and bind the build to rendered bytes."""
    if not PAGE_NAME_PATTERN.fullmatch(page_name):
        raise ValueError(f"invalid public page name: {page_name!r}")
    if "commonworld-page-build" in markup or "commonworld-page" in markup:
        raise ValueError("public page metadata already present")
    charset = '    <meta charset="utf-8" />'
    if markup.count(charset) != 1:
        raise ValueError("public page must contain exactly one canonical charset marker")
    metadata = (
        f'{charset}\n'
        f'    <meta name="commonworld-page" content="{page_name}" />\n'
        f'    <meta name="commonworld-page-build" content="{PAGE_BUILD_PLACEHOLDER}" />'
    )
    stamped = markup.replace(charset, metadata, 1)
    build = hashlib.sha256(stamped.encode("utf-8")).hexdigest()[:16]
    return stamped.replace(PAGE_BUILD_PLACEHOLDER, build, 1)


def page_build_metadata(markup: str) -> tuple[str, str]:
    """Read and validate the exact page/build pair from rendered markup."""
    page_matches = _PAGE_META_PATTERN.findall(markup)
    build_matches = _BUILD_META_PATTERN.findall(markup)
    if len(page_matches) != 1 or len(build_matches) != 1:
        raise ValueError("public page must declare exactly one page identity and build")
    page_name, build = page_matches[0], build_matches[0]
    if not PAGE_NAME_PATTERN.fullmatch(page_name):
        raise ValueError(f"invalid public page identity: {page_name!r}")
    if not PAGE_BUILD_PATTERN.fullmatch(build):
        raise ValueError(f"invalid public page build: {build!r}")
    return page_name, build
