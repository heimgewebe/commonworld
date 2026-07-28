#!/usr/bin/env python3
"""Validate provider-realistic cache coherence for every public Commonworld surface."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_page_release_manifest import (
    PUBLIC_PAGES,
    build_manifest,
    canonical_json,
    compute_release_id,
    snapshot_files,
)
from scripts.public_cache import asset_version, page_build_metadata, page_release_id

_MARKER_PATTERN = re.compile(r"<!-- commonworld-release-manifest:(\{[^\n]+\}) -->")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "assets/commonworld-page-builds.json"
    release_script = root / "assets/commonworld-release-check.js"
    not_found_path = root / "404.html"
    for path, message in (
        (manifest_path, "missing public release manifest"),
        (release_script, "missing browser release-check module"),
        (not_found_path, "missing custom release-probe 404 page"),
    ):
        if not path.is_file():
            errors.append(message)
    if errors:
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_manifest = build_manifest(root)
        computed_release = compute_release_id(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"invalid public release manifest: {error}")
        return errors
    if manifest != expected_manifest:
        errors.append("public release manifest does not match rendered pages")
    release_id = manifest.get("release_id", "")
    if release_id != computed_release:
        errors.append("public release identity does not match snapshot content")

    release_version = asset_version("assets/commonworld-release-check.js", root)
    release_tag = f'<script type="module" src="./assets/commonworld-release-check.js?v={release_version}"></script>'
    release_checked_pages = {"index.html", "de.html", "propose.html", "propose.de.html"}
    base_safe_skip_links = {
        "index.html": 'href="/#static-catalog-fallback"',
        "de.html": 'href="/de.html#static-catalog-fallback"',
        "propose.html": 'href="/propose.html#commons-proposal-form"',
        "propose.de.html": 'href="/propose.de.html#commons-proposal-form"',
    }
    for relative in PUBLIC_PAGES:
        page_path = root / relative
        try:
            page = page_path.read_text(encoding="utf-8")
            declared_page, build = page_build_metadata(page)
            declared_release = page_release_id(page)
        except (OSError, ValueError) as error:
            errors.append(f"invalid public page cache metadata for {relative}: {error}")
            continue
        if declared_page != relative or manifest.get("pages", {}).get(relative) != build:
            errors.append(f"public page build binding mismatch: {relative}")
        if declared_release != release_id:
            errors.append(f"public page release binding mismatch: {relative}")
        expected_base = f'<base href="/releases/{release_id}/" />'
        if page.count(expected_base) != 1:
            errors.append(f"public page release base mismatch: {relative}")
        if 'href="#' in page:
            errors.append(f"base-bound public page contains a fragment-only link: {relative}")
        expected_skip_link = base_safe_skip_links.get(relative)
        if expected_skip_link is not None and page.count(expected_skip_link) != 1:
            errors.append(f"public page base-safe skip link mismatch: {relative}")
        expected_release_count = 1 if relative in release_checked_pages else 0
        if page.count(release_tag) != expected_release_count:
            errors.append(
                f"public page release-check count mismatch: {relative} expected {expected_release_count}"
            )

    not_found = not_found_path.read_text(encoding="utf-8")
    markers = _MARKER_PATTERN.findall(not_found)
    if len(markers) != 1:
        errors.append("custom 404 must expose exactly one release manifest marker")
    else:
        try:
            marker_manifest = json.loads(markers[0])
        except json.JSONDecodeError as error:
            errors.append(f"custom 404 release marker is invalid JSON: {error}")
        else:
            if marker_manifest != manifest or markers[0] != canonical_json(manifest):
                errors.append("custom 404 release marker does not exactly match canonical manifest")
    if "<script" in not_found.lower():
        errors.append("custom release-probe 404 must remain script-free")

    releases_root = root / "releases"
    release_directories = sorted(path for path in releases_root.iterdir() if path.is_dir()) if releases_root.is_dir() else []
    if [path.name for path in release_directories] != [release_id]:
        errors.append("public build must retain exactly the current path-keyed release snapshot")
    else:
        snapshot_root = release_directories[0]
        for source in snapshot_files(root, include_manifest=True):
            relative = source.relative_to(root)
            target = snapshot_root / relative
            if not target.is_file():
                errors.append(f"release snapshot is missing public file: {relative.as_posix()}")
            elif target.read_bytes() != source.read_bytes():
                errors.append(f"release snapshot file differs from canonical public file: {relative.as_posix()}")

    release_source = release_script.read_text(encoding="utf-8")
    catalog_runtime_source = (root / "assets/commonworld-catalog-runtime.mjs").read_text(encoding="utf-8")
    for token in ("globalThis.document?.baseURI", "documentBase ?? locationHref", "new URL('./', pageUrl)"):
        if token not in catalog_runtime_source:
            errors.append(f"catalog runtime is not bound to the rendered release base URI: {token}")
    for token in ("/__cw_probe/", "commonworld-release-manifest:", "/releases/"):
        if token not in release_source:
            errors.append(f"release checker lacks provider-realistic path token: {token}")
    if "commonworld-page-builds.json?" in release_source or "searchParams.set(PROBE_PARAMETER" in release_source:
        errors.append("release checker must not rely on query strings as shared-cache keys")
    if "PROBE_TIMEOUT_MS = 3_000" not in release_source or "controller.abort()" not in release_source:
        errors.append("release checker must retain a hard bounded probe timeout")

    index = (root / "index.html").read_text(encoding="utf-8")
    for relative, token in (
        ("assets/commonworld-mark.svg", "./assets/commonworld-mark.svg"),
        ("assets/vendor/maplibre-gl.css", "./assets/vendor/maplibre-gl.css"),
        ("assets/vendor/maplibre-gl.js", "./assets/vendor/maplibre-gl.js"),
        ("index.css", "./index.css"),
        ("assets/ipad-layout.css", "./assets/ipad-layout.css"),
        ("assets/commonworld-app.js", "./assets/commonworld-app.js"),
    ):
        versioned = f'{token}?v={asset_version(relative, root)}'
        if versioned not in index:
            errors.append(f"index.html runtime asset lacks a content diagnostic tag: {relative}")

    proposal = (root / "propose.html").read_text(encoding="utf-8")
    for relative, token in (
        ("assets/commonworld-mark.svg", "./assets/commonworld-mark.svg"),
        ("index.css", "./index.css"),
        ("assets/proposal.css", "./assets/proposal.css"),
        ("assets/commonworld-proposal.js", "./assets/commonworld-proposal.js"),
    ):
        versioned = f'{token}?v={asset_version(relative, root)}'
        if versioned not in proposal:
            errors.append(f"propose.html runtime asset lacks a content diagnostic tag: {relative}")
    for token in (
        "commonworldProposalReleaseDraftV1",
        "RELEASE_DRAFT_MAX_AGE_MS",
        "commonworld:release-navigation",
    ):
        if token not in (root / "assets/commonworld-proposal.js").read_text(encoding="utf-8"):
            errors.append(f"proposal release-draft guard is incomplete: {token}")

    app = (root / "assets/commonworld-app.js").read_text(encoding="utf-8")
    for relative in (
        "assets/map/commonworld-country-boundaries.geojson",
        "assets/map/openfreemap-liberty.json",
    ):
        expected = f"./{relative}?v={asset_version(relative, root)}"
        if expected not in app:
            errors.append(f"application runtime URL lacks a content diagnostic tag: {relative}")
    if "cache: 'force-cache'" not in app:
        errors.append("release-snapshot country boundaries must retain efficient force-cache loading")

    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    build = package.get("scripts", {}).get("build", "")
    boundary_step = "node scripts/build_country_boundary_subset.mjs"
    render_step = "python3 scripts/render_public_shell.py"
    manifest_step = "python3 scripts/build_page_release_manifest.py"
    if boundary_step not in build or render_step not in build or build.index(boundary_step) >= build.index(render_step):
        errors.append("public build must generate country boundaries before snapshotting runtime URLs")
    if not build.endswith(manifest_step):
        errors.append("public build must finish by generating the path-keyed release snapshot")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld path-keyed browser cache coherence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
