#!/usr/bin/env python3
"""Deterministic cache-coherence helpers for public Commonworld pages."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PAGE_BUILD_PLACEHOLDER = "0" * 16
RELEASE_ID_PLACEHOLDER = "0" * 20
PAGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,79}$")
PAGE_BUILD_PATTERN = re.compile(r"^[0-9a-f]{16}$")
RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{20}$")
_PAGE_META_PATTERN = re.compile(r'<meta name="commonworld-page" content="([^"]+)" />')
_BUILD_META_PATTERN = re.compile(r'<meta name="commonworld-page-build" content="([0-9a-f]{16})" />')
_RELEASE_META_PATTERN = re.compile(r'<meta name="commonworld-release" content="([0-9a-f]{20})" />')
_RELEASE_BASE_PATTERN = re.compile(r'<base href="/releases/([0-9a-f]{20})/" />')


def asset_version(relative_path: str, root: Path) -> str:
    """Return a compact deterministic content version for one public asset."""
    return hashlib.sha256((root / relative_path).read_bytes()).hexdigest()[:12]


def _single_match(pattern: re.Pattern[str], markup: str, label: str) -> str:
    matches = pattern.findall(markup)
    if len(matches) != 1:
        raise ValueError(f"public page must declare exactly one {label}")
    return matches[0]


def canonicalize_page_release(markup: str) -> str:
    """Normalize the self-referential release id while preserving all other bytes."""
    release = _single_match(_RELEASE_META_PATTERN, markup, "release identity")
    base_release = _single_match(_RELEASE_BASE_PATTERN, markup, "release base")
    if release != base_release:
        raise ValueError("public page release identity and base disagree")
    normalized = _RELEASE_META_PATTERN.sub(
        f'<meta name="commonworld-release" content="{RELEASE_ID_PLACEHOLDER}" />',
        markup,
        count=1,
    )
    return _RELEASE_BASE_PATTERN.sub(
        f'<base href="/releases/{RELEASE_ID_PLACEHOLDER}/" />',
        normalized,
        count=1,
    )


def compute_page_build(markup: str) -> str:
    """Recompute the page build from final HTML with self-references normalized."""
    _single_match(_BUILD_META_PATTERN, markup, "page build")
    normalized = _BUILD_META_PATTERN.sub(
        f'<meta name="commonworld-page-build" content="{PAGE_BUILD_PLACEHOLDER}" />',
        canonicalize_page_release(markup),
        count=1,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def stamp_page_build(markup: str, page_name: str) -> str:
    """Insert page/release metadata and bind the build to rendered bytes."""
    if not PAGE_NAME_PATTERN.fullmatch(page_name):
        raise ValueError(f"invalid public page name: {page_name!r}")
    if any(token in markup for token in ('<meta name="commonworld-page-build"', '<meta name="commonworld-page"', '<meta name="commonworld-release"', '<base ')):
        raise ValueError("public page cache metadata already present")
    charset = '    <meta charset="utf-8" />'
    if markup.count(charset) != 1:
        raise ValueError("public page must contain exactly one canonical charset marker")
    metadata = (
        f'{charset}\n'
        f'    <meta name="commonworld-page" content="{page_name}" />\n'
        f'    <meta name="commonworld-page-build" content="{PAGE_BUILD_PLACEHOLDER}" />\n'
        f'    <meta name="commonworld-release" content="{RELEASE_ID_PLACEHOLDER}" />\n'
        f'    <base href="/releases/{RELEASE_ID_PLACEHOLDER}/" />'
    )
    stamped = markup.replace(charset, metadata, 1)
    return stamped.replace(PAGE_BUILD_PLACEHOLDER, compute_page_build(stamped), 1)


def finalize_page_release(markup: str, release_id: str) -> str:
    """Bind a placeholder-stamped page to one deterministic release snapshot."""
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError(f"invalid public release id: {release_id!r}")
    if _single_match(_RELEASE_META_PATTERN, markup, "release identity") != RELEASE_ID_PLACEHOLDER:
        raise ValueError("public page release identity is already finalized")
    if _single_match(_RELEASE_BASE_PATTERN, markup, "release base") != RELEASE_ID_PLACEHOLDER:
        raise ValueError("public page release base is already finalized")
    finalized = _RELEASE_META_PATTERN.sub(
        f'<meta name="commonworld-release" content="{release_id}" />',
        markup,
        count=1,
    )
    return _RELEASE_BASE_PATTERN.sub(
        f'<base href="/releases/{release_id}/" />',
        finalized,
        count=1,
    )


def page_build_metadata(markup: str) -> tuple[str, str]:
    """Read and verify the exact page/build pair from rendered markup."""
    page_name = _single_match(_PAGE_META_PATTERN, markup, "page identity")
    build = _single_match(_BUILD_META_PATTERN, markup, "page build")
    if not PAGE_NAME_PATTERN.fullmatch(page_name):
        raise ValueError(f"invalid public page identity: {page_name!r}")
    if not PAGE_BUILD_PATTERN.fullmatch(build):
        raise ValueError(f"invalid public page build: {build!r}")
    if compute_page_build(markup) != build:
        raise ValueError("public page build does not match final HTML bytes")
    return page_name, build


def page_release_id(markup: str) -> str:
    """Read and verify the release identity shared by metadata and the base URL."""
    release = _single_match(_RELEASE_META_PATTERN, markup, "release identity")
    base_release = _single_match(_RELEASE_BASE_PATTERN, markup, "release base")
    if release != base_release or not RELEASE_ID_PATTERN.fullmatch(release):
        raise ValueError("invalid public page release binding")
    return release
