#!/usr/bin/env python3
"""Validate the canonical CommonProject v3 schema and representative in-memory records."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"


def load_schema(root: Path = ROOT) -> dict:
    return json.loads((root / SCHEMA_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))


def base_record() -> dict:
    return {
        "schema_version": 3,
        "id": "shared-repair-place",
        "title": "Shared Repair Place",
        "summary": "A public Commons where people share tools, repair objects and learn practical skills together.",
        "kind": "geographic",
        "themes": ["repair", "shared-tools"],
        "actions": ["visit", "borrow", "learn", "contribute"],
        "presence": {
            "geographic": {
                "mode": "exact",
                "label": "Public repair venue",
                "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
            },
            "digital": {"available": False},
        },
        "provenance": {
            "sources": [
                {
                    "id": "official-website",
                    "type": "official-source",
                    "label": "Official website",
                    "url": "https://example.org/repair",
                    "retrieved_at": "2026-07-01",
                }
            ]
        },
        "curation": {
            "state": "candidate",
            "reviewed_at": "2026-07-01",
            "next_review_at": "2026-10-01",
        },
        "links": [
            {"type": "homepage", "label": "Official website", "url": "https://example.org/repair"}
        ],
        "handoff": {"enabled": False},
    }


def representative_records() -> tuple[dict, ...]:
    geographic = base_record()

    digital = copy.deepcopy(geographic)
    digital.update({"id": "open-knowledge-network", "kind": "digital"})
    digital["presence"] = {
        "geographic": {"mode": "not-applicable", "label": "No geographic center"},
        "digital": {"available": True, "reach": "global", "label": "Available online worldwide"},
    }

    hybrid = copy.deepcopy(geographic)
    hybrid.update({"id": "local-digital-mapping-network", "kind": "hybrid"})
    hybrid["presence"]["geographic"] = {
        "mode": "approximate",
        "label": "Hamburg region",
        "accuracy_meters_min": 5000,
    }
    hybrid["presence"]["digital"] = {
        "available": True,
        "reach": "network",
        "label": "Distributed online mapping network",
    }
    hybrid["relations"] = [
        {
            "target_id": "open-knowledge-network",
            "type": "local-digital-link",
            "source_url": "https://example.org/relation",
        }
    ]
    return geographic, digital, hybrid


def validation_errors(record: dict, root: Path = ROOT) -> list[str]:
    validator = Draft202012Validator(load_schema(root), format_checker=FormatChecker())
    return [error.message for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path))]


def validate_contracts(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = root / SCHEMA_PATH.relative_to(ROOT)
    if not path.is_file():
        return ["missing CommonProject v3 schema"]
    try:
        schema = load_schema(root)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        return [f"invalid CommonProject v3 schema: {error}"]

    for record in representative_records():
        for message in validation_errors(record, root):
            errors.append(f"representative record {record['id']} invalid: {message}")
    return errors


def main() -> int:
    errors = validate_contracts(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld CommonProject v3 contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
