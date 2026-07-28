#!/usr/bin/env python3
"""Validate browser cache coherence for every public Commonworld entry surface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_page_release_manifest import PUBLIC_PAGES, build_manifest
from scripts.public_cache import asset_version, page_build_metadata


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "assets/commonworld-page-builds.json"
    release_script = root / "assets/commonworld-release-check.js"
    if not manifest_path.is_file():
        errors.append("missing public page-build manifest")
        return errors
    if not release_script.is_file():
        errors.append("missing browser release-check module")
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_manifest = build_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"invalid public page-build manifest: {error}")
        return errors
    if manifest != expected_manifest:
        errors.append("public page-build manifest does not match rendered pages")

    release_version = asset_version("assets/commonworld-release-check.js", root)
    release_tag = f'<script type="module" src="./assets/commonworld-release-check.js?v={release_version}"></script>'
    release_checked_pages = {"index.html", "de.html", "propose.html", "propose.de.html"}
    for relative in PUBLIC_PAGES:
        page_path = root / relative
        try:
            declared_page, build = page_build_metadata(page_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"invalid public page cache metadata for {relative}: {error}")
            continue
        if declared_page != relative or manifest.get("pages", {}).get(relative) != build:
            errors.append(f"public page build binding mismatch: {relative}")
        page = page_path.read_text(encoding="utf-8")
        expected_release_count = 1 if relative in release_checked_pages else 0
        if page.count(release_tag) != expected_release_count:
            errors.append(
                f"public page release-check count mismatch: {relative} expected {expected_release_count}"
            )

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
            errors.append(f"index.html runtime asset is not content-versioned: {relative}")

    proposal = (root / "propose.html").read_text(encoding="utf-8")
    for relative, token in (
        ("assets/commonworld-mark.svg", "./assets/commonworld-mark.svg"),
        ("index.css", "./index.css"),
        ("assets/proposal.css", "./assets/proposal.css"),
        ("assets/commonworld-proposal.js", "./assets/commonworld-proposal.js"),
    ):
        versioned = f'{token}?v={asset_version(relative, root)}'
        if versioned not in proposal:
            errors.append(f"propose.html runtime asset is not content-versioned: {relative}")

    app = (root / "assets/commonworld-app.js").read_text(encoding="utf-8")
    for relative in (
        "assets/map/commonworld-country-boundaries.geojson",
        "assets/map/openfreemap-liberty.json",
    ):
        expected = f"./{relative}?v={asset_version(relative, root)}"
        if expected not in app:
            errors.append(f"application runtime URL is not content-versioned: {relative}")
    if "cache: 'force-cache'" not in app:
        errors.append("content-versioned country boundaries must retain efficient force-cache loading")

    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    build = package.get("scripts", {}).get("build", "")
    boundary_step = "node scripts/build_country_boundary_subset.mjs"
    render_step = "python3 scripts/render_public_shell.py"
    manifest_step = "python3 scripts/build_page_release_manifest.py"
    if boundary_step not in build or render_step not in build or build.index(boundary_step) >= build.index(render_step):
        errors.append("public build must generate country boundaries before versioning runtime URLs")
    if not build.endswith(manifest_step):
        errors.append("public build must finish by generating the page-build manifest")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld browser cache coherence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
