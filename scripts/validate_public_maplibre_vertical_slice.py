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
from scripts.validate_canonical_plan import validate_browser_smoke_contract

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
    Path("contracts/commonworld/digital-ring-taxonomy.contract.json"),
    Path("catalog/catalog.json"),
    Path("index.html"),
    Path("index.css"),
    Path("method.html"),
)
EXPECTED_SEED_IDS = [
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
EXPECTED_IDS = [
    "cltb-le-nid",
    "debian",
    "freifunk-hamburg",
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


# Bounded lexical scanner for named function declarations; this deliberately avoids
# a new JavaScript parser dependency while treating non-code delimiters as opaque.
_JAVASCRIPT_REGEX_PREFIX_KEYWORDS = frozenset({
    "await",
    "case",
    "delete",
    "do",
    "else",
    "in",
    "instanceof",
    "new",
    "of",
    "return",
    "throw",
    "typeof",
    "void",
    "yield",
})


def _javascript_identifier_character(character: str) -> bool:
    return bool(character) and (character.isalnum() or character in "_$")


def _javascript_regex_literal_starts(source: str, index: int) -> bool:
    previous = index - 1
    while previous >= 0 and source[previous].isspace():
        previous -= 1
    if previous < 0:
        return True
    if source[previous] in "([{:;,=!?&|~<>":
        return True
    if _javascript_identifier_character(source[previous]):
        start = previous
        while start >= 0 and _javascript_identifier_character(source[start]):
            start -= 1
        keyword = source[start + 1:previous + 1]
        return keyword in _JAVASCRIPT_REGEX_PREFIX_KEYWORDS and (start < 0 or source[start] != ".")
    return False


def _javascript_quoted_end(source: str, index: int, quote: str) -> int:
    cursor = index + 1
    while cursor < len(source):
        if source[cursor] == "\\":
            cursor += 2
        elif source[cursor] == quote:
            return cursor + 1
        else:
            cursor += 1
    return len(source)


def _javascript_line_comment_end(source: str, index: int) -> int:
    newline = source.find("\n", index + 2)
    return len(source) if newline < 0 else newline + 1


def _javascript_block_comment_end(source: str, index: int) -> int:
    closing = source.find("*/", index + 2)
    return len(source) if closing < 0 else closing + 2


def _javascript_trivia_end(source: str, index: int) -> int:
    cursor = index
    while cursor < len(source):
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if source.startswith("//", cursor):
            cursor = _javascript_line_comment_end(source, cursor)
        elif source.startswith("/*", cursor):
            cursor = _javascript_block_comment_end(source, cursor)
        else:
            return cursor
    return cursor


def _javascript_regex_literal_end(source: str, index: int) -> int:
    cursor = index + 1
    in_character_class = False
    while cursor < len(source):
        character = source[cursor]
        if character == "\\":
            cursor += 2
            continue
        if character in "\r\n":
            return index + 1
        if character == "[":
            in_character_class = True
        elif character == "]":
            in_character_class = False
        elif character == "/" and not in_character_class:
            cursor += 1
            while cursor < len(source) and (source[cursor].isalpha() or source[cursor].isdigit()):
                cursor += 1
            return cursor
        cursor += 1
    return index + 1


def _javascript_template_expression_end(source: str, index: int) -> int:
    depth = 1
    cursor = index
    while cursor < len(source):
        skipped = _javascript_noncode_end(source, cursor)
        if skipped is not None:
            cursor = skipped
            continue
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
            if depth == 0:
                return cursor + 1
        cursor += 1
    return len(source)


def _javascript_template_end(source: str, index: int) -> int:
    cursor = index + 1
    while cursor < len(source):
        if source[cursor] == "\\":
            cursor += 2
        elif source[cursor] == "`":
            return cursor + 1
        elif source.startswith("${", cursor):
            cursor = _javascript_template_expression_end(source, cursor + 2)
        else:
            cursor += 1
    return len(source)


def _javascript_noncode_end(source: str, index: int) -> int | None:
    character = source[index]
    if character in ("'", '"'):
        return _javascript_quoted_end(source, index, character)
    if character == "`":
        return _javascript_template_end(source, index)
    if source.startswith("//", index):
        return _javascript_line_comment_end(source, index)
    if source.startswith("/*", index):
        return _javascript_block_comment_end(source, index)
    if character == "/" and _javascript_regex_literal_starts(source, index):
        return _javascript_regex_literal_end(source, index)
    return None


def _javascript_matching_delimiter(source: str, opening_index: int, opening: str, closing: str) -> int:
    depth = 0
    cursor = opening_index
    while cursor < len(source):
        skipped = _javascript_noncode_end(source, cursor)
        if skipped is not None:
            cursor = skipped
            continue
        if source[cursor] == opening:
            depth += 1
        elif source[cursor] == closing:
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return -1


def _javascript_function_start(source: str, name: str) -> tuple[int, int]:
    cursor = 0
    while cursor < len(source):
        skipped = _javascript_noncode_end(source, cursor)
        if skipped is not None:
            cursor = skipped
            continue
        if not source.startswith("function", cursor):
            cursor += 1
            continue
        before = source[cursor - 1] if cursor > 0 else ""
        after_index = cursor + len("function")
        after = source[after_index] if after_index < len(source) else ""
        if _javascript_identifier_character(before) or _javascript_identifier_character(after):
            cursor += 1
            continue
        name_start = _javascript_trivia_end(source, after_index)
        if not source.startswith(name, name_start):
            cursor += 1
            continue
        name_end = name_start + len(name)
        if name_end < len(source) and _javascript_identifier_character(source[name_end]):
            cursor += 1
            continue
        parameter_start = _javascript_trivia_end(source, name_end)
        if parameter_start < len(source) and source[parameter_start] == "(":
            return cursor, parameter_start
        cursor += 1
    return -1, -1


def _javascript_function_source(source: str, name: str) -> str:
    start, parameter_start = _javascript_function_start(source, name)
    if start < 0:
        return ""
    parameter_end = _javascript_matching_delimiter(source, parameter_start, "(", ")")
    if parameter_end < 0:
        return ""

    opening = _javascript_trivia_end(source, parameter_end + 1)
    if opening >= len(source) or source[opening] != "{":
        return ""
    closing = _javascript_matching_delimiter(source, opening, "{", "}")
    return "" if closing < 0 else source[start:closing + 1]


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


def _valid_position(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _valid_ring(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 4
        and all(_valid_position(position) for position in value)
        and value[0] == value[-1]
    )


def _publicly_mappable(record: dict) -> bool:
    presence = record.get("presence", {}) if isinstance(record.get("presence"), dict) else {}
    locations = presence.get("geographic", [])
    if not isinstance(locations, list):
        return False
    for location in locations:
        if not isinstance(location, dict) or location.get("mode") == "hidden":
            continue
        geometry = location.get("geometry")
        if not isinstance(geometry, dict):
            continue
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        valid_geometry = (
            (geometry_type == "Point" and _valid_position(coordinates))
            or (geometry_type == "Polygon" and isinstance(coordinates, list) and bool(coordinates) and all(_valid_ring(ring) for ring in coordinates))
            or (
                geometry_type == "MultiPolygon"
                and isinstance(coordinates, list)
                and bool(coordinates)
                and all(isinstance(polygon, list) and bool(polygon) and all(_valid_ring(ring) for ring in polygon) for polygon in coordinates)
            )
        )
        if not valid_geometry:
            continue
        if location.get("mode") == "approximate":
            uncertainty = location.get("uncertainty_meters_min")
            if geometry_type != "Point" or not isinstance(uncertainty, (int, float)) or isinstance(uncertainty, bool) or uncertainty <= 0:
                continue
        if location.get("mode") in {"exact", "approximate"}:
            return True
    return False


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
    expected_binding_paths = {
        "package.json",
        "package-lock.json",
        "assets/vendor/maplibre-gl.js",
        "assets/vendor/maplibre-gl.css",
        "assets/vendor/MAPLIBRE-LICENSE.txt",
        "assets/map/openfreemap-liberty.json",
        "assets/commonworld-core.mjs",
        "assets/commonworld-app.js",
        "assets/commonworld-mark.svg",
        "index.html",
        "index.css",
        "catalog/catalog.json",
        "contracts/commonworld/public-maplibre-vertical-slice.contract.json",
        "docs/ops/machine-readable-surface.md",
        "scripts/render_public_shell.py",
        "scripts/validate_public_shell.py",
        "scripts/validate_public_catalog.py",
        "scripts/validate_public_maplibre_vertical_slice.py",
        "tests/js/commonworld-core.test.mjs",
    }
    binding_paths = {binding.get("path") for binding in bindings if isinstance(binding, dict)}
    if binding_paths != expected_binding_paths or len(bindings) != len(expected_binding_paths):
        errors.append("public MapLibre result evidence binding inventory mismatch")
    for binding in bindings:
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            errors.append("public MapLibre result contains malformed evidence binding")
            continue
        relative = binding["path"]
        digest = binding.get("sha256")
        if not (root / relative).is_file():
            errors.append(f"public MapLibre historical evidence path is missing: {relative}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"public MapLibre historical result contains invalid evidence hash: {relative}")
    # These bindings describe the immutable pre-merge evidence set. Current files are
    # validated below and by current-state.contract.json; later legitimate changes must
    # not be compared byte-for-byte with the historical snapshot.
    browser = result.get("browser_proof", {}) if isinstance(result.get("browser_proof"), dict) else {}
    assertions = browser.get("assertions", {}) if isinstance(browser.get("assertions"), dict) else {}
    expected_assertions = {
        "globe_first_root": True,
        "one_settings_gear": True,
        "shared_search_selection_and_focus": True,
        "visible_focus_return_after_surface_switch": True,
        "full_text_surface_scrollable": True,
        "no_javascript_catalog_scrollable": True,
        "sphere_center_matches_maplibre_projection": True,
        "side_sphere_fits_free_region": True,
        "six_layer_side_visual": True,
        "responsive_wide_right_padding": True,
        "responsive_narrow_bottom_padding": True,
        "reduced_motion_jump_to_zero_ms": True,
        "idle_map_render_delta_max": 0,
        "idle_overlay_render_delta_max": 0,
        "unexpected_resource_origins": 0,
        "uncaught_exceptions": 0,
        "console_errors": 0,
    }
    if browser.get("verdict") != "PASS" or assertions != expected_assertions:
        errors.append("public MapLibre globe-first browser proof result mismatch")
    scenarios = browser.get("scenarios") if isinstance(browser.get("scenarios"), list) else []
    if [item.get("id") for item in scenarios if isinstance(item, dict)] != ["desktop", "ipad", "mobile"]:
        errors.append("public MapLibre browser scenario inventory mismatch")
    for item in scenarios:
        if not isinstance(item, dict):
            errors.append("public MapLibre browser scenario is malformed")
            continue
        initial = item.get("initial_sphere", {}) if isinstance(item.get("initial_sphere"), dict) else {}
        side = item.get("side_sphere", {}) if isinstance(item.get("side_sphere"), dict) else {}
        if (
            item.get("verdict") != "PASS"
            or item.get("layer_stack_items") != 6
            or item.get("layer_stack_opacity") != 1
            or item.get("visible_text_cards_after_search") != 1
            or item.get("selected_project_after_roundtrip") != "debian"
            or item.get("project_cleared_after_focus_close") is not True
            or item.get("focus_return_target_after_close") != "globe-reset"
            or item.get("full_text_card_count") != 10
            or item.get("text_scroll_after", 0) <= item.get("text_scroll_before", 0)
            or item.get("text_scroll_height", 0) <= item.get("text_client_height", 0)
            or item.get("idle_map_render_delta") != 0
            or item.get("idle_overlay_render_delta") != 0
            or item.get("page_error_count") != 0
            or item.get("console_error_count") != 0
            or item.get("open_camera_command") != "easeTo"
            or item.get("close_camera_command") != "easeTo"
            or item.get("camera_duration_ms") != 260
            or initial.get("x") != initial.get("projected_x")
            or initial.get("y") != initial.get("projected_y")
            or side.get("x") != side.get("projected_x")
            or side.get("y") != side.get("projected_y")
            or not isinstance(initial.get("size"), (int, float))
            or not isinstance(side.get("size"), (int, float))
            or side.get("size") >= initial.get("size")
        ):
            errors.append(f"public MapLibre browser scenario mismatch: {item.get('id')}")
    reduced = browser.get("reduced_motion", {}) if isinstance(browser.get("reduced_motion"), dict) else {}
    if reduced != {"command": "jumpTo", "duration_ms": 0, "verdict": "PASS"}:
        errors.append("public MapLibre reduced-motion browser proof mismatch")
    no_javascript = browser.get("no_javascript", {}) if isinstance(browser.get("no_javascript"), dict) else {}
    no_js_scroll = no_javascript.get("scroll", {}) if isinstance(no_javascript.get("scroll"), dict) else {}
    if (
        no_javascript.get("verdict") != "PASS"
        or no_javascript.get("card_count") != 10
        or no_js_scroll.get("after", 0) <= no_js_scroll.get("before", 0)
        or no_js_scroll.get("scrollHeight", 0) <= no_js_scroll.get("clientHeight", 0)
    ):
        errors.append("public no-JavaScript catalog browser proof mismatch")
    if result.get("release_gates", {}).get("physical_android_chrome_current_globe_first_surface") != "REQUIRED_BEFORE_MERGE":
        errors.append("public Globe-first result must retain current physical Android as a pre-merge gate")
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
    if package.get("devDependencies") != {"playwright": "1.61.1"}:
        errors.append("package.json must pin the browser-gate Playwright dependency exactly")
    errors.extend(validate_browser_smoke_contract(root, package))
    packages = lock.get("packages", {}) if isinstance(lock.get("packages"), dict) else {}
    root_lock = packages.get("", {}) if isinstance(packages.get(""), dict) else {}
    maplibre_lock = packages.get("node_modules/maplibre-gl", {}) if isinstance(packages.get("node_modules/maplibre-gl"), dict) else {}
    if lock.get("lockfileVersion") != 3:
        errors.append("package-lock.json must use lockfileVersion 3")
    if root_lock.get("dependencies") != {"maplibre-gl": "5.24.0"} or maplibre_lock.get("version") != "5.24.0":
        errors.append("package-lock.json must resolve maplibre-gl exactly to 5.24.0")
    playwright_lock = packages.get("node_modules/playwright", {}) if isinstance(packages.get("node_modules/playwright"), dict) else {}
    if root_lock.get("devDependencies") != {"playwright": "1.61.1"} or playwright_lock.get("version") != "1.61.1":
        errors.append("package-lock.json must resolve Playwright exactly to 1.61.1")

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
    expected_runtime_publication = {
        "public": True,
        "source_policy": "official-and-public-registry-sources",
        "curation_state": "listed",
        "engine_selected": True,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
    }
    if any(publication.get(key) != expected for key, expected in expected_runtime_publication.items()):
        errors.append("public catalog runtime publication boundary mismatch")
    expected_machine_surface = {
        "access": "static_read_only",
        "manifest": "catalog/catalog.json",
        "project_base": "catalog/projects/",
        "project_schema": "contracts/commonworld/project.schema.json",
        "identity_field": "CommonProject.id",
        "api_runtime": False,
        "write_path": False,
        "standalone_cli": False,
    }
    if manifest.get("machine_surface") != expected_machine_surface:
        errors.append("public catalog machine-readable surface boundary mismatch")
    records = _catalog_records(root, manifest)
    identifiers = [record.get("id") for record in records]
    catalog_contract = contract.get("catalog", {}) if isinstance(contract.get("catalog"), dict) else {}
    manifest_ids = [
        Path(relative).stem
        for relative in manifest.get("project_files", [])
        if isinstance(relative, str)
    ]
    if identifiers != manifest_ids or len(set(identifiers)) != len(identifiers):
        errors.append("public MapLibre runtime must load each manifest identity exactly once")
    if len(records) != manifest.get("entry_count"):
        errors.append("public MapLibre runtime record count must match the catalog manifest")
    if not set(EXPECTED_IDS).issubset(identifiers):
        errors.append("public MapLibre runtime lost a reviewed vertical-slice identity")
    records_by_id = {record.get("id"): record for record in records if isinstance(record.get("id"), str)}
    baseline = manifest.get("seed_baseline", {}) if isinstance(manifest.get("seed_baseline"), dict) else {}
    if baseline.get("project_ids") != EXPECTED_SEED_IDS or catalog_contract.get("seed_baseline_ids") != EXPECTED_SEED_IDS:
        errors.append("public MapLibre runtime seed baseline identity mismatch")
    projection_coverage = {
        "globe_eligible_identities": 0,
        "digital_eligible_identities": 0,
        "cross_surface_identities": 0,
    }
    for record in records:
        globe_eligible = _publicly_mappable(record)
        digital_eligible = record.get("presence", {}).get("digital", {}).get("available") is True
        if globe_eligible:
            projection_coverage["globe_eligible_identities"] += 1
        if digital_eligible:
            projection_coverage["digital_eligible_identities"] += 1
        if globe_eligible and digital_eligible:
            projection_coverage["cross_surface_identities"] += 1
    minimum_projection_coverage = catalog_contract.get("minimum_projection_coverage", {})
    if any(projection_coverage[name] < minimum_projection_coverage.get(name, 0) for name in projection_coverage):
        errors.append("public MapLibre runtime no longer satisfies minimum projection coverage")
    for identifier in EXPECTED_SEED_IDS:
        record = records_by_id.get(identifier, {})
        presence = record.get("presence", {}) if isinstance(record.get("presence"), dict) else {}
        if presence.get("geographic") != []:
            errors.append(f"vertical-slice seed record must not contain geographic coordinates: {identifier}")
    for record in records:
        identifier = record.get("id")
        if any(key in record for key in ("layer", "derived_layer", "presentation_layer", "semantic_zoom", "digital_path")):
            errors.append(f"vertical-slice catalog record must not store presentation or semantic-zoom truth: {identifier}")

    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "index.css").read_text(encoding="utf-8")
    app = (root / "assets/commonworld-app.js").read_text(encoding="utf-8")
    core = (root / "assets/commonworld-core.mjs").read_text(encoding="utf-8")
    combined = "\n".join((html, css, app, core)).casefold()
    for token in FORBIDDEN_RUNTIME_TOKENS:
        if token.casefold() in combined:
            errors.append(f"public runtime contains forbidden dependency or telemetry token: {token}")
    for identifier in identifiers:
        if identifier in app or identifier in core:
            errors.append(f"public runtime code hardcodes catalog identity instead of loading it: {identifier}")
    for token in ("renderSphereRibbons(runtime.records);", "renderLayerDeck();", "ribbonRepeatCount(records.length, 10)"):
        if token not in app:
            errors.append(f"public runtime must use the tested text-ribbon lane architecture: {token}")
    for token in ("binaryName(record.title)", "sphere-ring-binary", "digital-ribbon-binary"):
        if token in app or token in css:
            errors.append(f"public text-ribbon surfaces must not render decorative binary text: {token}")
    for token in ("Binärcode", "Binärcodes"):
        if token in html:
            errors.append(f"public digital-sphere copy must not imply binary-code content: {token}")
    if re.search(r"cooperativeGestures\s*:\s*true", app):
        errors.append("public mobile globe must allow one-finger touch movement; cooperativeGestures may not be enabled")

    sphere_opacity = _javascript_function_source(app, "updateSphereOpacity")
    sphere_visuals = _javascript_function_source(app, "updateSphereVisuals")
    sphere_diagnostics = _javascript_function_source(app, "publishSphereDiagnostics")
    sphere_sampling = _javascript_function_source(app, "sampleSphereGeometry")
    if not all((sphere_opacity, sphere_visuals, sphere_diagnostics, sphere_sampling)):
        errors.append("public sphere performance functions must remain statically inspectable")

    diagnostic_dataset_read = re.compile(
        r"\belements\s*\.\s*(?:stage|sphere)\s*\.\s*dataset\s*"
        r"(?:\.\s*(?:globeDiameter|globeViewportRatio|sphereSize|sphereX|sphereY)\b"
        r"|\[\s*['\"](?:globeDiameter|globeViewportRatio|sphereSize|sphereX|sphereY)['\"]\s*\])"
    )
    if diagnostic_dataset_read.search(sphere_opacity):
        errors.append("sphere opacity must use runtime metrics instead of reading diagnostic DOM state")
    for property_name in ("--sphere-x", "--sphere-y", "--sphere-size"):
        duplicate_sphere_write = re.compile(
            rf"\bsetStylePropertyIfChanged\s*\(\s*elements\s*\.\s*sphere\s*,\s*['\"]{re.escape(property_name)}['\"]"
        )
        if duplicate_sphere_write.search(sphere_visuals):
            errors.append(f"sphere visual geometry must inherit {property_name} from the stage without duplicate writes")
    for property_name in ("x", "y", "diameter"):
        quantized_geometry = re.compile(
            rf"\bquantizeSpherePixel\s*\(\s*geometry\s*\.\s*{property_name}\s*\)"
        )
        expression = f"quantizeSpherePixel(geometry.{property_name})"
        if not quantized_geometry.search(sphere_visuals):
            errors.append(f"sphere visual hot path must quantize subpixel geometry: {expression}")
        if not quantized_geometry.search(sphere_diagnostics):
            errors.append(f"sphere diagnostics must publish quantized geometry: {expression}")
    if not re.search(
        r"\bquantizeSpherePixel\s*\(\s*geometry\s*\.\s*globeDiameter\s*\)",
        sphere_diagnostics,
    ):
        errors.append("sphere diagnostics must publish a quantized globe diameter")
    if not re.search(
        r"\bruntime\s*\.\s*sphereMetrics\s*\.\s*globeViewportRatio\s*=\s*globeViewportRatio\s*;?",
        sphere_opacity,
    ):
        errors.append("sphere opacity must refresh the full-precision runtime viewport ratio on every evaluation")
    if not re.search(
        r"\bNumber\s*\(\s*runtime\s*\.\s*sphereMetrics\s*\.\s*globeViewportRatio"
        r"\s*\.\s*toFixed\s*\(\s*4\s*\)\s*\)",
        sphere_diagnostics,
    ):
        errors.append("sphere diagnostics must read the runtime viewport ratio and round only during publication")
    if not re.search(r"\bsampledDiagnosticPublicationDue\s*\(", sphere_sampling):
        errors.append("sphere diagnostic cadence must use the tested admitted-sample helper")

    required_html = (
        '<script src="./assets/vendor/maplibre-gl.js" defer></script>',
        'href="./assets/vendor/maplibre-gl.css"',
        'id="map"',
        'id="semantic-level"',
        'id="semantic-summary"',
        'id="focus-locations"',
        'id="focus-relations"',
        'id="digital-sphere"',
        'id="sphere-edge-control"',
        'id="layer-panel"',
        'id="layer-breadcrumb"',
        'id="layer-current"',
        'id="layer-stack-visual"',
        'id="layer-track-deck"',
        'id="layer-search-toggle"',
        'id="project-focus"',
        'id="globe-surface"',
        'id="text-view"',
        'id="text-layer-breadcrumb"',
        'id="text-layer-current"',
        'id="settings-toggle"',
        'id="settings-panel"',
        'id="globe-results"',
        'role="region"',
        'id="commons-search"',
        'data-presentation-choice="globe"',
        'data-presentation-choice="text"',
        'href="./catalog/catalog.json"',
        'href="./contracts/commonworld/project.schema.json"',
        'href="./method.html"',
        'href="./contracts/commonworld/current-state.contract.json"',
    )
    for token in required_html:
        if token not in html:
            errors.append(f"public runtime shell missing token: {token}")
    expected_app_version = _sha256(root / "assets/commonworld-app.js")[:12]
    expected_css_version = _sha256(root / "index.css")[:12]
    expected_app_tag = f'<script type="module" src="./assets/commonworld-app.js?v={expected_app_version}"></script>'
    expected_css_tag = f'href="./index.css?v={expected_css_version}"'
    if expected_app_tag not in html:
        errors.append("public runtime shell must bind commonworld-app.js to its deterministic content hash")
    if expected_css_tag not in html:
        errors.append("public runtime shell must bind index.css to its deterministic content hash")
    if 'id="catalog-bootstrap"' in html:
        errors.append("public runtime shell must not expose catalog JSON as DOM text")
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
        "new window.maplibregl.Map",
        "setProjection({ type: 'globe' })",
        "runtime.map.easeTo",
        "runtime.map.jumpTo",
        "runtime.map.project(center)",
        "runtime.map.project([lng, lat])",
        "globeHorizonCoordinates(center)",
        "projectedGlobeCircle({ center: projectedCenter, horizon })",
        "runtime.map.getPadding()",
        "sphereLayout({",
        "setPresentation(",
        "filterRecords(",
        "buildDigitalPresentationTree(",
        "visibleDigitalNodes(",
        "setDigitalPath(",
        "normalizeDigitalPath(",
        "digitalPath",
        "window.addEventListener('popstate'",
        "setTimeout(() => writeHistory('replace'), 180)",
        "PUBLIC_MAP_SOURCE_ID",
        "publicMapFeatureCollection",
        "ensurePublicMapLayers",
        "semanticLocationLine",
        "overlayRenderCount += 1",
        "./commonworld-bootstrap-catalog.mjs",
        "bootstrapRecords()",
        "dataset.catalogDelivery = 'build-bound-bootstrap'",
        "verifyMapProvider",
        "degradeMap",
        "mapFailurePolicy",
        "LOCAL_FALLBACK_STYLE",
        "elements.skipLink.addEventListener('click'",
        "renderSphereRibbons(",
        "renderLayerDeck(",
        "overflowing",
    )
    for token in required_app:
        if token not in app:
            errors.append(f"public runtime application missing contract token: {token}")
    for token in ("deriveLayer", "validateDigitalTaxonomy", "deriveDigitalProjectPath", "buildDigitalPresentationTree", "visibleDigitalNodes", "normalizeDigitalPath", "binaryFragment", "binaryName", "ribbonRepeatCount", "stateFromSearch", "searchFromState", "filterRecords", "globeHorizonCoordinates", "projectedGlobeCircle", "sphereLayout", "sphereOpacityForGlobeRatio", "publicMapFeatureCollection", "evidencedRelations", "recordLocationSummaries", "recordPresentationLabel", "semanticLocationLine", "semanticZoomLevel"):
        if f"function {token}" not in core:
            errors.append(f"public runtime core missing function: {token}")
    if "setInterval" in app:
        errors.append("public runtime must not introduce an interval animation loop")
    animation_frame_calls = app.count("requestAnimationFrame")
    if animation_frame_calls > 5:
        errors.append("public runtime may use at most five one-shot animation frames for lane measurement, focus, staged reveal and pointer hit-test coalescing")
    for token in ("window.requestAnimationFrame(updateLaneOverflow)", "window.requestAnimationFrame(() =>"):
        if token not in app:
            errors.append(f"public runtime one-shot animation-frame contract missing token: {token}")
    if "zoom: runtime.map.getZoom()" in app:
        errors.append("public digital-sphere geometry must not use MapLibre zoom as a direct size input")
    if "sphereOpacityForZoom" in app or "sphereOpacityForZoom" in core:
        errors.append("public digital-sphere visibility must not use MapLibre zoom normalization")

    required_css = (
        ".topbar",
        ".globe-surface",
        ".digital-sphere",
        "--sphere-x",
        "--sphere-y",
        "--sphere-size",
        ".sphere-edge-control",
        ".sphere-ring-text",
        ".digital-breadcrumb",
        ".digital-current",
        ".layer-track-deck",
        ".digital-lane-scroll",
        "overflow-x: auto",
        "touch-action: pan-x",
        ".layer-panel",
        ".settings-panel",
        ".text-view",
        ".project-focus",
        ".catalog-grid",
        ".globe-results",
        ".method-page",
        ".maplibregl-ctrl-group button",
        "@media (max-width: 48rem)",
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

    surface = contract.get("surface", {}) if isinstance(contract.get("surface"), dict) else {}
    if surface != {
        "default": "globe",
        "root_globe_first": True,
        "full_viewport_globe": True,
        "marketing_intro_before_globe_forbidden": True,
        "single_settings_gear": True,
        "presentation_choices": ["globe", "text"],
        "same_catalog_filter_selection_and_focus_state": True,
        "text_surface_requires_webgl": False,
        "text_surface_independent_scroll_region": True,
        "no_javascript_catalog_overlay": True,
    }:
        errors.append("public globe-first surface contract mismatch")
    expected_catalog_contract = {
        "manifest": "catalog/catalog.json",
        "only_data_source": True,
        "entry_count_source": "manifest.entry_count",
        "commonproject_ids_source": "manifest.project_files[].CommonProject.id",
        "required_vertical_slice_ids": EXPECTED_IDS,
        "minimum_projection_coverage": {
            "globe_eligible_identities": 1,
            "digital_eligible_identities": 10,
            "cross_surface_identities": 1,
        },
        "seed_baseline_ids": EXPECTED_SEED_IDS,
        "fabricated_coordinates_forbidden": True,
        "hidden_locations_have_no_geometry": True,
        "geographic_commons_in_scope": True,
        "relations_require_known_commonproject_targets": True,
    }
    if contract.get("catalog") != expected_catalog_contract:
        errors.append("public MapLibre projection-coverage catalog contract mismatch")
    expected_geographic_surface = {
        "source_id": "commonworld-public-representations",
        "source_type": "derived_geojson",
        "identity_property": "project_id",
        "location_property": "location_id",
        "feature_count_source": "derived_public_geometry",
        "project_identity_count_source": "derived_public_geometry",
        "layers": [
            {"id": "commonworld-public-extents", "type": "fill", "minimum_zoom": 3.4, "representation_kind": "public_extent"},
            {"id": "commonworld-approximate-zones", "type": "fill", "minimum_zoom": 3.4, "representation_kind": "approximate_zone", "uncertainty_radius_source": "uncertainty_meters_min", "local_zoom_selectable": True},
            {"id": "commonworld-exact-anchors", "type": "circle", "minimum_zoom": 5.5, "representation_kind": "exact_anchor"},
        ],
        "hidden_locations_excluded": True,
        "search_filters_same_source": True,
        "map_click_selects_commonproject_id": True,
        "style_replacement_restores_layers": True,
        "semantic_zoom_levels": ["planet", "macroregion", "region", "local", "focus"],
        "semantic_zoom_catalog_assignment_forbidden": True,
        "location_line": True,
    }
    if contract.get("geographic_surface") != expected_geographic_surface:
        errors.append("public MapLibre geographic surface contract mismatch")
    digital_surface = contract.get("digital_sphere", {}) if isinstance(contract.get("digital_sphere"), dict) else {}
    for key, expected in {
        "taxonomy_contract": "contracts/commonworld/digital-ring-taxonomy.contract.json",
        "primary_path_membership": "derived_from_catalog_themes_and_public_digital_presence",
        "active_navigation_parameter": "digital_path",
        "presentation_hierarchy": "recursive_ring_bundle_tree",
        "overview_main_bundle_count": 5,
        "legacy_layer_count": 6,
        "geometry_anchor": "maplibre_projected_globe_horizon",
        "screen_fixed_center_forbidden": True,
        "side_view_keeps_overlay_attached": True,
    }.items():
        if digital_surface.get(key) != expected:
            errors.append(f"public digital-sphere synchrony contract mismatch: {key}")
    if digital_surface.get("geometry_inputs") != ["stage_bounds", "maplibre_center_projection", "maplibre_horizon_projection", "maplibre_padding"]:
        errors.append("public digital-sphere geometry inputs mismatch")
    if digital_surface.get("scale_fade") != {
        "overview_visible_through_globe_viewport_ratio": 1.05,
        "fade_until_globe_viewport_ratio": 2.1,
        "local_hidden_from_globe_viewport_ratio": 2.1,
    }:
        errors.append("public digital-sphere scale-fade contract mismatch")
    if digital_surface.get("geometry_acceptance_data_attributes") != [
        "data-map-projected-center-x",
        "data-map-projected-center-y",
        "data-sphere-x",
        "data-sphere-y",
        "data-sphere-size",
        "data-globe-diameter",
        "data-globe-geometry-source",
        "data-globe-viewport-ratio",
    ]:
        errors.append("public digital-sphere geometry acceptance attributes mismatch")
    if digital_surface.get("side_view_visual") != "hierarchical_ring_bundle_lanes_after_text_sphere_flight":
        errors.append("public digital-sphere side-layer visual mismatch")
    for key, expected in {
        "overview_ring_content": "commons_names_only",
        "progressive_disclosure": "current_node_direct_children_and_parent_breadcrumb_only",
        "parent_identity_sets_equal_child_union": True,
        "primary_child_identity_sets_disjoint": True,
        "side_view_identity_source": "same_CommonProject_records_not_same_DOM_elements",
        "multi_lane_horizontal_swipe": True,
        "single_lane_horizontal_swipe": True,
        "complete_rings_visible": False,
        "card_substitution": False,
        "search_and_filter_always_available": True,
        "geographic_only_records_excluded": True,
        "dual_presence_records_included": True,
    }.items():
        if digital_surface.get(key) != expected:
            errors.append(f"public digital-sphere close-up contract mismatch: {key}")
    navigation = contract.get("navigation", {}) if isinstance(contract.get("navigation"), dict) else {}
    if navigation.get("deep_link_parameters") != ["lng", "lat", "z", "b", "p", "view", "surface", "digital_path", "project", "q"]:
        errors.append("public globe/text deep-link parameters mismatch")
    if navigation.get("legacy_deep_link_parameters") != ["layer"]:
        errors.append("public globe/text legacy deep-link parameter mismatch")
    if navigation.get("search_and_digital_path_filter_shared_across_surfaces") is not True:
        errors.append("public globe/text discovery state must remain shared")
    if navigation.get("side_layer_standard_duration_ms") != 1080:
        errors.append("public side-layer camera duration mismatch")
    if navigation.get("side_layer_responsive_padding") != {"wide": "full_viewport_swipe_lanes", "narrow": "full_viewport_swipe_lanes"}:
        errors.append("public side-layer responsive padding contract mismatch")
    machine_surface = contract.get("machine_surface", {}) if isinstance(contract.get("machine_surface"), dict) else {}
    if machine_surface != {
        "access": "static_read_only",
        "manifest": "catalog/catalog.json",
        "project_base": "catalog/projects/",
        "schema": "contracts/commonworld/project.schema.json",
        "api_runtime": False,
        "write_path": False,
        "standalone_cli": False,
    }:
        errors.append("public machine-readable surface contract mismatch")
    accessibility = contract.get("accessibility", {}) if isinstance(contract.get("accessibility"), dict) else {}
    if accessibility.get("focus_returns_to_trigger_or_linear_fallback_on_close") is not True:
        errors.append("public MapLibre focus-return accessibility contract mismatch")

    boundary = contract.get("decision_boundary", {}) if isinstance(contract.get("decision_boundary"), dict) else {}
    if boundary != {
        "engine_selected": True,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
        "production_architecture_authorized": True,
        "production_provider_selected": True,
        "screen_reader_product_support_claimed": False,
    }:
        errors.append("public MapLibre vertical-slice decision boundary mismatch")
    release_gates = contract.get("release_gates", {}) if isinstance(contract.get("release_gates"), dict) else {}
    if release_gates.get("physical_android_chrome_previous_public_runtime") != "pass_operator_attestation":
        errors.append("previous public Android Chrome operator attestation must remain recorded")
    if release_gates.get("physical_android_chrome") != "pass_operator_attestation":
        errors.append("physical Android Chrome release evidence must remain passed")
    if release_gates.get("physical_android_chrome_current_globe_first_surface") != "pass_operator_attestation":
        errors.append("current Globe-first physical Android Chrome attestation must remain passed")
    if release_gates.get("github_required_check") != "pass":
        errors.append("current GitHub required check must remain passed")
    if release_gates.get("live_pages_smoke") != "pass":
        errors.append("current live Pages smoke must remain passed")
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
