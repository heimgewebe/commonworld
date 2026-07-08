#!/usr/bin/env python3
"""Generate the static commonworld catalog export sample deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEED_MANIFEST_PATH = ROOT / "examples" / "commonworld" / "seed-projects.json"
DEFAULT_OUTPUT_PATH = Path("examples/commonworld/catalog-export.sample.json")

BOUNDARY = {
    "access": "read-only",
    "write_behavior": "no writes, no submissions, no publication side effects",
    "authority": "derived projection only; CommonProject files remain the catalog claim source",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def relative_project_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def project_entry_for(path: Path, root: Path) -> dict[str, str]:
    project = load_json(path)
    profile = project.get("projections", {}).get("profile", {})
    return {
        "id": project["id"],
        "project_path": relative_project_path(path, root),
        "curation_state": project.get("curation", {}).get("state", ""),
        "location_mode": project.get("location", {}).get("mode", ""),
        "profile_handoff_state": profile.get("handoff_state", "none"),
    }


def iter_manifest_project_paths(root: Path) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    manifest_path = root / SEED_MANIFEST_PATH.relative_to(ROOT)
    manifest = load_json(manifest_path)
    manifest_dir = (root / "examples" / "commonworld").resolve()
    projects_dir = (manifest_dir / "projects").resolve()
    project_paths: list[Path] = []

    for project_path in manifest.get("project_paths", []):
        if not isinstance(project_path, str):
            errors.append("catalog export source manifest project_paths entries must be strings")
            continue
        candidate = (manifest_dir / project_path).resolve()
        try:
            candidate.relative_to(projects_dir)
        except ValueError:
            errors.append("catalog export source manifest project_paths entries must stay inside examples/commonworld/projects")
            continue
        if not candidate.is_file():
            errors.append(f"catalog export source manifest references missing project file: {project_path}")
            continue
        project_paths.append(candidate)

    return project_paths, errors


def build_catalog_export(root: Path = ROOT) -> tuple[dict[str, Any], list[str]]:
    root = root.resolve()
    project_paths, errors = iter_manifest_project_paths(root)
    entries = [project_entry_for(path, root) for path in project_paths]
    export = {
        "schema_version": 1,
        "kind": "commonworld.static_catalog_export",
        "scope": "proof",
        "source_manifest_path": "examples/commonworld/seed-projects.json",
        "entries": entries,
        "boundary": dict(BOUNDARY),
    }
    return export, errors


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_catalog_export(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(data), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root. Defaults to this checkout.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output file relative to --root unless absolute. Defaults to examples/commonworld/catalog-export.sample.json.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the output file is not up to date.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    export, errors = build_catalog_export(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    generated = stable_json(export)
    if args.check:
        if not output.is_file():
            print(f"ERROR: missing catalog export output: {output.relative_to(root)}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != generated:
            print(f"ERROR: catalog export output is stale: {output.relative_to(root)}", file=sys.stderr)
            return 1
        print("commonworld catalog export is up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"wrote {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
