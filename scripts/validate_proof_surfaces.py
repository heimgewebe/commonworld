#!/usr/bin/env python3
"""Validate the static commonworld proof surface registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PROOF_SURFACES_PATH = "proofs/proof-surfaces.json"
REQUIRED_SURFACE_IDS = ["project-profile", "map", "aether", "search"]


def proof_surfaces_path(root: Path = ROOT) -> Path:
    return root / PROOF_SURFACES_PATH


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def target_index_for_href(href: str) -> str:
    stripped = href.removeprefix("./").rstrip("/")
    return f"{stripped}/index.html"


def validate_proof_surface_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = proof_surfaces_path(root)
    if not path.is_file():
        return [f"missing proof surface registry: {PROOF_SURFACES_PATH}"]
    try:
        data = load_json(path)
    except json.JSONDecodeError:
        return ["proof surface registry is not valid JSON"]
    if data.get("schema_version") != 1:
        errors.append("proof surface registry must use schema_version 1")
    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list):
        return errors + ["proof surface registry must contain a surfaces list"]
    seen_ids: set[str] = set()
    actual_ids: list[str] = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            errors.append(f"proof surface registry surfaces[{index}] must be an object")
            continue
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"proof surface registry surfaces[{index}] needs id")
            continue
        actual_ids.append(surface_id)
        if surface_id in seen_ids:
            errors.append(f"proof surface registry duplicate id: {surface_id}")
        seen_ids.add(surface_id)
        for field in ("title", "href", "target_index", "role"):
            if not isinstance(surface.get(field), str) or not surface[field]:
                errors.append(f"proof surface registry {surface_id} needs {field}")
        href = surface.get("href")
        if isinstance(href, str) and (not href.startswith("./proofs/") or ".." in Path(href).parts):
            errors.append(f"proof surface registry {surface_id} href must stay under ./proofs/")
        target_index = surface.get("target_index")
        if isinstance(href, str) and isinstance(target_index, str):
            expected_target_index = target_index_for_href(href)
            if target_index != expected_target_index:
                errors.append(
                    f"proof surface registry {surface_id} target_index must match href target: {expected_target_index}"
                )
        if isinstance(target_index, str):
            if not target_index.startswith("proofs/") or ".." in Path(target_index).parts:
                errors.append(f"proof surface registry {surface_id} target_index must stay under proofs/")
            elif not (root / target_index).is_file():
                errors.append(f"proof surface registry target missing for {surface_id}: {target_index}")
    if actual_ids != REQUIRED_SURFACE_IDS:
        errors.append("proof surface registry must list project-profile, map, aether and search in hub order")
    return errors


def load_proof_surfaces(root: Path = ROOT) -> list[dict[str, str]]:
    errors = validate_proof_surface_registry(root)
    if errors:
        raise ValueError("; ".join(errors))
    data = load_json(proof_surfaces_path(root))
    return data["surfaces"]


def main() -> int:
    errors = validate_proof_surface_registry(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld proof surface registry validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
