#!/usr/bin/env python3
"""Validate the single current Commonworld operational truth against live repository contracts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path("contracts/commonworld/current-state.contract.json")
CATALOG_PATH = Path("catalog/catalog.json")
PROVIDER_PATH = Path("contracts/commonworld/production-delivery-provider.contract.json")
VERTICAL_SLICE_PATH = Path("contracts/commonworld/public-maplibre-vertical-slice.contract.json")
LE_NID_PATH = Path("catalog/projects/cltb-le-nid.json")


def _load(root: Path, relative: Path) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_current_state(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in (STATE_PATH, CATALOG_PATH, PROVIDER_PATH, VERTICAL_SLICE_PATH, LE_NID_PATH):
        if not (root / relative).is_file():
            errors.append(f"missing current-state dependency: {relative}")
    if errors:
        return errors

    try:
        state = _load(root, STATE_PATH)
        catalog = _load(root, CATALOG_PATH)
        provider = _load(root, PROVIDER_PATH)
        vertical = _load(root, VERTICAL_SLICE_PATH)
        le_nid = _load(root, LE_NID_PATH)
    except (OSError, json.JSONDecodeError) as error:
        return [f"current-state dependency is invalid: {error}"]

    if state.get("schema_version") != 2 or state.get("kind") != "commonworld_current_public_state":
        errors.append("current-state schema or kind mismatch")
    precedence = state.get("precedence", {})
    if precedence.get("current_operational_truth") != "this contract":
        errors.append("current-state precedence must identify this contract")
    if "do not override" not in precedence.get("historical_evidence", ""):
        errors.append("historical evidence must be explicitly non-overriding")

    public = state.get("public_surface", {})
    if public != {
        "url": "https://commonworld.net/",
        "default_presentation": "globe",
        "equivalent_text_presentation": True,
        "no_javascript_catalog": True,
        "machine_surface": "static_read_only",
    }:
        errors.append("current public-surface truth mismatch")

    renderer = state.get("renderer", {})
    if renderer != {
        "selected": True,
        "engine": "maplibre_gl_js",
        "version": "5.24.0",
        "public_runtime_uses_selected_engine": True,
    }:
        errors.append("current renderer truth mismatch")

    production = state.get("production", {})
    expected_production = {
        "architecture_authorized": True,
        "delivery": "github_pages_static",
        "basemap_provider_selected": True,
        "basemap_provider": "openfreemap_public_best_effort_noncritical",
        "provider_sla_claimed": False,
        "automatic_failover": False,
        "backend": False,
        "accounts": False,
        "write_path": False,
    }
    if production != expected_production:
        errors.append("current production truth mismatch")

    release = state.get("release_gates", {})
    expected_release = {
        "deterministic_build_and_tests": "pass",
        "public_shell_and_catalog_validation": "pass",
        "physical_android_chrome_current_globe_first_surface": "pass_operator_attestation",
        "github_required_check": "pass",
        "live_pages_smoke": "pass",
        "android_reduced_motion": "not_claimed",
        "screen_reader_product_support": "not_claimed",
    }
    if release != expected_release:
        errors.append("current release-gate truth mismatch")

    publication = catalog.get("publication", {})
    if publication.get("production_architecture_authorized") is not True:
        errors.append("catalog and current state disagree on production authorization")
    if publication.get("selected_engine") != renderer.get("engine"):
        errors.append("catalog and current state disagree on renderer")
    if publication.get("production_delivery") != production.get("delivery"):
        errors.append("catalog and current state disagree on production delivery")
    if publication.get("basemap_provider_boundary") != production.get("basemap_provider"):
        errors.append("catalog and current state disagree on basemap provider boundary")

    if provider.get("status") != "authorized_bounded_production":
        errors.append("provider contract and current state disagree on authorization")
    delivery = provider.get("delivery", {})
    basemap = provider.get("basemap", {})
    if delivery.get("selected") != production.get("delivery") or delivery.get("production_authorized") is not True:
        errors.append("provider contract and current state disagree on delivery")
    expected_basemap = "openfreemap_public_instance"
    if basemap.get("selected") != expected_basemap or basemap.get("production_authorized") is not True:
        errors.append("provider contract and current state disagree on basemap provider")
    if basemap.get("service_level_agreement_claimed") is not False:
        errors.append("provider contract must not claim a basemap SLA")

    boundary = vertical.get("decision_boundary", {})
    for key, expected in {
        "engine_selected": True,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
        "production_architecture_authorized": True,
        "production_provider_selected": True,
        "screen_reader_product_support_claimed": False,
    }.items():
        if boundary.get(key) != expected:
            errors.append(f"vertical-slice current boundary mismatch: {key}")

    historical = state.get("historical_evidence", [])
    actual_historical = {
        entry.get("path"): entry.get("sha256")
        for entry in historical
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    expected_historical = {
        "contracts/commonworld/renderer-selection.contract.json": "15c76c0875d42e4f670f6513d97804cf0805a054057cf74c0f99798f6432fd8a",
        "contracts/commonworld/digital-sphere.contract.json": "f0aaab7c259880b8cffc849d0e305d35a64f59ee76638e06da33a843ec28af7c",
        "docs/research/public-maplibre-vertical-slice-v1.result.json": "8f60b0baec90520a9e1b961c7d5453c0fe87da29f7ecf9132836475ff4cb95e6",
    }
    if actual_historical != expected_historical:
        errors.append("current-state historical evidence inventory or digest mismatch")
    for relative, digest in expected_historical.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"current-state historical evidence missing: {relative}")
        elif _sha256(path) != digest:
            errors.append(f"current-state historical evidence was rewritten: {relative}")

    licensing = state.get("licensing", {})
    le_nid_registry_source_ids = sorted(
        source.get("id")
        for source in le_nid.get("provenance", {}).get("sources", [])
        if isinstance(source, dict) and source.get("type") == "public-registry"
    )
    geographic_source_ids = {
        source_id
        for location in le_nid.get("presence", {}).get("geographic", [])
        if isinstance(location, dict)
        for source_id in location.get("source_ids", [])
        if isinstance(source_id, str)
    }
    if (
        le_nid_registry_source_ids != ["osm-le-nid-address", "osm-le-nid-building"]
        or not set(le_nid_registry_source_ids).issubset(geographic_source_ids)
    ):
        errors.append("current licensing source IDs must resolve to the published Le Nid registry sources")
    if licensing != {
        "code": "AGPL-3.0-only",
        "catalogue_data_default": "CC0-1.0",
        "catalogue_data_exceptions": [
            {
                "scope": "catalog/projects/cltb-le-nid.json#presence.geographic",
                "source_ids": ["osm-le-nid-address", "osm-le-nid-building"],
                "licence": "ODbL-1.0",
                "attribution": "© OpenStreetMap contributors",
            }
        ],
        "third_party_assets_retain_their_own_licences": True,
    }:
        errors.append("current licensing truth mismatch")
    if state.get("current_as_of") != "2026-07-15":
        errors.append("current-state date does not cover the mixed catalogue licensing truth")
    if not (root / "LICENSE").is_file() or not (root / "LICENSE-DATA.md").is_file():
        errors.append("declared code and data licences must exist")

    return errors


def main() -> int:
    errors = validate_current_state(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld current operational state validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
