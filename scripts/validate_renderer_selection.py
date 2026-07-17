#!/usr/bin/env python3
"""Validate the canonical renderer selection against all bound Commonworld evidence."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_public_catalog import derive_digital_layer

CONTRACT_PATH = Path("contracts/commonworld/renderer-selection.contract.json")
DIGITAL_CONTRACT_PATH = Path("contracts/commonworld/digital-sphere.contract.json")
RESULT_PATH = Path("docs/research/renderer-selection-v1.result.json")
REPORT_PATH = Path("docs/research/renderer-selection-v1.md")
CATALOG_PATH = Path("catalog/catalog.json")

HISTORICAL_EVIDENCE_SNAPSHOTS = {
    "contracts/commonworld/aggregation-zoom.contract.json": "docs/research/renderer-selection-v1.evidence/aggregation-zoom.contract.json",
    "contracts/commonworld/visual-semantics.contract.json": "docs/research/renderer-selection-v1.evidence/visual-semantics.contract.json",
    "contracts/commonworld/project.schema.json": "docs/research/renderer-selection-v1.evidence/project.schema.json",
}

EVIDENCE_PATHS = (
    "docs/research/renderer-engine-spike.result.json",
    "docs/research/maplibre-phase2-globe-proof.result.json",
    "docs/research/device-acceptance-performance-v4.result.json",
    "docs/research/physical-device-acceptance-v4-apple.result.json",
    "docs/research/digital-sphere-real-surface-v1.result.json",
    "contracts/commonworld/aggregation-zoom.contract.json",
    "contracts/commonworld/visual-semantics.contract.json",
    "contracts/commonworld/project.schema.json",
    "contracts/commonworld/renderer-selection.contract.json",
)
EXPECTED_DECISION = {
    "engine_selected": True,
    "selected_engine": "maplibre_gl_js",
    "production_architecture_authorized": False,
    "public_runtime_uses_selected_engine": False,
    "next_proof": "public_maplibre_globe_vertical_slice_with_seed_catalog",
}
EXPECTED_RENDERER_PUBLICATION = {
    "public": True,
    "source_policy": "official-and-public-registry-sources",
    "curation_state": "listed",
    "engine_selected": True,
    "selected_engine": "maplibre_gl_js",
    "public_runtime_uses_selected_engine": True,
}
EXPECTED_LAYER_COVERAGE = {
    "knowledge_data": ["wikidata", "wikipedia"],
    "software_infrastructure": ["debian", "libreoffice"],
    "media_culture": ["wikimedia-commons"],
    "learning_education": ["wikibooks", "wikiversity"],
    "communication_networks": ["freifunk", "mastodon"],
    "mixed_other": ["openstreetmap"],
}
EXPECTED_SEED_IDS = sorted(identifier for values in EXPECTED_LAYER_COVERAGE.values() for identifier in values)
EXPECTED_SOURCES = {
    "maplibre_docs": "https://maplibre.org/maplibre-gl-js/docs/",
    "maplibre_custom_layer": "https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/",
    "maplibre_globe_custom_layer_example": "https://maplibre.org/maplibre-gl-js/docs/examples/add-a-simple-custom-layer-on-a-globe/",
    "deck_gl_globe_view": "https://deck.gl/docs/api-reference/core/globe-view",
}
REQUIRED_REASONS = {
    "highest_measured_frame_rate_on_both_standardized_candidate_profiles",
    "native_globe_projection_and_camera_model",
    "direct_vector_tile_and_geospatial_style_path",
    "phase2_semantics_state_and_idle_gates_passed",
    "physical_apple_hardware_performance_gate_passed",
    "real_digital_surface_focus_camera_and_name_density_gates_passed",
    "public_seed_catalog_covers_all_digital_layers_without_geographic_fabrication",
    "single_primary_engine_avoids_three_js_runtime_and_second_webgl_context",
}
REQUIRED_RESOLVED_CONDITIONS = {
    "coverage_patterns",
    "uncertainty_boundary_and_halo",
    "realistic_vector_tiles",
    "digital_sphere_without_catalog_coordinates",
    "identity_deduplication",
    "deep_link_and_state_restoration",
    "reduced_motion_equivalence",
    "idle_pause",
    "physical_apple_webkit_hardware_gpu",
    "real_name_density",
    "shared_focus_panel",
    "maplibre_side_camera_and_browser_back_restore",
    "large_linear_view_virtualization",
    "public_catalog_schema_and_layer_derivation",
}
REQUIRED_FORBIDDEN_INTERPRETATIONS = {
    "production architecture is authorized",
    "the renderer decision alone established a public MapLibre runtime",
    "Android Chrome has been physically accepted",
    "screen reader product support has passed",
    "the digital sphere may create geographic catalog coordinates",
    "Three.js is an approved runtime dependency",
    "a floating CDN version may be used for production",
}


def _load_json(root: Path, relative: str | Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_set(value: object) -> set[str]:
    return {item for item in value if isinstance(item, str)} if isinstance(value, list) else set()


def _is_positive_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _safe_bound_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() not in EVIDENCE_PATHS:
        return None
    return path.as_posix()


def _catalog_records(root: Path, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    files = catalog.get("project_files", [])
    if not isinstance(files, list):
        return records
    for value in files:
        if not isinstance(value, str):
            continue
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 2 or path.parts[0] != "projects":
            continue
        full = root / "catalog" / Path(*path.parts)
        if not full.is_file():
            continue
        try:
            record = json.loads(full.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def validate_renderer_selection(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = (
        CONTRACT_PATH,
        DIGITAL_CONTRACT_PATH,
        RESULT_PATH,
        REPORT_PATH,
        CATALOG_PATH,
        *(Path(path) for path in HISTORICAL_EVIDENCE_SNAPSHOTS.values()),
    )
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing renderer selection file: {relative}")
    if errors:
        return errors

    try:
        contract = _load_json(root, CONTRACT_PATH)
        digital_contract = _load_json(root, DIGITAL_CONTRACT_PATH)
        result = _load_json(root, RESULT_PATH)
        catalog = _load_json(root, CATALOG_PATH)
        spike = _load_json(root, EVIDENCE_PATHS[0])
        phase2 = _load_json(root, EVIDENCE_PATHS[1])
        performance = _load_json(root, EVIDENCE_PATHS[2])
        apple = _load_json(root, EVIDENCE_PATHS[3])
        real_surface = _load_json(root, EVIDENCE_PATHS[4])
    except (OSError, json.JSONDecodeError) as error:
        return [f"renderer selection input is invalid JSON: {error}"]

    loaded_objects = {
        "renderer selection contract": contract,
        "digital sphere contract": digital_contract,
        "renderer selection result": result,
        "public catalog": catalog,
        "renderer spike": spike,
        "MapLibre phase-2 proof": phase2,
        "performance proof": performance,
        "Apple device proof": apple,
        "real-surface proof": real_surface,
    }
    malformed = [name for name, value in loaded_objects.items() if not isinstance(value, dict)]
    if malformed:
        return [f"renderer selection inputs must contain JSON objects: {', '.join(malformed)}"]

    # Contract identity and selected engine.
    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_renderer_selection_contract":
        errors.append("renderer selection contract schema or kind mismatch")
    if contract.get("selected_at") != "2026-07-12":
        errors.append("renderer selection date mismatch")
    selected_raw = contract.get("selected_engine", {})
    selected = _mapping(selected_raw)
    if not isinstance(selected_raw, dict) or selected.get("id") != "maplibre_gl_js":
        errors.append("renderer selection must choose MapLibre GL JS")
    if selected.get("package") != "maplibre-gl" or selected.get("tested_version") != "5.24.0":
        errors.append("selected MapLibre package and tested version mismatch")
    if _string_set(selected.get("selection_scope", [])) != {
        "primary_globe_renderer",
        "camera_and_semantic_zoom_authority",
        "geographic_style_and_vector_tile_pipeline",
    }:
        errors.append("selected renderer scope mismatch")
    for flag in ("not_catalog_truth", "not_editorial_workflow", "not_linear_fallback"):
        if selected.get(flag) is not True:
            errors.append(f"selected renderer boundary must remain true: {flag}")

    integration = contract.get("integration_model", {})
    expected_integration = {
        "one_primary_globe_canvas": True,
        "geographic_surface": "maplibre_style_layers_and_vector_sources",
        "digital_sphere": "bounded_synchronized_svg_overlay",
        "digital_sphere_identity_source": "CommonProject.id",
        "digital_sphere_catalog_coordinates_forbidden": True,
        "maplibre_custom_layer": "allowed_only_after_equivalent_contract_proof",
        "three_js_runtime_dependency_authorized": False,
        "second_independent_globe_authorized": False,
        "same_focus_and_navigation_state_across_all_views": True,
    }
    if integration != expected_integration:
        errors.append("renderer integration model mismatch")
    if contract.get("decision_boundary") != EXPECTED_DECISION:
        errors.append("renderer selection decision boundary mismatch")
    digital_decision = _mapping(digital_contract.get("decision_boundary", {}))
    for key in ("engine_selected", "selected_engine", "production_architecture_authorized"):
        if digital_decision.get(key) != EXPECTED_DECISION[key]:
            errors.append(f"digital sphere and renderer selection decisions differ: {key}")
    if _string_set(contract.get("selection_reasons", [])) != REQUIRED_REASONS:
        errors.append("renderer selection reasons are incomplete or changed")

    alternatives = _mapping(contract.get("alternatives", {}))
    if _mapping(alternatives.get("three_js", {})).get("status") != "not_selected":
        errors.append("Three.js must remain unselected")
    if _mapping(alternatives.get("cesium_js", {})).get("status") != "rejected_for_current_product_scope":
        errors.append("Cesium disposition mismatch")
    if _mapping(alternatives.get("deck_gl", {})).get("status") != "rejected_as_primary_globe":
        errors.append("deck.gl disposition mismatch")

    version = _mapping(contract.get("version_policy", {}))
    if version.get("selection_is_bound_to_tested_version") != "5.24.0":
        errors.append("renderer selection must remain bound to MapLibre 5.24.0")
    for flag in (
        "first_runtime_dependency_must_be_exactly_pinned",
        "lockfile_required_before_public_runtime_integration",
        "upgrade_requires_contract_and_device_regression_suite",
        "cdn_floating_version_forbidden",
    ):
        if version.get(flag) is not True:
            errors.append(f"renderer version policy must remain true: {flag}")

    gates = _mapping(contract.get("remaining_release_gates", {}))
    expected_gate_values = {
        "physical_android_chrome_hardware": "open",
        "public_seed_catalog_vertical_slice": "required_next",
        "production_tile_and_basemap_provider_decision": "open",
        "content_security_policy_and_worker_delivery": "open",
        "public_accessibility_and_linear_parity": "required",
        "screen_reader_product_support": "not_claimed",
    }
    if gates != expected_gate_values:
        errors.append("renderer release gates mismatch or overclaim completion")

    sources_raw = contract.get("official_sources", [])
    sources = sources_raw if isinstance(sources_raw, list) else []
    source_map = {
        item.get("id"): item
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(sources) != len(EXPECTED_SOURCES) or set(source_map) != set(EXPECTED_SOURCES):
        errors.append("renderer selection official source set mismatch")
    for source_id, expected_url in EXPECTED_SOURCES.items():
        source = source_map.get(source_id, {})
        if source.get("url") != expected_url or source.get("checked_at") != "2026-07-12":
            errors.append(f"renderer selection official source binding mismatch: {source_id}")

    # Decision-result identity and hash bindings.
    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_renderer_selection_v1":
        errors.append("renderer selection result schema or kind mismatch")
    if result.get("status") != "maplibre_selected_production_architecture_open":
        errors.append("renderer selection result status mismatch")
    if result.get("decided_at") != "2026-07-12":
        errors.append("renderer selection result date mismatch")
    if result.get("repository_base_commit") != "1df26e4c921aa22fd982ef81a3b8e3f15e171dd4":
        errors.append("renderer selection must remain bound to the decision base commit")

    bindings = result.get("evidence_bindings", [])
    binding_map: dict[str, str] = {}
    if not isinstance(bindings, list):
        errors.append("renderer evidence bindings must be a list")
        bindings = []
    for item in bindings:
        if not isinstance(item, dict):
            errors.append("renderer evidence binding must be an object")
            continue
        safe = _safe_bound_path(item.get("path"))
        digest = item.get("sha256")
        if safe is None or not isinstance(digest, str):
            errors.append("renderer evidence binding path or digest is invalid")
            continue
        if safe in binding_map:
            errors.append(f"renderer evidence binding duplicated: {safe}")
        binding_map[safe] = digest
    if set(binding_map) != set(EVIDENCE_PATHS):
        errors.append("renderer evidence binding inventory mismatch")
    for relative in EVIDENCE_PATHS:
        path = root / relative
        if not path.is_file():
            errors.append(f"renderer evidence file missing: {relative}")
            continue
        evidence_path = root / HISTORICAL_EVIDENCE_SNAPSHOTS.get(relative, relative)
        if not evidence_path.is_file():
            errors.append(f"renderer evidence snapshot missing: {evidence_path.relative_to(root)}")
            continue
        actual = _sha256(evidence_path)
        if binding_map.get(relative) != actual:
            errors.append(f"renderer evidence hash mismatch: {relative}")

    comparison = _mapping(result.get("candidate_comparison", {}))
    if comparison.get("source") != "docs/research/renderer-engine-spike.result.json":
        errors.append("renderer selection candidate comparison source mismatch")
    versions = _mapping(_mapping(spike.get("method", {})).get("candidate_versions", {}))
    if comparison.get("tested_versions") != versions:
        errors.append("renderer selection candidate versions differ from measured spike")
    measurements = _mapping(spike.get("measurements", {}))
    maplibre = _mapping(measurements.get("maplibre_gl_js", {}))
    fastest_profiles: list[str] = []
    for profile in ("desktop", "mobile_emulated"):
        maplibre_fps = _mapping(maplibre.get(profile, {})).get("fps")
        other_fps = [
            _mapping(_mapping(measurements.get(candidate, {})).get(profile, {})).get("fps")
            for candidate in ("cesium_js", "three_js", "deck_gl")
        ]
        if _is_positive_number(maplibre_fps) and all(_is_positive_number(value) for value in other_fps):
            if float(maplibre_fps) > max(float(value) for value in other_fps):
                fastest_profiles.append(profile)
    if comparison.get("maplibre_fastest_profiles") != fastest_profiles or fastest_profiles != ["desktop", "mobile_emulated"]:
        errors.append("MapLibre must remain fastest in both measured candidate profiles")
    expected_fps = {
        "desktop": _mapping(maplibre.get("desktop", {})).get("fps"),
        "mobile_emulated": _mapping(maplibre.get("mobile_emulated", {})).get("fps"),
    }
    if comparison.get("maplibre_fps") != expected_fps:
        errors.append("renderer selection MapLibre FPS summary drifted")
    if comparison.get("maplibre_gzip_bytes") != maplibre.get("bundle_gzip_bytes"):
        errors.append("renderer selection MapLibre bundle summary drifted")
    if comparison.get("fatal_runtime_errors") != maplibre.get("fatal_runtime_errors") or comparison.get("fatal_runtime_errors") != 0:
        errors.append("selected engine must retain zero measured fatal runtime errors")

    # Cross-check the conditions that became sufficient for selection.
    resolved = _mapping(result.get("resolved_selection_conditions", {}))
    if set(resolved) != REQUIRED_RESOLVED_CONDITIONS or any(value != "pass" for value in resolved.values()):
        errors.append("renderer selection conditions must all be explicitly passed")

    phase_gates = _mapping(phase2.get("gate_results", {}))
    phase_requirements = {
        "coverage_assessed_solid_density": "coverage_patterns",
        "coverage_partial_broken_hatch": "coverage_patterns",
        "coverage_unassessed_dot_grid": "coverage_patterns",
        "approximate_location_boundary_and_halo": "uncertainty_boundary_and_halo",
        "realistic_vector_tile_path": "realistic_vector_tiles",
        "identity_deduplication": "identity_deduplication",
        "maplibre_native_abstract_digital_sphere": "digital_sphere_without_catalog_coordinates",
        "deep_link_state_restoration": "deep_link_and_state_restoration",
        "reduced_motion_state_equivalence": "reduced_motion_equivalence",
        "idle_render_pause": "idle_pause",
    }
    for gate_name in phase_requirements:
        status = str(_mapping(phase_gates.get(gate_name, {})).get("status", ""))
        if not status.startswith("pass"):
            errors.append(f"required MapLibre phase-2 gate is not passed: {gate_name}")
    vector_evidence = _mapping(_mapping(phase_gates.get("realistic_vector_tile_path", {})).get("evidence", {}))
    if vector_evidence.get("source_type") != "vector" or not _is_positive_number(vector_evidence.get("requests")):
        errors.append("MapLibre selection requires the realistic vector-tile path")
    sphere_evidence = _mapping(_mapping(phase_gates.get("maplibre_native_abstract_digital_sphere", {})).get("evidence", {}))
    if sphere_evidence.get("usesGeographicCoordinates") is not False or sphere_evidence.get("placementPersistedToCatalog") is not False:
        errors.append("digital sphere proof must not create or persist geographic coordinates")

    apple_environment = _mapping(apple.get("environment", {}))
    apple_auto = _mapping(apple.get("automatic", {}))
    apple_verdict = _mapping(apple.get("normalized_verdict", {}))
    if apple_environment.get("hardware_gpu") is not True or apple_environment.get("browser_family") != "Apple WebKit Safari":
        errors.append("renderer selection requires the Apple WebKit hardware-GPU proof")
    if apple_auto.get("performance_gate_pass") is not True:
        errors.append("renderer selection requires the physical Apple performance gate")
    if not _is_positive_number(apple_auto.get("planet_median_fps")) or float(apple_auto["planet_median_fps"]) < 30:
        errors.append("physical Apple planet performance must remain at least 30 FPS")
    if not _is_positive_number(apple_auto.get("local_median_fps")) or float(apple_auto["local_median_fps"]) < 30:
        errors.append("physical Apple local performance must remain at least 30 FPS")
    if apple_verdict.get("apple_webkit_v4_prototype_acceptance") != "pass":
        errors.append("physical Apple prototype acceptance must remain passed")
    if apple_verdict.get("assistive_technology") != "waived_not_passed":
        errors.append("screen reader scope must remain waived, not passed")

    real_focus = _mapping(real_surface.get("focus_panel", {}))
    real_camera = _mapping(real_surface.get("side_camera", {}))
    real_perf = _mapping(real_surface.get("rendering_performance", {}))
    if real_focus.get("source") != "same_commonproject_v3_record" or real_focus.get("second_data_copy") is not False:
        errors.append("real surface must retain one focus panel derived from the same identity")
    standard = _mapping(real_camera.get("standard_transition", {}))
    reduced = _mapping(real_camera.get("reduced_motion_transition", {}))
    if standard.get("maplibre_command") != "maplibre.easeTo" or standard.get("browser_back_restored_exact") is not True:
        errors.append("real surface must retain the MapLibre side-camera and exact browser-back restore")
    if reduced.get("maplibre_command") != "maplibre.jumpTo" or reduced.get("duration_ms") != 0:
        errors.append("real surface reduced motion must retain MapLibre jumpTo at 0 ms")
    private_v6 = _mapping(real_perf.get("private_v6_browser_proof", {}))
    if private_v6.get("browser_test_status") != "pass" or _mapping(private_v6.get("performance", {})).get("gate_pass") is not True:
        errors.append("renderer selection requires the passed real-surface browser and performance proof")
    virtual = _mapping(private_v6.get("virtual_list", {}))
    if virtual.get("pass") is not True or virtual.get("total_items") != 50000:
        errors.append("renderer selection requires the 50,000-item virtual-list proof")

    installed_v4 = _mapping(performance.get("v4_installed_proof", {}))
    if installed_v4.get("performance_gate_pass") is not True or installed_v4.get("idle_map_render_delta") != 0 or installed_v4.get("idle_overlay_render_delta") != 0:
        errors.append("renderer selection requires the installed v4 performance and idle proof")

    # Public catalog alignment.
    publication = _mapping(catalog.get("publication", {}))
    if any(publication.get(key) != expected for key, expected in EXPECTED_RENDERER_PUBLICATION.items()):
        errors.append("public catalog renderer publication boundary mismatch")
    records = _catalog_records(root, catalog)
    records_by_id = {record.get("id"): record for record in records if isinstance(record.get("id"), str)}
    baseline = _mapping(catalog.get("seed_baseline", {}))
    baseline_ids = baseline.get("project_ids")
    if baseline_ids != EXPECTED_SEED_IDS:
        errors.append("renderer selection seed baseline identities differ from the historical decision")
        baseline_ids = EXPECTED_SEED_IDS
    seed_records = [records_by_id[identifier] for identifier in baseline_ids if identifier in records_by_id]
    if len(seed_records) != 10:
        errors.append("renderer selection requires exactly ten preserved public seed records")
    actual_coverage: dict[str, list[str]] = defaultdict(list)
    for record in seed_records:
        identifier = record.get("id")

        presence = record.get("presence", {})
        if not isinstance(presence, dict) or presence.get("geographic") != []:
            errors.append(f"public seed record must not gain geographic presence: {identifier}")
        if any(name in record for name in ("layer", "derived_layer", "presentation_layer", "semantic_zoom")):
            errors.append(f"public seed record must not store renderer or zoom truth: {identifier}")
        layer = derive_digital_layer(record, digital_contract)
        if isinstance(identifier, str) and isinstance(layer, str):
            actual_coverage[layer].append(identifier)
    actual_coverage = {key: sorted(values) for key, values in sorted(actual_coverage.items())}
    if actual_coverage != EXPECTED_LAYER_COVERAGE:
        errors.append("public seed catalog layer coverage differs from the renderer decision")

    alignment = _mapping(result.get("public_catalog_alignment", {}))
    expected_alignment = {
        "manifest_path": "catalog/catalog.json",
        "entry_count": 10,
        "commonproject_schema_version": 3,
        "all_records_digital": True,
        "all_geographic_presence_empty": True,
        "manual_layer_fields_present": False,
        "layer_coverage": EXPECTED_LAYER_COVERAGE,
    }
    if alignment != expected_alignment:
        errors.append("renderer selection public-catalog alignment summary mismatch")

    selection = _mapping(result.get("selection", {}))
    if selection.get("engine_selected") is not True or selection.get("selected_engine") != "maplibre_gl_js":
        errors.append("renderer selection result must choose MapLibre GL JS")
    if selection.get("selected_package") != "maplibre-gl" or selection.get("selected_tested_version") != "5.24.0":
        errors.append("renderer selection result package or version mismatch")
    if selection.get("primary_responsibilities") != [
        "globe_projection",
        "camera_and_semantic_zoom",
        "geographic_vector_sources",
        "geographic_style_layers",
        "feature_query_and_picking",
    ]:
        errors.append("renderer selection primary responsibilities mismatch")
    if selection.get("digital_sphere_strategy") != "bounded_synchronized_svg_overlay":
        errors.append("renderer selection result digital-sphere strategy mismatch")
    if selection.get("three_js_runtime_dependency_required") is not False:
        errors.append("renderer selection must not require a Three.js runtime")
    if selection.get("production_architecture_authorized") is not False:
        errors.append("renderer selection must not authorize production architecture")
    if selection.get("public_runtime_uses_selected_engine") is not False:
        errors.append("renderer selection result must remain historical and must not claim runtime integration")
    if selection.get("next_proof") != EXPECTED_DECISION["next_proof"]:
        errors.append("renderer selection next proof mismatch")

    open_gates = _mapping(result.get("open_gates", {}))
    expected_open_gates = {
        "physical_android_chrome_hardware": "open_release_compatibility_gate_not_engine_selection_blocker",
        "public_maplibre_vertical_slice": "required_next",
        "tile_and_basemap_provider": "open",
        "csp_and_worker_delivery": "open",
        "screen_reader_product_support": "not_claimed",
    }
    if open_gates != expected_open_gates:
        errors.append("renderer selection open release gates mismatch or overclaim completion")
    if _string_set(result.get("forbidden_interpretations", [])) != REQUIRED_FORBIDDEN_INTERPRETATIONS:
        errors.append("renderer selection forbidden interpretations are incomplete or changed")

    source_recheck = _mapping(result.get("official_source_recheck", {}))
    if source_recheck != {
        "checked_at": "2026-07-12",
        "maplibre_docs_current_install_example": "maplibre-gl@^5.24.0",
        "maplibre_globe_and_custom_layer_docs_available": True,
        "deck_gl_globe_view_still_marked_experimental": True,
    }:
        errors.append("renderer official-source recheck summary mismatch")

    # Runtime integration is validated by the separate public vertical-slice contract.

    report = (root / REPORT_PATH).read_text(encoding="utf-8")
    for token in (
        "MapLibre GL JS 5.24.0 wird die kanonische Primärengine",
        "keine Freigabe der vollständigen Produktionsarchitektur",
        "zusätzliche Three.js-Laufzeit",
        "physischer Android-Chrome-Gegencheck",
        "öffentlicher MapLibre-Globus-Vertikalschnitt",
        "Floating-CDN-Versionen sind verboten",
    ):
        if token not in report:
            errors.append(f"renderer selection report missing boundary token: {token}")

    return errors


def main() -> int:
    errors = validate_renderer_selection(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld canonical MapLibre renderer selection validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
