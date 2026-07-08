#!/usr/bin/env python3
"""Validate the commonworld search index input contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "blueprints" / "search-index-input-contract.md"
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "search-index-input.contract.json"

REQUIRED_DOC_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T014",
    "search index input contract and rebuild policy, no runtime implementation",
    "no search service",
    "no vector database",
    "no crawler",
    "no ingestion worker",
    "no public submissions",
    "no write path",
    "id",
    "title",
    "summary",
    "aspects",
    "curation_state",
    "location_label",
    "location_mode",
    "project_path",
    "profile_handoff_state",
    "source: CommonProject",
    "source: generated static catalog export",
    "indexable: true",
    "writes: false",
    "submissions: false",
    "private_review_data: false",
    "rebuild_mode: deterministic batch rebuild",
    "runtime_dependency: none",
    "must not introduce",
    "search endpoint or API route",
    "vector database",
    "weltgewebe write path",
    "generated search input sample",
)

FORBIDDEN_DOC_PHRASES = (
    "implement search now",
    "start the search server now",
    "create vector database",
    "enable crawler",
    "live ingestion is required",
    "public submissions are enabled",
    "requires authentication",
)

ALLOWED_FIELD_IDS = [
    "id",
    "title",
    "summary",
    "aspects",
    "curation_state",
    "location_label",
    "location_mode",
    "project_path",
    "profile_handoff_state",
]
ALLOWED_SOURCES = {"CommonProject", "generated static catalog export"}
REQUIRED_FORBIDDEN = {
    "account or role system",
    "crawler",
    "database requirement",
    "hidden private location data",
    "import mutation path",
    "live ingestion worker",
    "private review notes",
    "public submission route",
    "ranking model authority",
    "review write path",
    "search endpoint or API route",
    "search server",
    "vector database",
    "weltgewebe write path",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_search_index_input_contract(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    doc_path = root / DOC_PATH.relative_to(ROOT)
    contract_path = root / CONTRACT_PATH.relative_to(ROOT)

    if not doc_path.is_file():
        return [f"missing search index input contract doc: {doc_path.relative_to(root)}"]
    if not contract_path.is_file():
        return [f"missing search index input contract file: {contract_path.relative_to(root)}"]

    doc = doc_path.read_text(encoding="utf-8")
    lowered = doc.casefold()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"search index input contract doc missing required phrase: {phrase}")
    for phrase in FORBIDDEN_DOC_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"search index input contract doc includes forbidden shortcut: {phrase}")

    try:
        contract = load_json(contract_path)
    except json.JSONDecodeError as exc:
        return [f"search index input contract is not valid JSON: {exc}"]

    if contract.get("schema_version") != 1:
        errors.append("search index input contract must use schema_version 1")
    if contract.get("kind") != "commonworld.search_index_input_contract":
        errors.append("search index input contract kind must be commonworld.search_index_input_contract")
    if contract.get("task") != "COMMONWORLD-ATLAS-V1-T014":
        errors.append("search index input contract task must be COMMONWORLD-ATLAS-V1-T014")
    if contract.get("status") != "contract-only":
        errors.append("search index input contract status must be contract-only")
    if contract.get("source_contracts") != [
        "contracts/commonworld/project.schema.json",
        "contracts/commonworld/catalog-export.schema.json",
    ]:
        errors.append("search index input contract must anchor to the CommonProject and static catalog export contracts")

    boundary = contract.get("boundary", {})
    expected_boundary = {
        "implementation": "no search service",
        "persistence": "no database or vector store",
        "ingestion": "no crawler or live ingestion worker",
        "access": "derived-read-only",
    }
    for key, expected in expected_boundary.items():
        if boundary.get(key) != expected:
            errors.append(f"search index input contract boundary {key} must be {expected}")
    if "no writes" not in boundary.get("write_behavior", ""):
        errors.append("search index input contract boundary must prohibit writes")
    if "CommonProject files remain authoritative" not in boundary.get("authority", ""):
        errors.append("search index input contract boundary must preserve CommonProject authority")

    fields = contract.get("fields")
    if not isinstance(fields, list) or not fields:
        errors.append("search index input contract fields must be a non-empty list")
        fields = []
    field_ids = [field.get("id") for field in fields if isinstance(field, dict)]
    if field_ids != ALLOWED_FIELD_IDS:
        errors.append("search index input contract fields must exactly cover the allowed input fields in deterministic order")

    seen_fields: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            errors.append("search index input contract field entries must be objects")
            continue
        field_id = field.get("id")
        if not isinstance(field_id, str) or not field_id:
            errors.append("search index input contract fields must have stable ids")
        elif field_id in seen_fields:
            errors.append("search index input contract field ids must be unique")
        else:
            seen_fields.add(field_id)
        if field.get("source") not in ALLOWED_SOURCES:
            errors.append("search index input contract fields must derive from CommonProject data or generated static catalog export")
        if field.get("indexable") is not True:
            errors.append("search index input contract fields must explicitly be indexable public-read inputs")
        if field.get("writes") is not False:
            errors.append("search index input contract fields must not write")
        if field.get("submissions") is not False:
            errors.append("search index input contract fields must not create submissions")
        if field.get("private_review_data") is not False:
            errors.append("search index input contract fields must not include private review data")

    rebuild_policy = contract.get("rebuild_policy", {})
    expected_rebuild = {
        "rebuild_mode": "deterministic batch rebuild",
        "rebuild_trigger": "committed CommonProject, seed manifest, catalog export or search input contract changes",
        "runtime_dependency": "none",
        "stale_behavior": "validation fails until regenerated",
        "publication_side_effects": False,
        "review_side_effects": False,
    }
    for key, expected in expected_rebuild.items():
        if rebuild_policy.get(key) != expected:
            errors.append(f"search index input contract rebuild_policy {key} must be {expected}")

    forbidden = set(contract.get("forbidden", []))
    for required in sorted(REQUIRED_FORBIDDEN):
        if required not in forbidden:
            errors.append(f"search index input contract forbidden list missing: {required}")

    return errors


def main() -> int:
    errors = validate_search_index_input_contract(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld search index input contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
