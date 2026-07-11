#!/usr/bin/env python3
"""Validate the physical v3 finding and optimized v4 acceptance proof."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/device-acceptance-performance-v4.result.json"
REPORT = ROOT / "docs/research/device-acceptance-performance-v4.md"
BASE = "bdfde23189617a06dc1b82250f049e0d1ec7afab"
RAW_SHA = "e7b20d1d923ed43201b5b173c4bd1f7f717a6f3fcd7bcdc9c1c4826ee07fddaf"
RELEASE_SHA = "6516be94b78c1b432c92b0d2ec1b248bbe8d18f4ca8d2af92a8963bd96daad89"
HASHES = {
    "archive_sha256": "a0475f929b9eba749a524f4928c8cd9a3aa115e9b7143c3de3c60d2ccbca8cce",
    "physical_v3_review_sha256": "5c99791d100197beb23f9d3900ad6a7d2b53d2278b851fa9179452e45e5abd12",
    "same_workload_ab_sha256": "2d96aa7d8b484c0c428d28d3633f8f804b74c7f11065d85132dd6b54595c2eeb",
    "installed_proof_sha256": "93d854562179a93a0675e755b6c38e715e75450d411a7cfac573398bb37f78e2",
    "preparation_proof_sha256": "2947c4de8dc3285a37b87f003cb45976f6e40a60e5312b089d006c92858db248",
    "archive_manifest_sha256": "b497145d91d22ee130ab731aac0e5dcd8e2359dd86d49b2fd2c02e584cecaffc",
    "overview_screenshot_sha256": "2ab1bf6c6a1fba18c7d5d4f42edf06bfe7eb6b344ff4ff0def3eeb59a4a35fff",
    "side_view_screenshot_sha256": "9f9424c53a3cfb9d61ec765b0cea09ece16cbcef4e5fa0722b604e1c15626c1a",
    "acceptance_screenshot_sha256": "a55729189cbf5f2dd858e66c34883e587ac7365dd6ef05d669013c095c577e4f",
}
MANUAL_PASS = [
    "touch_rotation_zoom",
    "coverage_patterns",
    "uncertainty_halo_boundary",
    "digital_sphere",
    "shared_selection",
]
MANUAL_OPEN = ["background_roundtrip", "assistive_technology", "reduced_motion"]
OPEN_GATES = {
    "physical_apple_webkit_v4_three_runs",
    "physical_android_chrome_v4_three_runs",
    "background_roundtrip",
    "voiceover_or_talkback",
    "reduced_motion_physical_action",
    "real_catalog_layer_derivation",
    "real_name_density_and_legibility",
    "focus_panel_selection_parity",
    "side_on_camera_transition",
}
PRIVATE_PATTERNS = (
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.I),
    re.compile(r"Mozilla/5\.0"),
    re.compile(r'"session_id"\s*:'),
)


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / RESULT.relative_to(ROOT)).read_text(encoding="utf-8"))


def positive(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def close(actual: Any, expected: float, tolerance: float = 1e-9) -> bool:
    return positive(actual) and math.isclose(float(actual), expected, rel_tol=tolerance, abs_tol=tolerance)


def validate_device_acceptance_performance_v4(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing v4 performance result"]
    if not report_path.is_file():
        errors.append("missing v4 performance report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"v4 performance result is invalid JSON: {error}"]

    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_device_acceptance_performance_v4":
        errors.append("v4 performance proof schema mismatch")
    if result.get("status") != "v4_installed_physical_rerun_pending":
        errors.append("v4 physical rerun must remain pending")
    if result.get("recorded_at") != "2026-07-11" or result.get("repository_base_commit") != BASE:
        errors.append("v4 performance proof binding mismatch")

    physical = result.get("physical_v3_receipt", {})
    if physical.get("raw_receipt_sha256") != RAW_SHA or physical.get("raw_receipt_size_bytes") != 4880:
        errors.append("physical v3 receipt hash or size mismatch")
    if physical.get("raw_receipt_in_repository") is not False or physical.get("raw_receipt_mounted_to_operator_runtime") is not False:
        errors.append("raw physical receipt publication boundary mismatch")
    if physical.get("acceptance_version") != 3 or physical.get("overall_verdict") != "incomplete":
        errors.append("physical v3 receipt status mismatch")
    if physical.get("automatic_runs_completed") != 1 or physical.get("automatic_runs_required") != 3:
        errors.append("physical v3 receipt must remain one of three runs")
    if physical.get("manual_pass") != MANUAL_PASS or physical.get("manual_open") != MANUAL_OPEN:
        errors.append("physical v3 manual truth mismatch")
    environment = physical.get("environment", {})
    if environment != {
        "browser_family": "Apple WebKit Safari",
        "hardware_gpu": True,
        "viewport_width_css_px": 1180,
        "viewport_height_css_px": 684,
        "device_pixel_ratio": 2,
    }:
        errors.append("physical v3 normalized environment mismatch")
    single = physical.get("single_run", {})
    expected_single = {
        "planet_fps": 8.813160987074031,
        "planet_mean_frame_ms": 113.46666666666667,
        "local_fps": 4.422169811320755,
        "local_mean_frame_ms": 226.13333333333333,
    }
    for key, expected in expected_single.items():
        if not close(single.get(key), expected):
            errors.append(f"physical v3 single-run measurement mismatch: {key}")
    if single.get("map_render_count") != 510 or single.get("sphere_render_count") != 509:
        errors.append("physical v3 render counts mismatch")
    interpretation = physical.get("interpretation", {})
    if interpretation != {
        "performance_failure_real": True,
        "continuous_idle_rendering_proven": False,
        "render_counts_include_benchmark_work": True,
        "directly_comparable_to_v4_measurement": False,
    }:
        errors.append("physical v3 interpretation overclaims or changed")

    diagnosis = result.get("diagnosis", {})
    expected_diagnosis = {
        "v3_local_profile": "full_360_degree_bearing_rotation_at_zoom_6",
        "v3_timing": "generic_browser_animation_frame_not_confirmed_map_render",
        "immediate_navigation_state_write_on_moveend": True,
        "unchanged_svg_paths_rewritten_on_map_render": True,
        "full_device_pixel_ratio": 2,
        "idle_loop_found": False,
    }
    if diagnosis != expected_diagnosis:
        errors.append("v3 diagnosis mismatch or idle-loop overclaim")

    changes = result.get("v4_changes", {})
    expected_changes = {
        "benchmark_version": 4,
        "planet_profile": "90_frame_90_degree_overview_bearing",
        "local_profile": "90_frame_bounded_local_micro_pan",
        "browser_frame_aligned": True,
        "map_render_event_confirmed": True,
        "navigation_state_write_debounce_ms": 140,
        "unchanged_svg_geometry_cache": True,
        "hidden_local_sphere_skips_path_updates": True,
        "map_pixel_ratio_cap": 1.5,
        "acceptance_panel_hidden_during_measurement": True,
        "idle_observation_ms": 1500,
        "minimum_median_fps": 30,
        "maximum_idle_map_renders": 2,
        "maximum_idle_overlay_renders": 0,
        "automatic_failure_is_receipted": True,
    }
    if changes != expected_changes:
        errors.append("v4 benchmark or optimization contract mismatch")

    ab = result.get("same_workload_ab", {})
    if ab.get("environment") != "headless_chrome_software_webgl_1180x684_dpr2" or ab.get("single_run_frames_per_profile") != 90:
        errors.append("v3/v4 A/B environment mismatch")
    if ab.get("physical_device_claimed") is not False:
        errors.append("v3/v4 A/B must not claim physical hardware")
    v3 = ab.get("v3", {})
    v4 = ab.get("v4", {})
    for label, data in (("v3", v3), ("v4", v4)):
        for key in ("planet_fps", "local_fps", "planet_p95_frame_ms", "local_p95_frame_ms"):
            if not positive(data.get(key)):
                errors.append(f"invalid {label} A/B measurement: {key}")
        if data.get("idle_map_render_delta") != 0 or data.get("idle_overlay_render_delta") != 0:
            errors.append(f"{label} A/B idle rendering must remain zero")
    if v3.get("map_pixel_ratio") != 2 or v4.get("map_pixel_ratio") != 1.5:
        errors.append("A/B pixel-ratio configuration mismatch")
    if v3.get("overlay_geometry_writes") != 385 or v4.get("overlay_geometry_writes") != 0:
        errors.append("A/B SVG geometry-write evidence mismatch")
    if v3.get("navigation_state_writes") != 183 or v4.get("navigation_state_writes") != 3:
        errors.append("A/B navigation-state-write evidence mismatch")
    if not (v4.get("planet_fps", 0) > v3.get("planet_fps", 0) and v4.get("local_fps", 0) > v3.get("local_fps", 0)):
        errors.append("v4 must outperform v3 under the same workload")
    improvement = ab.get("improvement", {})
    if positive(v3.get("planet_fps")) and positive(v4.get("planet_fps")):
        ratio_planet = v4["planet_fps"] / v3["planet_fps"]
        if not close(improvement.get("planet_fps_ratio"), ratio_planet):
            errors.append("planet A/B improvement ratio mismatch")
    if positive(v3.get("local_fps")) and positive(v4.get("local_fps")):
        ratio_local = v4["local_fps"] / v3["local_fps"]
        if not close(improvement.get("local_fps_ratio"), ratio_local):
            errors.append("local A/B improvement ratio mismatch")
    if isinstance(v3.get("navigation_state_writes"), int) and v3.get("navigation_state_writes", 0) > 0:
        state_reduction = 100 * (1 - v4.get("navigation_state_writes", 0) / v3["navigation_state_writes"])
        if not close(improvement.get("navigation_state_write_reduction_percent"), state_reduction):
            errors.append("navigation-state reduction mismatch")
    if improvement.get("overlay_geometry_write_reduction_percent") != 100.0:
        errors.append("overlay geometry-write reduction mismatch")

    for proof_name in ("v4_preparation_proof", "v4_installed_proof"):
        proof = result.get(proof_name, {})
        if proof.get("runs") != 3 or proof.get("performance_gate_pass") is not True:
            errors.append(f"{proof_name} must contain three passing software runs")
        if proof.get("physical_device_tested") is not False:
            errors.append(f"{proof_name} must remain non-physical")
        if proof.get("planet_median_fps", 0) < 30 or proof.get("local_median_fps", 0) < 30:
            errors.append(f"{proof_name} is below the declared 30 FPS software gate")
        if proof.get("idle_map_render_delta") != 0 or proof.get("idle_overlay_render_delta") != 0 or proof.get("idle_state_write_delta") != 0:
            errors.append(f"{proof_name} idle deltas must remain zero")
    preparation = result.get("v4_preparation_proof", {})
    if preparation.get("map_pixel_ratio") != 1.5 or preparation.get("environment") != "headless_chrome_software_webgl_1180x684_dpr2":
        errors.append("v4 preparation environment mismatch")
    installed = result.get("v4_installed_proof", {})
    if installed.get("release_manifest_sha256") != RELEASE_SHA:
        errors.append("installed v4 release hash mismatch")
    if installed.get("acceptance_version") != 4 or installed.get("receipt_schema_version") != 4:
        errors.append("installed v4 receipt version mismatch")
    if installed.get("service_active_at_check") is not True or installed.get("service_restart_count_at_check") != 0:
        errors.append("installed v4 dated service evidence mismatch")
    if installed.get("continuous_health_not_claimed") is not True:
        errors.append("installed v4 must not claim continuous health")
    if installed.get("tailnet_only") is not True or installed.get("private_endpoint_in_repository") is not False:
        errors.append("installed v4 network privacy boundary mismatch")
    if installed.get("same_identity_and_label_between_side_and_linear") is not True:
        errors.append("installed v4 identity-and-label continuity mismatch")
    if installed.get("virtual_list_total") != 50000 or installed.get("virtual_list_maximum_rows", 999) > installed.get("virtual_list_theoretical_bound", 0):
        errors.append("installed v4 virtual-list bound mismatch")

    gates = result.get("open_gates", {})
    if set(gates) != OPEN_GATES or any(gates.get(key) is not True for key in OPEN_GATES):
        errors.append("v4 open-gate inventory mismatch")
    decision = result.get("decision", {})
    if decision != {
        "engine_selected": False,
        "production_architecture_authorized": False,
        "v4_physical_rerun_required": True,
        "next_action": "run_complete_v4_receipt_on_apple_webkit_then_android_chrome_and_review",
    }:
        errors.append("v4 decision boundary mismatch")

    artifacts = result.get("evidence_artifacts", {})
    for key, expected in HASHES.items():
        if artifacts.get(key) != expected:
            errors.append(f"v4 evidence hash mismatch: {key}")
    if artifacts.get("role") != "local_non_product_research_archive":
        errors.append("v4 evidence archive role mismatch")

    combined = result_path.read_text(encoding="utf-8")
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        combined += "\n" + report
        for token in (
            "kein Beweis für einen Dauerloop",
            "21,81 FPS",
            "34,12 FPS",
            "47,54 FPS",
            "physische Wiederholung",
            "engine_selected",
            "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"v4 performance report missing token: {token}")
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(combined):
            errors.append(f"private physical receipt material leaked: {pattern.pattern}")
    for public in ("index.html", "404.html"):
        path = root / public
        if path.is_file() and "device-acceptance-performance-v4" in path.read_text(encoding="utf-8"):
            errors.append(f"v4 research proof leaked into public shell: {public}")
    return errors


def main() -> int:
    errors = validate_device_acceptance_performance_v4(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld device acceptance performance v4 validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
