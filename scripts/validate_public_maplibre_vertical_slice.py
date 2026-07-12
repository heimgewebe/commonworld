#!/usr/bin/env python3
"""Validate the public MapLibre globe vertical slice and its release boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_public_shell import render_shell

CONTRACT_PATH = Path("contracts/commonworld/public-maplibre-vertical-slice.contract.json")
RESULT_PATH = Path("docs/research/public-maplibre-vertical-slice-v1.result.json")
REPORT_PATH = Path("docs/research/public-maplibre-vertical-slice-v1.md")
REQUIRED_FILES = (
    CONTRACT_PATH,
    RESULT_PATH,
    REPORT_PATH,
    Path("package.json"),
    Path("package-lock.json"),
    Path("assets/vendor/maplibre-gl.js"),
    Path("assets/vendor/maplibre-gl.css"),
    Path("assets/vendor/MAPLIBRE-NOTICE.txt"),
    Path("assets/vendor/MAPLIBRE-LICENSE.txt"),
    Path("assets/map/openfreemap-liberty.json"),
    Path("assets/commonworld-core.mjs"),
    Path("assets/commonworld-app.js"),
    Path("catalog/catalog.json"),
    Path("index.html"),
    Path("index.css"),
)
EXPECTED_IDS = [
    "debian",
    "freifunk",
    "libreoffice",
    "mastodon",
    "openstreetmap",
    "wikibooks",
    "wikidata",
    "wikimedia-commons",
    "wikipedia",
    "wikiversity",
]
EXPECTED_VENDOR_HASHES = {
    "assets/vendor/maplibre-gl.js": "45a9b07a9189ce56054c620a947ccf41e291e58c95e9b61533b740aaa65ee5cb",
    "assets/vendor/maplibre-gl.css": "ab1e70d59ec40465bae7e7030da2f3ccf28133fd502e62bd598eefbadfd7a732",
}
EXPECTED_STYLE_HASH = "74a4e3f2eacd4242dd2235b50ab6e14d0285e5e3bde07de2753949ec7f776a18"
ALLOWED_MAP_ORIGIN = "https://tiles.openfreemap.org"
FORBIDDEN_RUNTIME_TOKENS = (
    "unpkg.com",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "three.js",
    "three.min.js",
    "google-analytics",
    "googletagmanager",
    "segment.io",
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _urls(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            found.extend(_urls(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_urls(child))
    elif isinstance(value, str):
        found.extend(re.findall(r"https://[^\s\"'<>]+", value))
    return found


def _catalog_records(root: Path, manifest: dict) -> list[dict]:
    records: list[dict] = []
    for relative in manifest.get("project_files", []):
        if not isinstance(relative, str) or not relative.startswith("projects/") or ".." in relative:
            continue
        path = root / "catalog" / relative
        if path.is_file():
            value = _load(path)
            if isinstance(value, dict):
                records.append(value)
    return records


def validate_public_maplibre_vertical_slice(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing public MapLibre vertical-slice file: {relative}")
    if errors:
        return errors

    try:
        contract = _load(root / CONTRACT_PATH)
        result = _load(root / RESULT_PATH)
        package = _load(root / "package.json")
        lock = _load(root / "package-lock.json")
        style = _load(root / "assets/map/openfreemap-liberty.json")
        manifest = _load(root / "catalog/catalog.json")
    except (OSError, json.JSONDecodeError) as error:
        return [f"public MapLibre vertical-slice JSON is invalid: {error}"]
    objects = {"contract": contract, "result": result, "package": package, "lock": lock, "style": style, "manifest": manifest}
    if any(not isinstance(value, dict) for value in objects.values()):
        return ["public MapLibre vertical-slice control files must contain JSON objects"]

    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_public_maplibre_vertical_slice_contract":
        errors.append("public MapLibre contract schema or kind mismatch")
    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_public_maplibre_vertical_slice_result":
        errors.append("public MapLibre result schema or kind mismatch")
    if result.get("verdict") != "IMPLEMENTED_AWAITING_PHYSICAL_ANDROID_GATE":
        errors.append("public MapLibre result must retain the physical Android blocker")
    bindings = result.get("evidence_bindings") if isinstance(result.get("evidence_bindings"), list) else []
    for binding in bindings:
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            errors.append("public MapLibre result contains malformed evidence binding")
            continue
        path = root / binding["path"]
        if not path.is_file() or _sha256(path) != binding.get("sha256"):
            errors.append(f"public MapLibre result evidence hash mismatch: {binding.get('path')}")
    browser = result.get("browser_proof", {}) if isinstance(result.get("browser_proof"), dict) else {}
    assertions = browser.get("assertions", {}) if isinstance(browser.get("assertions"), dict) else {}
    if (
        browser.get("verdict") != "PASS"
        or assertions.get("idle_map_render_delta") != 0
        or assertions.get("idle_overlay_render_delta") != 0
        or assertions.get("focus_returned_after_close") is not True
    ):
        errors.append("public MapLibre browser proof result mismatch")
    standard_motion = browser.get("standard_motion", {}) if isinstance(browser.get("standard_motion"), dict) else {}
    if standard_motion.get("verdict") != "PASS" or standard_motion.get("close_camera_command") != "easeTo" or standard_motion.get("open_camera_command") != "easeTo" or standard_motion.get("duration_ms") != 260 or standard_motion.get("focus_returned_after_close") is not True:
        errors.append("public MapLibre standard-motion browser proof mismatch")
    if result.get("release_gates", {}).get("physical_android_chrome") != "REQUIRED_BEFORE_MERGE":
        errors.append("public MapLibre result must retain physical Android as a pre-merge gate")
    renderer = contract.get("renderer", {}) if isinstance(contract.get("renderer"), dict) else {}
    if renderer.get("engine") != "maplibre_gl_js" or renderer.get("package") != "maplibre-gl" or renderer.get("version") != "5.24.0":
        errors.append("public runtime must use exactly MapLibre GL JS 5.24.0")
    for flag in ("exact_dependency_required", "floating_cdn_forbidden", "one_primary_globe_canvas"):
        if renderer.get(flag) is not True:
            errors.append(f"public renderer contract must retain true: {flag}")
    for flag in ("three_js_runtime_authorized", "second_independent_globe_authorized"):
        if renderer.get(flag) is not False:
            errors.append(f"public renderer contract must retain false: {flag}")

    dependencies = package.get("dependencies")
    if dependencies != {"maplibre-gl": "5.24.0"}:
        errors.append("package.json must contain only the exactly pinned maplibre-gl 5.24.0 runtime dependency")
    packages = lock.get("packages", {}) if isinstance(lock.get("packages"), dict) else {}
    root_lock = packages.get("", {}) if isinstance(packages.get(""), dict) else {}
    maplibre_lock = packages.get("node_modules/maplibre-gl", {}) if isinstance(packages.get("node_modules/maplibre-gl"), dict) else {}
    if lock.get("lockfileVersion") != 3:
        errors.append("package-lock.json must use lockfileVersion 3")
    if root_lock.get("dependencies") != {"maplibre-gl": "5.24.0"} or maplibre_lock.get("version") != "5.24.0":
        errors.append("package-lock.json must resolve maplibre-gl exactly to 5.24.0")

    asset_contract = {
        item.get("path"): item.get("sha256")
        for item in renderer.get("local_browser_assets", [])
        if isinstance(item, dict)
    }
    if asset_contract != EXPECTED_VENDOR_HASHES:
        errors.append("public renderer asset hash contract mismatch")
    for relative, digest in EXPECTED_VENDOR_HASHES.items():
        if _sha256(root / relative) != digest:
            errors.append(f"vendored MapLibre asset hash mismatch: {relative}")
    notice = (root / "assets/vendor/MAPLIBRE-NOTICE.txt").read_text(encoding="utf-8")
    for token in ("MapLibre GL JS 5.24.0", "BSD-3-Clause", "maplibre-gl@5.24.0"):
        if token not in notice:
            errors.append(f"MapLibre notice missing token: {token}")
    license_path = root / "assets/vendor/MAPLIBRE-LICENSE.txt"
    expected_license_sha256 = "ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2"
    if _sha256(license_path) != expected_license_sha256:
        errors.append("MapLibre verbatim license hash mismatch")
    if renderer.get("license_file") != {
        "path": "assets/vendor/MAPLIBRE-LICENSE.txt",
        "sha256": expected_license_sha256,
        "copied_verbatim_from": "node_modules/maplibre-gl/LICENSE.txt",
    }:
        errors.append("MapLibre license-file contract mismatch")

    basemap = contract.get("basemap", {}) if isinstance(contract.get("basemap"), dict) else {}
    if basemap.get("style_snapshot_sha256") != EXPECTED_STYLE_HASH or _sha256(root / "assets/map/openfreemap-liberty.json") != EXPECTED_STYLE_HASH:
        errors.append("OpenFreeMap style snapshot hash mismatch")
    if basemap.get("allowed_runtime_origin") != ALLOWED_MAP_ORIGIN:
        errors.append("basemap runtime origin contract mismatch")
    if basemap.get("service_level_agreement_claimed") is not False or basemap.get("production_provider_commitment") is not False:
        errors.append("OpenFreeMap public instance must not be represented as a production SLA commitment")
    if set(basemap.get("attribution_required", [])) != {"OpenFreeMap", "OpenMapTiles", "OpenStreetMap"}:
        errors.append("basemap attribution contract is incomplete")
    style_urls = _urls(style)
    for url in style_urls:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin != ALLOWED_MAP_ORIGIN and url not in {
            "https://openfreemap.org/",
            "https://openmaptiles.org/",
            "https://www.openstreetmap.org/copyright",
        }:
            errors.append(f"map style contains an unapproved external URL: {url}")
    style_text = json.dumps(style, ensure_ascii=False)
    for token in ("OpenFreeMap", "OpenMapTiles", "OpenStreetMap"):
        if token not in style_text:
            errors.append(f"map style missing required attribution: {token}")

    publication = manifest.get("publication", {}) if isinstance(manifest.get("publication"), dict) else {}
    expected_publication = {
        "public": True,
        "source_policy": "official-sources-only",
        "curation_state": "listed",
        "engine_selected": True,
        "production_architecture_authorized": False,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
    }
    if publication != expected_publication:
        errors.append("public catalog runtime publication boundary mismatch")
    records = _catalog_records(root, manifest)
    identifiers = [record.get("id") for record in records]
    if identifiers != EXPECTED_IDS or contract.get("catalog", {}).get("commonproject_ids") != EXPECTED_IDS:
        errors.append("public MapLibre runtime must use exactly the ten canonical catalog identities")
    if len(records) != 10 or manifest.get("entry_count") != 10:
        errors.append("public MapLibre runtime requires exactly ten catalog records")
    for record in records:
        identifier = record.get("id")
        if record.get("kind") != "digital":
            errors.append(f"vertical-slice catalog record must remain digital: {identifier}")
        presence = record.get("presence", {}) if isinstance(record.get("presence"), dict) else {}
        if presence.get("geographic") != []:
            errors.append(f"vertical-slice catalog record must not contain geographic coordinates: {identifier}")
        if any(key in record for key in ("layer", "derived_layer", "presentation_layer")):
            errors.append(f"vertical-slice catalog record must not store presentation-layer truth: {identifier}")

    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "index.css").read_text(encoding="utf-8")
    app = (root / "assets/commonworld-app.js").read_text(encoding="utf-8")
    core = (root / "assets/commonworld-core.mjs").read_text(encoding="utf-8")
    combined = "\n".join((html, css, app, core)).casefold()
    for token in FORBIDDEN_RUNTIME_TOKENS:
        if token.casefold() in combined:
            errors.append(f"public runtime contains forbidden dependency or telemetry token: {token}")
    for identifier in EXPECTED_IDS:
        if identifier in app or identifier in core:
            errors.append(f"public runtime code hardcodes catalog identity instead of loading it: {identifier}")
    if "sphereStartOffset(layerIndex, recordIndex, records.length)" not in app:
        errors.append("public runtime must use the tested bounded digital-sphere offset helper")

    required_html = (
        '<script src="./assets/vendor/maplibre-gl.js" defer></script>',
        '<script type="module" src="./assets/commonworld-app.js"></script>',
        'href="./assets/vendor/maplibre-gl.css"',
        'id="map"',
        'id="digital-sphere"',
        'id="sphere-edge-control"',
        'id="layer-panel"',
        'id="project-focus"',
        'href="#catalog"',
        "Der erste interaktive Globus ist gebaut.",
        "OpenFreeMap liefert die Basiskarte",
    )
    for token in required_html:
        if token not in html:
            errors.append(f"public runtime shell missing token: {token}")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        errors.append("public runtime must not contain inline scripts")
    if re.search(r"\sstyle=", html, re.IGNORECASE):
        errors.append("public runtime must not contain inline style attributes")
    for match in re.findall(r"<(?:script|link)[^>]+(?:src|href)=\"(https?://[^\"]+)\"", html, re.IGNORECASE):
        errors.append(f"public runtime must not load script or stylesheet from a CDN: {match}")

    csp_match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    if not csp_match:
        errors.append("public runtime must declare a Content Security Policy")
    else:
        csp = csp_match.group(1)
        for token in (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "connect-src 'self' https://tiles.openfreemap.org",
            "worker-src 'self' blob:",
            "object-src 'none'",
            "form-action 'none'",
        ):
            if token not in csp:
                errors.append(f"public runtime CSP missing token: {token}")
        if "'unsafe-inline'" in csp or "'unsafe-eval'" in csp:
            errors.append("public runtime CSP must not authorize unsafe inline code or eval")

    required_app = (
        "./catalog/catalog.json",
        "new window.maplibregl.Map",
        "setProjection({ type: 'globe' })",
        "runtime.map.easeTo",
        "runtime.map.jumpTo",
        "window.addEventListener('popstate'",
        "setTimeout(() => writeHistory('replace'), 180)",
        "presence?.geographic?.length",
        "overlayRenderCount += 1",
    )
    for token in required_app:
        if token not in app:
            errors.append(f"public runtime application missing contract token: {token}")
    for token in ("deriveLayer", "binaryFragment", "stateFromSearch", "searchFromState", "sphereOpacityForZoom"):
        if f"function {token}" not in core:
            errors.append(f"public runtime core missing function: {token}")
    if "requestAnimationFrame" in app or "setInterval" in app:
        errors.append("public runtime must not introduce a continuous animation loop")

    required_css = (
        ".digital-sphere",
        ".sphere-edge-control",
        ".layer-panel",
        ".project-focus",
        ".catalog-grid",
        "@media (prefers-reduced-motion: reduce)",
        ":focus-visible",
    )
    for token in required_css:
        if token not in css:
            errors.append(f"public runtime CSS missing token: {token}")

    try:
        rendered = render_shell(root)
    except Exception as error:  # fail closed for malformed catalog inputs
        errors.append(f"deterministic public shell render failed: {error}")
    else:
        if rendered != html:
            errors.append("index.html does not match the deterministic catalog-derived shell render")

    accessibility = contract.get("accessibility", {}) if isinstance(contract.get("accessibility"), dict) else {}
    if accessibility.get("focus_returns_to_trigger_or_linear_fallback_on_close") is not True:
        errors.append("public MapLibre focus-return accessibility contract mismatch")

    boundary = contract.get("decision_boundary", {}) if isinstance(contract.get("decision_boundary"), dict) else {}
    if boundary != {
        "engine_selected": True,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
        "production_architecture_authorized": False,
        "production_provider_selected": False,
        "screen_reader_product_support_claimed": False,
    }:
        errors.append("public MapLibre vertical-slice decision boundary mismatch")
    release_gates = contract.get("release_gates", {}) if isinstance(contract.get("release_gates"), dict) else {}
    if release_gates.get("physical_android_chrome") != "required_before_merge":
        errors.append("physical Android Chrome must remain a merge release gate")
    if release_gates.get("android_reduced_motion") != "not_claimed":
        errors.append("Android reduced-motion support must not be claimed")
    if release_gates.get("screen_reader_product_support") != "not_claimed":
        errors.append("screen-reader product support must not be claimed")

    return errors


def main() -> int:
    errors = validate_public_maplibre_vertical_slice(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld public MapLibre vertical-slice validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
