#!/usr/bin/env python3
"""Generate the static commonworld search index input sample deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_catalog_export import build_catalog_export, stable_json
from scripts.validate_search_index_input_contract import ALLOWED_FIELD_IDS, validate_search_index_input_contract

CATALOG_EXPORT_PATH = ROOT / "examples" / "commonworld" / "catalog-export.sample.json"
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "search-index-input.contract.json"
DEFAULT_OUTPUT_PATH = Path("examples/commonworld/search-index-input.sample.json")
TASK = "COMMONWORLD-ATLAS-V1-T015"
KIND = "commonworld.static_search_index_input"

BOUNDARY = {
    "implementation": "no search service",
    "persistence": "no database or vector store",
    "ingestion": "no crawler or live ingestion worker",
    "access": "derived-read-only",
    "write_behavior": "no writes, no submissions, no publication side effects",
    "authority": "derived search input only; CommonProject files remain authoritative",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def aspect_input(aspect: dict[str, Any]) -> dict[str, str]:
    return {"id": aspect["id"], "label": aspect["label"]}


def load_project(root: Path, project_path: str) -> tuple[dict[str, Any] | None, list[str]]:
    projects_root = (root / "examples" / "commonworld" / "projects").resolve()
    project_file = (root / project_path).resolve()
    try:
        project_file.relative_to(projects_root)
    except ValueError:
        return None, ["search index input project paths must stay inside examples/commonworld/projects"]
    if not project_file.is_file():
        return None, [f"search index input project path is missing: {project_path}"]
    return load_json(project_file), []


def index_entry_for(root: Path, export_entry: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    project_path = export_entry.get("project_path")
    if not isinstance(project_path, str):
        return None, ["search index input export entries must include project_path"]
    project, errors = load_project(root, project_path)
    if errors:
        return None, errors
    assert project is not None
    if project.get("id") != export_entry.get("id"):
        return None, ["search index input project id must match the catalog export entry id"]

    entry = {
        "id": project["id"],
        "title": project["title"],
        "summary": project["summary"],
        "aspects": [aspect_input(aspect) for aspect in project.get("aspects", [])],
        "curation_state": export_entry["curation_state"],
        "location_label": project.get("location", {}).get("label", ""),
        "location_mode": export_entry["location_mode"],
        "project_path": project_path,
        "profile_handoff_state": export_entry["profile_handoff_state"],
    }
    if list(entry) != ALLOWED_FIELD_IDS:
        return None, ["search index input entry fields must match the T014 allowed fields in deterministic order"]
    return entry, []


def build_search_index_input(root: Path = ROOT) -> tuple[dict[str, Any], list[str]]:
    root = root.resolve()
    errors: list[str] = []

    contract_errors = validate_search_index_input_contract(root)
    errors.extend(contract_errors)

    export_path = root / CATALOG_EXPORT_PATH.relative_to(ROOT)
    if not export_path.is_file():
        return {}, [f"missing catalog export sample: {export_path.relative_to(root)}"]
    export = load_json(export_path)
    generated_export, export_errors = build_catalog_export(root)
    errors.extend(export_errors)
    if export != generated_export:
        errors.append("search index input requires an up-to-date static catalog export sample")

    entries: list[dict[str, Any]] = []
    for export_entry in export.get("entries", []):
        if not isinstance(export_entry, dict):
            errors.append("search index input export entries must be objects")
            continue
        entry, entry_errors = index_entry_for(root, export_entry)
        errors.extend(entry_errors)
        if entry is not None:
            entries.append(entry)

    if errors:
        return {}, errors

    payload = {
        "schema_version": 1,
        "kind": KIND,
        "task": TASK,
        "status": "static-sample-only",
        "scope": export["scope"],
        "source_contract": CONTRACT_PATH.relative_to(ROOT).as_posix(),
        "source_export": CATALOG_EXPORT_PATH.relative_to(ROOT).as_posix(),
        "entry_count": len(entries),
        "boundary": dict(BOUNDARY),
        "entries": entries,
    }
    return payload, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root. Defaults to this checkout.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output file relative to --root unless absolute. Defaults to examples/commonworld/search-index-input.sample.json.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the output file is not up to date.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    payload, errors = build_search_index_input(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    generated = stable_json(payload)
    if args.check:
        if not output.is_file():
            print(f"ERROR: missing search index input output: {output.relative_to(root)}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != generated:
            print(f"ERROR: search index input output is stale: {output.relative_to(root)}", file=sys.stderr)
            return 1
        print("commonworld search index input is up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"wrote {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
