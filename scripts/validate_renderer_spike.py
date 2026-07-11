#!/usr/bin/env python3
"""Validate the bounded Commonworld renderer-engine spike and its non-commitment boundary."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "docs" / "research" / "renderer-engine-spike.result.json"
REPORT_PATH = ROOT / "docs" / "research" / "renderer-engine-spike.md"

CANDIDATES = ("maplibre_gl_js", "cesium_js", "three_js", "deck_gl")
PROFILES = ("desktop", "mobile_emulated")
BASE_COMMIT = "9d27231e774dd72e02a8a6f3ba1f515e8543d391"
EXPECTED_VERSIONS = {
    "maplibre_gl_js": "5.24.0",
    "cesium_js": "1.143.0",
    "three_js": "0.185.1",
    "deck_gl": "9.3.6",
}
EXPECTED_EVIDENCE_HASHES = {
    "archive_sha256": "70106b8f1f0f2ad253290482a03e564bca629ed9497ac1916308ef073fde7f04",
    "authoritative_results_sha256": "9123110eca19a227691478a7cb05a63f8b71a458f0c031afa5cafaa9087985c1",
    "color_vision_results_sha256": "90186f8eec7701435c2eb52424c4e077859b516cd3d6724906f7846890368fbe",
}
EXPECTED_SOURCE_URLS = {
    "maplibre_gl_js": "https://maplibre.org/maplibre-gl-js/docs/",
    "cesium_viewer": "https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html",
    "three_js": "https://threejs.org/docs/",
    "deck_gl_globe_view": "https://deck.gl/docs/api-reference/core/globe-view",
}
REQUIRED_CONDITIONS = {
    "prove assessed_partial_unassessed interior textures without channel collision",
    "prove approximate-location dashed boundary and uncertainty halo",
    "prove or falsify a digital outer sphere without duplicating catalog identity",
    "run physical mobile Safari and Chrome tests on hardware GPU",
    "prove idle pause, hidden-tab pause, reduced motion and state restoration",
    "prove keyboard and screen-reader parity with the linear view",
    "retest with realistic vector-tile aggregation rather than one in-memory GeoJSON set",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_result(root: Path = ROOT) -> dict[str, Any]:
    path = root / RESULT_PATH.relative_to(ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_positive(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def validate_renderer_spike(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT_PATH.relative_to(ROOT)
    report_path = root / REPORT_PATH.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing renderer spike result"]
    if not report_path.is_file():
        errors.append("missing renderer spike report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"renderer spike result is invalid JSON: {error}"]

    if result.get("schema_version") != 1:
        errors.append("renderer spike schema_version must be 1")
    if result.get("kind") != "commonworld_renderer_engine_spike":
        errors.append("renderer spike kind mismatch")
    if result.get("status") != "measured_recommendation_not_engine_commitment":
        errors.append("renderer spike must remain a measured recommendation, not an engine commitment")
    if result.get("measured_at") != "2026-07-11":
        errors.append("renderer spike measurement date mismatch")
    if result.get("repository_base_commit") != BASE_COMMIT:
        errors.append("renderer spike must remain bound to the measured base commit")

    bindings = result.get("contract_bindings", {})
    expected_bindings = {
        "commonproject_schema_version": 3,
        "aggregation_zoom_schema_version": 1,
        "visual_semantics_schema_version": 1,
    }
    if bindings != expected_bindings:
        errors.append("renderer spike must bind the current CommonProject, zoom and visual contracts")

    method = result.get("method", {})
    versions = method.get("candidate_versions", {})
    if versions != EXPECTED_VERSIONS:
        errors.append("renderer spike candidate versions must remain exactly bound")
    build = method.get("build", {})
    if build != {"bundler": "esbuild 0.25.6", "format": "esm", "target": "es2022", "minified": True, "gzip_measurement": True}:
        errors.append("renderer spike build method mismatch")
    if method.get("browser") != "Google Chrome stable headless" or method.get("webgl_renderer") != "ANGLE SwiftShader software WebGL":
        errors.append("renderer spike browser and software-WebGL environment must remain explicit")
    workload = method.get("workload", {})
    if workload.get("deterministic_seed") != 20260711:
        errors.append("renderer spike workload seed must be deterministic")
    if (workload.get("point_count"), workload.get("line_count"), workload.get("polygon_count")) != (5000, 200, 20):
        errors.append("renderer spike workload counts mismatch")
    if workload.get("measured_rotation_frames") != 120:
        errors.append("renderer spike must measure 120 rotation frames")
    if workload.get("same_generated_geographic_workload_for_all_candidates") is not True:
        errors.append("all renderer candidates must receive the same generated workload")

    profiles = method.get("profiles", {})
    if set(profiles) != set(PROFILES):
        errors.append("renderer spike must contain desktop and mobile-emulated profiles")
    shell = method.get("common_shell_proofs", {})
    if shell != {"keyboard_buttons": 4, "deep_link_query_parsed": True, "linear_fallback_items": 10, "canvas_accessible_name_present": True, "prefers_reduced_motion_observed": True}:
        errors.append("renderer spike common shell proofs mismatch")
    limitations = method.get("limitations", {})
    if limitations.get("physical_mobile_device_tested") is not False:
        errors.append("renderer spike must not claim a physical mobile test")
    if limitations.get("hardware_gpu_tested") is not False:
        errors.append("renderer spike must not claim a hardware GPU test")
    for name in (
        "software_webgl_results_are_relative_not_production_fps",
        "network_tiles_and_basemap_excluded",
        "semantic_hatching_and_uncertainty_halo_not_fully_implemented",
        "digital_outer_sphere_not_proven_in_maplibre",
        "screen_reader_end_to_end_not_tested",
        "state_restoration_end_to_end_not_tested",
        "idle_and_hidden_tab_pause_not_tested",
        "real_catalog_data_not_used",
        "no_public_spike_fixture",
    ):
        if limitations.get(name) is not True:
            errors.append(f"renderer spike limitation must remain explicit: {name}")

    measurements = result.get("measurements", {})
    if set(measurements) != set(CANDIDATES):
        errors.append("renderer spike measurement candidate set mismatch")
    for candidate in CANDIDATES:
        entry = measurements.get(candidate, {})
        for name in ("bundle_js_bytes", "bundle_gzip_bytes"):
            if not isinstance(entry.get(name), int) or entry[name] <= 0:
                errors.append(f"{candidate} must have a positive {name}")
        if not isinstance(entry.get("extra_static_assets_bytes"), int) or entry["extra_static_assets_bytes"] < 0:
            errors.append(f"{candidate} must have a non-negative extra_static_assets_bytes")
        if entry.get("fatal_runtime_errors") != 0:
            errors.append(f"{candidate} must not retain fatal runtime errors")
        for profile in PROFILES:
            metrics = entry.get(profile, {})
            for name in ("mean_frame_ms", "p95_frame_ms", "fps", "heap_used_bytes"):
                if not _finite_positive(metrics.get(name)):
                    errors.append(f"{candidate} {profile} must have a positive finite {name}")
            if _finite_positive(metrics.get("p95_frame_ms")) and _finite_positive(metrics.get("mean_frame_ms")):
                if metrics["p95_frame_ms"] < metrics["mean_frame_ms"]:
                    errors.append(f"{candidate} {profile} p95 must not be below mean frame time")

    for profile in PROFILES:
        maplibre_fps = measurements.get("maplibre_gl_js", {}).get(profile, {}).get("fps", 0)
        competitors = [measurements.get(name, {}).get(profile, {}).get("fps", 0) for name in CANDIDATES[1:]]
        if not competitors or maplibre_fps <= max(competitors):
            errors.append(f"MapLibre must remain the fastest measured candidate for {profile}")
    if measurements.get("three_js", {}).get("bundle_gzip_bytes", 10**18) >= measurements.get("maplibre_gl_js", {}).get("bundle_gzip_bytes", 0):
        errors.append("Three.js must remain the smaller measured bundle")
    if measurements.get("cesium_js", {}).get("bundle_gzip_bytes", 0) <= measurements.get("maplibre_gl_js", {}).get("bundle_gzip_bytes", 10**18):
        errors.append("Cesium must remain larger than MapLibre in the measured bundle")

    assessment = result.get("capability_assessment", {})
    if assessment.get("maplibre_gl_js", {}).get("current_disposition") != "conditional_primary_candidate":
        errors.append("MapLibre disposition must remain conditional")
    if assessment.get("three_js", {}).get("current_disposition") != "specialist_overlay_or_fallback_candidate":
        errors.append("Three.js must remain a specialist candidate")
    if assessment.get("cesium_js", {}).get("current_disposition") != "reject_for_current_phase_cost_and_workload_mismatch":
        errors.append("Cesium disposition mismatch")
    deck = assessment.get("deck_gl", {})
    if deck.get("globe_and_geographic_semantic_zoom") != "documented_experimental_and_limited":
        errors.append("deck.gl GlobeView limitations must remain explicit")
    if deck.get("current_disposition") != "reject_as_primary_until_globe_contract_matures":
        errors.append("deck.gl disposition mismatch")

    color = result.get("color_vision_check", {})
    if color.get("distance_metric") != "colorspacious perceptual deltaE via CAM02-UCS":
        errors.append("color-vision distance metric must remain explicit")
    if color.get("conclusion") != "family_color_alone_is_not_reliable":
        errors.append("color-vision result must forbid color-only family meaning")
    if set(color.get("required_non_color_channels", [])) != {
        "family_glyph", "explicit_text_label", "geometry_or_list_context"
    }:
        errors.append("color-vision result must require glyph, text and context")
    if not _finite_positive(color.get("deutan_minimum_delta_e")) or color.get("deutan_minimum_delta_e") >= 5:
        errors.append("deutan simulation must retain the observed low color-only separation")

    recommendation = result.get("recommendation", {})
    if recommendation.get("engine_selected") is not False:
        errors.append("renderer spike must not select a production engine")
    if recommendation.get("primary_candidate") != "maplibre_gl_js":
        errors.append("MapLibre must remain the bounded next proof candidate")
    if recommendation.get("decision") != "advance_maplibre_to_bounded_phase2_globe_proof":
        errors.append("renderer spike decision must advance only a bounded MapLibre proof")
    if set(recommendation.get("conditions_before_engine_commitment", [])) != REQUIRED_CONDITIONS:
        errors.append("renderer commitment conditions are incomplete or changed")
    forbidden = set(recommendation.get("forbidden_interpretations", []))
    if "MapLibre is already the canonical production engine" not in forbidden:
        errors.append("renderer spike must explicitly forbid premature MapLibre commitment")

    evidence = result.get("evidence_artifacts", {})
    for name, expected in EXPECTED_EVIDENCE_HASHES.items():
        if evidence.get(name) != expected or not SHA256_RE.fullmatch(str(evidence.get(name, ""))):
            errors.append(f"renderer spike evidence hash invalid or changed: {name}")
    if evidence.get("repository_contains_raw_harness") is not False or evidence.get("repository_contains_screenshots") is not False:
        errors.append("raw harness and screenshots must stay outside the product repository")

    sources = result.get("official_sources", [])
    source_map = {source.get("id"): source for source in sources if isinstance(source, dict)}
    if set(source_map) != set(EXPECTED_SOURCE_URLS) or len(sources) != len(EXPECTED_SOURCE_URLS):
        errors.append("renderer spike must cite one official source per candidate")
    for source_id, expected_url in EXPECTED_SOURCE_URLS.items():
        source = source_map.get(source_id, {})
        if source.get("url") != expected_url:
            errors.append(f"official source URL mismatch: {source_id}")
        if source.get("checked_at") != "2026-07-11" or source.get("role") != "official_documentation":
            errors.append(f"official source binding mismatch: {source_id}")

    forbidden_repo_paths = (
        root / "package.json",
        root / "package-lock.json",
        root / "node_modules",
        root / "screenshots",
        root / "spikes",
    )
    for path in forbidden_repo_paths:
        if path.exists():
            errors.append(f"temporary renderer harness must not enter repository: {path.relative_to(root)}")

    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        for token in (
            "konditionaler Primärkandidat",
            "keine Engine-Festlegung",
            "physische Mobilgeräte",
            "Farbe allein darf keine Familie tragen",
        ):
            if token not in report:
                errors.append(f"renderer spike report missing boundary token: {token}")

    for public_file in ("index.html", "404.html"):
        path = root / public_file
        if path.is_file() and "renderer-engine-spike" in path.read_text(encoding="utf-8"):
            errors.append(f"renderer research must not leak into public surface: {public_file}")

    return errors


def main() -> int:
    errors = validate_renderer_spike(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld renderer engine spike validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
