#!/usr/bin/env python3
"""Validate the static commonworld catalog API route fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_catalog_api_route_fixtures import (
    BOUNDARY,
    CATALOG_EXPORT_PATH,
    CONTRACT_PATH,
    DEFAULT_OUTPUT_PATH,
    KIND,
    REQUIRED_ROUTE_IDS,
    TASK,
    build_catalog_api_route_fixtures,
)

DOC_PATH = ROOT / "docs" / "blueprints" / "catalog-api-route-fixtures.md"
FIXTURE_PATH = ROOT / DEFAULT_OUTPUT_PATH

REQUIRED_DOC_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T013",
    "static route fixture, no runtime implementation",
    "no API server",
    "no database",
    "no ingestion worker",
    "no public submissions",
    "no write path",
    "GET /catalog/v1/catalog-export",
    "GET /catalog/v1/projects",
    "GET /catalog/v1/projects/{project_id}",
    "method: GET",
    "access: public-read-only",
    "writes: false",
    "submissions: false",
    "auth_required: false",
    "status: 200",
    "must not introduce",
    "POST, PUT, PATCH or DELETE routes",
    "API server, router, handler or middleware",
    "weltgewebe write path",
    "stale fixture",
)

FORBIDDEN_DOC_PHRASES = (
    "implement the server now",
    "start the server now",
    "create database",
    "post route is allowed",
    "public submissions are enabled",
    "requires authentication",
)

FORBIDDEN_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_route_fixture_payload(root: Path, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = load_json(root / CONTRACT_PATH.relative_to(ROOT))
    export = load_json(root / CATALOG_EXPORT_PATH.relative_to(ROOT))
    routes = contract.get("routes")
    if not isinstance(routes, list):
        return ["catalog API route fixture validator requires contract routes to be a list"]
    route_map = {route.get("id"): route for route in routes if isinstance(route, dict)}

    if payload.get("schema_version") != 1:
        errors.append("catalog API route fixtures must use schema_version 1")
    if payload.get("kind") != KIND:
        errors.append(f"catalog API route fixtures kind must be {KIND}")
    if payload.get("task") != TASK:
        errors.append(f"catalog API route fixtures task must be {TASK}")
    if payload.get("status") != "static-fixture-only":
        errors.append("catalog API route fixtures status must be static-fixture-only")
    if payload.get("source_contract") != CONTRACT_PATH.relative_to(ROOT).as_posix():
        errors.append("catalog API route fixtures must anchor to the read-only catalog API contract")
    if payload.get("source_export") != CATALOG_EXPORT_PATH.relative_to(ROOT).as_posix():
        errors.append("catalog API route fixtures must anchor to the static catalog export sample")

    boundary = payload.get("boundary")
    if boundary != BOUNDARY:
        errors.append("catalog API route fixtures boundary must preserve the no-runtime read-only boundary")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        errors.append("catalog API route fixtures must contain a fixture list")
        return errors
    fixture_ids = [fixture.get("id") for fixture in fixtures if isinstance(fixture, dict)]
    if fixture_ids != REQUIRED_ROUTE_IDS:
        errors.append("catalog API route fixtures must exactly cover the T012 route ids in deterministic order")

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("catalog API route fixture entries must be objects")
            continue
        fixture_id = fixture.get("id")
        route = route_map.get(fixture_id)
        if not isinstance(fixture_id, str) or route is None:
            errors.append("catalog API route fixture id must match a known contract route")
            continue
        method = fixture.get("method")
        if method != "GET":
            errors.append(f"catalog API route fixture {fixture_id} must remain GET-only")
        if method in FORBIDDEN_METHODS:
            errors.append(f"catalog API route fixture {fixture_id} must not include {method} routes")
        if fixture.get("route_path_template") != route.get("path"):
            errors.append(f"catalog API route fixture {fixture_id} must preserve the contract route path")
        if fixture_id != "catalog-project-detail" and fixture.get("request_path") != route.get("path"):
            errors.append(f"catalog API route fixture {fixture_id} request path must equal the contract route path")
        if fixture.get("status") != 200:
            errors.append(f"catalog API route fixture {fixture_id} must be a successful static 200 example")
        if fixture.get("access") != "public-read-only":
            errors.append(f"catalog API route fixture {fixture_id} must remain public-read-only")
        if fixture.get("auth_required") is not False:
            errors.append(f"catalog API route fixture {fixture_id} must not require auth")
        if fixture.get("writes") is not False:
            errors.append(f"catalog API route fixture {fixture_id} must not write")
        if fixture.get("submissions") is not False:
            errors.append(f"catalog API route fixture {fixture_id} must not create submissions")
        if fixture.get("source") != route.get("source"):
            errors.append(f"catalog API route fixture {fixture_id} must preserve the contract source")
        if fixture.get("response_shape") != route.get("response_shape"):
            errors.append(f"catalog API route fixture {fixture_id} must preserve the contract response shape")

    fixture_map = {fixture.get("id"): fixture for fixture in fixtures if isinstance(fixture, dict)}
    export_fixture = fixture_map.get("catalog-export", {})
    if export_fixture.get("body") != export:
        errors.append("catalog-export route fixture body must equal the generated static catalog export sample")

    list_fixture = fixture_map.get("catalog-project-list", {})
    list_body = list_fixture.get("body", {})
    if list_body.get("kind") != "commonworld.catalog_project_list":
        errors.append("catalog-project-list route fixture body kind must be commonworld.catalog_project_list")
    if list_body.get("count") != len(export.get("entries", [])):
        errors.append("catalog-project-list route fixture count must match the static catalog export entries")
    if list_body.get("projects") != export.get("entries"):
        errors.append("catalog-project-list route fixture projects must be derived exactly from static catalog export entries")
    if list_body.get("boundary", {}).get("write_behavior") != "no writes, no submissions, no publication side effects":
        errors.append("catalog-project-list route fixture body must preserve no-write behavior")

    detail_fixture = fixture_map.get("catalog-project-detail", {})
    detail_params = detail_fixture.get("path_params", {})
    detail_id = detail_params.get("project_id") if isinstance(detail_params, dict) else None
    if not isinstance(detail_id, str) or not detail_id:
        errors.append("catalog-project-detail route fixture must declare a concrete project_id path param")
    else:
        expected_path = f"/catalog/v1/projects/{detail_id}"
        if detail_fixture.get("request_path") != expected_path:
            errors.append("catalog-project-detail route fixture request path must include the concrete project_id")
        detail_body = detail_fixture.get("body", {})
        if detail_body.get("id") != detail_id:
            errors.append("catalog-project-detail route fixture body id must match the project_id path param")
        body_source = detail_fixture.get("body_source_project_path")
        matching_entry = next((entry for entry in export.get("entries", []) if entry.get("id") == detail_id), None)
        if not matching_entry or body_source != matching_entry.get("project_path"):
            errors.append("catalog-project-detail route fixture body source must match the selected export entry")

    return errors


def validate_catalog_api_route_fixtures(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    doc_path = root / DOC_PATH.relative_to(ROOT)
    fixture_path = root / FIXTURE_PATH.relative_to(ROOT)

    if not doc_path.is_file():
        return [f"missing catalog API route fixture doc: {doc_path.relative_to(root)}"]
    if not fixture_path.is_file():
        return [f"missing catalog API route fixture file: {fixture_path.relative_to(root)}"]

    doc = doc_path.read_text(encoding="utf-8")
    lowered = doc.casefold()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"catalog API route fixture doc missing required phrase: {phrase}")
    for phrase in FORBIDDEN_DOC_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"catalog API route fixture doc includes forbidden shortcut: {phrase}")

    try:
        payload = load_json(fixture_path)
    except json.JSONDecodeError as exc:
        return [f"catalog API route fixture sample is not valid JSON: {exc}"]

    errors.extend(validate_route_fixture_payload(root, payload))

    generated, generated_errors = build_catalog_api_route_fixtures(root)
    errors.extend(generated_errors)
    if not generated_errors and payload != generated:
        errors.append("catalog API route fixture sample is stale")

    return errors


def main() -> int:
    errors = validate_catalog_api_route_fixtures(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld catalog API route fixture validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
