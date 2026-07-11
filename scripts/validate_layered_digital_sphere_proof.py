#!/usr/bin/env python3
"""Validate the installed layered digital sphere research proof."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/layered-digital-sphere-v1.result.json"
REPORT = ROOT / "docs/research/layered-digital-sphere-v1.md"
BASE = "c32156148e846e33009905affa29f00a465daf0e"
LAYERS = [
    "knowledge_data", "software_infrastructure", "media_culture",
    "learning_education", "communication_networks", "mixed_other",
]
HASHES = {
    "archive_sha256": "8204e0007e52276cd30b5f323f56ca74b770da46665d1331fd3701d012f1f3e6",
    "installed_proof_sha256": "c8b8e7fd6bba758fb9c4911bd9c67c7eb3485b5b5c46ae291e95e661eb18bdcd",
    "overview_screenshot_sha256": "9f858abc64fb6a5052ba3f3ac6ab20c8de8f41e301d871584ed899d48f8050cd",
    "side_view_screenshot_sha256": "6037f8c8287dd9808a8d006139e4783e8682b9eeb2d6a24947d58ba6edecc6ad",
    "archive_manifest_sha256": "eb22906f6574b82199c69fa559b0099f07e63457ac40ffdb037adfb7887e0cab",
    "design_input_review_sha256": "4fac1c316de32a2090a4f5b7ea7a16f36d4859d5ce3d4e17de0865d793189daa",
}
PRIVATE = (
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.I),
    re.compile(r"Mozilla/5\.0"),
)


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / RESULT.relative_to(ROOT)).read_text(encoding="utf-8"))


def positive(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)) and value > 0


def validate_layered_digital_sphere_proof(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing layered digital sphere result"]
    if not report_path.is_file():
        errors.append("missing layered digital sphere report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"layered digital sphere result is invalid JSON: {error}"]

    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_layered_digital_sphere_proof_v1":
        errors.append("layered digital sphere proof schema mismatch")
    if result.get("status") != "non_public_prototype_installed_physical_acceptance_pending":
        errors.append("physical acceptance must remain pending")
    if result.get("proved_at") != "2026-07-11" or result.get("repository_base_commit") != BASE:
        errors.append("layered digital sphere proof binding mismatch")

    source = result.get("source_input", {})
    if source != {
        "kind": "incomplete_physical_receipt_used_as_design_input",
        "automatic_performance_runs": 0,
        "shared_selection": "not_run",
        "voiceover_or_talkback": "not_run",
        "background_roundtrip": "pass_with_33305ms_evidence",
        "reduced_motion": "pass_with_active_preference_and_zero_duration_move",
        "acceptance_claimed": False,
        "raw_receipt_in_repository": False,
        "raw_receipt_sha256_available_to_operator": False,
    }:
        errors.append("source receipt truth mismatch or overclaim")

    contract = result.get("canonical_contract", {})
    if contract.get("path") != "contracts/commonworld/digital-sphere.contract.json":
        errors.append("digital sphere contract path mismatch")
    if contract.get("layer_count") != 6 or contract.get("layers") != LAYERS:
        errors.append("canonical digital layer inventory mismatch")
    if contract.get("layer_membership") != "derived_presentation_not_catalog_truth":
        errors.append("digital layer membership must remain derived presentation")
    if contract.get("primary_geometry") != "layered_glyph_paths_around_globe":
        errors.append("layered glyph paths must remain primary geometry")
    if contract.get("glyph_cycle") != ["short_common_name_fragment", "binary_fragment_derived_from_stable_identity"]:
        errors.append("digital glyph cycle mismatch")
    if contract.get("binary_meaning") != "deterministic_visual_encoding_not_payload_or_quality":
        errors.append("binary visual meaning boundary mismatch")
    if contract.get("invented_coordinates") is not False or contract.get("persistent_render_path_coordinates") is not False:
        errors.append("digital sphere must not use invented or persistent coordinates")

    prototype = result.get("prototype", {})
    expected_true = ("synthetic_data_only", "all_synthetic_layers_nonempty", "same_identity_ids")
    if prototype.get("public_surface_changed") is not False or prototype.get("point_cloud_primary") is not False:
        errors.append("prototype scope or geometry mismatch")
    if prototype.get("renderer") != "maplibre_globe_plus_svg_glyph_path_overlay" or prototype.get("canvas_count") != 1 or prototype.get("svg_text_paths") != 6:
        errors.append("prototype renderer evidence mismatch")
    for key in expected_true:
        if prototype.get(key) is not True:
            errors.append(f"prototype invariant must be true: {key}")
    if prototype.get("geographic_coordinates_for_digital_layer") is not False or prototype.get("telemetry") is not False:
        errors.append("prototype privacy boundary mismatch")

    globe = result.get("globe_behavior", {})
    numeric = ("earth_radius_px", "inner_shell_ratio", "inner_shell_radius_px", "outer_shell_ratio", "outer_shell_radius_px")
    if any(not positive(globe.get(key)) for key in numeric):
        errors.append("globe geometry evidence must be positive finite numbers")
    else:
        if abs(globe["inner_shell_radius_px"] / globe["earth_radius_px"] - 1.2) > 1e-9:
            errors.append("inner shell is not globe-relative")
        if abs(globe["outer_shell_radius_px"] / globe["earth_radius_px"] - 1.42) > 1e-9:
            errors.append("outer shell is not globe-relative")
    if globe.get("center_fade") is not True or globe.get("monotonic_fade") is not True:
        errors.append("center and zoom fade must remain proven")
    if [globe.get(k) for k in ("complete_enclosure_at_zoom", "full_visibility_through_zoom", "half_visibility_at_zoom", "hidden_from_zoom", "measured_hidden_at_zoom")] != [1.35, 1.8, 2.2, 2.6, 3.0]:
        errors.append("digital sphere zoom thresholds mismatch")

    interaction = result.get("interaction", {})
    if interaction != {
        "sphere_edge_annulus_opens_side_view": True,
        "side_view_layer_bands": 6,
        "all_side_view_bands_nonempty": True,
        "deep_link_query": "digital=layers",
        "browser_history_supported": True,
        "return_to_globe_supported": True,
        "reduced_motion_transition": "instant_state_change",
        "side_on_camera_transition_proven": False,
    }:
        errors.append("digital side-view interaction evidence mismatch")

    parity = result.get("selection_parity", {})
    if not (parity.get("selected_id") == parity.get("side_view_selected_id") == parity.get("linear_view_selected_id") == "common-00002"):
        errors.append("selection parity IDs mismatch")
    if parity.get("selection_label") != "Proof identity 2" or parity.get("automated_identity_and_label_pass") is not True:
        errors.append("automated identity and label parity evidence mismatch")
    if parity.get("focus_panel_present_in_prototype") is not False or parity.get("full_selection_parity_pass") is not False:
        errors.append("full focus-panel selection parity must remain unproven")
    if parity.get("physical_user_tested") is not False:
        errors.append("physical user selection test must remain false")

    accessibility = result.get("accessibility", {})
    for key in ("decorative_glyph_streams_aria_hidden", "side_layer_buttons_present", "linear_equivalent_present", "keyboard_automated_path_pass", "accessibility_tree_pass"):
        if accessibility.get(key) is not True:
            errors.append(f"accessibility invariant must be true: {key}")
    if accessibility.get("sphere_edge_accessible_name") != "Digitale Commons-Schichten öffnen":
        errors.append("sphere edge accessible name mismatch")
    if accessibility.get("voiceover_physical_tested") is not False or accessibility.get("talkback_physical_tested") is not False:
        errors.append("screen-reader physical tests must remain unproven")

    measurements = result.get("measurements", {})
    if measurements.get("software_webgl_relative_only") is not True or measurements.get("physical_device_fps_claimed") is not False:
        errors.append("performance evidence must remain relative software-WebGL only")
    for profile in ("small_profile", "large_profile"):
        data = measurements.get(profile, {})
        if data.get("runs") != 3:
            errors.append(f"{profile} must contain three runs")
        for key in ("planet_median_fps", "local_median_fps", "planet_max_p95_frame_ms", "local_max_p95_frame_ms"):
            if not positive(data.get(key)):
                errors.append(f"invalid {profile} measurement: {key}")
    if measurements.get("large_profile_optimization_required") is not True:
        errors.append("large-profile optimization gate must remain open")

    service = result.get("installed_service", {})
    if service != {
        "release_manifest_sha256": "a9f850c98dcf7b845cf7c7e17a1d7273a68393783aa0b70d280b214588b1fe6c",
        "acceptance_version": 3,
        "receipt_schema_version": 3,
        "active_at_check": True,
        "restart_count_at_check": 0,
        "tailnet_only": True,
        "private_endpoint_published_in_repository": False,
        "continuous_health_not_claimed": True,
    }:
        errors.append("installed v3 service evidence mismatch")

    gates = result.get("open_gates", {})
    expected_gates = {key: True for key in (
        "physical_apple_webkit_rerun", "physical_android_chrome_run", "voiceover_or_talkback",
        "large_profile_performance_optimization", "real_catalog_layer_derivation", "real_name_density_and_legibility",
        "focus_panel_selection_parity", "side_on_camera_transition",
    )}
    if gates != expected_gates:
        errors.append("layered sphere open-gate inventory mismatch")

    decision = result.get("decision", {})
    if decision.get("engine_selected") is not False or decision.get("production_architecture_authorized") is not False:
        errors.append("layered sphere proof must not authorize production")
    if decision.get("next_action") != "physically_review_layered_v3_then_optimize_large_profile_and_validate_real_derivation":
        errors.append("layered sphere next action mismatch")

    artifacts = result.get("evidence_artifacts", {})
    for key, expected in HASHES.items():
        if artifacts.get(key) != expected:
            errors.append(f"layered sphere artifact hash mismatch: {key}")
    if artifacts.get("role") != "local_non_product_research_archive":
        errors.append("layered sphere archive role mismatch")

    combined = result_path.read_text(encoding="utf-8")
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        combined += "\n" + report
        for token in (
            "keine Punktwolke mehr", "Auswahlparität", "VoiceOver und TalkBack wurden nicht physisch ausprobiert",
            "22,36 FPS", "engine_selected", "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"layered sphere report missing token: {token}")
    for pattern in PRIVATE:
        if pattern.search(combined):
            errors.append(f"private device material leaked: {pattern.pattern}")
    for public in ("index.html", "404.html"):
        path = root / public
        if path.is_file() and "layered-digital-sphere-v1" in path.read_text(encoding="utf-8"):
            errors.append(f"research proof leaked into public shell: {public}")
    return errors


def main() -> int:
    errors = validate_layered_digital_sphere_proof(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld layered digital sphere proof validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
