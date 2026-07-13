#!/usr/bin/env python3
"""Validate Commonworld's bounded production delivery/provider decision."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("contracts/commonworld/production-delivery-provider.contract.json")
VERTICAL = Path("contracts/commonworld/public-maplibre-vertical-slice.contract.json")
RESULT = Path("docs/research/production-delivery-provider-v1.result.json")
STYLE = Path("assets/map/openfreemap-liberty.json")
CATALOG = Path("catalog/catalog.json")
PAGES_DOC = Path("docs/ops/pages-dns.md")
EXPECTED_ACCEPTANCE = {
    "production-current-state",
    "production-provider-criteria",
    "production-decision",
    "production-failure-path",
    "production-no-implicit-migration",
}
EXPECTED_OPTIONS = {
    "openfreemap_public_instance",
    "openfreemap_self_hosted",
    "maptiler_custom_cloud",
    "protomaps_pmtiles_self_hosted",
}


def _load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _https_origin(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _style_origins(value: object) -> set[str]:
    origins: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            origins.update(_style_origins(child))
    elif isinstance(value, list):
        for child in value:
            origins.update(_style_origins(child))
    elif isinstance(value, str) and value.startswith("https://"):
        origin = _https_origin(value)
        if origin:
            origins.add(origin)
    return origins


def validate_production_delivery_provider(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = (CONTRACT, VERTICAL, RESULT, STYLE, CATALOG, PAGES_DOC, Path("docs/research/evidence/public-maplibre-vertical-slice-v1.catalog.json"))
    for path in required:
        if not (root / path).is_file():
            errors.append(f"missing production decision file: {path}")
    if errors:
        return errors
    try:
        contract = _load(root, CONTRACT)
        vertical = _load(root, VERTICAL)
        result = _load(root, RESULT)
        style = _load(root, STYLE)
        catalog = _load(root, CATALOG)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"production decision JSON invalid: {exc}"]

    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_production_delivery_provider_contract":
        errors.append("production decision schema or kind mismatch")
    if contract.get("status") != "authorized_bounded_production":
        errors.append("production decision must be bounded and authorized")
    authority = contract.get("authority", {})
    if authority.get("id") != "commonworld-project-operator" or not authority.get("decision_source"):
        errors.append("production decision must name its authority and source")

    scope = contract.get("scope", {})
    if scope.get("backend_authorized") is not False or scope.get("accounts_authorized") is not False or scope.get("sensitive_transactions_authorized") is not False:
        errors.append("bounded static production must not authorize backend, accounts or sensitive transactions")

    delivery = contract.get("delivery", {})
    expected_delivery = {
        "selected": "github_pages_static",
        "production_authorized": True,
        "source_branch": "main",
        "source_path": "/",
        "custom_domain": "commonworld.net",
        "https_required": True,
        "published_site_size_limit_gib": 1,
        "deployment_timeout_minutes": 10,
        "soft_bandwidth_limit_gib_per_month": 100,
        "rate_limiting_possible": True,
        "service_level_agreement_claimed": False,
    }
    for key, expected in expected_delivery.items():
        if delivery.get(key) != expected:
            errors.append(f"production delivery boundary mismatch: {key}")

    basemap = contract.get("basemap", {})
    expected_basemap = {
        "selected": "openfreemap_public_instance",
        "runtime_origin": "https://tiles.openfreemap.org",
        "production_authorized": True,
        "critical_dependency": False,
        "service_level": "best_effort_without_sla",
        "service_level_agreement_claimed": False,
        "warranty_claimed": False,
        "personalized_support_claimed": False,
        "api_key_required": False,
        "continuity_guarantee_claimed": False,
        "data_freshness_guarantee_claimed": False,
    }
    for key, expected in expected_basemap.items():
        if basemap.get(key) != expected:
            errors.append(f"basemap provider boundary mismatch: {key}")
    privacy = basemap.get("privacy_boundary", {})
    if privacy.get("accounts") is not False or privacy.get("cookies") is not False:
        errors.append("OpenFreeMap privacy boundary must not invent accounts or cookies")
    if privacy.get("temporary_security_logging_possible") is not True or privacy.get("temporary_security_log_retention_days_max") != 30:
        errors.append("OpenFreeMap incident logging boundary missing")
    if privacy.get("cloudflare_processing_possible") is not True:
        errors.append("OpenFreeMap Cloudflare processing boundary missing")

    options = contract.get("option_comparison", [])
    option_ids = {entry.get("id") for entry in options if isinstance(entry, dict)}
    if option_ids != EXPECTED_OPTIONS:
        errors.append("provider option comparison is incomplete")
    selected = [entry.get("id") for entry in options if isinstance(entry, dict) and entry.get("decision") == "selected_now"]
    if selected != ["openfreemap_public_instance"]:
        errors.append("exactly the bounded OpenFreeMap public option must be selected")
    for entry in options:
        if not isinstance(entry, dict):
            errors.append("provider comparison entry must be an object")
            continue
        for axis in ("sla", "privacy", "attribution", "rate_limit", "direct_cost", "observability", "fallback", "data_freshness", "operational_burden"):
            if not entry.get(axis):
                errors.append(f"provider option {entry.get('id')} missing axis: {axis}")

    failure = contract.get("failure_contract", {})
    for key in ("provider_outage", "rate_limiting", "stale_tiles", "pages_failure", "dns_failure", "rollback", "backend_failover"):
        if not failure.get(key):
            errors.append(f"production failure contract missing: {key}")
    if "keep_linear_catalog" not in failure.get("provider_outage", ""):
        errors.append("provider outage must preserve the linear catalog")
    migration = contract.get("migration", {})
    if migration.get("authorized") is not False or migration.get("requires_separate_reviewed_task") is not True:
        errors.append("production decision must not implicitly authorize migration")

    origins = _style_origins(style)
    if origins != {basemap.get("runtime_origin")}:
        errors.append(f"style runtime origins differ from provider boundary: {sorted(origins)}")
    metadata = style.get("metadata", {})
    if metadata.get("commonworld:provider") != "openfreemap_public_instance":
        errors.append("style metadata provider mismatch")

    vertical_basemap = vertical.get("basemap", {})
    vertical_decision = vertical.get("decision_boundary", {})
    if scope.get("predecessor_contract") != VERTICAL.as_posix():
        errors.append("production decision must name the historical vertical-slice predecessor")
    snapshot = scope.get("predecessor_catalog_snapshot")
    if snapshot != "docs/research/evidence/public-maplibre-vertical-slice-v1.catalog.json":
        errors.append("production decision must name the frozen predecessor catalog")
    elif not (root / snapshot).is_file():
        errors.append("frozen predecessor catalog is missing")
    if vertical_basemap.get("service_level_agreement_claimed") is not False or vertical_basemap.get("production_provider_commitment") is not False:
        errors.append("historical vertical slice must retain its pre-production provider boundary")
    if vertical_decision.get("production_architecture_authorized") is not False or vertical_decision.get("production_provider_selected") is not False:
        errors.append("historical vertical-slice decision must not be rewritten")

    publication = catalog.get("publication", {})
    if publication.get("production_architecture_authorized") is not True:
        errors.append("public catalog does not publish bounded production authorization")
    if publication.get("production_delivery") != "github_pages_static":
        errors.append("public catalog production delivery mismatch")
    if publication.get("basemap_provider_boundary") != "openfreemap_public_best_effort_noncritical":
        errors.append("public catalog basemap boundary mismatch")

    if result.get("verdict") != "pass" or result.get("decision") != "authorize_github_pages_with_noncritical_openfreemap_best_effort_boundary":
        errors.append("production decision result is not PASS")
    statuses = {entry.get("id"): entry.get("status") for entry in result.get("acceptance", []) if isinstance(entry, dict)}
    if set(statuses) != EXPECTED_ACCEPTANCE or any(status != "pass" for status in statuses.values()):
        errors.append("production decision result acceptance is incomplete")
    if result.get("migration_authorized") is not False:
        errors.append("production result must not authorize migration")

    pages_doc = (root / PAGES_DOC).read_text(encoding="utf-8")
    for phrase in ("Bounded production authorization", "100 GiB", "noncritical dependency", "separate reviewed task"):
        if phrase not in pages_doc:
            errors.append(f"Pages operations contract missing production boundary: {phrase}")
    return errors


def main() -> int:
    errors = validate_production_delivery_provider(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld production delivery/provider validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
