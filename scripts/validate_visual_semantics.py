#!/usr/bin/env python3
"""Validate Commonworld's renderer-neutral visual semantics and research cases."""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "visual-semantics.contract.json"
PROJECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"
ZOOM_CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "aggregation-zoom.contract.json"
CASE_MATRIX_PATH = ROOT / "tests" / "cases" / "visual-semantics.real-cases.json"

FAMILY_IDS = (
    "ecology_land",
    "knowledge_data",
    "making_infrastructure",
    "care_provision",
)
COMMONS_TYPE_IDS = (
    "knowledge",
    "software",
    "culture",
    "food-seeds",
    "water",
    "energy",
    "housing-land",
    "health-care",
    "tools-repair",
    "community-network",
    "other",
)
COMMONS_TYPE_CODES = ("WD", "SI", "KM", "SE", "WB", "EN", "BW", "PG", "WR", "GN", "AN")
COVERAGE_STATES = ("assessed", "partial", "unassessed")
UNCERTAINTY_MODES = ("exact", "public_extent", "approximate", "hidden")
DENSITY_BANDS = (
    "positive_low",
    "positive_middle",
    "positive_high",
    "positive_exceptional",
)
PUBLIC_SURFACE_FILES = ("index.html", "404.html", "README.md")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract(root: Path = ROOT) -> dict[str, Any]:
    return _load_json(root / CONTRACT_PATH.relative_to(ROOT))


def load_cases(root: Path = ROOT) -> dict[str, Any]:
    return _load_json(root / CASE_MATRIX_PATH.relative_to(ROOT))


def _relative_luminance(hex_color: str) -> float:
    value = hex_color.removeprefix("#")
    if len(value) != 6:
        raise ValueError("color must be a six-digit hex token")
    channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def family_composition(support_counts: Mapping[str, int], contract: Mapping[str, Any]) -> str:
    """Resolve aggregate primary-family counts without inventing identity weights."""
    if not support_counts:
        raise ValueError("family support counts must not be empty")
    known = {family["id"] for family in contract["family_taxonomy"]["families"]}
    if set(support_counts) - known:
        raise ValueError("family support counts contain unknown family ids")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in support_counts.values()):
        raise ValueError("family support counts must be non-negative integer identity counts")
    total = sum(float(value) for value in support_counts.values())
    if total <= 0:
        raise ValueError("family support counts must contain a positive value")

    ranked = sorted(((family_id, float(value) / total) for family_id, value in support_counts.items()), key=lambda item: (-item[1], item[0]))
    top_id, top_share = ranked[0]
    second_share = ranked[1][1] if len(ranked) > 1 else 0.0
    rules = contract["family_taxonomy"]["composition"]
    epsilon = 1e-12
    if top_share + epsilon >= rules["dominant_share_min"] and top_share - second_share + epsilon >= rules["dominant_margin_min"]:
        return top_id
    return rules["mixed_style_id"]


