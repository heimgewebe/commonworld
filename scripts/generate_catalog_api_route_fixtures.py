#!/usr/bin/env python3
"""Generate static read-only catalog API route fixtures deterministically."""

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

CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-api.contract.json"
CATALOG_EXPORT_PATH = ROOT / "examples" / "commonworld" / "catalog-export.sample.json"
DEFAULT_OUTPUT_PATH = Path("examples/commonworld/catalog-api-route-fixtures.sample.json")

TASK = "COMMONWORLD-ATLAS-V1-T013"
KIND = "commonworld.static_catalog_api_route_fixtures"
REQUIRED_ROUTE_IDS = ["catalog-export", "catalog-project-list", "catalog-project-detail"]

BOUNDARY = {
    "implementation": "no API server",
    "persistence": "no database",
    "ingestion": "no ingestion worker",
    "access": "public-read-only",
    "write_behavior": "no writes, no submissions, no publication side effects",
    "authority": "static route fixture only; generated catalog export and CommonProject files remain authoritative",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def route_by_id(contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    routes = contract.get("routes")
    if not isinstance(routes, list):
        return {}, ["catalog API contract routes must be a list"]

    by_id: dict[str, dict[str, Any]] = {}
    for route in routes:
        if not isinstance(route, dict):
            errors.append("catalog API contract route entries must be objects")
            continue
        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id:
            errors.append("catalog API contract route entries must have stable string ids")
            continue
        if route_id in by_id:
            errors.append(f"duplicate catalog API route id: {route_id}")
            continue
        by_id[route_id] = route

    if list(by_id) != REQUIRED_ROUTE_IDS:
        errors.append("catalog API route fixtures require the exact T012 route ids in deterministic order")
    return by_id, errors


def validate_read_only_route(route: dict[str, Any], route_id: str) -> list[str]:
    errors: list[str] = []
    if route.get("method") != "GET":
        errors.append(f"catalog API route {route_id} must remain GET-only")
    if route.get("access") != "public-read-only":
        errors.append(f"catalog API route {route_id} must remain public-read-only")
    if route.get("auth_required") is not False:
        errors.append(f"catalog API route {route_id} must not require auth")
    if route.get("writes") is not False:
        errors.append(f"catalog API route {route_id} must not write")
    if route.get("submissions") is not False:
        errors.append(f"catalog API route {route_id} must not create submissions")
    return errors


def project_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "project_path": entry["project_path"],
        "curation_state": entry["curation_state"],
        "location_mode": entry["location_mode"],
        "profile_handoff_state": entry["profile_handoff_state"],
    }


def load_project_detail(root: Path, export: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    entries = export.get("entries")
    if not isinstance(entries, list) or not entries:
        return None, None, ["catalog API route fixtures require at least one catalog export entry"]
    entry = entries[0]
    if not isinstance(entry, dict):
        return None, None, ["catalog API route fixture detail source entry must be an object"]
    project_path = entry.get("project_path")
    if not isinstance(project_path, str):
        return None, None, ["catalog API route fixture detail source entry needs project_path"]
    project_file = (root / project_path).resolve()
    projects_root = (root / "examples" / "commonworld" / "projects").resolve()
    try:
        project_file.relative_to(projects_root)
    except ValueError:
        return None, None, ["catalog API route fixture detail source must stay inside examples/commonworld/projects"]
    if not project_file.is_file():
        return None, None, [f"catalog API route fixture detail source is missing: {project_path}"]
    return entry, load_json(project_file), []


def build_catalog_api_route_fixtures(root: Path = ROOT) -> tuple[dict[str, Any], list[str]]:
    root = root.resolve()
    errors: list[str] = []

    contract_path = root / CONTRACT_PATH.relative_to(ROOT)
    export_path = root / CATALOG_EXPORT_PATH.relative_to(ROOT)
    if not contract_path.is_file():
        return {}, [f"missing catalog API contract: {contract_path.relative_to(root)}"]
    if not export_path.is_file():
        return {}, [f"missing catalog export sample: {export_path.relative_to(root)}"]

    contract = load_json(contract_path)
    export = load_json(export_path)
    generated_export, export_errors = build_catalog_export(root)
    errors.extend(export_errors)
    if export != generated_export:
        errors.append("catalog API route fixtures require an up-to-date static catalog export sample")

    routes, route_errors = route_by_id(contract)
    errors.extend(route_errors)
    for route_id in REQUIRED_ROUTE_IDS:
        route = routes.get(route_id)
        if route:
            errors.extend(validate_read_only_route(route, route_id))

    detail_entry, detail_project, detail_errors = load_project_detail(root, export)
    errors.extend(detail_errors)
    if errors:
        return {}, errors

    assert detail_entry is not None
    assert detail_project is not None
    detail_project_id = detail_entry["id"]
    if detail_project.get("id") != detail_project_id:
        errors.append("catalog API route fixture detail body id must match selected export entry")
        return {}, errors

    entries = export["entries"]
    fixtures = [
        {
            "id": "catalog-export",
            "method": routes["catalog-export"]["method"],
            "route_path_template": routes["catalog-export"]["path"],
            "request_path": routes["catalog-export"]["path"],
            "status": 200,
            "access": routes["catalog-export"]["access"],
            "auth_required": routes["catalog-export"]["auth_required"],
            "writes": routes["catalog-export"]["writes"],
            "submissions": routes["catalog-export"]["submissions"],
            "source": routes["catalog-export"]["source"],
            "response_shape": routes["catalog-export"]["response_shape"],
            "body": export,
        },
        {
            "id": "catalog-project-list",
            "method": routes["catalog-project-list"]["method"],
            "route_path_template": routes["catalog-project-list"]["path"],
            "request_path": routes["catalog-project-list"]["path"],
            "status": 200,
            "access": routes["catalog-project-list"]["access"],
            "auth_required": routes["catalog-project-list"]["auth_required"],
            "writes": routes["catalog-project-list"]["writes"],
            "submissions": routes["catalog-project-list"]["submissions"],
            "source": routes["catalog-project-list"]["source"],
            "response_shape": routes["catalog-project-list"]["response_shape"],
            "body": {
                "schema_version": 1,
                "kind": "commonworld.catalog_project_list",
                "source_export_path": CATALOG_EXPORT_PATH.relative_to(ROOT).as_posix(),
                "count": len(entries),
                "projects": [project_summary(entry) for entry in entries],
                "boundary": {
                    "access": "public-read-only",
                    "write_behavior": "no writes, no submissions, no publication side effects",
                },
            },
        },
        {
            "id": "catalog-project-detail",
            "method": routes["catalog-project-detail"]["method"],
            "route_path_template": routes["catalog-project-detail"]["path"],
            "request_path": routes["catalog-project-detail"]["path"].replace("{project_id}", detail_project_id),
            "path_params": {"project_id": detail_project_id},
            "status": 200,
            "access": routes["catalog-project-detail"]["access"],
            "auth_required": routes["catalog-project-detail"]["auth_required"],
            "writes": routes["catalog-project-detail"]["writes"],
            "submissions": routes["catalog-project-detail"]["submissions"],
            "source": routes["catalog-project-detail"]["source"],
            "response_shape": routes["catalog-project-detail"]["response_shape"],
            "body_source_project_path": detail_entry["project_path"],
            "body": detail_project,
        },
    ]

    payload = {
        "schema_version": 1,
        "kind": KIND,
        "task": TASK,
        "status": "static-fixture-only",
        "source_contract": CONTRACT_PATH.relative_to(ROOT).as_posix(),
        "source_export": CATALOG_EXPORT_PATH.relative_to(ROOT).as_posix(),
        "boundary": dict(BOUNDARY),
        "fixtures": fixtures,
    }
    return payload, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root. Defaults to this checkout.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output file relative to --root unless absolute. Defaults to examples/commonworld/catalog-api-route-fixtures.sample.json.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the output file is not up to date.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    fixtures, errors = build_catalog_api_route_fixtures(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    generated = stable_json(fixtures)
    if args.check:
        if not output.is_file():
            print(f"ERROR: missing catalog API route fixture output: {output.relative_to(root)}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != generated:
            print(f"ERROR: catalog API route fixture output is stale: {output.relative_to(root)}", file=sys.stderr)
            return 1
        print("commonworld catalog API route fixtures are up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"wrote {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
