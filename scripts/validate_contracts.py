#!/usr/bin/env python3
"""Validate commonworld CommonProject contracts and seed fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
ASPECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "aspect.schema.json"
PROJECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"
PROJECT_EXAMPLES_DIR = ROOT / "examples" / "commonworld" / "projects"
WEIGHT_TOLERANCE = 0.001


class ContractValidationError(Exception):
    """Raised when a commonworld contract or fixture is invalid."""


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_contract_set(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], Registry]:
    aspect_schema = load_json(root / "contracts" / "commonworld" / "aspect.schema.json")
    project_schema = load_json(root / "contracts" / "commonworld" / "project.schema.json")

    Draft202012Validator.check_schema(aspect_schema)
    Draft202012Validator.check_schema(project_schema)

    registry = Registry().with_resources(
        [
            (aspect_schema["$id"], Resource.from_contents(aspect_schema)),
            (project_schema["$id"], Resource.from_contents(project_schema)),
        ]
    )
    return aspect_schema, project_schema, registry


def iter_project_examples(root: Path = ROOT) -> Iterable[Path]:
    return sorted((root / "examples" / "commonworld" / "projects").glob("*.json"))


def semantic_errors(project: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    aspect_ids = [aspect["id"] for aspect in project.get("aspects", [])]
    if len(aspect_ids) != len(set(aspect_ids)):
        errors.append("aspect ids must be unique within one project")

    weight_sum = sum(float(aspect["weight"]) for aspect in project.get("aspects", []))
    if abs(weight_sum - 1.0) > WEIGHT_TOLERANCE:
        errors.append(f"aspect weights must sum to 1.0, got {weight_sum:.3f}")

    location = project.get("location", {})
    location_mode = location.get("mode")
    projections = project.get("projections", {})
    projection_keys = set(projections)
    map_projection = projections.get("map", {})
    profile_projection = projections.get("profile", {})
    sphere = project.get("sphere")

    if "profile" not in projection_keys:
        errors.append("all projects must include a profile projection")

    if location_mode == "hidden" and "map" in projection_keys:
        errors.append("hidden locations must not expose a map projection")

    if sphere == "place":
        if "map" not in projection_keys:
            errors.append("place projects must include a map projection")
        if "aether" in projection_keys:
            errors.append("place projects must not include an aether projection; use hybrid when a digital extension exists")

    if sphere == "digital":
        if "aether" not in projection_keys:
            errors.append("digital projects must include an aether projection")
        if "map" in projection_keys:
            errors.append("digital projects must not include a map projection; use hybrid when a map anchor exists")

    if sphere == "hybrid":
        if "aether" not in projection_keys:
            errors.append("hybrid projects must include an aether projection")
        if location_mode in {"exact", "approximate"} and "map" not in projection_keys:
            errors.append("location-safe hybrid projects must include a map projection")

    if map_projection:
        appearance = map_projection.get("appearance")
        location_claim = map_projection.get("location_claim")
        if location_mode == "approximate" and location_claim != "approximate":
            errors.append("approximate locations must use approximate map location_claim")
        if appearance == "approximate-halo" and location_claim != "approximate":
            errors.append("approximate-halo must use approximate location_claim")
        if appearance == "local-marker" and location_claim != "exact":
            errors.append("local-marker must use exact location_claim")

    if project.get("handoff", {}).get("enabled") is False and profile_projection.get("handoff_state") == "available":
        errors.append("disabled handoff must not have available profile handoff_state")

    if location_mode == "hidden" and "coordinates" in location:
        errors.append("hidden locations must not include coordinates")

    if location_mode == "exact" and location.get("precision") != "exact":
        errors.append("exact locations must use precision exact")

    curation = project.get("curation", {})
    provenance_sources = project.get("provenance", {}).get("sources", [])
    if curation.get("state") == "fixture":
        if not any(source.get("type") == "fixture" for source in provenance_sources):
            errors.append("fixture entries need fixture provenance")
    else:
        if not all(source.get("type") != "fixture" for source in provenance_sources):
            errors.append("non-fixture entries must not rely on fixture provenance")

    handoff = project.get("handoff")
    if handoff and not handoff.get("enabled") and any(
        key in handoff for key in ("project_id", "url", "action_label")
    ):
        errors.append("disabled handoff must not expose action fields")

    return errors

def validate_project(
    project: dict[str, Any],
    *,
    project_schema: dict[str, Any],
    registry: Registry,
) -> list[str]:
    validator = Draft202012Validator(
        project_schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    schema_errors = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(project), key=lambda item: list(item.absolute_path))
    ]
    return schema_errors + semantic_errors(project)


def validate_all(root: Path = ROOT) -> list[str]:
    _, project_schema, registry = load_contract_set(root)

    example_paths = list(iter_project_examples(root))
    errors: list[str] = []
    if len(example_paths) < 2:
        errors.append("at least two project examples are required")

    for path in example_paths:
        project = load_json(path)
        project_errors = validate_project(
            project,
            project_schema=project_schema,
            registry=registry,
        )
        errors.extend(f"{path.relative_to(root)}: {error}" for error in project_errors)

    return errors


def main() -> int:
    errors = validate_all(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("commonworld contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
