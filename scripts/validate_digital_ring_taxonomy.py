#!/usr/bin/env python3
"""Validate the versioned digital ring-bundle taxonomy against the live catalog."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.digital_taxonomy import (
    CONTRACT_PATH,
    ID_PATTERN,
    ROOT_ID,
    children_by_parent,
    derive_project_path,
    load_taxonomy,
    node_map,
    normalize_path,
    path_for_node,
    serialize_path,
    theme_map,
)

CATALOG_PATH = Path("catalog/catalog.json")
EXPECTED_FIELDS = [
    "knowledge_learning_culture",
    "software_tools_production",
    "communication_networks",
    "provision_land_ecology",
    "cooperation_self_organization",
]
EXPECTED_FIELD_LABELS = {
    "knowledge_learning_culture": "Wissen, Lernen und Kultur",
    "software_tools_production": "Software, Werkzeuge und Produktion",
    "communication_networks": "Kommunikation und Netze",
    "provision_land_ecology": "Versorgung, Land und Ökologie",
    "cooperation_self_organization": "Kooperation und Selbstorganisation",
}
LEGACY_LAYER_IDS = {
    "knowledge_data",
    "software_infrastructure",
    "media_culture",
    "learning_education",
    "communication_networks",
    "mixed_other",
}
CORE_TAXONOMY_KEYS = [
    "schema_version",
    "kind",
    "version",
    "version_rule",
    "levels",
    "root_id",
    "unknown_theme_node_id",
    "nodes",
    "compound_rules",
    "tie_rules",
    "same_field_tie_fallbacks",
    "legacy_layer_aliases",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(root: Path) -> list[dict[str, Any]]:
    manifest = _load_json(root / CATALOG_PATH)
    records: list[dict[str, Any]] = []
    for relative in manifest.get("project_files", []):
        if isinstance(relative, str) and relative.startswith("projects/") and ".." not in relative:
            value = _load_json(root / "catalog" / relative)
            if isinstance(value, dict):
                records.append(value)
    return records


def _is_digital(record: dict[str, Any]) -> bool:
    return record.get("presence", {}).get("digital", {}).get("available") is True


def _field_for_node(taxonomy: dict[str, Any], node_id: str) -> str | None:
    nodes = node_map(taxonomy)
    node = nodes.get(node_id)
    while node and node.get("parent_id") not in (None, taxonomy.get("root_id", ROOT_ID)):
        node = nodes.get(node.get("parent_id"))
    return node["id"] if node and node.get("type") == "field" else None


def _canon(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _core_taxonomy(root: Path) -> dict[str, Any] | None:
    probe = """
import { DIGITAL_TAXONOMY } from './assets/commonworld-core.mjs';
console.log(JSON.stringify(DIGITAL_TAXONOMY));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", probe],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return json.loads(completed.stdout)


