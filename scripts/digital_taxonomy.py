"""Shared digital ring-bundle taxonomy helpers for generators and validators."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("contracts/commonworld/digital-ring-taxonomy.contract.json")
ROOT_ID = "sphere"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")


def load_taxonomy(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))


def node_map(taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in taxonomy.get("nodes", []) if isinstance(node, dict) and isinstance(node.get("id"), str)}


def children_by_parent(taxonomy: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    children: dict[str, list[dict[str, Any]]] = {}
    for node in taxonomy.get("nodes", []):
        parent = node.get("parent_id") if isinstance(node, dict) else None
        if isinstance(parent, str):
            children.setdefault(parent, []).append(node)
    for siblings in children.values():
        siblings.sort(key=lambda node: (node.get("order", 0), node.get("id", "")))
    return children


def path_for_node(taxonomy: dict[str, Any], node_id: str) -> list[str] | None:
    nodes = node_map(taxonomy)
    node = nodes.get(node_id)
    path: list[str] = []
    seen: set[str] = set()
    while node:
        identifier = node["id"]
        if identifier in seen:
            return None
        seen.add(identifier)
        path.insert(0, identifier)
        parent = node.get("parent_id")
        if parent is None:
            break
        node = nodes.get(parent)
    return path if path and path[0] == taxonomy.get("root_id", ROOT_ID) else None


def serialize_path(path: list[str] | tuple[str, ...] | str | None) -> str:
    if isinstance(path, str):
        parts = [part.strip() for part in path.split("/") if part.strip()]
    elif path:
        parts = [str(part).strip() for part in path if str(part).strip()]
    else:
        parts = [ROOT_ID]
    return "/".join(parts or [ROOT_ID])


def normalize_path(value: object, taxonomy: dict[str, Any]) -> dict[str, Any]:
    root = [taxonomy.get("root_id", ROOT_ID)]
    fail = {"valid": False, "path": root, "path_key": serialize_path(root), "node_id": root[0]}
    # Only an absent/empty value denotes the root; every explicit slash must separate two canonical segments.
    if not isinstance(value, list) and str(value or "") == "":
        return {"valid": True, "path": root, "path_key": serialize_path(root), "node_id": root[0]}
    parts = [str(part) for part in value] if isinstance(value, list) else str(value or "").split("/")
    if not parts or any(not part or part != part.strip() for part in parts):
        return fail
    if any(part in {".", ".."} or not ID_PATTERN.fullmatch(part) for part in parts):
        return fail
    nodes = node_map(taxonomy)
    if parts[0] != taxonomy.get("root_id", ROOT_ID) or parts[0] not in nodes:
        return fail
    current = nodes[parts[0]]
    for part in parts[1:]:
        child = nodes.get(part)
        if not child or child.get("parent_id") != current["id"]:
            return fail
        current = child
    return {"valid": True, "path": parts, "path_key": serialize_path(parts), "node_id": current["id"]}


def theme_map(taxonomy: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node in taxonomy.get("nodes", []):
        for theme in node.get("themes", []) if isinstance(node, dict) else []:
            mapping[theme] = node["id"]
    return mapping


def _field_id(taxonomy: dict[str, Any], node_id: str) -> str | None:
    nodes = node_map(taxonomy)
    node = nodes.get(node_id)
    while node and node.get("parent_id") not in (None, taxonomy.get("root_id", ROOT_ID)):
        node = nodes.get(node.get("parent_id"))
    return node["id"] if node and node.get("type") == "field" else None


def _add_candidate(candidates: dict[str, dict[str, Any]], node_id: str, score: int, themes: list[str], source: str) -> None:
    current = candidates.get(node_id)
    if current is None or current["score"] < score:
        candidates[node_id] = {
            "node_id": node_id,
            "score": score,
            "matched_themes": set(themes) if current is None else set(current["matched_themes"]) | set(themes),
            "sources": {source} if current is None else set(current["sources"]) | {source},
        }
    elif source.startswith("theme:") and all(str(entry).startswith("theme:") for entry in current["sources"]):
        current["score"] += score
        current["matched_themes"].update(themes)
        current["sources"].add(source)
    elif current["score"] == score:
        current["matched_themes"].update(themes)
        current["sources"].add(source)


def derive_project_path(record: dict[str, Any], taxonomy: dict[str, Any] | None = None) -> dict[str, Any] | None:
    taxonomy = taxonomy or load_taxonomy()
    if record.get("presence", {}).get("digital", {}).get("available") is not True:
        return None
    themes = sorted({theme for theme in record.get("themes", []) if isinstance(theme, str)})
    mapping = theme_map(taxonomy)
    unknown = [theme for theme in themes if theme not in mapping]
    candidates: dict[str, dict[str, Any]] = {}
    for theme in themes:
        target = mapping.get(theme)
        if target:
            _add_candidate(candidates, target, 1, [theme], f"theme:{theme}")
    theme_set = set(themes)
    for rule in taxonomy.get("compound_rules", []):
        all_themes = rule.get("all_themes", [])
        if all_themes and all(theme in theme_set for theme in all_themes):
            _add_candidate(candidates, rule["target_node_id"], len(all_themes) + 1, list(all_themes), f"compound:{rule['id']}")
    diagnostic_path = path_for_node(taxonomy, taxonomy["unknown_theme_node_id"]) or [taxonomy.get("root_id", ROOT_ID)]
    if not candidates:
        return {
            "status": "unclassified",
            "reason": "no-known-digital-theme",
            "path": diagnostic_path,
            "path_key": serialize_path(diagnostic_path),
            "node_id": taxonomy["unknown_theme_node_id"],
            "matched_themes": [],
            "unknown_themes": unknown,
            "candidate_node_ids": [],
        }
    maximum = max(candidate["score"] for candidate in candidates.values())
    winners = [candidate for candidate in candidates.values() if candidate["score"] == maximum]
    if len(winners) > 1:
        winner_ids = sorted(candidate["node_id"] for candidate in winners)
        for rule in taxonomy.get("tie_rules", []):
            if sorted(rule.get("candidate_node_ids", [])) == winner_ids:
                matched = sorted(set().union(*(winner["matched_themes"] for winner in winners)))
                winners = [{"node_id": rule["target_node_id"], "score": maximum, "matched_themes": set(matched), "sources": {f"tie:{rule['id']}"}}]
                break
        else:
            fields = sorted({_field_id(taxonomy, node_id) for node_id in winner_ids} - {None})
            fallback = taxonomy.get("same_field_tie_fallbacks", {}).get(fields[0]) if len(fields) == 1 else None
            if fallback:
                matched = sorted(set().union(*(winner["matched_themes"] for winner in winners)))
                winners = [{"node_id": fallback, "score": maximum, "matched_themes": set(matched), "sources": {f"same-field:{fields[0]}"}}]
    if len(winners) != 1:
        return {
            "status": "unclassified",
            "reason": "unresolved-theme-tie",
            "path": diagnostic_path,
            "path_key": serialize_path(diagnostic_path),
            "node_id": taxonomy["unknown_theme_node_id"],
            "matched_themes": [],
            "unknown_themes": unknown,
            "candidate_node_ids": sorted(candidate["node_id"] for candidate in winners),
        }
    winner = winners[0]
    path = path_for_node(taxonomy, winner["node_id"]) or [taxonomy.get("root_id", ROOT_ID)]
    return {
        "status": "classified_with_unknown_theme_diagnostic" if unknown else "classified",
        "reason": "+".join(sorted(winner["sources"])),
        "path": path,
        "path_key": serialize_path(path),
        "node_id": winner["node_id"],
        "matched_themes": sorted(winner["matched_themes"]),
        "unknown_themes": unknown,
        "candidate_node_ids": [winner["node_id"]],
    }


def path_label(path: list[str], taxonomy: dict[str, Any], include_root: bool = False) -> str:
    nodes = node_map(taxonomy)
    labels = [
        nodes[node_id]["label_de"]
        for node_id in path
        if node_id in nodes and (include_root or node_id != taxonomy.get("root_id", ROOT_ID))
    ]
    return " › ".join(labels)
