#!/usr/bin/env python3
"""Validate the normalized physical Apple-WebKit v4 acceptance result."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/physical-device-acceptance-v4-apple.result.json"
REPORT = ROOT / "docs/research/physical-device-acceptance-v4-apple.md"
RAW_SHA = "6a0c4d2897ffb438756535694ba13ad04ab1f373d25247451ef20a4a6e9e8805"
V5_MANIFEST = "3e4eb9b92e21357a87368a674609e5b49199fad6ed75963bbfad1aa20a8280f5"
PASS_CHECKS = [
    "touch_rotation_zoom",
    "coverage_patterns",
    "uncertainty_halo_boundary",
    "digital_sphere",
    "shared_selection",
    "background_roundtrip",
]
REQUIRED_CHECKS = PASS_CHECKS + ["reduced_motion"]
OPEN_GATES = {
    "physical_android_chrome_v5",
    "real_catalog_layer_derivation",
    "real_name_density_and_legibility",
    "focus_panel_selection_parity",
    "side_on_camera_transition",
}
PRIVATE_PATTERNS = (
    re.compile(r'"session_id"\s*:'),
    re.compile(r'"userAgent"\s*:'),
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.I),
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


def close(actual: Any, expected: float) -> bool:
    return positive(actual) and math.isclose(float(actual), expected, rel_tol=1e-9, abs_tol=1e-9)


def validate_physical_device_acceptance_v4_apple(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing physical Apple-WebKit v4 result"]
    if not report_path.is_file():
        errors.append("missing physical Apple-WebKit v4 report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"physical Apple-WebKit v4 result is invalid JSON: {error}"]

    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_physical_device_acceptance_v4_apple":
        errors.append("physical Apple-WebKit v4 schema mismatch")
    if result.get("status") != "apple_webkit_v4_accepted_for_prototype_performance_and_interaction":
        errors.append("Apple-WebKit v4 normalized status mismatch")
    if result.get("recorded_at") != "2026-07-11" or result.get("repository_base_commit") != "23a5ace5104ba06410ddc3177a1b87615a103d5b":
        errors.append("physical Apple-WebKit v4 binding mismatch")

    raw = result.get("raw_receipt", {})
    expected_raw = {
        "sha256": RAW_SHA,
        "size_bytes": 10669,
        "acceptance_version": 4,
        "schema_version": 4,
        "overall_verdict": "incomplete",
        "completion_errors": ["2 manuelle Prüfung(en) sind noch offen."],
        "started_at": "2026-07-11T17:45:01.456Z",
        "completed_at": "2026-07-11T17:48:46.958Z",
        "raw_file_in_repository": False,
        "private_session_id_published": False,
        "raw_user_agent_published": False,
    }
    if raw != expected_raw:
        errors.append("raw receipt binding or privacy boundary mismatch")

    environment = result.get("environment", {})
    if environment != {
        "browser_family": "Apple WebKit Safari",
        "hardware_gpu": True,
        "gpu_family": "Apple GPU",
        "touch_capable": True,
        "touch_points": 5,
        "viewport_width_css_px": 1180,
        "viewport_height_css_px": 701,
        "device_pixel_ratio": 2,
        "map_pixel_ratio": 1.5,
        "reduced_motion_at_start": True,
        "reduced_motion_at_completion": True,
    }:
        errors.append("physical Apple-WebKit environment mismatch")

    automatic = result.get("automatic", {})
    if automatic.get("runs") != 3 or automatic.get("benchmark_version") != 4:
        errors.append("three v4 physical performance runs are required")
    for key, expected in {
        "planet_median_fps": 50.47672462141715,
        "local_median_fps": 50.93378607808757,
        "planet_max_p95_frame_ms": 25.000000000029104,
        "local_max_p95_frame_ms": 23,
    }.items():
        if not close(automatic.get(key), expected):
            errors.append(f"physical performance value mismatch: {key}")
    if automatic.get("minimum_median_fps") != 30:
        errors.append("physical performance gate threshold mismatch")
    for key in (
        "performance_gate_pass",
        "planet_pass",
        "local_pass",
        "idle_pass",
        "digital_sphere_globe_relative",
        "digital_sphere_complete_enclosure",
        "digital_sphere_overview_visible",
        "digital_sphere_local_hidden",
        "virtual_list_dom_bound_pass",
    ):
        if automatic.get(key) is not True:
            errors.append(f"physical automatic invariant must be true: {key}")
    if automatic.get("digital_sphere_layer_count") != 6:
        errors.append("physical digital-sphere layer count mismatch")
    if automatic.get("idle_observation_ms") != 1500:
        errors.append("physical idle observation duration mismatch")
    for key in (
        "idle_map_render_delta",
        "idle_overlay_render_delta",
        "idle_overlay_update_call_delta",
        "idle_state_write_delta",
    ):
        if automatic.get(key) != 0:
            errors.append(f"physical idle delta must remain zero: {key}")

    manual = result.get("manual_raw", {})
    if manual.get("pass") != PASS_CHECKS or manual.get("not_run") != ["assistive_technology", "reduced_motion"]:
        errors.append("raw manual-check truth mismatch")
    if manual.get("background_longest_hidden_ms") != 32608:
        errors.append("physical background duration mismatch")
    if manual.get("reduced_motion_preference_active") is not True:
        errors.append("raw Reduced Motion preference must remain active")
    if manual.get("reduced_motion_last_motion_duration_ms") is not None:
        errors.append("raw missing Reduced Motion duration must not be invented")

    policy = result.get("policy_evaluation", {})
    if policy.get("required_manual_checks") != REQUIRED_CHECKS or policy.get("optional_manual_checks") != ["assistive_technology"]:
        errors.append("prototype manual-check policy inventory mismatch")
    assistive = policy.get("assistive_technology", {})
    if assistive != {
        "status": "waived_by_product_owner",
        "scope": "non_public_prototype_acceptance_only",
        "screen_reader_product_support_claimed": False,
        "physical_screen_reader_test_required_for_this_prototype": False,
        "waiver_source": "user_message_after_receipt_upload_2026-07-11",
        "waiver_normalized": "voiceover_not_required_for_non_public_prototype",
    }:
        errors.append("screenreader waiver mismatch or support overclaim")
    reduced = policy.get("reduced_motion", {})
    if reduced != {
        "status": "accepted_by_active_preference_and_product_owner_attestation",
        "preference_active_at_start_and_completion": True,
        "product_owner_attested_working": True,
        "raw_machine_duration_missing": True,
        "raw_receipt_mutated": False,
        "v5_future_receipts_capture_zero_duration_automatically": True,
        "attestation_source": "user_message_after_receipt_upload_2026-07-11",
        "attestation_normalized": "movement_reduction_works",
    }:
        errors.append("Reduced Motion attestation boundary mismatch")
    if policy.get("all_prototype_required_manual_checks_satisfied") is not True:
        errors.append("prototype required checks must be satisfied")

    verdict = result.get("normalized_verdict", {})
    if verdict != {
        "apple_webkit_performance": "pass",
        "apple_webkit_interaction": "pass",
        "background_roundtrip": "pass",
        "reduced_motion": "pass_by_attestation_with_machine_gap_disclosed",
        "assistive_technology": "waived_not_passed",
        "screen_reader_support": "not_claimed",
        "apple_webkit_v4_prototype_acceptance": "pass",
    }:
        errors.append("normalized Apple-WebKit verdict mismatch")

    gates = result.get("remaining_gates", {})
    if set(gates) != OPEN_GATES or any(gates.get(key) != "open" for key in OPEN_GATES):
        errors.append("remaining gate inventory mismatch")
    decision = result.get("decision", {})
    if decision != {
        "engine_selected": False,
        "production_architecture_authorized": False,
        "apple_webkit_v4_rerun_required": False,
        "screen_reader_test_required_for_prototype_acceptance": False,
        "next_action": "run_v5_on_android_chrome_then_real_data_focus_and_side_camera_proof",
    }:
        errors.append("physical acceptance decision boundary mismatch")

    release = result.get("acceptance_v5_release", {})
    if release != {
        "installed_manifest_sha256": V5_MANIFEST,
        "acceptance_version": 5,
        "receipt_schema_version": 5,
        "assistive_technology_default": "waived",
        "reduced_motion_self_triggered_machine_proof": True,
        "service_active_at_check": True,
        "service_restart_count_at_check": 0,
        "continuous_health_not_claimed": True,
    }:
        errors.append("installed acceptance v5 evidence mismatch")

    artifacts = result.get("evidence_artifacts", {})
    expected_hashes = {
        "v5_archive_sha256": "87175f3059ad9c7d9aeb8a260dc3381d8a182f9e186817a76b82d68714f9147d",
        "v5_installed_proof_sha256": "2dac4b14174a973624da46b12f8b934dd85340d7a0148c2fba5273b1ddafa31c",
        "v5_installed_screenshot_sha256": "9b183d461ce97f72d93968c3ed97355498ac6514478b08366ef9d5b7b21c936c",
        "v5_preparation_proof_sha256": "001aa5a70261700f84ecf84b2509d596145e8c6e9ee9bfe9c351e6501798a068",
        "v5_archive_manifest_sha256": "a76d2fb556101385f7196b4a876ef3c9193e7c99988b62983b35ac2f531ebde3",
        "role": "local_non_product_research_archive",
    }
    if artifacts != expected_hashes:
        errors.append("physical v4 or acceptance v5 artifact binding mismatch")

    combined = result_path.read_text(encoding="utf-8")
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        combined += "\n" + report
        for token in (
            "50,48 FPS",
            "50,93 FPS",
            "32,608 Sekunden",
            "pass_by_attestation_with_machine_gap_disclosed",
            "Screenreader-Unterstützung wird nicht",
            "Android Chrome",
            "engine_selected",
            "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"physical Apple-WebKit report missing token: {token}")
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(combined):
            errors.append(f"private raw receipt material leaked: {pattern.pattern}")
    for public in ("index.html", "404.html"):
        path = root / public
        if path.is_file() and "physical-device-acceptance-v4-apple" in path.read_text(encoding="utf-8"):
            errors.append(f"physical acceptance research leaked into public shell: {public}")
    return errors


def main() -> int:
    errors = validate_physical_device_acceptance_v4_apple(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld physical Apple-WebKit v4 acceptance validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