def _validate_tree_sets(
    taxonomy: dict[str, Any],
    path_by_id: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    paths_by_node_id = {
        node_id: path_for_node(taxonomy, node_id)
        for node_id in node_map(taxonomy)
    }
    identity_sets: dict[str, set[str]] = {
        serialize_path(path): set()
        for path in paths_by_node_id.values()
        if path
    }
    direct_identity_sets: dict[str, set[str]] = {path_key: set() for path_key in identity_sets}
    for identifier, path_key in path_by_id.items():
        parts = path_key.split("/")
        direct_identity_sets.setdefault(path_key, set()).add(identifier)
        for index in range(1, len(parts) + 1):
            identity_sets.setdefault("/".join(parts[:index]), set()).add(identifier)

    children = children_by_parent(taxonomy)
    for parent_id, child_nodes in children.items():
        parent_path = paths_by_node_id.get(parent_id)
        if not parent_path:
            continue
        parent_key = serialize_path(parent_path)
        union: set[str] = set()
        child_sets: list[tuple[str, set[str]]] = []
        for child in child_nodes:
            child_path = paths_by_node_id.get(child["id"])
            if not child_path:
                continue
            child_key = serialize_path(child_path)
            child_set = set(identity_sets.get(child_key, set()))
            child_sets.append((child_key, child_set))
            union.update(child_set)
        if not child_sets:
            union.update(direct_identity_sets.get(parent_key, set()))
        if identity_sets.get(parent_key, set()) != union:
            errors.append(f"digital taxonomy parent identity set is not the exact child union: {parent_key}")
        for (left_key, left_set), (right_key, right_set) in combinations(child_sets, 2):
            overlap = sorted(left_set & right_set)
            if overlap:
                errors.append(f"digital taxonomy child identity sets overlap below {parent_key}: {left_key} / {right_key} -> {overlap}")
    return errors


def validate_digital_ring_taxonomy(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in (
        CONTRACT_PATH,
        CATALOG_PATH,
        Path("contracts/commonworld/digital-sphere.contract.json"),
        Path("contracts/commonworld/aggregation-zoom.contract.json"),
        Path("assets/commonworld-core.mjs"),
    ):
        if not (root / relative).is_file():
            errors.append(f"missing digital ring taxonomy dependency: {relative}")
    if errors:
        return errors

    try:
        taxonomy = load_taxonomy(root)
        records = _records(root)
    except (OSError, json.JSONDecodeError) as error:
        return [f"digital ring taxonomy dependency is invalid: {error}"]

    if taxonomy.get("schema_version") != 1 or taxonomy.get("kind") != "commonworld_digital_ring_bundle_taxonomy":
        errors.append("digital ring taxonomy schema or kind mismatch")
    if taxonomy.get("version") != "digital-ring-bundles-v1":
        errors.append("digital ring taxonomy version mismatch")
    if "stable ids" not in taxonomy.get("version_rule", ""):
        errors.append("digital ring taxonomy version rule must protect stable ids")
    if taxonomy.get("levels") != ["sphere", "field", "network", "identity"]:
        errors.append("digital ring taxonomy levels must be sphere, field, network, identity")
    if taxonomy.get("root_id") != ROOT_ID:
        errors.append("digital ring taxonomy root_id must be sphere")
    bindings = taxonomy.get("binds_contracts", {}) if isinstance(taxonomy.get("binds_contracts"), dict) else {}
    if bindings.get("digital_sphere") != "contracts/commonworld/digital-sphere.contract.json":
        errors.append("digital ring taxonomy must bind to the digital-sphere contract")
    if bindings.get("aggregation_zoom") != "contracts/commonworld/aggregation-zoom.contract.json":
        errors.append("digital ring taxonomy must bind to the aggregation-zoom contract")
    if bindings.get("catalog_identity") != "CommonProject.id":
        errors.append("digital ring taxonomy must derive identity from CommonProject.id")

    nodes = taxonomy.get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        return errors + ["digital ring taxonomy nodes must be a non-empty list"]
    nodes_by_id = node_map(taxonomy)
    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(node_ids) != len(set(node_ids)):
        errors.append("digital ring taxonomy node ids must be unique")
    roots = [node for node in nodes if isinstance(node, dict) and node.get("parent_id") is None]
    if len(roots) != 1 or roots[0].get("id") != ROOT_ID or roots[0].get("type") != "sphere":
        errors.append("digital ring taxonomy must have exactly one sphere root")
    for node in nodes:
        if not isinstance(node, dict):
            errors.append("digital ring taxonomy node is malformed")
            continue
        identifier = node.get("id")
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
            errors.append(f"digital ring taxonomy node id is not stable ASCII: {identifier}")
        if node.get("type") not in {"sphere", "field", "network", "interface", "diagnostic"}:
            errors.append(f"digital ring taxonomy node has invalid type: {identifier}")
        if not isinstance(node.get("label_de"), str) or not node["label_de"].strip():
            errors.append(f"digital ring taxonomy node lacks a German label: {identifier}")
        if not isinstance(node.get("order"), int) or isinstance(node.get("order"), bool) or node["order"] < 0:
            errors.append(f"digital ring taxonomy node lacks stable order: {identifier}")
        parent_id = node.get("parent_id")
        if parent_id is not None and parent_id not in nodes_by_id:
            errors.append(f"digital ring taxonomy node has missing parent: {identifier}")
        path = path_for_node(taxonomy, identifier) if isinstance(identifier, str) else None
        if not path:
            errors.append(f"digital ring taxonomy node does not have a valid root path: {identifier}")
    for parent_id, siblings in children_by_parent(taxonomy).items():
        orders = [node.get("order") for node in siblings]
        if len(orders) != len(set(orders)):
            errors.append(f"digital ring taxonomy sibling order is not unique below {parent_id}")
        ids_in_file = [node.get("id") for node in nodes if isinstance(node, dict) and node.get("parent_id") == parent_id]
        ids_by_order = [node.get("id") for node in siblings]
        if ids_in_file != ids_by_order:
            errors.append(f"digital ring taxonomy sibling file order must match stable order below {parent_id}")
    for node in nodes:
        seen: set[str] = set()
        current = node if isinstance(node, dict) else None
        while current and current.get("parent_id") is not None:
            identifier = current.get("id")
            if identifier in seen:
                errors.append(f"digital ring taxonomy contains a cycle at {identifier}")
                break
            seen.add(identifier)
            current = nodes_by_id.get(current.get("parent_id"))

    fields = [
        node["id"]
        for node in nodes
        if isinstance(node, dict) and node.get("parent_id") == ROOT_ID and node.get("type") == "field"
    ]
    if fields != EXPECTED_FIELDS or taxonomy.get("main_field_order") != EXPECTED_FIELDS:
        errors.append("digital ring taxonomy must expose exactly the five canonical main fields")
    for identifier, label in EXPECTED_FIELD_LABELS.items():
        if nodes_by_id.get(identifier, {}).get("label_de") != label:
            errors.append(f"digital ring taxonomy field label mismatch: {identifier}")
    unknown_id = taxonomy.get("unknown_theme_node_id")
    if nodes_by_id.get(unknown_id, {}).get("type") != "diagnostic":
        errors.append("digital ring taxonomy unknown-theme node must be a diagnostic node")

    theme_owners: dict[str, str] = {}
    for node in nodes:
        for theme in node.get("themes", []) if isinstance(node, dict) else []:
            if not isinstance(theme, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,95}", theme):
                errors.append(f"digital ring taxonomy theme id is invalid: {theme}")
            if theme in theme_owners:
                errors.append(f"digital ring taxonomy theme has multiple owners: {theme}")
            theme_owners[theme] = node["id"]

    digital_records = [record for record in records if _is_digital(record)]
    if not digital_records:
        errors.append("digital ring taxonomy requires at least one current digital catalog identity")
    actual_themes = sorted({
        theme
        for record in digital_records
        for theme in record.get("themes", [])
        if isinstance(theme, str)
    })
    known_themes = taxonomy.get("known_current_digital_themes")
    if known_themes != actual_themes:
        errors.append("digital ring taxonomy known_current_digital_themes must equal the current digital catalog themes")
    for theme in actual_themes:
        owner = theme_owners.get(theme)
        if owner in {None, ROOT_ID, unknown_id}:
            errors.append(f"digital ring taxonomy current theme is not explicitly classified: {theme}")

    compound_keys: set[tuple[str, ...]] = set()
    for rule in taxonomy.get("compound_rules", []):
        if not isinstance(rule, dict) or not ID_PATTERN.fullmatch(str(rule.get("id", ""))):
            errors.append(f"digital ring taxonomy compound rule id is invalid: {rule}")
            continue
        themes = rule.get("all_themes", [])
        if not isinstance(themes, list) or not themes:
            errors.append(f"digital ring taxonomy compound rule has no themes: {rule.get('id')}")
            continue
        key = tuple(sorted(themes))
        if key in compound_keys:
            errors.append(f"digital ring taxonomy duplicate compound theme set: {rule.get('id')}")
        compound_keys.add(key)
        if rule.get("target_node_id") not in nodes_by_id or rule.get("target_node_id") == unknown_id:
            errors.append(f"digital ring taxonomy compound rule targets invalid node: {rule.get('id')}")
        if any(theme not in theme_owners for theme in themes):
            errors.append(f"digital ring taxonomy compound rule references an unknown theme: {rule.get('id')}")
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            errors.append(f"digital ring taxonomy compound rule lacks reason: {rule.get('id')}")
    tie_keys: set[tuple[str, ...]] = set()
    for rule in taxonomy.get("tie_rules", []):
        if not isinstance(rule, dict) or not ID_PATTERN.fullmatch(str(rule.get("id", ""))):
            errors.append(f"digital ring taxonomy tie rule id is invalid: {rule}")
            continue
        candidates = rule.get("candidate_node_ids", [])
        if not isinstance(candidates, list) or len(candidates) < 2 or any(candidate not in nodes_by_id for candidate in candidates):
            errors.append(f"digital ring taxonomy tie rule has invalid candidates: {rule.get('id')}")
        key = tuple(sorted(candidates))
        if key in tie_keys:
            errors.append(f"digital ring taxonomy duplicate tie rule candidate set: {rule.get('id')}")
        tie_keys.add(key)
        if rule.get("target_node_id") not in nodes_by_id or rule.get("target_node_id") == unknown_id:
            errors.append(f"digital ring taxonomy tie rule targets invalid node: {rule.get('id')}")
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            errors.append(f"digital ring taxonomy tie rule lacks reason: {rule.get('id')}")
    for field_id, target_id in (taxonomy.get("same_field_tie_fallbacks", {}) or {}).items():
        if field_id not in EXPECTED_FIELDS or target_id not in nodes_by_id:
            errors.append(f"digital ring taxonomy same-field fallback is invalid: {field_id}->{target_id}")
        elif _field_for_node(taxonomy, target_id) != field_id:
            errors.append(f"digital ring taxonomy same-field fallback must stay within its field: {field_id}->{target_id}")

    aliases = taxonomy.get("legacy_layer_aliases", [])
    alias_ids = {alias.get("alias") for alias in aliases if isinstance(alias, dict)}
    if alias_ids != LEGACY_LAYER_IDS:
        errors.append("digital ring taxonomy must map all six legacy layer ids")
    for alias in aliases:
        if not isinstance(alias, dict):
            errors.append("digital ring taxonomy legacy alias is malformed")
            continue
        normalized = normalize_path(alias.get("target_path"), taxonomy)
        if not normalized["valid"]:
            errors.append(f"digital ring taxonomy legacy alias target is invalid: {alias.get('alias')}")
        if alias.get("alias") == "mixed_other" and (normalized["path_key"] != ROOT_ID or alias.get("broad_alias_without_filter") is not True):
            errors.append("digital ring taxonomy legacy mixed_other must migrate to the root without a public rest filter")

    core = _core_taxonomy(root)
    if core is None:
        errors.append("digital ring taxonomy core export could not be read by Node")
    else:
        expected_core = {key: taxonomy.get(key) for key in CORE_TAXONOMY_KEYS}
        actual_core = {key: core.get(key) for key in CORE_TAXONOMY_KEYS}
        if _canon(actual_core) != _canon(expected_core):
            errors.append("digital ring taxonomy contract and core export diverge")

    path_by_id: dict[str, str] = {}
    for record in digital_records:
        derivation = derive_project_path(record, taxonomy)
        identifier = record.get("id")
        if not derivation:
            errors.append(f"digital ring taxonomy lost digital identity: {identifier}")
            continue
        if derivation.get("status") != "classified":
            errors.append(f"digital ring taxonomy does not classify current identity {identifier}: {derivation}")
        path_key = derivation.get("path_key")
        if not isinstance(path_key, str) or path_key in {ROOT_ID, serialize_path([ROOT_ID, str(unknown_id)])} or "mixed_other" in path_key:
            errors.append(f"digital ring taxonomy current identity has invalid public path: {identifier}:{path_key}")
        if identifier in path_by_id:
            errors.append(f"digital ring taxonomy duplicates current identity: {identifier}")
        elif isinstance(identifier, str) and isinstance(path_key, str):
            path_by_id[identifier] = path_key
    if sorted(path_by_id) != sorted(record.get("id") for record in digital_records):
        errors.append("digital ring taxonomy must derive exactly one path per digital CommonProject id")
    errors.extend(_validate_tree_sets(taxonomy, path_by_id))

    reversed_records = list(reversed(digital_records))
    reversed_themes = []
    for record in digital_records:
        clone = json.loads(json.dumps(record))
        if isinstance(clone.get("themes"), list):
            clone["themes"] = list(reversed(clone["themes"]))
        reversed_themes.append(clone)
    permuted_records = digital_records[7:] + digital_records[:7]
    for label, variant in {
        "reversed-records": reversed_records,
        "reversed-themes": reversed_themes,
        "permuted-records": permuted_records,
    }.items():
        variant_paths = {
            record["id"]: derive_project_path(record, taxonomy)["path_key"]
            for record in variant
            if _is_digital(record)
        }
        if variant_paths != path_by_id:
            errors.append(f"digital ring taxonomy derivation is not deterministic for {label}")

    def case(themes: list[str], available: bool = True) -> dict[str, Any] | None:
        return derive_project_path({"id": "case", "themes": themes, "presence": {"digital": {"available": available}}}, taxonomy)

    expected_cases = {
        "unique": (case(["free-software"]), "sphere/software_tools_production/free_software", "classified"),
        "same-field-tie": (case(["knowledge", "education"]), "sphere/knowledge_learning_culture/knowledge_learning_bridge", "classified"),
        "cross-field-tie": (case(["open-data", "open-source"]), "sphere/software_tools_production/knowledge_software_bridge", "classified"),
        "unknown": (case(["future-theme"]), "sphere/unclassified_future_theme", "unclassified"),
    }
    for label, (result, expected_path, expected_status) in expected_cases.items():
        if not result or result.get("path_key") != expected_path or result.get("status") != expected_status:
            errors.append(f"digital ring taxonomy derivation case failed: {label}:{result}")
    if case(["education"], available=False) is not None:
        errors.append("digital ring taxonomy must return no path for non-digital records")
    if expected_cases["unknown"][0] and expected_cases["unknown"][0].get("unknown_themes") != ["future-theme"]:
        errors.append("digital ring taxonomy unknown theme diagnostic must be machine-readable")

    for alias in sorted(LEGACY_LAYER_IDS):
        target = next((entry.get("target_path") for entry in aliases if isinstance(entry, dict) and entry.get("alias") == alias), None)
        if normalize_path(target, taxonomy).get("path") != target:
            errors.append(f"digital ring taxonomy legacy alias does not roundtrip: {alias}")
    roundtrip_path = ["sphere", "communication_networks", "community_networks"]
    if normalize_path(serialize_path(roundtrip_path), taxonomy).get("path") != roundtrip_path:
        errors.append("digital ring taxonomy canonical path string does not roundtrip")
    for value in ("", "sphere/../communication_networks", "sphere/communication_networks/../../catalog", "sphere/unknown", "communication_networks"):
        normalized = normalize_path(value, taxonomy)
        if value == "":
            if normalized.get("valid") is not True or normalized.get("path") != [ROOT_ID]:
                errors.append("digital ring taxonomy empty path must resolve to the root")
        elif normalized.get("valid") is not False or normalized.get("path") != [ROOT_ID]:
            errors.append(f"digital ring taxonomy invalid path must fail closed to root: {value}")

    runtime = taxonomy.get("runtime_requirements", {}) if isinstance(taxonomy.get("runtime_requirements"), dict) else {}
    expected_runtime = {
        "canonical_url_parameter": "digital_path",
        "legacy_layer_parameter": "preserved_as_filter_until_explicit_digital_path_selection",
        "invalid_path_behavior": "fail_closed_to_sphere_root_without_partial_filter",
        "primary_membership": "one_path_per_digital_commonproject_id",
        "child_identity_sets_disjoint_for_primary_membership": True,
        "parent_identity_set_equals_union_of_direct_children": True,
        "progressive_disclosure": "render_current_node_direct_children_and_breadcrumb_only",
        "identity_nodes_derive_from_commonproject_id": True,
        "unknown_future_themes_are_diagnostic_not_public_rest_bucket": True,
        "known_current_themes_must_not_route_to_unclassified": True,
        "legacy_mixed_other_is_not_a_public_rest_category": True,
        "catalog_presentation_fields_forbidden": True,
    }
    if runtime != expected_runtime:
        errors.append("digital ring taxonomy runtime requirements mismatch")

    return errors


def main() -> int:
    errors = validate_digital_ring_taxonomy(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld digital ring taxonomy validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