def identity_family_style(assignment: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    """Resolve one identity from an evidence-reasoned primary family or explicit mixed state."""
    known = {family["id"] for family in contract["family_taxonomy"]["families"]}
    primary = assignment.get("primary_family")
    secondary = assignment.get("secondary_families", [])
    mixed = assignment.get("mixed_families", [])
    if primary is not None:
        if primary not in known or set(secondary) - known or primary in secondary or len(secondary) != len(set(secondary)):
            raise ValueError("identity family assignment contains invalid or duplicate families")
        if len(secondary) > contract["family_taxonomy"]["secondary_families_max"]:
            raise ValueError("identity family assignment has too many secondary families")
        if mixed:
            raise ValueError("identity assignment must not mix primary and mixed forms")
        return primary
    if secondary:
        raise ValueError("secondary families require a primary family")
    if len(mixed) != len(set(mixed)) or len(set(mixed)) < 2 or set(mixed) - known:
        raise ValueError("mixed identity assignment requires at least two known families")
    if len(set(mixed)) > contract["family_taxonomy"]["maximum_families_per_identity"]:
        raise ValueError("mixed identity assignment has too many families")
    return contract["family_taxonomy"]["composition"]["identity_without_defensible_primary"]


def weighted_density_thresholds(
    samples: list[tuple[float, float]],
    contract: Mapping[str, Any],
) -> tuple[float, float, float] | None:
    """Calculate snapshot thresholds from positive densities and assessed surface weights."""
    minimum = contract["density_legend"]["positive_sample_minimum_buckets"]
    if len(samples) < minimum:
        return None
    normalized: list[tuple[float, float]] = []
    for value, assessed_surface in samples:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError("density calibration samples must use positive numeric densities")
        if not isinstance(assessed_surface, (int, float)) or isinstance(assessed_surface, bool) or assessed_surface <= 0:
            raise ValueError("density calibration samples must use positive assessed surface weights")
        normalized.append((float(value), float(assessed_surface)))
    normalized.sort(key=lambda item: item[0])
    total_weight = sum(weight for _value, weight in normalized)
    quantiles = [entry["upper_weighted_quantile"] for entry in contract["density_legend"]["positive_bands"][:-1]]
    thresholds: list[float] = []
    cumulative = 0.0
    target_index = 0
    for value, weight in normalized:
        cumulative += weight
        while target_index < len(quantiles) and cumulative + 1e-12 >= quantiles[target_index] * total_weight:
            thresholds.append(value)
            target_index += 1
    if len(thresholds) != 3:
        raise ValueError("density calibration could not resolve canonical thresholds")
    return tuple(thresholds)


def density_band(
    value: float,
    positive_thresholds: tuple[float, float, float],
    eligible_bucket_count: int,
    contract: Mapping[str, Any],
) -> str:
    """Classify a raw assessed density using snapshot-frozen thresholds."""
    if value < 0:
        raise ValueError("density must not be negative")
    if value == 0:
        return contract["density_legend"]["zero_band"]["id"]
    if eligible_bucket_count < contract["density_legend"]["positive_sample_minimum_buckets"]:
        return contract["density_legend"]["insufficient_sample_output"]
    if len(positive_thresholds) != 3 or not (0 < positive_thresholds[0] <= positive_thresholds[1] <= positive_thresholds[2]):
        raise ValueError("positive density thresholds must be three ordered positive values")
    if value <= positive_thresholds[0]:
        return "positive_low"
    if value <= positive_thresholds[1]:
        return "positive_middle"
    if value <= positive_thresholds[2]:
        return "positive_high"
    return "positive_exceptional"


def coverage_texture(state: str, contract: Mapping[str, Any]) -> str:
    by_state = {entry["id"]: entry["interior_texture_role"] for entry in contract["coverage_semantics"]["states"]}
    return by_state[state]


def uncertainty_style(mode: str, contract: Mapping[str, Any]) -> tuple[str, str]:
    by_mode = {entry["id"]: entry for entry in contract["uncertainty_semantics"]["modes"]}
    entry = by_mode[mode]
    return entry["boundary_role"], entry["halo_role"]


def privacy_decision(scenario: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    """Return the fail-closed release action for one privacy scenario."""
    mode = scenario["mode"]
    policy = contract["privacy_release"]
    if mode == "hidden":
        return "nonspatial_only"
    if mode == "exact":
        return "release_exact_public"
    if mode == "public_extent":
        return "release_public_extent"
    if mode != "approximate":
        raise ValueError(f"unsupported privacy mode: {mode}")

    parent_available = bool(scenario.get("parent_available", False))
    diameter = scenario.get("bucket_effective_diameter_m")
    uncertainty = scenario.get("maximum_uncertainty_meters_min")
    if not isinstance(diameter, (int, float)) or not isinstance(uncertainty, (int, float)) or diameter <= 0 or uncertainty <= 0:
        return "coarsen" if parent_available else "withhold_numeric_value"
    minimum_diameter = policy["approximate_bucket_minimum_diameter_factor"] * uncertainty
    if diameter < minimum_diameter:
        return "coarsen" if parent_available else "withhold_numeric_value"

    k = policy["k_anonymity_min"]
    count = scenario.get("identity_count", 0)
    if not isinstance(count, int) or count < k:
        return "coarsen" if parent_available else "withhold_numeric_value"
    if scenario.get("complete_reference_cohort_selected") is not True:
        return "coarsen" if parent_available else "withhold_selected_and_complement"
    return "release_aggregate"


def _contains_forbidden_coordinate_key(value: Any) -> bool:
    if isinstance(value, dict):
        forbidden = {"coordinates", "latitude", "longitude", "lat", "lon", "lng"}
        if forbidden & set(value):
            return True
        return any(_contains_forbidden_coordinate_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_coordinate_key(item) for item in value)
    return False


def validate_visual_semantics(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required_files = (
        (CONTRACT_PATH, "visual semantics contract"),
        (PROJECT_SCHEMA_PATH, "CommonProject schema"),
        (ZOOM_CONTRACT_PATH, "aggregation zoom contract"),
        (CASE_MATRIX_PATH, "visual semantics case matrix"),
    )
    for relative, label in required_files:
        if not (root / relative.relative_to(ROOT)).is_file():
            errors.append(f"missing {label}")
    if errors:
        return errors

    try:
        contract = load_contract(root)
        cases_doc = load_cases(root)
        project_schema = _load_json(root / PROJECT_SCHEMA_PATH.relative_to(ROOT))
        zoom_contract = _load_json(root / ZOOM_CONTRACT_PATH.relative_to(ROOT))
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid visual semantics input: {error}"]

    if contract.get("schema_version") != 1:
        errors.append("visual semantics schema_version must be 1")
    sources = contract.get("source_contracts", {})
    if sources.get("commonproject", {}).get("schema_version") != 4:
        errors.append("visual semantics must bind to CommonProject v4")
    if sources.get("aggregation_zoom", {}).get("schema_version") != 1:
        errors.append("visual semantics must bind to aggregation zoom v1")
    if project_schema.get("properties", {}).get("schema_version", {}).get("const") != 4:
        errors.append("loaded CommonProject schema must remain version 4")
    if zoom_contract.get("schema_version") != 1:
        errors.append("loaded aggregation zoom contract must remain version 1")

    channels = contract.get("channel_separation", {})
    expected_channels = {
        "hue": "profile_selected_commons_classification",
        "lightness": "normalized_current_density",
        "interior_texture": "coverage_state",
        "boundary_and_halo": "location_precision_and_uncertainty",
        "geometry": "published_spatial_form",
        "text": "explicit_semantic_label_and_numeric_value",
    }
    for name, meaning in expected_channels.items():
        if channels.get(name) != meaning:
            errors.append(f"visual channel {name} must mean only {meaning}")
    for name in (
        "color_never_only_channel",
        "one_primary_meaning_per_visual_channel",
        "family_pattern_forbidden_to_reserve_texture_for_coverage",
        "red_green_good_bad_semantics_forbidden",
        "moral_quality_or_rank_forbidden",
    ):
        if channels.get(name) is not True:
            errors.append(f"visual channel invariant must be true: {name}")

    classification_profiles = contract.get("classification_profiles", {})
    if classification_profiles.get("active_public_geographic_profile") != "exclusive_commons_type_v1":
        errors.append("active public geographic classification profile must be exclusive_commons_type_v1")
    profiles = classification_profiles.get("profiles", [])
    active_profiles = [profile for profile in profiles if profile.get("id") == "exclusive_commons_type_v1"]
    if len(active_profiles) != 1:
        errors.append("visual semantics must define exactly one exclusive_commons_type_v1 profile")
    else:
        active_profile = active_profiles[0]
        values = active_profile.get("values", [])
        if tuple(value.get("id") for value in values) != COMMONS_TYPE_IDS:
            errors.append("active Commons type profile must match the canonical filter order")
        if tuple(value.get("code") for value in values) != COMMONS_TYPE_CODES:
            errors.append("active Commons type profile must define the canonical non-color codes")
        if len({value.get("fill_seed_dark_surface") for value in values}) != len(COMMONS_TYPE_IDS):
            errors.append("active Commons type profile must use distinct hue tokens")
        if active_profile.get("no_hue_blending") is not True:
            errors.append("active Commons type profile must forbid hue blending")
        if active_profile.get("text_label_required") is not True:
            errors.append("active Commons type profile must require full text labels")
        if active_profile.get("non_color_code_required") is not False:
            errors.append("active Commons type profile must not require map abbreviations")
        if active_profile.get("map_abbreviation_rendering") != "forbidden":
            errors.append("active Commons type profile must forbid map abbreviation rendering")
        if active_profile.get("accessible_text_equivalent_required") is not True:
            errors.append("active Commons type profile must require an accessible text equivalent")
        if active_profile.get("country_composition_rule") != "preserve_discrete_hues_as_proportional_stripes_without_blending":
            errors.append("active Commons type profile must preserve country composition hues as proportional stripes")
        if active_profile.get("coverage_texture_reserved") is not True:
            errors.append("active Commons type profile must reserve texture for coverage")
        reference_dark = active_profile.get("reference_dark_surface")
        minimum_contrast = active_profile.get("minimum_non_text_contrast_ratio")
        if reference_dark != "#111827" or minimum_contrast != 3.0:
            errors.append("active Commons type profile must use the canonical dark surface contrast rule")
        for value in values:
            try:
                ratio = contrast_ratio(value.get("fill_seed_dark_surface", ""), reference_dark)
            except (TypeError, ValueError):
                errors.append(f"Commons type {value.get('id')} must define a valid dark-surface hue token")
            else:
                if ratio < minimum_contrast:
                    errors.append(f"Commons type {value.get('id')} must meet dark-surface non-text contrast")
    family_profiles = [profile for profile in profiles if profile.get("id") == "commons_family_v1"]
    if len(family_profiles) != 1 or family_profiles[0].get("active_in_geographic_impressions_v1") is not False:
        errors.append("commons_family_v1 must remain an inactive research profile for geographic impressions v1")

    taxonomy = contract.get("family_taxonomy", {})
    families = taxonomy.get("families", [])
    if tuple(entry.get("id") for entry in families) != FAMILY_IDS:
        errors.append("visual family order and ids must remain canonical")
    hue_roles = [entry.get("hue_role") for entry in families]
    glyph_roles = [entry.get("non_color", {}).get("glyph_role") for entry in families]
    if len(set(hue_roles)) != len(FAMILY_IDS):
        errors.append("every Commons family must have a distinct hue role")
    if len(set(glyph_roles)) != len(FAMILY_IDS):
        errors.append("every Commons family must have a distinct non-color glyph role")
    palette_rules = taxonomy.get("palette_rules", {})
    light_surface = palette_rules.get("reference_light_surface")
    dark_surface = palette_rules.get("reference_dark_surface")
    minimum_contrast = palette_rules.get("minimum_non_text_contrast_ratio")
    if light_surface != "#FFFFFF" or dark_surface != "#111827" or minimum_contrast != 3.0:
        errors.append("palette reference surfaces and minimum non-text contrast must remain canonical")
    for name in (
        "fill_seed_is_not_text_color",
        "every_density_lightness_band_requires_contrast_test",
        "family_distinction_still_requires_glyph_and_text",
    ):
        if palette_rules.get(name) is not True:
            errors.append(f"palette invariant must be true: {name}")
    for entry in families:
        if not entry.get("semantic_scope"):
            errors.append(f"visual family {entry.get('id')} must define semantic scope")
        if entry.get("non_color", {}).get("text_label_required") is not True:
            errors.append(f"visual family {entry.get('id')} must require a text label")
        if "pattern" in entry.get("non_color", {}):
            errors.append(f"visual family {entry.get('id')} must not consume the coverage texture channel")
        tokens = entry.get("palette_tokens", {})
        try:
            light_contrast = contrast_ratio(tokens.get("fill_seed_light_surface", ""), light_surface)
            dark_contrast = contrast_ratio(tokens.get("fill_seed_dark_surface", ""), dark_surface)
        except (TypeError, ValueError):
            errors.append(f"visual family {entry.get('id')} must define valid light and dark fill seed colors")
        else:
            if light_contrast < minimum_contrast or dark_contrast < minimum_contrast:
                errors.append(f"visual family {entry.get('id')} fill seeds must meet non-text contrast on reference surfaces")
    composition = taxonomy.get("composition", {})
    if composition.get("dominant_share_min") != 0.6 or composition.get("dominant_margin_min") != 0.2:
        errors.append("family dominance must require 60 percent share and 20 point margin")
    if composition.get("mixed_style_id") != "mixed_cross_domain" or composition.get("mixed_hue_role") != "neutral":
        errors.append("mixed family composition must use the neutral mixed style")
    try:
        mixed_light_contrast = contrast_ratio(composition.get("mixed_fill_seed_light_surface", ""), light_surface)
        mixed_dark_contrast = contrast_ratio(composition.get("mixed_fill_seed_dark_surface", ""), dark_surface)
    except (TypeError, ValueError):
        errors.append("mixed family composition must define valid light and dark fill seed colors")
    else:
        if mixed_light_contrast < minimum_contrast or mixed_dark_contrast < minimum_contrast:
            errors.append("mixed family fill seeds must meet non-text contrast on reference surfaces")
    if composition.get("no_hue_blending") is not True:
        errors.append("semantic family hues must never be blended")
    if composition.get("applies_to") != "aggregate_primary_family_identity_counts":
        errors.append("family dominance percentages must apply only to measured aggregate primary-family counts")
    if composition.get("identity_without_defensible_primary") != "mixed_cross_domain":
        errors.append("identities without a defensible primary family must use the mixed style")
    if composition.get("identity_secondary_families_use_non_color_glyphs") is not True:
        errors.append("identity secondary families must use non-color glyphs")
    if taxonomy.get("numeric_identity_family_weights_forbidden") is not True:
        errors.append("numeric family weights on individual Commons must be forbidden")
    if taxonomy.get("secondary_families_max") != 2:
        errors.append("identity family assignments may expose at most two secondary families")

    density = contract.get("density_legend", {})
    if density.get("basis") != zoom_contract.get("intensity", {}).get("unit"):
        errors.append("visual density legend must use the aggregation contract density unit")
    if density.get("eligible_coverage_state") != "assessed":
        errors.append("comparative density bands must be restricted to assessed coverage")
    if density.get("positive_sample_minimum_buckets") != 20:
        errors.append("comparative density banding must require at least 20 eligible buckets")
    if density.get("weighting") != "assessed_surface_km2":
        errors.append("density quantiles must be weighted by assessed surface")
    calibration = density.get("calibration_population", {})
    if calibration.get("grid") != "non_overlapping_equal_area_reference_cells" or calibration.get("nominal_cell_area_km2") != 10000:
        errors.append("density thresholds must use non-overlapping 10,000 km² equal-area reference cells")
    if calibration.get("threshold_population_id_required") is not True:
        errors.append("density threshold calibration population must have a snapshot identifier")
    if calibration.get("nested_display_buckets_excluded_from_threshold_sample") is not True:
        errors.append("nested display buckets must not distort the density threshold sample")
    bands = density.get("positive_bands", [])
    if tuple(entry.get("id") for entry in bands) != DENSITY_BANDS:
        errors.append("positive density bands must remain low, middle, high and exceptional")
    if [entry.get("upper_weighted_quantile") for entry in bands] != [0.25, 0.75, 0.95, 1.0]:
        errors.append("density bands must use the canonical weighted quantiles")
    thresholds = density.get("threshold_rules", {})
    if thresholds.get("weighted_quantile_rule") != "smallest_value_whose_cumulative_assessed_surface_reaches_or_exceeds_quantile_times_total_weight":
        errors.append("weighted density quantiles must use the canonical cumulative-surface rule")
    for name in (
        "computed_from_positive_assessed_buckets_only",
        "frozen_in_catalog_snapshot_metadata",
        "same_thresholds_across_geographic_zoom_levels_for_snapshot",
        "numeric_thresholds_visible_in_legend",
        "duplicate_thresholds_collapse_adjacent_bands",
        "threshold_rounding_must_not_change_raw_values",
        "cross_snapshot_recalibration_must_be_labeled",
    ):
        if thresholds.get(name) is not True:
            errors.append(f"density threshold invariant must be true: {name}")
    if density.get("visual_channel") != "monotonic_lightness_within_family_hue":
        errors.append("density must use monotonic lightness within the family hue")

    coverage = contract.get("coverage_semantics", {})
    coverage_entries = coverage.get("states", [])
    if tuple(entry.get("id") for entry in coverage_entries) != COVERAGE_STATES:
        errors.append("coverage visual states must be assessed, partial and unassessed")
    textures = [entry.get("interior_texture_role") for entry in coverage_entries]
    if len(set(textures)) != len(COVERAGE_STATES):
        errors.append("coverage states must use distinct interior textures")
    for name in (
        "text_label_required",
        "texture_roles_must_be_distinct",
        "privacy_withheld_is_not_coverage_state",
        "catalog_absence_must_not_select_texture",
        "color_must_not_encode_coverage",
    ):
        if coverage.get(name) is not True:
            errors.append(f"coverage invariant must be true: {name}")

    uncertainty = contract.get("uncertainty_semantics", {})
    uncertainty_entries = uncertainty.get("modes", [])
    if tuple(entry.get("id") for entry in uncertainty_entries) != UNCERTAINTY_MODES:
        errors.append("uncertainty modes must be exact, public_extent, approximate and hidden")
    by_mode = {entry.get("id"): entry for entry in uncertainty_entries}
    if by_mode.get("approximate", {}).get("boundary_role") != "dashed_boundary":
        errors.append("approximate geometry must use a dashed uncertainty boundary")
    if by_mode.get("approximate", {}).get("halo_minimum_radius_source") != "uncertainty_meters_min":
        errors.append("approximate halo must preserve the declared minimum uncertainty")
    if by_mode.get("hidden", {}).get("spatial_geometry_forbidden") is not True:
        errors.append("hidden locations must forbid spatial geometry")
    for name in (
        "coverage_uses_interior_uncertainty_uses_boundary",
        "approximate_geometry_must_not_be_sharpened",
        "hidden_location_has_no_map_substitute",
    ):
        if uncertainty.get(name) is not True:
            errors.append(f"uncertainty invariant must be true: {name}")

    privacy = contract.get("privacy_release", {})
    if privacy.get("k_anonymity_min") != 5:
        errors.append("privacy-sensitive aggregate release must require k=5")
    if privacy.get("approximate_bucket_minimum_diameter_factor") != 2.0:
        errors.append("approximate aggregate diameter must be at least twice maximum contributor uncertainty")
    for name in (
        "exact_public_geometry_exempt",
        "hidden_spatial_aggregation_forbidden",
        "coarsen_before_suppress",
        "subcounts_require_k",
        "filter_complements_require_k",
        "arbitrary_filter_intersection_release_forbidden",
        "raw_member_ids_forbidden",
        "human_review_required_before_sensitive_publication",
    ):
        if privacy.get(name) is not True:
            errors.append(f"privacy release invariant must be true: {name}")
    if privacy.get("noise_addition_in_phase1") is not False:
        errors.append("phase 1 must not imply a differential privacy noise mechanism")
    if privacy.get("formal_anonymity_guarantee") is not False:
        errors.append("k=5 must not be represented as a formal anonymity guarantee")
    if privacy.get("filtered_approximate_release_scope") != "complete_reference_cohort_only_per_commons_type_and_bucket":
        errors.append("filtered approximate release must require the complete reference cohort per type and bucket")
    if privacy.get("differencing_protection") != "filtered_approximate_counts_release_only_when_the_complete_reference_cohort_is_selected_otherwise_coarsen_or_withhold":
        errors.append("filter differencing must forbid partial reference-cohort releases")

    case_contract = contract.get("case_matrix", {})
    if case_contract.get("path") != "tests/cases/visual-semantics.real-cases.json":
        errors.append("visual semantics contract must bind the canonical research case matrix")
    for name in (
        "public_repository_visibility_acknowledged",
        "not_catalog_truth",
        "not_verification_of_named_project_for_publication",
        "no_exact_private_coordinates",
        "source_references_required",
    ):
        if case_contract.get(name) is not True:
            errors.append(f"case matrix boundary must be true: {name}")
    source_review = case_contract.get("source_review", {})
    for name in (
        "checked_at_required",
        "future_date_forbidden",
        "official_primary_sources_required",
        "refresh_before_public_catalog_use",
        "stale_source_never_becomes_catalog_claim",
    ):
        if source_review.get(name) is not True:
            errors.append(f"case source review invariant must be true: {name}")
    if source_review.get("network_fetch_in_ci") is not False:
        errors.append("case source review must not add flaky network fetches to CI")

    if cases_doc.get("schema_version") != 1:
        errors.append("visual semantics case matrix schema_version must be 1")
    visibility = cases_doc.get("visibility", {})
    for name in (
        "repository_test_only_not_product_content",
        "public_repository_visibility_acknowledged",
        "excluded_from_public_shell",
        "not_catalog_truth",
        "not_publication_verification",
    ):
        if visibility.get(name) is not True:
            errors.append(f"case matrix visibility boundary must be true: {name}")
    if _contains_forbidden_coordinate_key(cases_doc):
        errors.append("research case matrix must not contain exact coordinate fields")
    try:
        checked_at = date.fromisoformat(cases_doc.get("checked_at", ""))
    except (TypeError, ValueError):
        errors.append("research case matrix checked_at must be an ISO date")
    else:
        if checked_at > date.today():
            errors.append("research case matrix checked_at must not be in the future")

    source_records = cases_doc.get("sources", {})
    for source_id, source in source_records.items():
        url = source.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append(f"research source {source_id} must use an https URL")
        if not source.get("source_kind") or not source.get("evidence_summary"):
            errors.append(f"research source {source_id} must include kind and evidence summary")
        if not str(source.get("source_kind", "")).startswith("official_"):
            errors.append(f"research source {source_id} must be an official primary source")

    case_records = cases_doc.get("cases", [])
    case_ids = [case.get("id") for case in case_records]
    if len(case_records) < 8 or len(set(case_ids)) != len(case_ids):
        errors.append("research matrix must contain at least eight uniquely identified cases")
    covered_archetypes: set[str] = set()
    covered_families: set[str] = set()
    valid_case_modes = set(UNCERTAINTY_MODES) | {"not_applicable", "separate_public_local_community_anchors"}
    texture_by_state = {entry["id"]: entry["interior_texture_role"] for entry in coverage_entries}
    for case in case_records:
        case_id = case.get("id", "<missing>")
        refs = case.get("source_refs", [])
        if not refs or any(ref not in source_records for ref in refs):
            errors.append(f"research case {case_id} must resolve every source reference")
        if not case.get("research_claim") or not case.get("project_pattern"):
            errors.append(f"research case {case_id} must explain its claim and project pattern")
        covered_archetypes.update(case.get("archetypes", []))
        modes = case.get("location_modes", [])
        if not modes or set(modes) - valid_case_modes:
            errors.append(f"research case {case_id} contains unsupported location modes")
        if "family_weights" in case:
            errors.append(f"research case {case_id} must not use false-precision family weights")
        assignment = case.get("family_assignment", {})
        primary = assignment.get("primary_family")
        assignment_families = set(assignment.get("secondary_families", [])) | set(assignment.get("mixed_families", []))
        if primary:
            assignment_families.add(primary)
        covered_families.update(assignment_families)
        try:
            resolved = identity_family_style(assignment, contract)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"research case {case_id} has invalid family assignment: {error}")
        else:
            if resolved != case.get("expected_composition"):
                errors.append(f"research case {case_id} expected family composition does not match contract")
            if case.get("expected_channels", {}).get("hue") != resolved:
                errors.append(f"research case {case_id} expected hue does not match resolved family composition")
        state = case.get("coverage_state")
        if state not in COVERAGE_STATES:
            errors.append(f"research case {case_id} must use a canonical coverage state")
        else:
            expected_texture = case.get("expected_channels", {}).get("interior_texture")
            if expected_texture != texture_by_state[state]:
                errors.append(f"research case {case_id} coverage texture does not match its state")
        relation_policy = case.get("expected_relation_policy")
        if relation_policy and relation_policy.get("speculative_connections") != "exclude":
            errors.append(f"research case {case_id} must exclude speculative relations")
        privacy_scenarios = list(case.get("privacy_scenarios", []))
        if case.get("privacy_scenario"):
            privacy_scenarios.append(case["privacy_scenario"])
        for scenario in privacy_scenarios:
            try:
                decision = privacy_decision(scenario, contract)
            except (KeyError, TypeError, ValueError) as error:
                errors.append(f"research case {case_id} has invalid privacy scenario: {error}")
            else:
                if decision != scenario.get("expected_decision"):
                    errors.append(f"research case {case_id} privacy decision {decision} does not match expected {scenario.get('expected_decision')}")

    required_archetypes = set(case_contract.get("required_archetypes", []))
    if not required_archetypes <= covered_archetypes:
        errors.append(f"research cases miss required archetypes: {sorted(required_archetypes - covered_archetypes)}")
    if set(FAMILY_IDS) != covered_families:
        errors.append("research cases must exercise every canonical Commons family")

    for file_name in PUBLIC_SURFACE_FILES:
        path = root / file_name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        leaked = [case_id for case_id in case_ids if case_id and case_id in text]
        if leaked:
            errors.append(f"research case ids must not appear in public surface {file_name}: {leaked}")

    renderer = contract.get("renderer_boundary", {})
    for name in (
        "no_engine_choice",
        "no_pixel_sizes",
        "no_shader_or_dom_type",
        "no_public_fixture_generation",
        "renderer_must_preserve_all_semantic_channels",
    ):
        if renderer.get(name) is not True:
            errors.append(f"renderer boundary must be true: {name}")

    return errors


def main() -> int:
    errors = validate_visual_semantics(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld visual semantics and real-case validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
