#!/usr/bin/env python3
"""Validate the commonworld read-only catalog API contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "blueprints" / "catalog-api-contract.md"
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-api.contract.json"

REQUIRED_DOC_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T012",
    "read-only API contract, no runtime implementation",
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
    "must not introduce",
    "POST, PUT, PATCH or DELETE routes",
    "weltgewebe write path",
    "static mock response or route fixture",
)

FORBIDDEN_DOC_PHRASES = (
    "implement the server now",
    "create database",
    "post route is allowed",
    "public submissions are enabled",
    "requires authentication",
)

ALLOWED_PATHS = [
    "/catalog/v1/catalog-export",
    "/catalog/v1/projects",
    "/catalog/v1/projects/{project_id}",
]
ALLOWED_SOURCES = {"generated static catalog export", "accepted CommonProject data"}
FORBIDDEN_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_catalog_api_contract(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    doc_path = root / DOC_PATH.relative_to(ROOT)
    contract_path = root / CONTRACT_PATH.relative_to(ROOT)

    if not doc_path.is_file():
        return [f"missing catalog API contract doc: {doc_path.relative_to(root)}"]
    if not contract_path.is_file():
        return [f"missing catalog API contract file: {contract_path.relative_to(root)}"]

    doc = doc_path.read_text(encoding="utf-8")
    lowered = doc.casefold()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"catalog API contract doc missing required phrase: {phrase}")
    for phrase in FORBIDDEN_DOC_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"catalog API contract doc includes forbidden shortcut: {phrase}")

    try:
        contract = load_json(contract_path)
    except json.JSONDecodeError as exc:
        return [f"catalog API contract is not valid JSON: {exc}"]

    if contract.get("schema_version") != 1:
        errors.append("catalog API contract must use schema_version 1")
    if contract.get("kind") != "commonworld.read_only_catalog_api_contract":
        errors.append("catalog API contract kind must be commonworld.read_only_catalog_api_contract")
    if contract.get("task") != "COMMONWORLD-ATLAS-V1-T012":
        errors.append("catalog API contract task must be COMMONWORLD-ATLAS-V1-T012")
    if contract.get("status") != "contract-only":
        errors.append("catalog API contract status must be contract-only")
    if contract.get("source_contract") != "contracts/commonworld/catalog-export.schema.json":
        errors.append("catalog API contract must anchor to the static catalog export schema")

    boundary = contract.get("boundary", {})
    expected_boundary = {
        "implementation": "no API server",
        "persistence": "no database",
        "ingestion": "no ingestion worker",
        "access": "public-read-only",
    }
    for key, expected in expected_boundary.items():
        if boundary.get(key) != expected:
            errors.append(f"catalog API contract boundary {key} must be {expected}")
    if "no writes" not in boundary.get("write_behavior", ""):
        errors.append("catalog API contract boundary must prohibit writes")
    if "CommonProject files remain authoritative" not in boundary.get("authority", ""):
        errors.append("catalog API contract boundary must preserve CommonProject authority")

    routes = contract.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("catalog API contract routes must be a non-empty list")
        routes = []
    paths = [route.get("path") for route in routes if isinstance(route, dict)]
    if paths != ALLOWED_PATHS:
        errors.append("catalog API contract routes must exactly cover the allowed read-only catalog paths in deterministic order")

    route_ids: set[str] = set()
    for route in routes:
        if not isinstance(route, dict):
            errors.append("catalog API contract route entries must be objects")
            continue
        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id:
            errors.append("catalog API contract routes must have stable ids")
        elif route_id in route_ids:
            errors.append("catalog API contract route ids must be unique")
        else:
            route_ids.add(route_id)
        method = route.get("method")
        if method != "GET":
            errors.append("catalog API contract routes must be GET-only")
        if method in FORBIDDEN_METHODS:
            errors.append(f"catalog API contract must not include {method} routes")
        if route.get("path") not in ALLOWED_PATHS:
            errors.append("catalog API contract route path is not allowed")
        if route.get("source") not in ALLOWED_SOURCES:
            errors.append("catalog API contract routes must derive from accepted CommonProject data or generated static catalog export")
        if route.get("access") != "public-read-only":
            errors.append("catalog API contract routes must be public-read-only")
        if route.get("auth_required") is not False:
            errors.append("catalog API contract public routes must not require auth")
        if route.get("writes") is not False:
            errors.append("catalog API contract routes must not write")
        if route.get("submissions") is not False:
            errors.append("catalog API contract routes must not create submissions")

    forbidden = set(contract.get("forbidden", []))
    for required in (*sorted(FORBIDDEN_METHODS), "public submissions", "review write path", "import mutation path", "database requirement", "server implementation", "weltgewebe write path"):
        if required not in forbidden:
            errors.append(f"catalog API contract forbidden list missing: {required}")

    return errors


def main() -> int:
    errors = validate_catalog_api_contract(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld catalog API contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
