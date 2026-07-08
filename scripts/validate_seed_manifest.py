#!/usr/bin/env python3
"""Validate the shared commonworld seed project manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_contracts import iter_project_examples


def seed_manifest_path(root: Path = ROOT) -> Path:
    return root / "examples" / "commonworld" / "seed-projects.json"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def expected_seed_paths(root: Path = ROOT) -> list[str]:
    manifest_directory = seed_manifest_path(root).parent
    return [path.relative_to(manifest_directory).as_posix() for path in iter_project_examples(root)]


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_seed_manifest(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = seed_manifest_path(root)
    if not manifest_path.is_file():
        return [f"missing shared seed manifest: {manifest_path.relative_to(root)}"]
    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError:
        return ["seed-projects.json is not valid JSON"]

    if manifest.get("schema_version") != 1:
        errors.append("seed-projects.json must use schema_version 1")

    project_paths = manifest.get("project_paths")
    expected_paths = expected_seed_paths(root)
    if project_paths != expected_paths:
        errors.append("seed-projects.json must list all project examples in deterministic order")

    if isinstance(project_paths, list):
        for project_path in project_paths:
            if not isinstance(project_path, str):
                errors.append("seed-projects.json project_paths entries must be strings")
                continue
            if project_path.startswith("/") or ".." in Path(project_path).parts:
                errors.append("seed-projects.json project_paths entries must stay inside examples/commonworld")
                continue
            referenced_path = (manifest_path.parent / project_path).resolve()
            projects_dir = (root / "examples" / "commonworld" / "projects").resolve()
            if not path_is_relative_to(referenced_path, projects_dir):
                errors.append("seed-projects.json project_paths entries must point into examples/commonworld/projects")
                continue
            if not referenced_path.is_file():
                errors.append(f"seed-projects.json references missing seed file: {project_path}")
    else:
        errors.append("seed-projects.json must contain a project_paths list")

    return errors


def main() -> int:
    errors = validate_seed_manifest(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld seed manifest validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
