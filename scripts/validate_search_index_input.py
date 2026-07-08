#!/usr/bin/env python3
"""Validate the generated commonworld search index input sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_search_index_input import (
    BOUNDARY,
    CATALOG_EXPORT_PATH,
    CONTRACT_PATH,
    DEFAULT_OUTPUT_PATH,
    KIND,
    TASK,
    build_search_index_input,
)
from scripts.validate_search_index_input_contract import ALLOWED_FIELD_IDS

SEARCH_INPUT_PATH = ROOT / DEFAULT_OUTPUT_PATH
FORBIDDEN_ENTRY_FIELDS = {
    "coordinates",
    "lat",
    "lon",
    "provenance",
    "review_notes",
    "private_review_notes",
    "handoff",
    "links",
    "writes",
    "submissions",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_entry(entry: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    if list(entry) != ALLOWED_FIELD_IDS:
        errors.append(f"search index input entry {index} fields must exactly match the T014 allowed fields")
    for forbidden in sorted(FORBIDDEN_ENTRY_FIELDS):
        if forbidden in entry:
            errors.append(f"search index input entry {index} must not include forbidden field: {forbidden}")
    if not isinstance(entry.get("aspects"), list) or not entry.get("aspects"):
        errors.append(f"search index input entry {index} must include at least one aspect")
    else:
        for aspect in entry["aspects"]:
            if not isinstance(aspect, dict) or list(aspect) != ["id", "label"]:
                errors.append(f"search index input entry {index} aspects must only expose id and label")
    if entry.get("location_mode") == "hidden" and "coordinates" in json.dumps(entry):
        errors.append(f"search index input entry {index} must not expose coordinates for hidden locations")
    return errors


def validate_search_index_input(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    path = root / SEARCH_INPUT_PATH.relative_to(ROOT)
    if not path.is_file():
        return [f"missing search index input sample: {path.relative_to(root)}"]

    try:
        payload = load_json(path)
    except json.JSONDecodeError as exc:
        return [f"search index input sample is not valid JSON: {exc}"]

    if payload.get("schema_version") != 1:
        errors.append("search index input sample must use schema_version 1")
    if payload.get("kind") != KIND:
        errors.append(f"search index input sample kind must be {KIND}")
    if payload.get("task") != TASK:
        errors.append(f"search index input sample task must be {TASK}")
    if payload.get("status") != "static-sample-only":
        errors.append("search index input sample status must be static-sample-only")
    if payload.get("source_contract") != CONTRACT_PATH.relative_to(ROOT).as_posix():
        errors.append("search index input sample must anchor to the T014 search input contract")
    if payload.get("source_export") != CATALOG_EXPORT_PATH.relative_to(ROOT).as_posix():
        errors.append("search index input sample must anchor to the static catalog export")
    if payload.get("boundary") != BOUNDARY:
        errors.append("search index input sample must preserve the no-runtime read-only boundary")

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("search index input sample entries must be a non-empty list")
        entries = []
    if payload.get("entry_count") != len(entries):
        errors.append("search index input sample entry_count must match entries length")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"search index input entry {index} must be an object")
            continue
        errors.extend(validate_entry(entry, index))

    generated, generated_errors = build_search_index_input(root)
    errors.extend(generated_errors)
    if not generated_errors and payload != generated:
        errors.append("search index input sample is stale")

    return errors


def main() -> int:
    errors = validate_search_index_input(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld search index input validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
