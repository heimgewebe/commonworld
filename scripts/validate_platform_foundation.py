#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_RELATIVE_PATH = Path("contracts/commonworld/platform-foundation-gate.contract.json")


class RobotsMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.directives: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {name.lower(): (value or "") for name, value in attrs}
        if values.get("name", "").lower() == "robots":
            self.directives.extend(
                token.strip().lower()
                for token in values.get("content", "").split(",")
                if token.strip()
            )


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing authoritative input: {path.relative_to(path.parents[2]) if len(path.parents) > 2 else path}")
        return {}
    except json.JSONDecodeError as error:
        errors.append(f"invalid JSON in {path}: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"authoritative input must be an object: {path}")
        return {}
    return value


def nested(value: dict[str, Any], path: tuple[str, ...], errors: list[str], label: str) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            errors.append(f"missing {label}: {'.'.join(path)}")
            return None
        current = current[key]
    return current


def has_noindex(path: Path, errors: list[str]) -> bool:
    try:
        markup = path.read_text(encoding="utf-8")
    except OSError as error:
        errors.append(f"cannot read candidate locale surface {path}: {error}")
        return False
    parser = RobotsMetaParser()
    try:
        parser.feed(markup)
    except Exception as error:  # HTMLParser can surface malformed declarations.
        errors.append(f"cannot parse candidate locale surface {path}: {error}")
        return False
    return "noindex" in parser.directives


def validate_platform_foundation(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    gate = load_json(root / GATE_RELATIVE_PATH, errors)
    inputs = gate.get("authoritative_inputs")
    if not isinstance(inputs, dict):
        errors.append("missing authoritative_inputs object")
        return errors, {}

    required_inputs = {"catalog", "commons_basis_index", "current_state", "locale_release", "project_schema"}
    missing_inputs = sorted(required_inputs - set(inputs))
    extra_inputs = sorted(set(inputs) - required_inputs)
    if missing_inputs:
        errors.append(f"missing authoritative input declarations: {', '.join(missing_inputs)}")
    if extra_inputs:
        errors.append(f"undeclared validator inputs must be removed or enforced: {', '.join(extra_inputs)}")
    if missing_inputs:
        return errors, {}

    catalog = load_json(root / str(inputs["catalog"]), errors)
    basis = load_json(root / str(inputs["commons_basis_index"]), errors)
    current = load_json(root / str(inputs["current_state"]), errors)
    locale = load_json(root / str(inputs["locale_release"]), errors)
    schema = load_json(root / str(inputs["project_schema"]), errors)

    project_files = catalog.get("project_files")
    basis_files = basis.get("basis_files")
    if not isinstance(project_files, list) or not all(isinstance(item, str) for item in project_files):
        errors.append("catalog project_files must be an array of relative paths")
        project_files = []
    if not isinstance(basis_files, list) or not all(isinstance(item, str) for item in basis_files):
        errors.append("basis_files must be an array of relative paths")
        basis_files = []

    if catalog.get("entry_count") != len(project_files):
        errors.append("catalog entry_count drift")
    if basis.get("entry_count") != len(basis_files):
        errors.append("basis entry_count drift")
    if len(set(project_files)) != len(project_files):
        errors.append("duplicate catalog project file")
    if len(set(basis_files)) != len(basis_files):
        errors.append("duplicate Commons basis file")

    project_ids: set[str] = set()
    for relative in project_files:
        project = load_json(root / "catalog" / relative, errors)
        project_id = project.get("id")
        if isinstance(project_id, str):
            project_ids.add(project_id)
        else:
            errors.append(f"catalog project lacks string id: {relative}")

    basis_ids: set[str] = set()
    for relative in basis_files:
        entry = load_json(root / "catalog/commons-bases" / relative, errors)
        project_id = entry.get("project_id")
        if isinstance(project_id, str):
            basis_ids.add(project_id)
        else:
            errors.append(f"Commons basis lacks string project_id: {relative}")

    unknown_basis_ids = sorted(basis_ids - project_ids)
    if unknown_basis_ids:
        errors.append(f"Commons basis references unknown projects: {', '.join(unknown_basis_ids)}")

    debt = len(project_ids - basis_ids)
    baseline = gate.get("baseline")
    if not isinstance(baseline, dict) or not isinstance(baseline.get("legacy_basis_debt_ceiling"), int):
        errors.append("baseline legacy_basis_debt_ceiling must be an integer")
        debt_ceiling = -1
    else:
        debt_ceiling = baseline["legacy_basis_debt_ceiling"]
    if debt_ceiling >= 0 and debt > debt_ceiling:
        errors.append(f"Commons basis debt increased: {debt} > {debt_ceiling}")
    if catalog.get("entry_count") - basis.get("entry_count", 0) != debt:
        errors.append("derived basis debt mismatch")

    schema_states_raw = nested(schema, ("$defs", "activity", "properties", "status", "enum"), errors, "project activity states")
    current_states_raw = nested(current, ("activity_status_policy", "public_states"), errors, "current activity states")
    schema_states = set(schema_states_raw) if isinstance(schema_states_raw, list) else set()
    current_states = set(current_states_raw) if isinstance(current_states_raw, list) else set()
    # This enum is deliberately the public activity vocabulary. Internal editorial
    # workflow states belong in a separate schema field and must not leak here.
    if current_states != schema_states:
        errors.append("public activity status policy drifts from project schema")

    decision = locale.get("decision")
    rollout = locale.get("rollout")
    registry = locale.get("locale_registry")
    released = set(decision.get("released_locales", [])) if isinstance(decision, dict) else set()
    candidates = {
        tag: data
        for tag, data in registry.items()
        if isinstance(registry, dict) and isinstance(data, dict) and data.get("status") == "candidate"
    } if isinstance(registry, dict) else {}
    if released & candidates.keys():
        errors.append("candidate locale listed as released")
    if not isinstance(rollout, dict) or rollout.get("candidate_locales_must_not_be_selectable") is not True:
        errors.append("candidate locales became selectable")
    if not isinstance(rollout, dict) or rollout.get("candidate_surfaces_must_be_noindex") is not True:
        errors.append("candidate noindex gate disabled")
    for tag, data in candidates.items():
        surfaces = data.get("surface_files")
        if not isinstance(surfaces, dict):
            errors.append(f"candidate locale has no surface_files object: {tag}")
            continue
        for surface in surfaces.values():
            if not isinstance(surface, str) or not has_noindex(root / surface, errors):
                errors.append(f"candidate locale surface is indexable: {surface}")

    gate_decision = gate.get("decision")
    expected_decision = {
        "catalog_intake_mode": "bounded_evidence_complete_only",
        "locale_activation_mode": "candidate_only",
        "wide_or_automated_catalog_expansion_allowed": False,
        "new_locale_automatic_selection_allowed": False,
        "new_locale_indexing_allowed": False,
    }
    if gate_decision != expected_decision:
        errors.append("platform foundation decision differs from the enforced policy")

    expected_invariants = {
        "catalog_counts_are_derived_not_hardcoded": True,
        "basis_debt_must_not_grow": True,
        "candidate_locales_must_be_noindex": True,
        "candidate_locales_must_not_be_selectable": True,
        "public_activity_status_sets_must_match_project_schema": True,
    }
    if gate.get("invariants") != expected_invariants:
        errors.append("platform foundation invariants contain unenforced or weakened declarations")

    report = {
        "catalog_entries": len(project_ids),
        "structured_basis_entries": len(basis_ids),
        "legacy_basis_debt": debt,
        "legacy_basis_debt_ceiling": debt_ceiling,
        "candidate_locales": sorted(candidates),
        "activity_states": sorted(current_states),
    }
    return errors, report


def main() -> int:
    errors, report = validate_platform_foundation()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
