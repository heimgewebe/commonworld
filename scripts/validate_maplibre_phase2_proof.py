#!/usr/bin/env python3
"""Validate the bounded MapLibre Phase-2 proof and its fail-closed limits."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/maplibre-phase2-globe-proof.result.json"
REPORT = ROOT / "docs/research/maplibre-phase2-globe-proof.md"
BASE_COMMIT = "314b06a04016e8f87a930e092ca77b6d0a33c6fb"
EXPECTED_VERSIONS = {
    "maplibre_gl_js": "5.24.0",
    "geojson_vt": "6.1.0",
    "vt_pbf": "4.3.0",
    "esbuild": "0.25.6",
    "puppeteer_core": "24.12.1",
}
EXPECTED_WORKLOAD = {
    "deterministic_seed": 20260711,
    "unique_identities": 5000,
    "geographic_representations": 4000,
    "digital_representations": 2000,
    "hybrid_identities": 1000,
    "approximate_zones": 235,
    "coverage_buckets": 24,
    "relations": 320,
    "linear_identity_items": 5000,
    "vector_tile_requests": 92,
    "vector_tile_bytes": 792403,
    "vector_tile_zooms": [1, 2, 3, 4, 5, 6],
}
EXPECTED_BUNDLE = {
    "js_bytes": 1055763,
    "js_gzip_bytes": 287358,
    "css_bytes": 69939,
    "css_gzip_bytes": 10054,
    "total_output_bytes": 1125702,
}
EXPECTED_GATE_STATUS = {
    "coverage_assessed_solid_density": "pass",
    "coverage_partial_broken_hatch": "pass",
    "coverage_unassessed_dot_grid": "pass",
    "approximate_location_boundary_and_halo": "pass",
    "realistic_vector_tile_path": "pass",
    "identity_deduplication": "pass",
    "maplibre_native_abstract_digital_sphere": "pass",
    "deep_link_state_restoration": "pass",
    "linear_identity_and_selection_parity": "pass",
    "keyboard_navigation": "pass",
    "accessibility_tree_structure": "pass",
    "reduced_motion_state_equivalence": "pass",
    "idle_render_pause": "pass",
    "browser_lifecycle_freeze": "pass_bounded_transition_frame",
    "visibility_handler_pause_and_resume": "pass_application_handler_only",
    "physical_mobile_safari": "blocked_no_connected_device",
    "physical_mobile_chrome": "blocked_no_connected_device",
    "hardware_gpu_performance": "blocked_not_measured",
    "real_screen_reader_session": "blocked_not_measured",
}
EXPECTED_HASHES = {
    "archive_sha256": "198b4f3d3e36074cfc9773374ac3403cf90ae6c705c29d36ed2ff7537898b22f",
    "authoritative_results_sha256": "ac574f124763c3c69a41fca656dcb09a6805d894f49224219aaee3d9b9eb9441",
    "normalized_result_sha256": "360139fb40dc5dceac8a3dbb94e6082121cffaa203051a2341944f1dcd54e25e",
    "image_integrity_sha256": "fa7ec48a166786f6a94ae4590e5846a4ffc9dcb9506f2e4f91a16adb208866fb",
    "manifest_sha256": "838c70a076f07499893068e34ac6d6862fc6cca71a2e045ba3434645e0a7a8ce",
}
EXPECTED_SOURCES = {
    "maplibre_custom_layer": "https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/",
    "maplibre_globe_custom_layer_example": "https://maplibre.org/maplibre-gl-js/docs/examples/add-a-simple-custom-layer-on-a-globe/",
    "maplibre_style_layers": "https://maplibre.org/maplibre-style-spec/layers/",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / RESULT.relative_to(ROOT)).read_text(encoding="utf-8"))


def _positive(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def validate_maplibre_phase2_proof(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing MapLibre Phase-2 result"]
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"MapLibre Phase-2 result is invalid JSON: {error}"]
    if not report_path.is_file():
        errors.append("missing MapLibre Phase-2 report")

    if result.get("schema_version") != 1:
        errors.append("MapLibre Phase-2 schema_version must be 1")
    if result.get("kind") != "commonworld_maplibre_phase2_globe_proof":
        errors.append("MapLibre Phase-2 kind mismatch")
    if result.get("status") != "local_gates_pass_physical_acceptance_blocked":
        errors.append("MapLibre Phase-2 status must retain physical acceptance block")
    if result.get("repository_base_commit") != BASE_COMMIT:
        errors.append("MapLibre Phase-2 result must remain bound to measured base")
    if result.get("versions") != EXPECTED_VERSIONS:
        errors.append("MapLibre Phase-2 versions must remain exactly bound")
    if result.get("workload") != EXPECTED_WORKLOAD:
        errors.append("MapLibre Phase-2 workload mismatch")
    if result.get("bundle") != EXPECTED_BUNDLE:
        errors.append("MapLibre Phase-2 bundle measurement mismatch")

    gates = result.get("gate_results", {})
    if set(gates) != set(EXPECTED_GATE_STATUS):
        errors.append("MapLibre Phase-2 gate inventory mismatch")
    for gate, expected in EXPECTED_GATE_STATUS.items():
        if gates.get(gate, {}).get("status") != expected:
            errors.append(f"MapLibre Phase-2 gate status mismatch: {gate}")

    assessed = gates.get("coverage_assessed_solid_density", {}).get("evidence", {})
    if assessed != {"rendered_features": 23, "layer": "coverage-assessed"}:
        errors.append("assessed coverage evidence mismatch")
    if gates.get("coverage_partial_broken_hatch", {}).get("evidence", {}).get("pattern") != "coverage-partial-hatch":
        errors.append("partial coverage hatch evidence missing")
    if gates.get("coverage_unassessed_dot_grid", {}).get("evidence", {}).get("pattern") != "coverage-unassessed-dots":
        errors.append("unassessed coverage dot-grid evidence missing")
    uncertainty = gates.get("approximate_location_boundary_and_halo", {}).get("evidence", {})
    if uncertainty.get("rendered_features") != 8:
        errors.append("uncertainty render count mismatch")
    if set(uncertainty.get("layers", [])) != {"uncertainty-halo", "uncertainty-boundary"}:
        errors.append("uncertainty halo and dashed boundary incomplete")
    if uncertainty.get("radius_source") != "uncertainty_meters_min":
        errors.append("uncertainty radius source mismatch")

    vector = gates.get("realistic_vector_tile_path", {}).get("evidence", {})
    if vector != {"source_type": "vector", "requests": 92, "bytes": 792403, "zooms": [1, 2, 3, 4, 5, 6]}:
        errors.append("vector tile evidence mismatch")
    identities = gates.get("identity_deduplication", {}).get("evidence", {})
    if identities != {
        "unique_identities": 5000,
        "geographic_representations": 4000,
        "digital_representations": 2000,
        "union_identities": 5000,
        "hybrid_identities": 1000,
    }:
        errors.append("geographic and digital channels must deduplicate to 5000 identities")

    digital = gates.get("maplibre_native_abstract_digital_sphere", {})
    if digital.get("boundary") != "custom_gl_clip_space_ephemeral_vectors_not_map_projection_or_catalog_coordinates":
        errors.append("native digital sphere boundary mismatch")
    if digital.get("evidence") != {
        "kind": "maplibre_custom_gl_abstract_sphere",
        "pointCount": 2000,
        "usesMapProjection": False,
        "usesGeographicCoordinates": False,
        "placementPersistedToCatalog": False,
        "sharesIdentityIds": True,
    }:
        errors.append("native digital sphere must remain projection-free, coordinate-free and identity-bound")

    restoration = gates.get("deep_link_state_restoration", {}).get("evidence", {})
    if restoration.get("before") != restoration.get("after"):
        errors.append("deep-link state was not restored exactly")
    linear = gates.get("linear_identity_and_selection_parity", {})
    if linear.get("evidence", {}).get("itemCount") != 5000:
        errors.append("linear view must retain 5000 identities")
    if linear.get("production_virtualization") != "not_proven":
        errors.append("linear-list virtualization must remain unproven")
    accessibility = gates.get("accessibility_tree_structure", {})
    if accessibility.get("real_screen_reader_session") != "not_tested":
        errors.append("accessibility tree must not be presented as real screen-reader proof")
    for field in ("hasGlobeName", "hasLinearViewName", "hasFirstIdentity", "hasLastIdentity"):
        if accessibility.get("evidence", {}).get(field) is not True:
            errors.append(f"accessibility-tree evidence missing: {field}")
    reduced = gates.get("reduced_motion_state_equivalence", {}).get("evidence", {})
    if reduced.get("reducedMotion") is not True or reduced.get("duration") != 0:
        errors.append("reduced motion must preserve state with zero-duration motion")
    if gates.get("idle_render_pause", {}).get("evidence") != {"mapRenderDelta": 0, "overlayRenderDelta": 0}:
        errors.append("idle rendering must remain stopped")
    lifecycle = gates.get("browser_lifecycle_freeze", {})
    delta = lifecycle.get("evidence", {}).get("renderDelta", {})
    if lifecycle.get("acceptance") != "no continuous rendering during freeze; at most one map and one custom-layer frame across freeze/resume transition":
        errors.append("browser lifecycle acceptance boundary mismatch")
    if delta.get("map", 99) > 1 or delta.get("overlay", 99) > 1:
        errors.append("browser lifecycle freeze exceeded transition-frame budget")
    visibility = gates.get("visibility_handler_pause_and_resume", {})
    if visibility.get("real_background_tab_roundtrip") != "not_tested":
        errors.append("real background-tab roundtrip must remain unproven")

    performance = result.get("performance", {})
    if performance.get("relative_not_physical_device_fps") is not True:
        errors.append("software-WebGL FPS must remain relative")
    if performance.get("runs_per_profile_and_level") != 3:
        errors.append("performance proof must retain three runs per profile and level")
    for profile in ("desktop", "mobile_emulated"):
        for level in ("planet", "local"):
            metrics = performance.get("summary", {}).get(profile, {}).get(level, {})
            if metrics.get("runs") != 3:
                errors.append(f"performance run count mismatch: {profile} {level}")
            values = [metrics.get(name) for name in ("min_fps", "median_fps", "max_fps")]
            if not all(_positive(value) for value in values):
                errors.append(f"invalid performance metrics: {profile} {level}")
            elif not values[0] <= values[1] <= values[2]:
                errors.append(f"performance ordering invalid: {profile} {level}")

    decision = result.get("decision", {})
    if decision.get("engine_selected") is not False:
        errors.append("MapLibre Phase-2 proof must not select a production engine")
    if decision.get("production_architecture_authorized") is not False:
        errors.append("MapLibre Phase-2 proof must not authorize production architecture")
    if decision.get("maplibre_primary_candidate_retained") is not True:
        errors.append("MapLibre must remain the primary candidate")
    if decision.get("maplibre_native_custom_layer_candidate_retained") is not True:
        errors.append("native custom layer candidate must remain retained")
    if decision.get("three_js_runtime_dependency_required") is not False:
        errors.append("Three.js runtime dependency must remain unnecessary for this proof")
    if decision.get("next_action") != "physical_device_and_assistive_technology_acceptance":
        errors.append("next action must remain physical-device and assistive-technology acceptance")

    expected_limits = {
        "physical_mobile_devices_tested": False,
        "hardware_gpu_tested": False,
        "voiceover_or_talkback_tested": False,
        "real_background_tab_roundtrip_tested": False,
        "public_proof_published": False,
        "real_catalog_records_used": False,
        "linear_list_virtualization_proven": False,
        "software_webgl_results_are_relative": True,
    }
    if result.get("limitations") != expected_limits:
        errors.append("MapLibre Phase-2 limitations must remain explicit and fail-closed")

    evidence = result.get("evidence_artifacts", {})
    for field, expected in EXPECTED_HASHES.items():
        value = str(evidence.get(field, ""))
        if value != expected or not SHA256_RE.fullmatch(value):
            errors.append(f"MapLibre Phase-2 evidence hash changed: {field}")
    for field in ("repository_contains_raw_harness", "repository_contains_screenshots", "repository_contains_node_dependencies"):
        if evidence.get(field) is not False:
            errors.append(f"non-product proof material entered repository: {field}")

    source_map = {item.get("id"): item for item in result.get("official_sources", []) if isinstance(item, dict)}
    if set(source_map) != set(EXPECTED_SOURCES) or len(result.get("official_sources", [])) != len(EXPECTED_SOURCES):
        errors.append("official source inventory mismatch")
    for source_id, expected_url in EXPECTED_SOURCES.items():
        source = source_map.get(source_id, {})
        if source.get("url") != expected_url or source.get("checked_at") != "2026-07-11":
            errors.append(f"official source binding mismatch: {source_id}")

    if result.get("gate_summary") != {"pass_or_bounded_pass": 15, "blocked": 4, "total": 19}:
        errors.append("MapLibre Phase-2 gate summary mismatch")

    for relative in ("node_modules", "screenshots", "spikes", "proofs", "maplibre-phase2-harness"):
        if (root / relative).exists():
            errors.append(f"temporary Phase-2 harness must not enter product repository: {relative}")
    for public_file in ("index.html", "404.html"):
        path = root / public_file
        if path.is_file() and "maplibre-phase2-globe-proof" in path.read_text(encoding="utf-8"):
            errors.append(f"Phase-2 research leaked into public surface: {public_file}")

    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        for token in (
            "Engine- und Produktionsarchitekturentscheidung bleibt trotzdem gesperrt",
            "CustomLayerInterface",
            "usesMapProjection",
            "physischem Mobilgerät",
            "engine_selected",
            "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"MapLibre Phase-2 report missing boundary token: {token}")

    return errors


def main() -> int:
    errors = validate_maplibre_phase2_proof(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld MapLibre Phase-2 proof validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
