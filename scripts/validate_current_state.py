#!/usr/bin/env python3
"""Validate the single current Commonworld operational truth against live repository contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import date
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path("contracts/commonworld/current-state.contract.json")
CATALOG_PATH = Path("catalog/catalog.json")
PROVIDER_PATH = Path("contracts/commonworld/production-delivery-provider.contract.json")
VERTICAL_SLICE_PATH = Path("contracts/commonworld/public-maplibre-vertical-slice.contract.json")
DIGITAL_RING_PATH = Path("contracts/commonworld/digital-ring-taxonomy.contract.json")
CATALOG_PLATFORM_PATH = Path("contracts/commonworld/catalog-platform.contract.json")
APP_PATH = Path("assets/commonworld-app.js")
LE_NID_PATH = Path("catalog/projects/cltb-le-nid.json")
SECURITY_POLICY_PATH = Path("SECURITY.md")
SECURITY_TXT_PATH = Path(".well-known/security.txt")
JEKYLL_CONFIG_PATH = Path("_config.yml")
PRODUCTION_READBACK_PATH = Path("scripts/verify_pages_deployment.py")
PRODUCTION_READBACK_WORKFLOW_PATH = Path(".github/workflows/production-readback.yml")
SECURITY_EXPIRY_WORKFLOW_PATH = Path(".github/workflows/security-policy-expiry.yml")


def _load(root: Path, relative: Path) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_current_state(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in (STATE_PATH, CATALOG_PATH, PROVIDER_PATH, VERTICAL_SLICE_PATH, DIGITAL_RING_PATH, CATALOG_PLATFORM_PATH, APP_PATH, LE_NID_PATH, SECURITY_POLICY_PATH, SECURITY_TXT_PATH, JEKYLL_CONFIG_PATH, PRODUCTION_READBACK_PATH, PRODUCTION_READBACK_WORKFLOW_PATH, SECURITY_EXPIRY_WORKFLOW_PATH):
        if not (root / relative).is_file():
            errors.append(f"missing current-state dependency: {relative}")
    if errors:
        return errors

    try:
        state = _load(root, STATE_PATH)
        catalog = _load(root, CATALOG_PATH)
        provider = _load(root, PROVIDER_PATH)
        vertical = _load(root, VERTICAL_SLICE_PATH)
        digital_ring = _load(root, DIGITAL_RING_PATH)
        catalog_platform = _load(root, CATALOG_PLATFORM_PATH)
        app = (root / APP_PATH).read_text(encoding="utf-8")
        le_nid = _load(root, LE_NID_PATH)
        production_readback = (root / PRODUCTION_READBACK_PATH).read_text(encoding="utf-8")
        production_readback_workflow = (root / PRODUCTION_READBACK_WORKFLOW_PATH).read_text(encoding="utf-8")
        security_expiry_workflow = (root / SECURITY_EXPIRY_WORKFLOW_PATH).read_text(encoding="utf-8")
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

    if state.get("activity_status_policy") != {
        "public_states": ["active", "paused", "seasonal", "unknown", "ended"],
        "unknown_semantics": "documented_practice_current_operation_not_timely_verified",
        "unknown_review_max_days": 45,
        "unknown_public_notice_required": True,
    }:
        errors.append("current public activity-status policy mismatch")

    digital_records = []
    digital_themes = set()
    for relative in catalog.get("project_files", []):
        if not isinstance(relative, str) or not relative.startswith("projects/") or ".." in relative:
            continue
        record_path = root / "catalog" / relative
        if not record_path.is_file():
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("presence", {}).get("digital", {}).get("available") is True:
            digital_records.append(record)
            digital_themes.update(theme for theme in record.get("themes", []) if isinstance(theme, str))
        if any(key in record for key in ("layer", "derived_layer", "presentation_layer", "semantic_zoom", "digital_path")):
            errors.append(f"current catalog record must not store presentation taxonomy fields: {relative}")
    digital_ring_state = state.get("digital_ring_taxonomy", {})
    expected_digital_ring_static = {
        "contract": "contracts/commonworld/digital-ring-taxonomy.contract.json",
        "version": "digital-ring-bundles-v1",
        "canonical_url_parameter": "digital_path",
        "main_field_count": 5,
        "legacy_layer_links": "preserved_as_filter_until_explicit_digital_path_selection",
        "invalid_path_behavior": "fail_closed_to_sphere_root_without_partial_filter",
        "catalog_presentation_fields_forbidden": True,
    }
    for key, expected in expected_digital_ring_static.items():
        if digital_ring_state.get(key) != expected:
            errors.append(f"current digital ring taxonomy static truth mismatch: {key}")
    expected_digital_ring_keys = set(expected_digital_ring_static) | {
        "current_digital_identity_count",
        "current_known_theme_count",
    }
    if set(digital_ring_state) != expected_digital_ring_keys:
        errors.append("current digital ring taxonomy field inventory mismatch")
    if digital_ring.get("version") != expected_digital_ring_static["version"]:
        errors.append("digital ring taxonomy contract version must match current state")
    if len([node for node in digital_ring.get("nodes", []) if node.get("parent_id") == "sphere" and node.get("type") == "field"]) != 5:
        errors.append("digital ring taxonomy contract must expose five current fields")
    if digital_ring_state.get("current_digital_identity_count") != len(digital_records):
        errors.append("current catalog digital identity count does not match current state")
    if digital_ring_state.get("current_known_theme_count") != len(digital_themes):
        errors.append("current catalog digital theme count does not match current state")

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

    security_disclosure = state.get("security_disclosure", {})
    expected_security_disclosure = {
        "confidential_channel": "github_private_vulnerability_reporting",
        "private_vulnerability_reporting_enabled": True,
        "contact": "https://github.com/heimgewebe/commonworld/security/advisories/new",
        "repository_policy": "SECURITY.md",
        "public_discovery": ".well-known/security.txt",
        "public_discovery_url": "https://commonworld.net/.well-known/security.txt",
        "public_issues_confidential": False,
        "exact_production_readback": True,
        "host_configuration": "_config.yml includes only .well-known",
        "expiry_monitoring": "github_actions_weekly_best_effort",
        "scheduled_workflow_inactivity_boundary_days": 60,
        "manual_reenable_required_after_automatic_disablement": True,
        "trust_boundary": "repository_review_and_github_settings_not_self_attested",
    }
    if security_disclosure != expected_security_disclosure:
        errors.append("current security-disclosure truth mismatch")
    if '.well-known/security.txt' not in production_readback:
        errors.append("current production readback does not include security.txt")
    if (root / JEKYLL_CONFIG_PATH).read_text(encoding="utf-8") != "include:\n  - .well-known\n":
        errors.append("current host configuration does not publish only .well-known")
    if "--verify-live-setting" not in production_readback_workflow or "steps.security_setting.outcome != 'success'" not in production_readback_workflow:
        errors.append("current production readback does not enforce private vulnerability reporting")
    expiry_markers = ('cron: "17 5 * * 1"', "python3 scripts/validate_security_policy.py", "--verify-live-setting", "steps.security_setting.outcome != 'success'")
    if any(marker not in security_expiry_workflow for marker in expiry_markers):
        errors.append("current security-expiry workflow mismatch")

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

    catalog_delivery = state.get("catalog_delivery", {})
    expected_catalog_delivery = {
        "contract": "contracts/commonworld/catalog-delivery-budget.contract.json",
        "design": "compact_build_bound_bootstrap_with_generation_bound_selected_detail_shadow",
        "canonical_records": "catalog/projects/*.json",
        "startup_project_json_requests": 0,
        "runtime_catalogue_parity_check": True,
        "runtime_catalogue_parity_scope": "selected_identity_compact_shard_and_generation_bound_detail_shadow",
        "runtime_catalogue_visible_source": "compact_build_bound_bootstrap",
        "runtime_catalogue_detail_loading": True,
        "runtime_catalogue_detail_strategy": "content_addressed_shard_descriptor",
        "runtime_catalogue_cache_limits": {"shards": 8, "details": 16},
        "runtime_catalogue_selection_states": ["idle", "loading", "retrying", "ready", "mismatch", "degraded"],
        "runtime_catalogue_failure_policy": "keep_compact_bootstrap",
        "bootstrap_asset_failure_policy": "keep_generated_linear_catalogue",
        "runtime_catalogue_retry_policy": "reload_platform_and_clear_shadow_caches",
        "runtime_catalogue_cutover_authorized": False,
        "build_and_ci_catalogue_parity_check": True,
        "no_javascript_projection": "generated_static_catalogue_preserved_until_successful_interactive_start",
        "redesign_trigger": "measured_transfer_parse_or_dom_budget_not_entry_count_alone",
    }
    if catalog_delivery != expected_catalog_delivery:
        errors.append("current catalog-delivery truth mismatch")

    transition = catalog_platform.get("browser_transition", {})
    shadow = transition.get("shadow_runtime_observation", {})
    if transition.get("current_visible_catalog") != catalog_delivery.get("runtime_catalogue_visible_source"):
        errors.append("catalog platform and current state disagree on visible catalogue source")
    if shadow != {
        "aggregate_manifest": True,
        "selected_identity_shard": True,
        "selected_identity_detail": True,
    }:
        errors.append("catalog platform shadow-observation truth mismatch")
    if shadow.get("selected_identity_shard") is not catalog_delivery.get("runtime_catalogue_parity_check"):
        errors.append("catalog platform and current state disagree on runtime catalogue parity")
    if shadow.get("selected_identity_detail") is not catalog_delivery.get("runtime_catalogue_detail_loading"):
        errors.append("catalog platform and current state disagree on detail loading")
    if transition.get("selection_states") != catalog_delivery.get("runtime_catalogue_selection_states"):
        errors.append("catalog platform and current state disagree on detail selection states")
    runtime_cache = catalog_platform.get("runtime_cache", {})
    if {
        "shards": runtime_cache.get("shards_max_entries"),
        "details": runtime_cache.get("details_max_entries"),
    } != catalog_delivery.get("runtime_catalogue_cache_limits"):
        errors.append("catalog platform and current state disagree on runtime catalogue cache limits")
    if transition.get("cutover_authorized") is not catalog_delivery.get("runtime_catalogue_cutover_authorized"):
        errors.append("catalog platform and current state disagree on bootstrap cutover authorization")
    if (
        runtime_cache.get("explicit_retry_refresh") != "reload_manifest_aggregate_and_clear_shard_detail_caches"
        or catalog_delivery.get("runtime_catalogue_retry_policy") != "reload_platform_and_clear_shadow_caches"
    ):
        errors.append("catalog platform and current state disagree on fresh retry policy")
    if (
        transition.get("aggregate_failure_policy") != "keep_compact_bootstrap_and_mark_degraded"
        or transition.get("shard_failure_policy") != "keep_compact_bootstrap_and_mark_selected_identity_degraded"
        or transition.get("detail_failure_policy") != "keep_compact_bootstrap_and_offer_selected_identity_fresh_platform_retry"
        or catalog_delivery.get("runtime_catalogue_failure_policy") != "keep_compact_bootstrap"
    ):
        errors.append("catalog platform and current state disagree on runtime fallback policy")

    detail_projection = catalog_platform.get("public_projection", {}).get("details", {})
    if detail_projection.get("strategy") != "content-addressed-shard-descriptors":
        errors.append("catalog platform detail strategy mismatch")
    if detail_projection.get("mutable_identity_path_for_runtime_loading") is not False:
        errors.append("catalog runtime detail path must be immutable and content-addressed")
    if transition.get("selected_detail_parity") != "content_addressed_schema_boundary_and_compact_projection_parity":
        errors.append("catalog platform selected-detail parity boundary mismatch")
    detail_boundary = catalog_platform.get("detail_validation_boundary", {})
    if detail_boundary.get("browser_reimplements_complete_json_schema") is not False:
        errors.append("catalog browser boundary must not claim a complete JSON Schema reimplementation")
    if detail_boundary.get("visible_data_replacement") is not False:
        errors.append("catalog detail shadow must not replace visible bootstrap data")

    required_runtime_tokens = (
        "createCatalogLoadCache",
        "loadCatalogShard",
        "loadCatalogDetail",
        "function observeCatalogRecordShadow(",
        "function loadCatalogShardOnce(",
        "function loadCatalogDetailOnce(",
        "function retryCatalogDetailShadow(",
        "observeCatalogPlatform({ retryIdentifier: identifier, forceRefresh: true })",
        "dataset.catalogDelivery = 'build-bound-bootstrap'",
        "catalogDetailShadow",
        "document.querySelector('#text-skip-link')",
        "target.hash = 'text-view'",
        "document.querySelector('[data-static-catalog-fallback]')?.remove()",
    )
    for token in required_runtime_tokens:
        if token not in app:
            errors.append(f"current runtime does not implement declared catalog shadow truth: {token}")

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
        "docs/research/digital-sphere-v1.contract.json": "f0aaab7c259880b8cffc849d0e305d35a64f59ee76638e06da33a843ec28af7c",
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
    try:
        current_as_of = date.fromisoformat(str(state.get("current_as_of", "")))
    except ValueError:
        current_as_of = None
    if current_as_of is None or current_as_of < date(2026, 7, 28):
        errors.append("current-state date does not cover the security-disclosure and catalog-shard truth")
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
