#!/usr/bin/env python3
"""Validate the canonical aggregation and semantic zoom derivation contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "aggregation-zoom.contract.json"
PROJECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"

LEVELS = ("planet", "macroregion", "region", "local", "focus")
DIGITAL_LEVELS = ("sphere", "field", "network", "identity")


def load_contract(root: Path = ROOT) -> dict:
    return json.loads((root / CONTRACT_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))


def load_project_schema(root: Path = ROOT) -> dict:
    return json.loads((root / PROJECT_SCHEMA_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))


def public_record(record: dict, contract: dict) -> bool:
    state = record.get("curation", {}).get("state")
    return state in contract["publication_eligibility"]["public_curation_states"]


def density_record(record: dict, contract: dict) -> bool:
    eligibility = contract["publication_eligibility"]
    return (
        record.get("curation", {}).get("state") in eligibility["density_curation_states"]
        and record.get("activity", {}).get("status") in eligibility["density_activity_states"]
    )


def unique_identity_ids(identity_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(identity_ids)))


def theme_counts(records: Iterable[dict]) -> dict[str, int]:
    members: dict[str, set[str]] = {}
    for record in records:
        project_id = record["id"]
        for theme in set(record.get("themes", [])):
            members.setdefault(theme, set()).add(project_id)
    return {theme: len(ids) for theme, ids in sorted(members.items())}


def coverage_zero_meaning(state: str, contract: dict) -> str:
    return contract["coverage"]["zero_interpretation"][state]


def public_spatial_representation(location: dict, contract: dict) -> dict | None:
    mode = location.get("mode")
    rules = contract["uncertainty_and_privacy"]
    if mode == "hidden":
        return None
    if mode == "exact":
        return {"mode": mode, "geometry": location.get("geometry"), "rule": rules["exact"]}
    if mode == "approximate":
        return {
            "mode": mode,
            "geometry": location.get("geometry"),
            "uncertainty_meters_min": location.get("uncertainty_meters_min"),
            "rule": rules["approximate"],
        }
    return None


def identity_channels(record: dict) -> tuple[str, ...]:
    channels: list[str] = []
    geographic = record.get("presence", {}).get("geographic", [])
    if any(location.get("mode") in {"exact", "approximate"} for location in geographic if isinstance(location, dict)):
        channels.append("geographic")
    if record.get("presence", {}).get("digital", {}).get("available"):
        channels.append("digital")
    return tuple(channels)


def _enum(schema: dict, definition: str, property_name: str) -> set[str]:
    return set(schema["$defs"][definition]["properties"][property_name]["enum"])


def validate_semantic_zoom(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path, label in ((CONTRACT_PATH, "aggregation zoom contract"), (PROJECT_SCHEMA_PATH, "CommonProject schema")):
        if not (root / path.relative_to(ROOT)).is_file():
            errors.append(f"missing {label}")
    if errors:
        return errors

    try:
        contract = load_contract(root)
        project_schema = load_project_schema(root)
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid aggregation zoom contract input: {error}"]

    if contract.get("schema_version") != 1:
        errors.append("aggregation zoom schema_version must be 1")
    source = contract.get("source_contract", {})
    if source.get("schema_version") != 4 or source.get("identity_key") != "CommonProject.id":
        errors.append("aggregation zoom contract must bind to CommonProject v4 identity")

    aggregation = contract.get("aggregation_unit", {})
    expected_aggregation = {
        "name": "commonproject_identity",
        "bucket_count_rule": "one_identity_at_most_once_per_bucket",
        "global_count_rule": "one_identity_at_most_once_in_global_totals",
        "multi_anchor_rule": "anchors_select_spatial_buckets_but_never_multiply_identity_count_within_one_bucket",
        "theme_count_rule": "one_identity_at_most_once_per_theme_per_bucket",
        "dual_presence_rule": "one_identity_with_geographic_and_digital_representations",
    }
    for key, expected in expected_aggregation.items():
        if aggregation.get(key) != expected:
            errors.append(f"aggregation unit {key} must be {expected}")

    eligibility = contract.get("publication_eligibility", {})
    schema_curation = _enum(project_schema, "curation", "state")
    schema_activity = _enum(project_schema, "activity", "status")
    public_curation = set(eligibility.get("public_curation_states", []))
    excluded_curation = set(eligibility.get("excluded_public_curation_states", []))
    density_curation = set(eligibility.get("density_curation_states", []))
    density_activity = set(eligibility.get("density_activity_states", []))
    non_density_activity = set(eligibility.get("visible_but_not_density_activity_states", []))
    if public_curation | excluded_curation != schema_curation or public_curation & excluded_curation:
        errors.append("public and excluded curation states must be disjoint and cover the CommonProject enum")
    if not density_curation or not density_curation <= public_curation:
        errors.append("density curation states must be a non-empty subset of public states")
    if density_activity | non_density_activity != schema_activity or density_activity & non_density_activity:
        errors.append("density and non-density activity states must be disjoint and cover the CommonProject enum")
    if eligibility.get("stale_visible_but_not_density") is not True or "stale" not in public_curation or "stale" in density_curation:
        errors.append("stale records must remain public but must not raise current density")

    intensity = contract.get("intensity", {})
    if intensity.get("unit") != "unique_identities_per_10000_assessed_km2":
        errors.append("geographic intensity must use normalized unique identity density")
    if intensity.get("normalization_area") != "assessed_surface_km2":
        errors.append("density must normalize only by assessed surface")
    if not intensity.get("spatial_extent_is_separate_geometry_signal"):
        errors.append("spatial extent must remain separate from density intensity")
    if "raw_anchor_count" not in intensity.get("forbidden_meanings", []):
        errors.append("raw anchor count must be forbidden as intensity")
    if intensity.get("density_allowed_for_coverage_states") != ["assessed"]:
        errors.append("normalized density must be restricted to fully assessed coverage")
    if intensity.get("partial_coverage_output") != "lower_bound_identity_count_without_density":
        errors.append("partial coverage must expose only a lower-bound count, never normalized density")
    if intensity.get("unassessed_coverage_output") != "unknown_without_zero_or_density":
        errors.append("unassessed coverage must expose neither zero nor normalized density")

    coverage = contract.get("coverage", {})
    if tuple(coverage.get("states", [])) != ("assessed", "partial", "unassessed"):
        errors.append("coverage states must distinguish assessed, partial and unassessed")
    expected_zero = {
        "assessed": "supported_low_density",
        "partial": "catalog_lower_bound_only",
        "unassessed": "unknown_not_zero",
    }
    if coverage.get("zero_interpretation") != expected_zero:
        errors.append("coverage zero meanings must not collapse missing data into low density")
    if not coverage.get("must_not_infer_from_catalog_absence"):
        errors.append("coverage must not be inferred from catalog absence")
    if set(coverage.get("evidence_required_for", [])) != {"assessed", "partial"}:
        errors.append("assessed and partial coverage must require explicit evidence")

    digital_coverage = contract.get("digital_coverage", {})
    if tuple(digital_coverage.get("states", [])) != ("curated_scope", "partial_scope", "unknown_scope"):
        errors.append("digital coverage must distinguish curated, partial and unknown scope")
    for name in (
        "must_name_assessed_universe",
        "must_not_claim_global_completeness_without_defined_universe",
        "must_not_infer_from_catalog_absence",
        "no_geographic_area_denominator",
    ):
        if digital_coverage.get(name) is not True:
            errors.append(f"digital coverage invariant must be true: {name}")

    privacy = contract.get("uncertainty_and_privacy", {})
    if privacy.get("hidden") != "exclude_from_spatial_buckets_and_geometry_but_allow_nonspatial_totals":
        errors.append("hidden locations must remain outside spatial aggregation")
    if "without_sharpening" not in privacy.get("approximate", ""):
        errors.append("approximate locations must never be sharpened")
    if not privacy.get("aggregate_must_not_enable_reverse_inference"):
        errors.append("aggregates must prevent privacy reverse inference")
    if privacy.get("small_count_suppression_required_when_privacy_would_be_weakened") is not True:
        errors.append("privacy-sensitive small aggregates must support suppression or coarsening")

    clusters = contract.get("clusters", {})
    if clusters.get("aggregation_member_key") != "CommonProject.id":
        errors.append("clusters must use CommonProject identity")
    if clusters.get("semantic_clusters_dissolve_on_entry_to") != "local":
        errors.append("semantic clusters must dissolve on entry to local level")
    if clusters.get("local_exception") != "transient_screen_collision_group_only":
        errors.append("local clusters may only remain for transient screen collision")
    if not clusters.get("hidden_locations_never_join_geographic_clusters"):
        errors.append("hidden locations must never join geographic clusters")
    if clusters.get("count_rule") != "unique_identity_count_not_anchor_count":
        errors.append("cluster counts must use identities rather than anchors")
    if clusters.get("transient_group_must_expose_member_identity_ids") is not True:
        errors.append("transient collision groups must expose their member identities")

    relations = contract.get("relations", {})
    for name in (
        "no_inferred_relations",
        "aggregate_only_evidenced_source_relations",
        "local_threads_require_known_visible_endpoints",
        "hidden_endpoint_must_not_be_relocated_or_revealed",
    ):
        if relations.get(name) is not True:
            errors.append(f"relation invariant must be true: {name}")

    output_shapes = contract.get("output_shapes", {})
    required_shapes = {
        "coverage_field",
        "density_field",
        "identity_cluster",
        "identity_summary",
        "public_representation",
        "relation_summary",
        "collision_group",
        "focus_record",
        "digital_coverage_summary",
        "theme_distribution",
        "reach_distribution",
        "network_summary",
    }
    if set(output_shapes) != required_shapes:
        errors.append("aggregation contract output shapes must match the canonical transport-neutral set")
    for shape_name, required_fields in {
        "coverage_field": {"bucket_id", "coverage_state", "observed_at", "evidence_refs"},
        "density_field": {"bucket_id", "unique_identity_count", "assessed_surface_km2", "identities_per_10000_km2", "theme_identity_counts"},
        "identity_cluster": {"cluster_id", "member_identity_ids", "unique_identity_count", "public_geometry"},
        "identity_summary": {"project_id", "title", "kind", "themes", "activity_status", "curation_state", "public_representations"},
        "relation_summary": {"source_project_id", "target_project_id", "relation_type", "source_ids"},
        "focus_record": {"commonproject"},
        "digital_coverage_summary": {"coverage_state", "scope_label", "observed_at", "evidence_refs"},
        "network_summary": {"summary_id", "unique_identity_count", "evidenced_relation_count", "theme_identity_counts"},
    }.items():
        if set(output_shapes.get(shape_name, {}).get("required", [])) != required_fields:
            errors.append(f"output shape {shape_name} must retain its canonical required fields")
    if output_shapes.get("density_field", {}).get("allowed_coverage_states") != ["assessed"]:
        errors.append("density output shape must be restricted to assessed coverage")
    if output_shapes.get("identity_cluster", {}).get("member_key") != "CommonProject.id":
        errors.append("identity cluster members must use CommonProject.id")
    if output_shapes.get("public_representation", {}).get("approximate_requires") != ["public_geometry", "uncertainty_meters_min"]:
        errors.append("approximate public representations must carry geometry and minimum uncertainty")
    if output_shapes.get("focus_record", {}).get("exactly_one_identity") is not True:
        errors.append("focus output shape must contain exactly one identity")
    digital_shape = output_shapes.get("digital_coverage_summary", {})
    if digital_shape.get("geographic_area_forbidden") is not True:
        errors.append("digital coverage output must forbid geographic area denominators")
    if set(digital_shape.get("evidence_required_for", [])) != {"curated_scope", "partial_scope"}:
        errors.append("digital coverage output must require evidence for curated and partial scope")
    if digital_shape.get("unknown_scope_must_not_claim_assessed_universe") is not True:
        errors.append("unknown digital scope must not claim an assessed universe")
    network_shape = output_shapes.get("network_summary", {})
    if network_shape.get("member_identity_ids_forbidden") is not True:
        errors.append("aggregate network summaries must not expose full member identity lists")
    if "member_identity_ids" in network_shape.get("required", []):
        errors.append("aggregate network summary required fields must not contain member identity ids")

    levels = contract.get("levels", [])
    if tuple(level.get("id") for level in levels) != LEVELS:
        errors.append("semantic zoom levels must be planet, macroregion, region, local and focus")
    by_level = {level.get("id"): level for level in levels}
    expected_level_shapes = {
        "planet": ["coverage_field", "density_field", "theme_distribution", "digital_coverage_summary"],
        "macroregion": ["coverage_field", "density_field", "theme_distribution", "network_summary"],
        "region": ["identity_cluster", "public_representation", "relation_summary", "identity_summary"],
        "local": ["identity_summary", "public_representation", "relation_summary", "collision_group"],
        "focus": ["focus_record"],
    }
    for level_id, shape_refs in expected_level_shapes.items():
        if by_level.get(level_id, {}).get("shape_refs") != shape_refs:
            errors.append(f"semantic zoom level {level_id} must bind to its canonical output shapes")
    if "individual_markers" not in by_level.get("planet", {}).get("forbidden", []):
        errors.append("planet level must forbid individual markers")
    if "semantic_clusters" not in by_level.get("local", {}).get("forbidden", []):
        errors.append("local level must forbid semantic clusters")
    if by_level.get("focus", {}).get("identity_detail") != "exactly_one_complete_record":
        errors.append("focus must resolve to exactly one complete CommonProject record")

    digital_levels = contract.get("digital_levels", [])
    if tuple(level.get("id") for level in digital_levels) != DIGITAL_LEVELS:
        errors.append("digital zoom levels must be sphere, field, network and identity")
    expected_digital_shapes = {
        "sphere": ["digital_coverage_summary", "theme_distribution", "reach_distribution", "network_summary"],
        "field": ["digital_coverage_summary", "theme_distribution", "network_summary"],
        "network": ["identity_summary", "relation_summary"],
        "identity": ["focus_record"],
    }
    for level in digital_levels:
        level_id = level.get("id")
        if "invented_coordinates" not in level.get("forbidden", []):
            errors.append(f"digital level {level_id} must forbid invented coordinates")
        if level.get("shape_refs") != expected_digital_shapes.get(level_id):
            errors.append(f"digital level {level_id} must bind to its canonical output shapes")

    invariants = contract.get("cross_view_invariants", {})
    for name in (
        "same_filters_same_identity_set",
        "linear_view_uses_same_derived_result",
        "focus_record_is_source_commonproject",
        "no_manual_zoom_assignment_in_commonproject",
        "no_renderer_specific_pixels_or_engine_types",
    ):
        if invariants.get(name) is not True:
            errors.append(f"cross-view invariant must be true: {name}")

    return errors


def main() -> int:
    errors = validate_semantic_zoom(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld aggregation and semantic zoom contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
