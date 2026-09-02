#!/usr/bin/env python3
"""Validate source-bound Commons admission decisions and the legacy review queue."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = Path("contracts/commonworld/commons-definition.contract.json")
SCHEMA_PATH = Path("contracts/commonworld/commons-basis.schema.json")
CATALOG_PATH = Path("catalog/catalog.json")
BASIS_INDEX_PATH = Path("catalog/commons-bases/index.json")
RETRO_POLICY_PATH = Path("catalog/commons-bases/retroreview-policy.json")
DIMENSIONS = (
    "shared_resource",
    "community",
    "commoning_practice",
    "rules_and_responsibility",
    "common_benefit",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT, *, today: date | None = None) -> list[str]:
    today = today or date.today()
    errors: list[str] = []

    required_paths = (
        DEFINITION_PATH,
        SCHEMA_PATH,
        CATALOG_PATH,
        BASIS_INDEX_PATH,
        RETRO_POLICY_PATH,
    )
    for relative in required_paths:
        if not (root / relative).is_file():
            errors.append(f"missing Commons admission file: {relative}")
    if errors:
        return errors

    definition = _load(root / DEFINITION_PATH)
    schema = _load(root / SCHEMA_PATH)
    manifest = _load(root / CATALOG_PATH)
    index = _load(root / BASIS_INDEX_PATH)
    policy = _load(root / RETRO_POLICY_PATH)

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        errors.append(f"invalid Commons basis schema: {error}")
        return errors
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    if definition.get("kind") != "commonworld_commons_definition_contract":
        errors.append("invalid Commons definition contract kind")
    dimension_ids = [
        item.get("id")
        for item in definition.get("required_dimensions", [])
        if isinstance(item, dict)
    ]
    if dimension_ids != list(DIMENSIONS):
        errors.append(f"definition dimensions must be exactly {list(DIMENSIONS)}")
    try:
        effective_from = date.fromisoformat(definition["transition"]["effective_from"])
    except (KeyError, TypeError, ValueError):
        errors.append("definition transition effective_from must be a date")
        effective_from = date.max

    project_files = manifest.get("project_files", [])
    if not isinstance(project_files, list) or len(project_files) != manifest.get("entry_count"):
        errors.append("catalog manifest entry_count mismatch")
        return errors

    projects: dict[str, dict] = {}
    for relative in project_files:
        path = root / "catalog" / relative
        if not path.is_file():
            errors.append(f"catalog project file missing: {relative}")
            continue
        project = _load(path)
        project_id = project.get("id")
        if not isinstance(project_id, str):
            errors.append(f"{relative}: missing project id")
            continue
        if project_id in projects:
            errors.append(f"duplicate project id: {project_id}")
        projects[project_id] = project

    basis_files = index.get("basis_files", [])
    if not isinstance(basis_files, list):
        errors.append("Commons basis index basis_files must be an array")
        basis_files = []
    if basis_files != sorted(set(basis_files)):
        errors.append("Commons basis index basis_files must be sorted and unique")
    if len(basis_files) != index.get("entry_count"):
        errors.append("Commons basis index entry_count mismatch")

    bases: dict[str, dict] = {}
    for filename in basis_files:
        path = root / "catalog" / "commons-bases" / filename
        if not path.is_file():
            errors.append(f"Commons basis file missing: {filename}")
            continue
        basis = _load(path)
        for error in sorted(
            validator.iter_errors(basis),
            key=lambda item: (list(item.path), item.message),
        ):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{filename}:{location}: {error.message}")
        project_id = basis.get("project_id")
        if not isinstance(project_id, str):
            continue
        if project_id in bases:
            errors.append(f"duplicate Commons basis project_id: {project_id}")
        bases[project_id] = basis
        project = projects.get(project_id)
        if project is None:
            errors.append(f"{filename}: unknown catalog project {project_id}")
            continue
        known_sources = {
            source.get("id")
            for source in project.get("provenance", {}).get("sources", [])
            if isinstance(source, dict) and isinstance(source.get("id"), str)
        }
        statuses: dict[str, object] = {}
        for dimension in DIMENSIONS:
            criterion = basis.get("criteria", {}).get(dimension, {})
            statuses[dimension] = criterion.get("status")
            unknown = sorted(set(criterion.get("source_ids", [])) - known_sources)
            if unknown:
                errors.append(
                    f"{filename}:{dimension} references unknown project sources: {unknown}"
                )

        decision = basis.get("decision")
        if decision == "include":
            not_supported = [
                dimension
                for dimension, status in statuses.items()
                if status != "supported"
            ]
            if not_supported:
                errors.append(
                    f"{filename}: include decision requires supported dimensions: {not_supported}"
                )
        elif decision == "needs_information":
            unresolved = [
                dimension
                for dimension, status in statuses.items()
                if status in {"partial", "unknown"}
            ]
            contradicted = [
                dimension
                for dimension, status in statuses.items()
                if status == "unsupported"
            ]
            if not unresolved:
                errors.append(
                    f"{filename}: needs_information requires at least one partial or unknown dimension"
                )
            if contradicted:
                errors.append(
                    f"{filename}: unsupported dimensions require reject, not needs_information: {contradicted}"
                )
        elif decision == "reject":
            contradicted = [
                dimension
                for dimension, status in statuses.items()
                if status == "unsupported"
            ]
            if not contradicted:
                errors.append(
                    f"{filename}: reject requires at least one unsupported dimension"
                )

        try:
            basis_reviewed_at = date.fromisoformat(basis["reviewed_at"])
            project_reviewed_at = date.fromisoformat(project["curation"]["reviewed_at"])
            if basis_reviewed_at != project_reviewed_at:
                errors.append(
                    f"{filename}: basis reviewed_at must equal project curation.reviewed_at"
                )
        except (KeyError, TypeError, ValueError):
            pass

    queue: list[tuple[date, str]] = []
    for project_id, project in projects.items():
        curation = project.get("curation", {})
        try:
            reviewed_at = date.fromisoformat(curation["reviewed_at"])
            next_review_at = date.fromisoformat(curation["next_review_at"])
            catalogued_at = date.fromisoformat(curation.get("catalogued_at", "9999-12-31"))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{project_id}: invalid or missing curation review dates")
            continue

        requires_basis = reviewed_at >= effective_from or catalogued_at >= effective_from
        basis = bases.get(project_id)
        if requires_basis and basis is None:
            errors.append(
                f"{project_id}: new or materially re-reviewed record lacks Commons basis"
            )
        if basis is not None and basis.get("decision") != "include":
            if curation.get("state") not in {"candidate", "stale", "archived"}:
                errors.append(
                    f"{project_id}: non-include Commons decision cannot remain {curation.get('state')}"
                )
        public_state = curation.get("state") in {"listed", "verified", "featured"}
        if basis is None:
            try:
                migration_grace_until = date.fromisoformat(
                    policy["deadline"]["migration_grace_until"]
                )
            except (KeyError, TypeError, ValueError):
                errors.append("retro-review policy migration_grace_until must be a date")
                migration_grace_until = effective_from
            effective_deadline = max(next_review_at, migration_grace_until)
            queue.append((effective_deadline, project_id))
            if today > effective_deadline and public_state:
                errors.append(
                    f"{project_id}: legacy Commons basis review overdue since {effective_deadline}"
                )
        elif today > next_review_at and public_state:
            errors.append(
                f"{project_id}: Commons basis re-review overdue since {next_review_at}"
            )

    if policy.get("scope", {}).get("selection") != "all_catalog_records_without_commons_basis":
        errors.append("retro-review policy must dynamically select every record without a basis")
    if policy.get("deadline", {}).get("source_field") != "curation.next_review_at":
        errors.append("retro-review policy deadline must use curation.next_review_at")
    if policy.get("publication_effect", {}).get("automatic_publication_or_rejection") is not False:
        errors.append("retro-review policy must not automate publication or rejection")

    expected_basis_ids = sorted(bases)
    indexed_basis_ids = sorted(Path(item).stem for item in basis_files)
    if expected_basis_ids != indexed_basis_ids:
        errors.append("Commons basis filenames must equal their project ids")

    if not errors:
        queue.sort()
        next_due = queue[0][0].isoformat() if queue else "none"
        print(
            f"Commons admission ok: {len(bases)} structured bases; "
            f"{len(queue)} legacy records queued; next due {next_due}"
        )
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
