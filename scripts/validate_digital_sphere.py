#!/usr/bin/env python3
"""Validate the layered digital Commons sphere presentation contract."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/commonworld/digital-sphere.contract.json"
EXPECTED_LAYER_ORDER = (
    "knowledge_data",
    "software_infrastructure",
    "media_culture",
    "learning_education",
    "communication_networks",
    "mixed_other",
)
EXPECTED_GLYPH_CYCLE = (
    "short_common_name_fragment",
    "binary_fragment_derived_from_stable_identity",
)


def load_contract(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / CONTRACT.relative_to(ROOT)).read_text(encoding="utf-8"))


def validate_digital_sphere(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = root / CONTRACT.relative_to(ROOT)
    if not path.is_file():
        return ["missing digital sphere presentation contract"]
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"digital sphere contract is invalid JSON: {error}"]

    if contract.get("schema_version") != 1:
        errors.append("digital sphere schema_version must be 1")
    if contract.get("kind") != "commonworld_digital_sphere_presentation_contract":
        errors.append("digital sphere kind mismatch")

    boundary = contract.get("catalog_boundary", {})
    expected_boundary = {
        "source_identity": "CommonProject.id",
        "layer_membership_source": "derived_from_existing_topics_families_and_public_digital_presence",
        "manual_catalog_layer_field_forbidden": True,
        "invented_geographic_coordinates_forbidden": True,
        "persistent_render_path_coordinates_forbidden": True,
        "hybrid_identity_duplication_forbidden": True,
    }
    if boundary != expected_boundary:
        errors.append("digital sphere catalog boundary mismatch")

    model = contract.get("layer_model", {})
    order = tuple(model.get("order", []))
    if order != EXPECTED_LAYER_ORDER:
        errors.append("digital sphere layer order mismatch")
    layers = model.get("layers", [])
    if not isinstance(layers, list) or tuple(item.get("id") for item in layers) != EXPECTED_LAYER_ORDER:
        errors.append("digital sphere layers must exactly match the canonical order")
    for layer in layers if isinstance(layers, list) else []:
        if not isinstance(layer.get("label_de"), str) or not layer["label_de"].strip():
            errors.append(f"digital layer missing German label: {layer.get('id')}")
        derived = layer.get("derived_from")
        if not isinstance(derived, list) or not derived or any(not isinstance(item, str) or not item for item in derived):
            errors.append(f"digital layer missing derivation terms: {layer.get('id')}")
    if model.get("membership_rule") != "one_primary_presentation_layer_per_visible_representation_with_optional_cross_layer_relations":
        errors.append("digital layer membership rule mismatch")
    if model.get("layer_count_is_presentation_configuration_not_catalog_truth") is not True:
        errors.append("digital layers must remain presentation configuration")

    stream = contract.get("stream_model", {})
    if stream.get("primary_geometry") != "layered_glyph_paths_around_globe":
        errors.append("digital sphere must use layered glyph paths")
    if stream.get("isolated_point_cloud_as_primary_representation_forbidden") is not True:
        errors.append("isolated point cloud must not remain the primary digital representation")
    if tuple(stream.get("glyph_cycle", [])) != EXPECTED_GLYPH_CYCLE:
        errors.append("digital glyph cycle must alternate readable names and stable-ID binary fragments")
    for invariant in (
        "name_fragment_must_remain_human_readable",
        "paths_are_ephemeral_presentation",
        "individual_identity_may_repeat_visually_but_counts_once",
        "relations_require_catalog_evidence",
    ):
        if stream.get(invariant) is not True:
            errors.append(f"digital stream invariant must be true: {invariant}")
    if stream.get("binary_fragment_semantics") != "deterministic_visual_encoding_not_project_payload_or_quality_score":
        errors.append("binary glyphs must not claim payload or quality meaning")

    globe = contract.get("globe_mode", {})
    for invariant in (
        "outer_shell",
        "shell_must_extend_beyond_visible_earth_rim",
        "initial_view_shell_visible",
        "further_zoom_out_reveals_complete_enclosure",
    ):
        if globe.get(invariant) is not True:
            errors.append(f"digital globe invariant must be true: {invariant}")
    center = globe.get("center_fade", {})
    if center != {
        "enabled": True,
        "purpose": "keep_the_commons_world_readable",
        "minimum_opacity_at_view_center": 0.0,
        "maximum_opacity_near_outer_rim": 1.0,
        "fade_is_screen_space_visibility_not_catalog_data": True,
    }:
        errors.append("digital sphere center-fade contract mismatch")
    zoom = globe.get("zoom_fade", {})
    expected_zoom = {
        "overview_visible_through_zoom": 1.8,
        "fade_until_zoom": 2.6,
        "local_hidden_from_zoom": 2.6,
        "monotonic_fade_required": True,
    }
    if zoom != expected_zoom:
        errors.append("digital sphere zoom-fade contract mismatch")
    numeric = [zoom.get("overview_visible_through_zoom"), zoom.get("fade_until_zoom"), zoom.get("local_hidden_from_zoom")]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in numeric):
        errors.append("digital sphere zoom thresholds must be finite numbers")
    elif not (numeric[0] < numeric[1] == numeric[2]):
        errors.append("digital sphere zoom fade must end exactly where local hiding begins")
    if globe.get("motion") != {
        "continuous_rotation_forbidden": True,
        "stop_on_interaction_focus_hidden_page_or_reduced_motion": True,
    }:
        errors.append("digital sphere motion boundary mismatch")

    interaction = contract.get("interaction", {})
    hit = interaction.get("sphere_edge_hit_target", {})
    if hit != {
        "available_in_initial_view": True,
        "shape": "annulus_around_visible_globe",
        "minimum_css_px": 24,
        "must_not_block_globe_center_interaction": True,
        "accessible_name_de": "Digitale Commons-Schichten öffnen",
    }:
        errors.append("digital sphere edge hit-target contract mismatch")
    if interaction.get("open_action") != "transition_to_side_layer_view":
        errors.append("digital sphere must open the side layer view")
    if interaction.get("reduced_motion_open_action") != "instant_state_change_without_camera_animation":
        errors.append("digital layer transition must support reduced motion")
    if interaction.get("browser_history_and_deep_link_required") is not True or interaction.get("close_action_returns_to_previous_globe_state") is not True:
        errors.append("digital layer mode must preserve navigation state")

    side = contract.get("side_layer_view", {})
    expected_side_true = (
        "layers_stacked",
        "layer_order_matches_layer_model",
        "earth_remains_quiet_orientation_reference",
        "same_surface_not_separate_application",
        "same_identity_ids_as_globe_mode",
        "layer_selection_filters_without_changing_identity_truth",
        "focus_opens_same_commonproject_record",
        "linear_equivalent_required",
    )
    if side.get("camera_relation") != "side_on":
        errors.append("digital layer view must be side-on")
    for invariant in expected_side_true:
        if side.get(invariant) is not True:
            errors.append(f"digital side-view invariant must be true: {invariant}")

    parity = contract.get("selection_parity", {})
    for invariant in (
        "single_selected_identity",
        "same_id_across_globe_sphere_side_view_search_and_linear",
        "view_change_must_preserve_selection",
        "hybrid_geographic_and_digital_representations_focus_together",
    ):
        if parity.get(invariant) is not True:
            errors.append(f"selection parity invariant must be true: {invariant}")
    if "dieselbe CommonProject-ID" not in str(parity.get("definition_de", "")):
        errors.append("selection parity needs a plain German identity definition")
    if "dieselbe Name" in str(parity.get("plain_language_test_de", "")):
        errors.append("selection parity test contains ungrammatical wording")
    if "derselbe Name" not in str(parity.get("plain_language_test_de", "")):
        errors.append("selection parity needs a concrete plain-language test")

    accessibility = contract.get("accessibility", {})
    for invariant in (
        "sphere_is_not_only_visual",
        "layer_buttons_and_linear_identity_list_required",
        "keyboard_path_required",
        "screen_reader_path_required",
        "unproven_screen_reader_must_never_be_reported_as_pass",
        "physical_screen_reader_test_waived_by_product_owner",
        "reduced_motion_state_equivalence_required",
        "glyph_streams_aria_hidden_when_equivalent_text_exists",
    ):
        if accessibility.get(invariant) is not True:
            errors.append(f"digital accessibility invariant must be true: {invariant}")
    if accessibility.get("voiceover_physical_test_currently_proven") is not False:
        errors.append("VoiceOver physical proof must remain false until actually tested")
    if accessibility.get("physical_screen_reader_test_required_for_non_public_prototype_acceptance") is not False:
        errors.append("physical screenreader test must remain optional for non-public prototype acceptance")
    if accessibility.get("screen_reader_product_support_claimed") is not False:
        errors.append("screenreader product support must not be claimed")
    if accessibility.get("physical_screen_reader_waiver_scope") != "non_public_prototype_acceptance_only":
        errors.append("physical screenreader waiver scope mismatch")

    performance = contract.get("performance_and_privacy", {})
    for invariant in (
        "bounded_visible_glyph_count_required",
        "offscreen_or_hidden_layers_pause",
        "raw_member_ids_must_not_be_exposed_by_aggregate_glyph_streams",
        "hidden_location_never_encoded_in_glyph_or_path",
        "no_telemetry_required",
        "unchanged_glyph_geometry_must_not_be_rewritten",
        "navigation_state_writes_must_be_coalesced",
        "benchmark_requires_browser_frame_alignment_and_map_render_confirmation",
    ):
        if performance.get(invariant) is not True:
            errors.append(f"digital performance/privacy invariant must be true: {invariant}")
    if performance.get("settled_idle_map_render_delta_max") != 2:
        errors.append("settled idle map-render bound must be 2")
    if performance.get("settled_idle_overlay_render_delta_max") != 0:
        errors.append("settled idle overlay-render bound must be 0")

    real_surface = contract.get("real_surface_v1", {})
    if real_surface.get("reference_set_path") != "tests/cases/digital-sphere.reference-projects.json":
        errors.append("real-surface reference set path mismatch")
    if real_surface.get("reference_projects_are_public_catalog") is not False:
        errors.append("real-surface references must not be public catalog truth")
    if real_surface.get("commonproject_schema_version") != 3:
        errors.append("real-surface references must bind to CommonProject v3")
    derivation = real_surface.get("layer_derivation", {})
    if derivation != {
        "source_identity": "CommonProject.id",
        "requires_digital_presence_available": True,
        "missing_digital_presence_result": "no_digital_layer",
        "unique_highest_topic_score_result": "selected_layer",
        "tie_or_unmapped_result": "mixed_other",
        "manual_layer_override_forbidden": True,
    }:
        errors.append("real-surface layer derivation contract mismatch")
    names = real_surface.get("name_presentation", {})
    if names.get("visible_name_limit_per_layer") != 2:
        errors.append("real-surface visible name limit must be 2 per layer")
    if names.get("orbit_label_max_chars") != 18:
        errors.append("real-surface orbit label length must be bounded at 18 characters")
    for invariant in (
        "visible_orbit_labels_must_have_accessible_full_text",
        "side_view_uses_full_commonproject_title",
        "focus_panel_uses_full_commonproject_title",
        "different_full_names_must_not_share_visible_short_label",
        "binary_fragments_aria_hidden_and_decorative",
        "source_backed_reference_names_precede_synthetic_load_names",
    ):
        if names.get(invariant) is not True:
            errors.append(f"real-surface name invariant must be true: {invariant}")
    focus = real_surface.get("focus_panel", {})
    if focus.get("single_shared_panel") is not True or focus.get("second_data_copy_forbidden") is not True:
        errors.append("real-surface focus panel must be single and source-derived")
    if focus.get("source") != "same_commonproject_v3_record":
        errors.append("real-surface focus panel source mismatch")
    if focus.get("required_fields") != [
        "full_name",
        "summary",
        "commons_kind",
        "themes",
        "actions",
        "digital_presence",
        "official_links",
        "sources",
        "curation",
        "reference_dataset_notice",
    ]:
        errors.append("real-surface focus panel required fields mismatch")
    if focus.get("reference_dataset_notice_required") is not True:
        errors.append("real-surface focus panel must require a reference dataset notice")
    camera = real_surface.get("side_camera", {})
    if camera.get("animated_command") != "maplibre.easeTo":
        errors.append("real-surface side camera must use MapLibre easeTo for animated motion")
    if camera.get("reduced_motion_command") != "maplibre.jumpTo" or camera.get("reduced_motion_duration_ms") != 0:
        errors.append("real-surface reduced-motion camera must use MapLibre jumpTo with 0 ms")
    for invariant in (
        "maplibre_camera_required",
        "css_only_shift_forbidden",
        "save_complete_previous_state",
        "target_requires_bearing_pitch_zoom_and_padding",
        "new_input_interrupts_transition",
        "close_and_browser_back_restore_exact_previous_state",
        "layer_stack_beside_damped_globe",
        "independent_mode_forbidden",
    ):
        if camera.get(invariant) is not True:
            errors.append(f"real-surface side-camera invariant must be true: {invariant}")

    decision = contract.get("decision_boundary", {})
    if decision != {
        "engine_selected": False,
        "production_architecture_authorized": False,
        "next_proof": "physical_android_v6_acceptance_then_editorial_catalog_process",
    }:
        errors.append("digital sphere decision boundary mismatch")

    return errors


def main() -> int:
    errors = validate_digital_sphere(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld layered digital sphere contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
