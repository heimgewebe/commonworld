#!/usr/bin/env python3
"""Validate the source-backed digital sphere real-surface proof."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_contracts import validation_errors
RESULT = ROOT / "docs" / "research" / "digital-sphere-real-surface-v1.result.json"
REPORT = ROOT / "docs" / "research" / "digital-sphere-real-surface-v1.md"
REFERENCE_SET = ROOT / "tests" / "cases" / "digital-sphere.reference-projects.json"
DIGITAL_CONTRACT = ROOT / "contracts" / "commonworld" / "digital-sphere.contract.json"
V4_PERFORMANCE_RESULT = ROOT / "docs" / "research" / "device-acceptance-performance-v4.result.json"

LAYER_TOPICS: OrderedDict[str, tuple[str, ...]] = OrderedDict(
    (
        ("knowledge_data", ("knowledge", "open-data", "research", "documentation")),
        ("software_infrastructure", ("free-software", "open-source", "infrastructure", "platform")),
        ("media_culture", ("open-media", "culture", "archives", "creative-commons")),
        ("learning_education", ("education", "open-educational-resources", "learning")),
        ("communication_networks", ("communication", "community-network", "federation", "protocol")),
    )
)
LAYER_ORDER = tuple(LAYER_TOPICS) + ("mixed_other",)
VISIBLE_NAME_LIMIT_PER_LAYER = 2
ORBIT_LABEL_MAX_CHARS = 18
REFERENCE_COUNT = 12
FOCUS_ID = "meta-wiki-reference"
TIE_FALLBACK_IDS = {"openstreetmap-reference", "meta-wiki-reference"}
PRIVATE_PATTERNS = (
    re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}\b"),
    re.compile(r"\b[\w.-]+\.ts\.net\b", re.I),
    re.compile(r"Mozilla/5\.0"),
    re.compile(r"\.png\b", re.I),
    re.compile(r"screenshot_sha", re.I),
    re.compile(r"raw_user_agent", re.I),
)


def _path(root: Path, path: Path) -> Path:
    return root / path.relative_to(ROOT)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_result(root: Path = ROOT) -> dict[str, Any]:
    return _load_json(_path(root, RESULT))


def load_reference_set(root: Path = ROOT) -> dict[str, Any]:
    return _load_json(_path(root, REFERENCE_SET))


def load_records(root: Path = ROOT) -> list[dict[str, Any]]:
    data = load_reference_set(root)
    records = data.get("records", [])
    return [record for record in records if isinstance(record, dict)]


def derive_digital_layer(record: dict[str, Any]) -> str | None:
    digital = record.get("presence", {}).get("digital", {})
    if not isinstance(digital, dict) or digital.get("available") is not True:
        return None

    themes = {theme for theme in record.get("themes", []) if isinstance(theme, str)}
    scores = {
        layer: sum(1 for topic in topics if topic in themes)
        for layer, topics in LAYER_TOPICS.items()
    }
    maximum = max(scores.values(), default=0)
    if maximum <= 0:
        return "mixed_other"
    winners = [layer for layer, score in scores.items() if score == maximum]
    return winners[0] if len(winners) == 1 else "mixed_other"


def _clean_title(title: str) -> str:
    return " ".join(title.upper().split())


def _truncate(cleaned: str, max_chars: int = ORBIT_LABEL_MAX_CHARS) -> str:
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 3:
        return cleaned[:max_chars]
    return cleaned[: max_chars - 3].rstrip() + "..."


def unique_orbit_labels(records: Iterable[dict[str, Any]], max_chars: int = ORBIT_LABEL_MAX_CHARS) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    used: dict[str, str] = {}
    for record in records:
        title = str(record["title"])
        cleaned = _clean_title(title)
        label = _truncate(cleaned, max_chars)
        if label in used and used[label] != title:
            suffix = "-" + hashlib.sha1(str(record["id"]).encode("utf-8")).hexdigest()[:3].upper()
            label = _truncate(cleaned, max_chars - len(suffix)) + suffix
            collision_index = 1
            while label in used and used[label] != title:
                numbered = f"{suffix[:3]}{collision_index}"
                label = _truncate(cleaned, max_chars - len(numbered)) + numbered
                collision_index += 1
        used[label] = title
        labels[str(record["id"])] = {
            "visible_text": label,
            "accessible_full_text": title,
        }
    return labels


def binary_fragment(project_id: str) -> str:
    value = int(hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:4], 16)
    return format(value, "016b")


def grouped_records(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {layer: [] for layer in LAYER_ORDER}
    for record in records:
        layer = derive_digital_layer(record)
        if layer is not None:
            grouped[layer].append(record)
    return grouped


def visible_records_for_layer(records: Iterable[dict[str, Any]], layer: str, limit: int = VISIBLE_NAME_LIMIT_PER_LAYER) -> list[dict[str, Any]]:
    members = [record for record in records if derive_digital_layer(record) == layer]
    indexed = list(enumerate(members))
    indexed.sort(key=lambda item: (not item[1].get("_source_backed_reference", True), item[0]))
    return [record for _index, record in indexed[:limit]]


def focus_panel(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": record["id"],
        "full_name": record["title"],
        "summary": record["summary"],
        "commons_kind": record["kind"],
        "themes": list(record["themes"]),
        "actions": list(record["actions"]),
        "digital_presence": copy.deepcopy(record["presence"]["digital"]),
        "official_links": copy.deepcopy(record["links"]),
        "sources": copy.deepcopy(record["provenance"]["sources"]),
        "curation": copy.deepcopy(record["curation"]),
        "reference_dataset_notice": "Nichtoeffentlicher Referenzdatensatz; keine Commonworld-Katalogveroeffentlichung.",
    }


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def focus_panel_hash(record: dict[str, Any]) -> str:
    return stable_hash(focus_panel(record))


def source_camera_state() -> dict[str, Any]:
    return {
        "center_lng": 10.0,
        "center_lat": 20.0,
        "zoom": 1.35,
        "bearing": 0.0,
        "pitch": 0.0,
        "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0},
        "filters": [],
        "search_query": "",
        "selected_id": FOCUS_ID,
        "focus_id": FOCUS_ID,
        "digital_mode": "globe",
    }


def side_camera_target() -> dict[str, Any]:
    return {
        "center_lng": 10.0,
        "center_lat": 20.0,
        "zoom": 1.23,
        "bearing": 24.0,
        "pitch": 36.0,
        "padding": {"top": 0, "right": 519, "bottom": 0, "left": 0},
        "filters": [],
        "search_query": "",
        "selected_id": FOCUS_ID,
        "focus_id": FOCUS_ID,
        "digital_mode": "layers",
    }


def camera_transition(reduced_motion: bool = False) -> dict[str, Any]:
    source = source_camera_state()
    target = side_camera_target()
    return {
        "source_state": source,
        "saved_state_keys": sorted(source),
        "maplibre_command": "maplibre.jumpTo" if reduced_motion else "maplibre.easeTo",
        "duration_ms": 0 if reduced_motion else 260,
        "target_state": target,
        "restored_state_after_close": copy.deepcopy(source),
        "restored_exact": True,
        "url": f"?digital=layers&focus={FOCUS_ID}",
        "selected_id": FOCUS_ID,
        "focus_id": FOCUS_ID,
    }


def selection_paths(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    record = next(item for item in records if item["id"] == FOCUS_ID)
    panel_hash = focus_panel_hash(record)
    paths = (
        "digital_sphere_edge",
        "layer_button",
        "linear_view",
        "search",
        "deep_link",
        "browser_back",
    )
    return [
        {
            "path": path,
            "selected_id": FOCUS_ID,
            "focus_panel_hash": panel_hash,
            "active_focus_count": 1,
            "url": f"?digital=layers&focus={FOCUS_ID}" if path != "browser_back" else f"?focus={FOCUS_ID}",
        }
        for path in paths
    ]


def contains_coordinate_material(value: Any) -> bool:
    coordinate_keys = {"geometry", "coordinates", "lon", "lng", "lat", "latitude", "longitude"}
    if isinstance(value, dict):
        for key, child in value.items():
            if key in coordinate_keys:
                return True
            if contains_coordinate_material(child):
                return True
    elif isinstance(value, list):
        return any(contains_coordinate_material(child) for child in value)
    return False


def build_layer_coverage(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = grouped_records(records)
    return [
        {
            "id": layer,
            "count": len(grouped[layer]),
            "project_ids": [record["id"] for record in grouped[layer]],
        }
        for layer in LAYER_ORDER
    ]


def build_name_presentation(records: list[dict[str, Any]]) -> dict[str, Any]:
    labels = unique_orbit_labels(records)
    grouped = grouped_records(records)
    visible_by_layer = []
    for layer in LAYER_ORDER:
        visible = visible_records_for_layer(grouped[layer], layer)
        visible_by_layer.append(
            {
                "layer": layer,
                "visible_name_count": len(visible),
                "visible_names": [
                    {
                        "project_id": record["id"],
                        "visible_text": labels[record["id"]]["visible_text"],
                        "accessible_full_text": labels[record["id"]]["accessible_full_text"],
                    }
                    for record in visible
                ],
            }
        )
    return {
        "visible_name_limit_per_layer": VISIBLE_NAME_LIMIT_PER_LAYER,
        "orbit_label_max_chars": ORBIT_LABEL_MAX_CHARS,
        "visible_by_layer": visible_by_layer,
        "meta_wiki_visible_text": labels["meta-wiki-reference"]["visible_text"],
        "meta_wiki_accessible_full_text": labels["meta-wiki-reference"]["accessible_full_text"],
        "side_view_full_names_source": "CommonProject.title",
        "focus_panel_full_name_source": "CommonProject.title",
        "binary_fragments": [
            {
                "project_id": record["id"],
                "fragment": binary_fragment(record["id"]),
                "aria_hidden": True,
                "role": "decorative",
            }
            for record in records
        ],
    }


def _layer_topics_from_contract(root: Path) -> dict[str, tuple[str, ...]]:
    contract = _load_json(_path(root, DIGITAL_CONTRACT))
    layers = contract.get("layer_model", {}).get("layers", [])
    return {
        layer.get("id"): tuple(layer.get("derived_from", ()))
        for layer in layers
        if layer.get("id") in LAYER_TOPICS
    }


def _report_text(root: Path) -> str:
    return _path(root, REPORT).read_text(encoding="utf-8")


def _combined_public_text(root: Path) -> str:
    chunks = []
    for path in (RESULT, REPORT):
        target = _path(root, path)
        if target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _v4_floor(root: Path) -> dict[str, Any]:
    result = _load_json(_path(root, V4_PERFORMANCE_RESULT))
    floor = result["v4_installed_proof"]
    return {
        "source": "docs/research/device-acceptance-performance-v4.result.json:v4_installed_proof",
        "runs": floor["runs"],
        "planet_median_fps": floor["planet_median_fps"],
        "local_median_fps": floor["local_median_fps"],
        "idle_map_render_delta": floor["idle_map_render_delta"],
        "idle_overlay_render_delta": floor["idle_overlay_render_delta"],
        "idle_state_write_delta": floor["idle_state_write_delta"],
        "performance_gate_pass": floor["performance_gate_pass"],
    }


def _public_shell_contains_reference_data(root: Path, records: list[dict[str, Any]]) -> list[str]:
    html_path = root / "index.html"
    if not html_path.is_file():
        return ["missing index.html for public-shell leakage check"]
    html = html_path.read_text(encoding="utf-8")
    leaks = []
    for record in records:
        for token in (record["id"], record["title"]):
            if token in html:
                leaks.append(token)
        for link in record.get("links", []):
            if isinstance(link, dict) and link.get("url") in html:
                leaks.append(link["url"])
    return leaks


def _validate_reference_records(root: Path, records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(records) != REFERENCE_COUNT:
        errors.append(f"reference record count must be {REFERENCE_COUNT}")
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        errors.append("reference project ids must be unique")
    for record in records:
        record_id = record.get("id", "<missing>")
        for message in validation_errors(record, root):
            errors.append(f"reference record {record_id} invalid: {message}")
        if record.get("kind") != "digital":
            errors.append(f"reference record {record_id} must remain fully digital")
        digital = record.get("presence", {}).get("digital", {})
        if not isinstance(digital, dict) or digital.get("available") is not True:
            errors.append(f"reference record {record_id} must have digital presence")
        geographic = record.get("presence", {}).get("geographic")
        if geographic != []:
            errors.append(f"reference record {record_id} must not contain a geographic anchor")
        if contains_coordinate_material(record.get("presence", {}).get("geographic")):
            errors.append(f"reference record {record_id} must not contain geographic coordinate material")
        if str(record.get("title", "")).startswith(("Proof identity", "Virtual identity")):
            errors.append(f"reference record {record_id} must prefer a source-backed public name")
    return errors


def _validate_result_layer_coverage(result: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    expected = build_layer_coverage(records)
    if result.get("layer_coverage") != expected:
        errors.append("result layer coverage does not match deterministic CommonProject-v3 derivation")
    counts = {item["id"]: item["count"] for item in expected}
    if set(counts) != set(LAYER_ORDER) or any(count <= 0 for count in counts.values()):
        errors.append("all six digital layers must be occupied by the twelve references")
    for record in records:
        layer = derive_digital_layer(record)
        if record["id"] in TIE_FALLBACK_IDS and layer != "mixed_other":
            errors.append(f"tie fallback did not select mixed_other for {record['id']}")
    no_digital = copy.deepcopy(records[0])
    no_digital["presence"]["digital"] = {"available": False, "source_ids": no_digital["presence"]["digital"]["source_ids"]}
    if derive_digital_layer(no_digital) is not None:
        errors.append("missing digital presence must produce no digital layer")
    unmapped = copy.deepcopy(records[0])
    unmapped["themes"] = ["unmapped-topic"]
    if derive_digital_layer(unmapped) != "mixed_other":
        errors.append("unmapped digital topics must fall back to mixed_other")
    return errors


def _validate_name_presentation(result: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    expected = build_name_presentation(records)
    presentation = result.get("name_presentation", {})
    if presentation != expected:
        errors.append("name presentation result does not match the deterministic bounded derivation")
        return errors
    for layer in presentation["visible_by_layer"]:
        if layer["visible_name_count"] > VISIBLE_NAME_LIMIT_PER_LAYER:
            errors.append(f"visible name limit exceeded for {layer['layer']}")
        for item in layer["visible_names"]:
            if not item["accessible_full_text"] or item["visible_text"].startswith("Proof identity"):
                errors.append(f"visible label for {item['project_id']} did not prefer the source-backed name")
    visible_to_full: dict[str, str] = {}
    for layer in presentation["visible_by_layer"]:
        for item in layer["visible_names"]:
            previous = visible_to_full.setdefault(item["visible_text"], item["accessible_full_text"])
            if previous != item["accessible_full_text"]:
                errors.append("different full names produced the same visible short text")
    meta_title = next(record["title"] for record in records if record["id"] == "meta-wiki-reference")
    if presentation["meta_wiki_accessible_full_text"] != meta_title:
        errors.append("Meta-Wiki long-name stress case must retain full accessible text")
    if len(presentation["meta_wiki_visible_text"]) > ORBIT_LABEL_MAX_CHARS:
        errors.append("Meta-Wiki orbit label must remain bounded")
    for fragment in presentation["binary_fragments"]:
        if fragment.get("aria_hidden") is not True or fragment.get("role") != "decorative":
            errors.append(f"binary fragment must be decorative and aria-hidden: {fragment.get('project_id')}")
        if not re.fullmatch(r"[01]{16}", str(fragment.get("fragment", ""))):
            errors.append(f"binary fragment must be a deterministic 16-bit visual token: {fragment.get('project_id')}")
    return errors


def _validate_focus_and_selection(result: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    focus_record = next((record for record in records if record["id"] == FOCUS_ID), None)
    if focus_record is None:
        return ["focus reference record missing"]
    expected_hash = focus_panel_hash(focus_record)
    focus = result.get("focus_panel", {})
    required_fields = [
        "full_name", "summary", "commons_kind", "themes", "actions",
        "digital_presence", "official_links", "sources", "curation", "reference_dataset_notice",
    ]
    if focus.get("source") != "same_commonproject_v3_record" or focus.get("second_data_copy") is not False:
        errors.append("focus panel must derive from the same CommonProject record without a second data copy")
    if focus.get("selected_id") != FOCUS_ID or focus.get("focus_panel_hash") != expected_hash:
        errors.append("focus panel hash or selected identity mismatch")
    if focus.get("fields") != required_fields:
        errors.append("focus panel must expose the required real-surface fields")
    if "Referenzdatensatz" not in str(focus.get("reference_dataset_notice", "")):
        errors.append("focus panel must clearly mark the non-public reference dataset")

    expected_paths = selection_paths(records)
    selection = result.get("selection_parity", {})
    if selection.get("paths") != expected_paths:
        errors.append("selection parity paths must keep the same id and focus panel hash")
    if selection.get("single_focus") is not True or selection.get("active_focus_count") != 1:
        errors.append("selection parity must prove exactly one focus")
    if selection.get("view_switch_preserves_focus") is not True:
        errors.append("view switches must preserve the current focus")
    geographic = selection.get("geographic_representation")
    if geographic != {
        "applicable": False,
        "reason": "all_reference_records_are_fully_digital_without_public_geographic_geometry",
        "project_coordinates_created": False,
    }:
        errors.append("geographic representation truth must stay explicit for fully digital references")
    return errors


def _validate_camera(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    side = result.get("side_camera", {})
    standard = side.get("standard_transition", {})
    reduced = side.get("reduced_motion_transition", {})
    expected_standard = camera_transition(reduced_motion=False)
    expected_reduced = camera_transition(reduced_motion=True)
    if standard != expected_standard:
        errors.append("standard side camera transition must match the MapLibre target and exact restore state")
    if reduced != expected_reduced:
        errors.append("reduced-motion transition must reach the same camera target immediately")
    if reduced.get("target_state") != standard.get("target_state") or reduced.get("duration_ms") != 0:
        errors.append("reduced motion must use the same target state with 0 ms duration")
    layout = side.get("layer_stack_layout", {})
    if layout != {
        "spatial_relation": "beside_damped_globe",
        "independent_mode": False,
        "earth_opacity": 0.38,
        "layers_stacked": True,
    }:
        errors.append("side layer stack must remain spatially beside the damped globe in the same surface")
    if side.get("interruptible") is not True or side.get("map_stop_called_on_new_input") is not True:
        errors.append("side camera movement must be interruptible by new input")
    return errors


def _validate_performance_and_shell(root: Path, result: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    performance = result.get("rendering_performance", {})
    floor = _v4_floor(root)
    if performance.get("v4_software_profile_floor") != floor:
        errors.append("performance floor must be bound to the normalized v4 installed software proof")
    if performance.get("new_browser_fps_claimed") is not True:
        errors.append("private v6 browser measurement must remain recorded as a normalized claim")
    expected_v6 = {
        "kind": "normalized_private_acceptance_release_summary",
        "release_id": "20260712-v6-c67f8cabef4b",
        "release_manifest_sha256": "c67f8cabef4b7e79141ae861a73adf8b77043c43cfa477bc6237587bdfbe95e6",
        "release_server_tested": True,
        "browser_test_status": "pass",
        "source_backed_reference_projects": 12,
        "viewport": {"width": 1180, "height": 684, "device_scale_factor": 2},
        "camera": {
            "animated_command": "maplibre.easeTo",
            "animated_duration_ms": 260,
            "animated_exact_restore": True,
            "reduced_motion_command": "maplibre.jumpTo",
            "reduced_motion_duration_ms": 0,
            "reduced_motion_exact_restore": True,
            "css_only_shift": False,
        },
        "virtual_list": {
            "total_items": 50000,
            "maximum_rendered_rows": 15,
            "theoretical_maximum_rows": 23,
            "pass": True,
        },
        "performance": {
            "runs": 3,
            "planet_median_fps": 32.276574333484454,
            "local_median_fps": 56.95121165002101,
            "minimum_median_fps": 30,
            "gate_pass": True,
        },
        "idle": {
            "observation_ms": 1500,
            "map_render_delta": 0,
            "overlay_render_delta": 0,
            "state_write_delta": 0,
        },
        "console_errors": [],
        "raw_private_artifacts_published": False,
        "screenshots_published": False,
        "physical_device_tested": False,
        "engine_selected": False,
        "production_architecture_authorized": False,
    }
    if performance.get("private_v6_browser_proof") != expected_v6:
        errors.append("private v6 browser proof summary must match the hash-bound normalized evidence")
    if performance.get("public_runtime_changed") is not False:
        errors.append("public runtime must remain unchanged by the reference-data proof")
    if performance.get("continuous_idle_rendering") is not False:
        errors.append("continuous idle rendering must be absent")
    if performance.get("idle_map_render_delta") > 2 or performance.get("idle_overlay_render_delta") != 0:
        errors.append("idle render bounds exceed the digital sphere contract")
    if performance.get("visible_orbit_names_total") != REFERENCE_COUNT:
        errors.append("visible orbit names should contain the bounded source-backed reference set")
    synthetic = performance.get("synthetic_load_identity_test", {})
    if synthetic != {
        "synthetic_identity_count": 50000,
        "synthetic_reference_name_displacement": False,
        "synthetic_identities_public_catalog": False,
    }:
        errors.append("synthetic load identities must not displace or become real reference names")
    if performance.get("regression_excluded_as_far_as_local_harness_allows") is not True:
        errors.append("performance regression scope must be explicitly bounded and pass the local static gates")

    public_shell = result.get("public_shell", {})
    leaks = _public_shell_contains_reference_data(root, records)
    if leaks:
        errors.append(f"public shell contains reference data: {sorted(leaks)}")
    if public_shell.get("reference_data_in_index_html") is not False or public_shell.get("public_shell_changed") is not False:
        errors.append("public shell must stay free of reference data and runtime changes")
    return errors


def _validate_boundaries(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundaries = result.get("acceptance_boundaries", {})
    expected = {
        "source_backed_reference_projects_are_published_catalog": False,
        "editorial_catalog_admission_separate_process": True,
        "physical_android_chrome_checked": False,
        "screenreader_prototype_scope": "waived_not_passed",
        "raw_receipts_or_private_endpoints_published": False,
    }
    if boundaries != expected:
        errors.append("acceptance boundaries must not overclaim publication, Android, screenreader, or private evidence")
    decision = result.get("decision", {})
    if decision.get("engine_selected") is not False or decision.get("production_architecture_authorized") is not False:
        errors.append("engine and production architecture gates must remain false")
    if decision.get("next_action") != "physical_android_chrome_v6_then_editorial_catalog_process":
        errors.append("next action must keep Android Chrome and editorial cataloging separate")
    return errors


def validate_digital_sphere_real_surface(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = (RESULT, REPORT, REFERENCE_SET, DIGITAL_CONTRACT, V4_PERFORMANCE_RESULT)
    for path in required:
        if not _path(root, path).is_file():
            errors.append(f"missing required real-surface file: {path.relative_to(ROOT)}")
    if errors:
        return errors

    try:
        result = load_result(root)
        reference_set = load_reference_set(root)
        records = load_records(root)
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid real-surface proof input: {error}"]

    if result.get("schema_version") != 1 or result.get("kind") != "commonworld_digital_sphere_real_surface_v1":
        errors.append("digital sphere real-surface result schema mismatch")
    if result.get("status") != "private_v6_browser_reference_surface_validated_physical_android_open":
        errors.append("real-surface proof status must keep physical Android Chrome open")
    if result.get("checked_at") != "2026-07-12":
        errors.append("real-surface proof date mismatch")

    if reference_set.get("kind") != "commonworld_source_backed_digital_surface_reference_set":
        errors.append("reference set kind mismatch")
    visibility = reference_set.get("visibility", {})
    for key in (
        "repository_test_only_not_product_content",
        "excluded_from_public_shell",
        "not_catalog_truth",
        "not_publication_verification",
        "real_project_names_used_only_for_derivation_and_legibility",
    ):
        if visibility.get(key) is not True:
            errors.append(f"reference set visibility boundary must be true: {key}")

    contract_topics = _layer_topics_from_contract(root)
    if contract_topics != dict(LAYER_TOPICS):
        errors.append("digital sphere contract topic mapping does not match real-surface derivation")

    errors.extend(_validate_reference_records(root, records))
    source = result.get("source_reference_set", {})
    if source != {
        "path": "tests/cases/digital-sphere.reference-projects.json",
        "record_count": REFERENCE_COUNT,
        "commonproject_schema_version": 3,
        "records_schema_v3_valid": True,
        "published_catalog": False,
        "public_shell_content": False,
    }:
        errors.append("source reference-set summary mismatch")

    derivation = result.get("layer_derivation", {})
    if derivation.get("topic_mapping") != {layer: list(topics) for layer, topics in LAYER_TOPICS.items()}:
        errors.append("layer derivation topic mapping mismatch")
    if derivation.get("missing_digital_presence") != "no_digital_layer":
        errors.append("missing digital presence must map to no digital layer")
    if derivation.get("unique_highest_topic_score") != "select_that_layer":
        errors.append("unique highest topic score must select that layer")
    if derivation.get("tie_or_unmapped") != "mixed_other":
        errors.append("tie or unmapped topics must select mixed_other")

    errors.extend(_validate_result_layer_coverage(result, records))
    errors.extend(_validate_name_presentation(result, records))
    errors.extend(_validate_focus_and_selection(result, records))
    errors.extend(_validate_camera(result))
    errors.extend(_validate_performance_and_shell(root, result, records))
    errors.extend(_validate_boundaries(result))

    report = _report_text(root)
    for token in (
        "quellengebundene Referenzprojekte != veröffentlichter Commonworld-Katalog",
        "Android Chrome physisch mit dem v6-Paket nicht geprüft",
        "Screenreader für diesen Prototyp entfallen, nicht bestanden",
        "redaktionelle Katalogaufnahme ist ein separater Prozess",
        "engine_selected                    = false",
        "production_architecture_authorized = false",
    ):
        if token not in report:
            errors.append(f"real-surface report missing required token: {token}")

    combined = _combined_public_text(root)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(combined):
            errors.append(f"private raw material leaked into real-surface proof: {pattern.pattern}")
    return errors


def main() -> int:
    errors = validate_digital_sphere_real_surface(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld digital sphere real-surface validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
