#!/usr/bin/env python3
"""Validate the rejected first physical run and the v2 rerun boundary."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/research/device-acceptance-rerun-v2.result.json"
REPORT = ROOT / "docs/research/device-acceptance-rerun-v2.md"
BASE_COMMIT = "e958560c8cd6373548af4fbf97a51a90f95d6c64"
EXPECTED_FINDINGS = [
    {"id": "three_automatic_runs_missing", "severity": "blocking"},
    {"id": "reduced_motion_not_active", "severity": "blocking"},
    {"id": "digital_sphere_screen_fixed", "severity": "blocking"},
    {"id": "manual_pass_conflicts_with_note", "severity": "blocking"},
    {"id": "background_interval_not_machine_bound", "severity": "nonblocking"},
]
HASHES = {
    "v2_archive_sha256": "068ecc3050d5900b34a1f80990ba9ce18131fd35924ced4652dd73b31a5a773c",
    "v2_preparation_proof_sha256": "79ebd4f8de00bd9d8f97aeafea6120c5aa631cd25a0cc4e4c53b754784bbd52b",
    "v2_installed_service_proof_sha256": "574bf5d04bfc7e9238eabf7e4f931229b5b4b48e547fff072713eaf8768474a3",
    "first_receipt_review_sha256": "ec35a118b30e4618583a6149227217c0ad2d6bcc6cad428091521b8d6603ec5c",
    "first_receipt_sha256": "08966f7fa788e6f4dd96735844f254d379320c5f0c864cb23ddecad18596b320",
    "v2_manifest_sha256": "66aa23a5d700ec7d35a40436483a1e5e711cf2a011df4bd020580629adc971a9",
}
RELEASE_MANIFEST_SHA256 = "2378646d2755aefbf5f56ac2a3e93407ac025960a4b02042e7731d985deaaa69"
SUPERSEDED_MANIFEST_SHA256 = "4902bf3777c9700eb54da10fb16aa491b135480655bc6171ff724e460b3c3916"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_ENDPOINT_PATTERNS = (
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.IGNORECASE),
)


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / RESULT.relative_to(ROOT)).read_text(encoding="utf-8"))


def validate_device_acceptance_rerun(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    result_path = root / RESULT.relative_to(ROOT)
    report_path = root / REPORT.relative_to(ROOT)
    if not result_path.is_file():
        return ["missing physical acceptance rerun result"]
    if not report_path.is_file():
        errors.append("missing physical acceptance rerun report")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"physical acceptance rerun result is invalid JSON: {error}"]

    if result.get("schema_version") != 1:
        errors.append("rerun schema_version must be 1")
    if result.get("kind") != "commonworld_device_acceptance_rerun_v2":
        errors.append("rerun kind mismatch")
    if result.get("status") != "first_physical_run_rejected_rerun_required":
        errors.append("first physical run must remain rejected and require rerun")
    if result.get("reviewed_at") != "2026-07-11":
        errors.append("rerun review date mismatch")
    if result.get("repository_base_commit") != BASE_COMMIT:
        errors.append("rerun result must remain base-commit bound")

    if result.get("scope") != {
        "public_surface_changed": False,
        "synthetic_data_only": True,
        "raw_receipt_in_repository": False,
        "device_identifier_in_repository": False,
        "private_endpoint_in_repository": False,
        "screenshots_in_repository": False,
        "tailnet_service_updated": True,
    }:
        errors.append("rerun publication boundary mismatch")

    first = result.get("first_physical_run", {})
    expected_first = {
        "device_class": "Apple WebKit touch device with hardware WebGL2",
        "manual_checks_marked_pass": 8,
        "automatic_performance_runs": 0,
        "reduced_motion_active": False,
        "background_interval_machine_verified": False,
        "digital_sphere_observation": "screen_fixed_size_instead_of_globe_relative_shell",
        "manual_note_conflict": True,
        "accepted": False,
        "receipt_sha256": HASHES["first_receipt_sha256"],
    }
    if first != expected_first:
        errors.append("first physical-run evidence mismatch or overclaim")
    if result.get("findings") != EXPECTED_FINDINGS:
        errors.append("physical finding inventory or severity mismatch")

    remediation = result.get("remediation_v2", {})
    expected_remediation = {
        "release_manifest_sha256": RELEASE_MANIFEST_SHA256,
        "supersedes_release_manifest_sha256": SUPERSEDED_MANIFEST_SHA256,
        "receipt_schema_version": 2,
        "digital_sphere_globe_relative": True,
        "overview_shell_ratio": 1.2,
        "overview_earth_radius_px": 188.4158305875921,
        "overview_shell_radius_px": 226.09899670511052,
        "local_sphere_hidden": True,
        "automatic_runs_required": 3,
        "all_manual_checks_must_be_complete": True,
        "background_minimum_hidden_ms": 10000,
        "reduced_motion_runtime_evidence_required": True,
        "failed_check_requires_note": True,
        "incomplete_save_blocked": True,
        "service_active_at_check": True,
        "continuous_health_not_claimed": True,
    }
    if remediation != expected_remediation:
        errors.append("v2 remediation evidence mismatch")
    ratio = remediation.get("overview_shell_ratio")
    earth = remediation.get("overview_earth_radius_px")
    shell = remediation.get("overview_shell_radius_px")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) for value in (ratio, earth, shell)):
        errors.append("v2 sphere geometry must be finite numeric evidence")
    elif not (1.15 <= float(ratio) <= 1.25 and abs(float(shell) / float(earth) - float(ratio)) < 1e-9):
        errors.append("v2 sphere shell must remain globe-relative at the proved ratio")

    if result.get("rerun_gate") != {
        "apple_webkit_rerun_pending": True,
        "android_chrome_independent_run_pending": True,
        "hardware_gpu_review_pending": True,
        "assistive_technology_review_pending": True,
        "real_background_roundtrip_pending": True,
    }:
        errors.append("physical rerun gates must remain pending")

    decision = result.get("decision", {})
    if decision.get("engine_selected") is not False:
        errors.append("rerun evidence must not select an engine")
    if decision.get("production_architecture_authorized") is not False:
        errors.append("rerun evidence must not authorize production architecture")
    if decision.get("next_action") != "rerun_physical_acceptance_with_v2_then_review_receipt":
        errors.append("next action must remain v2 physical rerun and receipt review")

    artifacts = result.get("evidence_artifacts", {})
    for field, expected in HASHES.items():
        value = str(artifacts.get(field, ""))
        if value != expected or not SHA256_RE.fullmatch(value):
            errors.append(f"rerun artifact hash mismatch: {field}")
    if artifacts.get("archive_role") != "local_non_product_research_archive":
        errors.append("rerun archive role mismatch")

    combined = result_path.read_text(encoding="utf-8")
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        combined += "\n" + report
        for token in (
            "nicht bestanden",
            "keine der drei verpflichtenden automatischen Messungen",
            "blieb optisch gleich groß",
            "Radius von exakt dem 1,2-Fachen",
            "unvollständige Läufe können nicht gespeichert werden",
            "engine_selected",
            "production_architecture_authorized",
        ):
            if token not in report:
                errors.append(f"rerun report missing boundary token: {token}")
    for pattern in PRIVATE_ENDPOINT_PATTERNS:
        if pattern.search(combined):
            errors.append(f"private endpoint leaked into rerun evidence: {pattern.pattern}")

    for public_file in ("index.html", "404.html"):
        path = root / public_file
        if path.is_file() and "device-acceptance-rerun-v2" in path.read_text(encoding="utf-8"):
            errors.append(f"rerun research leaked into public shell: {public_file}")
    for relative in (
        "docs/research/device-acceptance-rerun-v2-receipt.json",
        "docs/research/device-acceptance-rerun-v2-screenshots",
        "device-acceptance-rerun-v2",
    ):
        if (root / relative).exists():
            errors.append(f"private rerun material must stay outside repository: {relative}")

    return errors


def main() -> int:
    errors = validate_device_acceptance_rerun(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld physical device rerun validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
