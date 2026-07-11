#!/usr/bin/env python3
"""Validate the non-public device acceptance pack without claiming physical acceptance."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/device-acceptance-pack-v1.result.json"
REPORT = ROOT / "docs/research/device-acceptance-pack-v1.md"
BASE_COMMIT = "8a9b2344a16433254001487c7cc813d3df061d47"
MANUAL_CHECKS = {
    "touch_rotation_zoom",
    "coverage_patterns",
    "uncertainty_halo_boundary",
    "digital_sphere",
    "shared_selection",
    "background_roundtrip",
    "assistive_technology",
    "reduced_motion",
}
ARTIFACT_HASHES = {
    "archive_sha256": "be7b673e30bfe4e124f6d21c068962cd1450760568e235b9e28763e0ce811b22",
    "preparation_proof_sha256": "3241ac53bf1e9c9044c10a4ca508bbd9dc11eca52e402009b00911ee109108f0",
    "installed_service_proof_sha256": "60372bcc86a10cbf0758729e07ea490cdbf99b480f9abe4af6173534528ccb0b",
    "manifest_sha256": "8986c58d4660e34bf807796530da27bc3d7cc036ed13a75aeeccc930bed4d396",
    "virtual_list_screenshot_sha256": "e9edd3c778b2b74d8fdf4ee8e66952902acf7fef2d589e80acac060b4f7f7123",
    "acceptance_panel_screenshot_sha256": "3d6c7d80c156fa6e98c20f8cdf82fed2ebcceba33a550451bdf32123fb6aa47c",
}
RELEASE_FILES = {
    "server.mjs": {"bytes": 49647, "sha256": "6885bdeb0b4359c538f5271a09815d40609bd8e8fc91547a9e73bfbbb3611091"},
    "dist/index.html": {"bytes": 8667, "sha256": "39241c7183995ebbbd74e877acab2334bcd1ae31355690f776946ef53221fc70"},
    "dist/app.js": {"bytes": 1069726, "sha256": "976f42192916f7ea3e23b389e10b3ce2860dff3337dd9b93fdf38e3ddd0d2262"},
    "dist/app.css": {"bytes": 69939, "sha256": "3f1950959649e58019fa90fc6349e058975624ad389afc8f896e91c7ac631cf0"},
    "dist/bundle-sizes.json": {"bytes": 244, "sha256": "ba6e2b450d7e1430896bc19d8894ce176253f5db171fed1ded75f786b40de37d"},
}
PRIVATE_ENDPOINT_PATTERNS = (
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.IGNORECASE),
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / RESULT.relative_to(ROOT)).read_text(encoding="utf-8"))


def _positive_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def validate_device_acceptance_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing device acceptance pack result"]
    if not report_path.is_file():
        errors.append("missing device acceptance pack report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"device acceptance pack result is invalid JSON: {error}"]

    if result.get("schema_version") != 1:
        errors.append("device acceptance schema_version must be 1")
    if result.get("kind") != "commonworld_device_acceptance_pack_v1":
        errors.append("device acceptance kind mismatch")
    if result.get("status") != "pack_ready_physical_execution_pending":
        errors.append("physical execution must remain pending")
    if result.get("prepared_at") != "2026-07-11":
        errors.append("device acceptance preparation date mismatch")
    if result.get("repository_base_commit") != BASE_COMMIT:
        errors.append("device acceptance result must remain base-commit bound")

    scope = result.get("scope", {})
    expected_scope = {
        "public_surface_changed": False,
        "synthetic_data_only": True,
        "raw_harness_in_repository": False,
        "screenshots_in_repository": False,
        "node_dependencies_in_repository": False,
        "device_endpoint_published_in_repository": False,
        "tailnet_only_service_installed": True,
        "direct_tailnet_endpoint_verified": True,
        "magic_dns_verified": False,
    }
    if scope != expected_scope:
        errors.append("device acceptance scope or privacy boundary mismatch")

    linear = result.get("virtualized_linear_view", {})
    exact_linear = {
        "parity_dataset_identities": 5000,
        "scale_dataset_identities": 50000,
        "fixed_row_height_px": 52,
        "overscan_rows": 7,
        "maximum_rendered_rows": 17,
        "maximum_allowed_rows": 25,
        "last_entry_index": 49999,
        "search_last_entry_pass": True,
        "home_end_navigation_pass": True,
        "identity_selection_parity_pass": True,
        "dom_bound_pass": True,
        "real_catalog_data_tested": False,
    }
    if linear != exact_linear:
        errors.append("virtualized linear-view evidence mismatch")
    if linear.get("maximum_rendered_rows", 99) > linear.get("maximum_allowed_rows", 0):
        errors.append("virtualized linear view exceeded its DOM bound")

    measurement = result.get("preparation_measurement", {})
    if measurement.get("environment") != "headless Chrome ANGLE/SwiftShader software WebGL":
        errors.append("preparation environment mismatch")
    if measurement.get("viewport") != {
        "width": 390,
        "height": 844,
        "device_scale_factor": 2,
        "mobile_emulation": True,
        "touch_emulation": True,
    }:
        errors.append("preparation viewport mismatch")
    if measurement.get("runs_per_scale") != 3:
        errors.append("three preparation runs per scale are required")
    for field in ("planet_median_fps", "local_median_fps", "planet_max_p95_frame_ms", "local_max_p95_frame_ms"):
        if not _positive_number(measurement.get(field)):
            errors.append(f"invalid preparation measurement: {field}")
    if measurement.get("relative_not_physical_device_fps") is not True:
        errors.append("software-WebGL measurements must remain relative")
    if measurement.get("console_errors") != 0:
        errors.append("preparation proof contains browser console errors")

    package = result.get("acceptance_package", {})
    if package.get("release_manifest_sha256") != "4902bf3777c9700eb54da10fb16aa491b135480655bc6171ff724e460b3c3916":
        errors.append("release manifest hash mismatch")
    if package.get("release_files") != RELEASE_FILES:
        errors.append("release file inventory or hash mismatch")
    if package.get("bundle_sizes") != {
        "browser_js_gzip_bytes": 292234,
        "browser_css_gzip_bytes": 10054,
        "server_bundle_gzip_bytes": 16914,
        "browser_total_output_bytes": 1139665,
    }:
        errors.append("release bundle-size evidence mismatch")
    if package.get("receipt_contract") != {
        "maximum_body_bytes": 1000000,
        "file_mode": "0600",
        "fixed_manual_check_inventory": True,
        "virtual_list_bound_required": True,
        "engine_authorization_forbidden": True,
        "production_architecture_authorization_forbidden": True,
        "same_origin_required": True,
        "maximum_receipt_files": 100,
    }:
        errors.append("receipt contract must remain fail-closed")
    security = package.get("security_headers", {})
    if set(security) != {
        "content_security_policy",
        "same_origin_connect_only",
        "same_origin_or_blob_workers_only",
        "frame_ancestors_none",
        "referrer_policy_no_referrer",
        "content_type_nosniff",
        "sensors_and_payment_disabled",
    } or not all(value is True for value in security.values()):
        errors.append("security-header evidence must remain complete")

    service = package.get("service", {})
    expected_service = {
        "unit": "commonworld-device-acceptance.service",
        "binding_scope": "tailscale_ipv4_only",
        "active": True,
        "restart_count": 0,
        "loopback_listener": False,
        "public_ingress": False,
        "result_directory_private": True,
        "no_new_privileges": True,
        "protect_system_strict": True,
        "protect_home_read_only": True,
        "private_tmp": True,
        "restricted_address_families": ["AF_UNIX", "AF_INET", "AF_INET6"],
        "authentication_boundary": "tailnet_membership_only",
        "application_authentication": False,
        "state_snapshot_checked_at": "2026-07-11",
        "continuous_health_not_claimed": True,
    }
    if service != expected_service:
        errors.append("installed service evidence or tailnet boundary mismatch")

    manual = result.get("manual_acceptance_gate", {})
    checks = manual.get("required_checks", [])
    if len(checks) != len(MANUAL_CHECKS) or set(checks) != MANUAL_CHECKS:
        errors.append("manual acceptance check inventory mismatch")
    if manual.get("all_checks_pending") is not True:
        errors.append("manual physical checks must remain pending")
    for field in (
        "physical_mobile_safari_tested",
        "physical_mobile_chrome_tested",
        "hardware_gpu_tested",
        "real_voiceover_or_talkback_tested",
        "real_background_tab_roundtrip_tested",
    ):
        if manual.get(field) is not False:
            errors.append(f"unproven physical claim must remain false: {field}")

    decision = result.get("decision", {})
    if decision.get("engine_selected") is not False:
        errors.append("device pack must not select a production engine")
    if decision.get("production_architecture_authorized") is not False:
        errors.append("device pack must not authorize production architecture")
    if decision.get("next_action") != "execute_physical_device_and_assistive_technology_acceptance":
        errors.append("next action must remain physical device acceptance")
    if len(decision.get("forbidden_interpretations", [])) != 5:
        errors.append("forbidden interpretation inventory mismatch")

    artifacts = result.get("evidence_artifacts", {})
    for field, expected in ARTIFACT_HASHES.items():
        value = str(artifacts.get(field, ""))
        if value != expected or not SHA256_RE.fullmatch(value):
            errors.append(f"device acceptance artifact hash mismatch: {field}")
    if artifacts.get("archive_role") != "local_non_product_research_archive":
        errors.append("device acceptance archive role mismatch")

    combined = result_path.read_text(encoding="utf-8")
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        combined += "\n" + report
        for token in (
            "physische Geräte- und Assistenztechnikabnahme ist noch nicht erfolgt",
            "höchstens 17 Zeilen",
            "Tailnet-only-Bindung",
            "crypto.getRandomValues()",
            "engine_selected",
            "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"device acceptance report missing boundary token: {token}")
    for pattern in PRIVATE_ENDPOINT_PATTERNS:
        if pattern.search(combined):
            errors.append(f"private endpoint leaked into repository evidence: {pattern.pattern}")

    for relative in (
        "device-acceptance-pack",
        "proofs/device-acceptance",
        "spikes/device-acceptance",
        "docs/research/device-acceptance-screenshots",
    ):
        if (root / relative).exists():
            errors.append(f"raw device acceptance material must stay outside repository: {relative}")
    for public_file in ("index.html", "404.html"):
        path = root / public_file
        if path.is_file() and "device-acceptance-pack-v1" in path.read_text(encoding="utf-8"):
            errors.append(f"device acceptance research leaked into public shell: {public_file}")

    return errors


def main() -> int:
    errors = validate_device_acceptance_pack(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld device acceptance pack validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
