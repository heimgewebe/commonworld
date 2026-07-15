#!/usr/bin/env python3
"""Validate the T006 real geographic and hybrid Commons vertical slice."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("contracts/commonworld/real-hybrid-commons.contract.json")
RESEARCH_PATH = Path("docs/research/real-hybrid-commons-v1.result.json")
CURRENT_STATE_PATH = Path("contracts/commonworld/current-state.contract.json")
EXPECTED_PROJECTS = ("cltb-le-nid", "freifunk-hamburg", "freifunk")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _location(record: dict, identifier: str) -> dict | None:
    values = record.get("presence", {}).get("geographic", [])
    if not isinstance(values, list):
        return None
    return next(
        (value for value in values if isinstance(value, dict) and value.get("id") == identifier),
        None,
    )


def _node_projection(root: Path) -> tuple[dict | None, str | None]:
    script = """
import fs from 'node:fs';
import {
  MAX_MAP_ZOOM,
  evidencedRelations,
  publicMapFeatureCollection,
} from './assets/commonworld-core.mjs';

const manifest = JSON.parse(fs.readFileSync('./catalog/catalog.json', 'utf8'));
const records = manifest.project_files.map((path) =>
  JSON.parse(fs.readFileSync('./catalog/' + path, 'utf8'))
);
console.log(JSON.stringify({
  geojson: publicMapFeatureCollection(records),
  relations: evidencedRelations(records),
  maximum_map_zoom: MAX_MAP_ZOOM,
}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as error:
        return None, f"invalid Node projection output: {error}"


def validate_real_hybrid_commons(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required_files = {
        "contract": root / CONTRACT_PATH,
        "research result": root / RESEARCH_PATH,
        "current state": root / CURRENT_STATE_PATH,
        "manifest": root / "catalog/catalog.json",
        "Le Nid record": root / "catalog/projects/cltb-le-nid.json",
        "Freifunk Hamburg record": root / "catalog/projects/freifunk-hamburg.json",
        "Freifunk parent record": root / "catalog/projects/freifunk.json",
        "core runtime": root / "assets/commonworld-core.mjs",
        "application runtime": root / "assets/commonworld-app.js",
        "public shell": root / "index.html",
        "data licence": root / "LICENSE-DATA.md",
    }
    for label, path in required_files.items():
        if not path.is_file():
            errors.append(f"missing T006 {label}: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        contract = _load(required_files["contract"])
        research = _load(required_files["research result"])
        current_state = _load(required_files["current state"])
        manifest = _load(required_files["manifest"])
        records = {
            identifier: _load(root / "catalog/projects" / f"{identifier}.json")
            for identifier in EXPECTED_PROJECTS
        }
    except (OSError, json.JSONDecodeError) as error:
        return [f"T006 control or catalog data is invalid: {error}"]

    if contract.get("schema_version") != 1:
        errors.append("T006 contract schema mismatch")
    le_nid = records["cltb-le-nid"]
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
        errors.append("T006 ODbL exception source IDs must resolve to Le Nid registry-backed geometry")
    expected_licensing = {
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
    }
    if (
        current_state.get("schema_version") != 2
        or current_state.get("current_as_of") != "2026-07-15"
        or current_state.get("licensing") != expected_licensing
    ):
        errors.append("T006 canonical current-state licensing does not preserve the ODbL geometry exception")
    if contract.get("source_contract") != {
        "id": "https://commonworld.net/contracts/commonworld/project.schema.json",
        "schema_version": 3,
        "identity_key": "CommonProject.id",
    }:
        errors.append("T006 source contract binding mismatch")
    if contract.get("catalog_validation") != {
        "production_validator": "scripts/validate_public_catalog.py",
        "seed_regression_validator": "scripts/validate_public_seed_baseline.py",
        "vertical_slice_validator": "scripts/validate_real_hybrid_commons.py",
        "production_allows_kinds": ["geographic", "digital", "hybrid"],
        "production_source_types": ["official-source", "public-registry"],
        "seed_constraints_do_not_apply_to_new_records": True,
    }:
        errors.append("T006 validator separation contract mismatch")

    map_contract = contract.get("map_derivation", {})
    if map_contract.get("geojson_source_id") != "commonworld-public-representations":
        errors.append("T006 GeoJSON source identifier mismatch")
    if map_contract.get("feature_identity_property") != "project_id":
        errors.append("T006 feature identity property mismatch")
    if (
        map_contract.get("hidden_locations_excluded") is not True
        or map_contract.get("invented_coordinates_forbidden") is not True
    ):
        errors.append("T006 hidden-location or invented-coordinate protection missing")
    semantic_zoom = contract.get("semantic_zoom", {})
    if semantic_zoom.get("catalog_zoom_assignment_forbidden") is not True:
        errors.append("T006 semantic zoom must remain presentation-only")
    if (
        semantic_zoom.get("maximum_map_zoom") != 18
        or semantic_zoom.get("building_inspection_zoom") != 18
    ):
        errors.append("T006 map must permit reviewed building geometry inspection at zoom 18")
    local_level = next(
        (level for level in semantic_zoom.get("levels", []) if level.get("id") == "local"),
        {},
    )
    if local_level.get("maximum_zoom_inclusive") != 18:
        errors.append("T006 local semantic zoom must cover the complete map zoom range")
    cross_view = contract.get("cross_view", {})
    if cross_view.get("selection_key") != "CommonProject.id":
        errors.append("T006 cross-view identity key mismatch")
    if cross_view.get("selection_does_not_mutate_filters") is not True:
        errors.append("T006 project selection must remain independent from discovery filters")

    files = set(manifest.get("project_files", []))
    for identifier in ("cltb-le-nid", "freifunk-hamburg"):
        if f"projects/{identifier}.json" not in files:
            errors.append(f"T006 public catalog is missing {identifier}")

    hamburg = records["freifunk-hamburg"]
    if le_nid.get("kind") != "geographic":
        errors.append("T006 Le Nid must be one geographic CommonProject")
    if (
        hamburg.get("kind") != "hybrid"
        or hamburg.get("presence", {}).get("digital", {}).get("available") is not True
    ):
        errors.append("T006 Freifunk Hamburg must be one hybrid CommonProject with digital presence")

    exact = _location(le_nid, "cltb-le-nid-entrance")
    extent = _location(le_nid, "cltb-le-nid-building")
    approximate = _location(hamburg, "freifunk-hamburg-community-area")
    hidden = _location(hamburg, "freifunk-hamburg-private-routers")
    geometry_evidence = research.get("geometry_evidence", {})
    expected_point = geometry_evidence.get("cltb_le_nid", {}).get("address_point")
    expected_polygon = geometry_evidence.get("cltb_le_nid", {}).get("building_polygon")
    expected_hamburg = geometry_evidence.get("freifunk_hamburg", {}).get("community_point")

    if (
        not exact
        or exact.get("mode") != "exact"
        or exact.get("geometry") != {"type": "Point", "coordinates": expected_point}
    ):
        errors.append("T006 Le Nid exact public anchor differs from reviewed research evidence")
    if (
        not extent
        or extent.get("mode") != "exact"
        or extent.get("geometry") != {"type": "Polygon", "coordinates": expected_polygon}
    ):
        errors.append("T006 Le Nid public extent differs from reviewed registry evidence")
    if (
        not approximate
        or approximate.get("mode") != "approximate"
        or approximate.get("geometry") != {"type": "Point", "coordinates": expected_hamburg}
    ):
        errors.append(
            "T006 Freifunk Hamburg approximate community anchor differs from official API evidence"
        )
    if not approximate or approximate.get("uncertainty_meters_min") != 5000:
        errors.append(
            "T006 Freifunk Hamburg must preserve at least five kilometres of declared uncertainty"
        )
    if (
        not hidden
        or hidden.get("mode") != "hidden"
        or "geometry" in hidden
        or "uncertainty_meters_min" in hidden
    ):
        errors.append(
            "T006 private router locations must remain hidden without geometry or replacement precision"
        )

    relations = hamburg.get("relations", [])
    expected_relation = next(
        (
            relation
            for relation in relations
            if relation.get("target_id") == "freifunk"
            and relation.get("type") == "chapter-of"
        ),
        None,
    )
    if not expected_relation or not expected_relation.get("source_ids"):
        errors.append(
            "T006 Freifunk Hamburg must retain an evidenced chapter-of relation to Freifunk"
        )

    projection, projection_error = _node_projection(root)
    if projection_error:
        errors.append(f"T006 core projection failed: {projection_error}")
    elif projection is not None:
        if projection.get("maximum_map_zoom") != contract.get("semantic_zoom", {}).get("maximum_map_zoom"):
            errors.append("T006 runtime map zoom limit differs from the reviewed contract")
        features = projection.get("geojson", {}).get("features", [])
        expected_feature_ids = [
            "cltb-le-nid:cltb-le-nid-entrance",
            "cltb-le-nid:cltb-le-nid-building",
            "freifunk-hamburg:freifunk-hamburg-community-area",
        ]
        if [feature.get("id") for feature in features] != expected_feature_ids:
            errors.append(
                "T006 public GeoJSON must contain exactly the reviewed point, extent and approximate anchor"
            )
        if any(
            feature.get("properties", {}).get("location_id")
            == "freifunk-hamburg-private-routers"
            for feature in features
        ):
            errors.append("T006 hidden router location leaked into public GeoJSON")
        if any(
            feature.get("properties", {}).get("project_id")
            not in {"cltb-le-nid", "freifunk-hamburg"}
            for feature in features
        ):
            errors.append("T006 public GeoJSON contains an unexpected project identity")
        projected_relations = projection.get("relations", [])
        if not any(
            relation.get("source_project_id") == "freifunk-hamburg"
            and relation.get("target_project_id") == "freifunk"
            and relation.get("relation_type") == "chapter-of"
            for relation in projected_relations
        ):
            errors.append("T006 evidenced relation is missing from core projection")

    app = required_files["application runtime"].read_text(encoding="utf-8")
    core = required_files["core runtime"].read_text(encoding="utf-8")
    shell = required_files["public shell"].read_text(encoding="utf-8")
    licence = required_files["data licence"].read_text(encoding="utf-8")

    for token in (
        "publicMapFeatureCollection",
        "evidencedRelations",
        "recordLocationSummaries",
        "recordPresentationLabel",
        "semanticLocationLine",
        "semanticZoomLevel",
    ):
        if f"function {token}" not in core:
            errors.append(f"T006 core runtime missing derivation function: {token}")
    if "maxZoom: MAX_MAP_ZOOM" not in app:
        errors.append("T006 MapLibre runtime does not use the shared reviewed zoom limit")
    for token in (
        "commonworld-public-representations",
        "commonworld-public-extents",
        "commonworld-approximate-anchors",
        "commonworld-exact-anchors",
        "publicMapFeatureCollection",
        "semanticLocationLine",
        "MAX_MAP_ZOOM",
    ):
        if token not in app:
            errors.append(f"T006 application runtime missing map or semantic integration: {token}")
    for token in (
        'id="semantic-level"',
        'id="semantic-summary"',
        'id="focus-locations"',
        'id="focus-relations"',
    ):
        if token not in shell:
            errors.append(f"T006 public shell missing cross-view location surface: {token}")
    for token in ("OpenStreetMap contributors", "ODbL", "260066697", "13966522352"):
        if token not in licence:
            errors.append(f"T006 data licence missing public-registry attribution: {token}")
    verification = research.get("implementation_verification", {})
    catalog_evidence = verification.get("catalog", {})
    browser_evidence = verification.get("final_browser_verification", {})
    privacy_evidence = verification.get("privacy_readback", {})
    regression_evidence = verification.get("regression", {})
    source_evidence = verification.get("source_availability", {})
    final_tree_evidence = verification.get("final_tree_validation", {})
    if (
        research.get("status") != "verified_for_publication"
        or research.get("checked_at") != "2026-07-15"
        or verification.get("observed_at") != "2026-07-15"
        or catalog_evidence.get("entry_count") != 12
        or catalog_evidence.get("public_map_feature_ids") != expected_feature_ids
        or catalog_evidence.get("hidden_router_in_geojson") is not False
        or catalog_evidence.get("selection_does_not_mutate_filters") is not True
        or catalog_evidence.get("maximum_map_zoom") != 18
        or browser_evidence.get("scenarios") != {"passed": 12, "failed": 0}
        or browser_evidence.get("receipt_sha256") != "045ad89fed016e005c1a11d097980bce92b908609a4692b9e88651453ddd5ba4"
        or privacy_evidence.get("hidden_geometry") is not False
        or privacy_evidence.get("hidden_precision") is not False
        or privacy_evidence.get("hidden_router_in_map_diagnostics") is not False
        or privacy_evidence.get("private_maplibre_fields_used") is not False
        or regression_evidence.get("python_tests") != {"passed": 355, "failed": 0}
        or regression_evidence.get("javascript_tests") != {"passed": 22, "failed": 0}
        or regression_evidence.get("make_validate") != "PASS"
        or source_evidence.get("successful_http_responses") != 6
        or final_tree_evidence.get("receipt_sha256") != "2a7c8dc84f7290153e37aeb60a3d6ff76b4f9cbbf7e6d67fb1e1bde8469d5e22"
        or final_tree_evidence.get("python_tests") != {"passed": 357, "failed": 0}
        or final_tree_evidence.get("javascript_tests") != {"passed": 22, "failed": 0}
        or final_tree_evidence.get("browser_scenarios") != {"passed": 12, "failed": 0}
        or final_tree_evidence.get("make_validate") != "PASS"
        or final_tree_evidence.get("git_diff_check") != "PASS"
        or final_tree_evidence.get("renderer_deterministic") is not True
        or final_tree_evidence.get("scope") != "implementation, contracts and tests before evidence-binding-only update"
        or verification.get("review_remediation", {}).get("status") != "fixed_and_regression_tested"
        or verification.get("review_remediation", {}).get("geometry_exception_licence") != "ODbL-1.0"
        or verification.get("review_remediation", {}).get("semantic_focus_status") != "fixed_and_regression_tested"
        or verification.get("review_remediation", {}).get("semantic_focus_validation_receipt_sha256")
        != "045ad89fed016e005c1a11d097980bce92b908609a4692b9e88651453ddd5ba4"
        or verification.get("review_remediation", {}).get("live_smoke_catalog_status") != "fixed_and_regression_tested"
        or verification.get("review_remediation", {}).get("live_smoke_catalog_validation_receipt_sha256")
        != "3e6d8cb2d346cfa9c8714d1c7cde1a419d41daacdce9881bc52797a0b240c54f"
        or verification.get("review_remediation", {}).get("live_smoke_publication_status")
        != "fixed_and_regression_tested"
        or verification.get("review_remediation", {}).get("licensing_source_id_status")
        != "fixed_and_regression_tested"
        or verification.get("review_remediation", {}).get("codex_followup_validation_receipt_sha256")
        != "2a7c8dc84f7290153e37aeb60a3d6ff76b4f9cbbf7e6d67fb1e1bde8469d5e22"
    ):
        errors.append(
            "T006 research result is not bound to the observed implementation evidence"
        )
    return errors


def main() -> int:
    errors = validate_real_hybrid_commons(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld real geographic and hybrid Commons validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
