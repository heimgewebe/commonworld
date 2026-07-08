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


def validate_source_requirements(source: dict[str, Any], context: str) -> list[str]:
    errors: list[str] = []
    source_type = source.get("type")
    if source_type in {"official-source", "public-registry"}:
        if not source.get("url") or not source.get("retrieved_at"):
            errors.append(f"{context}: {source_type} sources need url and retrieved_at")
    if source_type in {"manual-curation", "derived"}:
        if not source.get("note"):
            errors.append(f"{context}: {source_type} sources need note")
    return errors


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
    curation_state = curation.get("state")
    provenance_sources = project.get("provenance", {}).get("sources", [])
    source_types = [source.get("type") for source in provenance_sources]
    non_fixture_sources = [source for source in provenance_sources if source.get("type") != "fixture"]

    if curation_state == "fixture":
        if not any(source_type == "fixture" for source_type in source_types):
            errors.append("fixture entries need fixture provenance")
        if any(source_type != "fixture" for source_type in source_types):
            errors.append("fixture entries must not mix fixture and non-fixture provenance")
    else:
        if any(source_type == "fixture" for source_type in source_types):
            errors.append("non-fixture entries must not rely on fixture provenance")

    if curation_state in {"candidate", "curated", "archived"}:
        if not curation.get("reviewed_by") or not curation.get("reviewed_at"):
            errors.append("candidate, curated and archived entries need reviewed_by and reviewed_at")
        if not non_fixture_sources:
            errors.append("candidate, curated and archived entries need non-fixture provenance")

    if curation_state == "curated":
        if len(non_fixture_sources) < 2:
            errors.append("curated entries need at least two non-fixture sources")
        if non_fixture_sources and all(source.get("type") == "derived" for source in non_fixture_sources):
            errors.append("curated entries must not rely only on derived sources")

    for index, source in enumerate(provenance_sources):
        errors.extend(validate_source_requirements(source, f"provenance.sources[{index}]"))

    for aspect in project.get("aspects", []):
        aspect_id = aspect.get("id", "<unknown>")
        for index, source in enumerate(aspect.get("evidence", [])):
            errors.extend(validate_source_requirements(source, f"aspects[{aspect_id}].evidence[{index}]"))

    handoff = project.get("handoff")
    if handoff and not handoff.get("enabled") and any(
        key in handoff for key in ("project_id", "url", "action_label")
    ):
        errors.append("disabled handoff must not expose action fields")
    if handoff and handoff.get("enabled") is True:
        if curation_state != "curated":
            errors.append("handoff actions require curated curation state")
        if handoff.get("system") != "weltgewebe":
            errors.append("handoff actions must target weltgewebe")
        if not handoff.get("project_id"):
            errors.append("handoff actions require weltgewebe project_id")
        if not handoff.get("url"):
            errors.append("handoff actions require explicit weltgewebe URL")
        action_label = handoff.get("action_label", "").casefold()
        forbidden_action_terms = ("join", "manage", "decide", "administer", "submit", "coordinate")
        if any(term in action_label for term in forbidden_action_terms):
            errors.append("handoff action_label must stay neutral until authorization is modeled")
    if curation_state == "archived" and handoff and handoff.get("enabled") is True:
        errors.append("archived entries must not expose handoff actions")

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
