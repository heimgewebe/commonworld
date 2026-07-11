#!/usr/bin/env python3
"""Validate CommonProject v3 against its non-public real-world case matrix."""

from __future__ import annotations

import copy
import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

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
            "geographic": [
                {
                    "id": "public-workshop",
                    "mode": "exact",
                    "label": "Public repair venue",
                    "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
                    "source_ids": ["official-website"],
                }
            ],
            "digital": {"available": False, "source_ids": ["official-website"]},
        },
        "activity": {
            "status": "active",
            "observed_at": "2026-07-01",
            "source_ids": ["official-website"],
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


def _source(identifier: str, url: str) -> dict:
    return {
        "id": identifier,
        "type": "official-source",
        "label": identifier.replace("-", " ").title(),
        "url": url,
        "retrieved_at": "2026-07-01",
    }


def representative_records() -> tuple[dict, ...]:
    exact_place = base_record()

    extended_area = copy.deepcopy(exact_place)
    extended_area.update({"id": "community-forest", "title": "Community Forest"})
    extended_area["presence"]["geographic"][0].update(
        {
            "id": "managed-area",
            "label": "Publicly documented managed forest area",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[9.9, 53.4], [10.1, 53.4], [10.1, 53.6], [9.9, 53.4]]],
            },
        }
    )

    approximate_place = copy.deepcopy(exact_place)
    approximate_place.update({"id": "protected-seed-library", "title": "Protected Seed Library"})
    approximate_place["presence"]["geographic"][0] = {
        "id": "protected-region",
        "mode": "approximate",
        "label": "Rural district; exact storage site withheld",
        "geometry": {"type": "Point", "coordinates": [9.8, 53.7]},
        "uncertainty_meters_min": 15000,
        "privacy_note": "The public point is deliberately displaced to protect the collection.",
        "source_ids": ["official-website"],
    }

    hidden_place = copy.deepcopy(exact_place)
    hidden_place.update({"id": "sheltered-mutual-aid-store", "title": "Sheltered Mutual Aid Store"})
    hidden_place["presence"]["geographic"][0] = {
        "id": "withheld-site",
        "mode": "hidden",
        "label": "Location disclosed only through trusted contact",
        "privacy_note": "The exact location is withheld for the safety of participants.",
        "source_ids": ["official-website"],
    }

    digital = copy.deepcopy(exact_place)
    digital.update({"id": "open-knowledge-network", "title": "Open Knowledge Network", "kind": "digital"})
    digital["presence"] = {
        "geographic": [],
        "digital": {
            "available": True,
            "reach": "global",
            "label": "Available online worldwide",
            "source_ids": ["official-website"],
        },
    }

    regional = copy.deepcopy(exact_place)
    regional.update({"id": "regional-water-cooperative", "title": "Regional Water Cooperative"})
    regional["presence"]["geographic"][0] = {
        "id": "watershed-area",
        "mode": "exact",
        "label": "Documented cooperative watershed",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[9.0, 52.9], [9.4, 52.9], [9.4, 53.2], [9.0, 52.9]]],
                [[[9.6, 53.0], [9.9, 53.0], [9.9, 53.3], [9.6, 53.0]]],
            ],
        },
        "source_ids": ["official-website"],
    }

    multiple_anchors = copy.deepcopy(exact_place)
    multiple_anchors.update({"id": "tool-library-network", "title": "Tool Library Network"})
    multiple_anchors["presence"]["geographic"] = [
        {
            "id": "north-branch",
            "mode": "exact",
            "label": "North branch",
            "geometry": {"type": "Point", "coordinates": [10.01, 53.60]},
            "source_ids": ["official-website"],
        },
        {
            "id": "south-branch",
            "mode": "exact",
            "label": "South branch",
            "geometry": {"type": "Point", "coordinates": [10.02, 53.47]},
            "source_ids": ["official-website"],
        },
    ]

    hybrid = copy.deepcopy(exact_place)
    hybrid.update({"id": "local-digital-mapping-network", "title": "Local Digital Mapping Network", "kind": "hybrid"})
    hybrid["presence"]["geographic"][0] = {
        "id": "hamburg-region",
        "mode": "approximate",
        "label": "Hamburg region",
        "geometry": {"type": "Point", "coordinates": [10.0, 53.55]},
        "uncertainty_meters_min": 5000,
        "source_ids": ["official-website"],
    }
    hybrid["presence"]["digital"] = {
        "available": True,
        "reach": "network",
        "label": "Distributed online mapping network",
        "source_ids": ["official-website"],
    }

    related = copy.deepcopy(hybrid)
    related.update({"id": "mapping-chapter", "title": "Mapping Chapter"})
    related["provenance"]["sources"].append(
        _source("network-directory", "https://example.org/network-directory")
    )
    related["relations"] = [
        {
            "target_id": "open-knowledge-network",
            "type": "chapter-of",
            "source_ids": ["network-directory"],
        }
    ]

    paused_stale = copy.deepcopy(exact_place)
    paused_stale.update({"id": "paused-community-kitchen", "title": "Paused Community Kitchen"})
    paused_stale["activity"] = {
        "status": "paused",
        "observed_at": "2026-06-15",
        "source_ids": ["official-website"],
        "note": "Public activities are temporarily suspended.",
    }
    paused_stale["curation"] = {
        "state": "stale",
        "reviewed_by": "Commonworld editorial review",
        "reviewed_at": "2026-07-01",
        "next_review_at": "2026-07-15",
        "notes": "The record needs a fresh operational check before active presentation.",
    }

    return (
        exact_place,
        extended_area,
        approximate_place,
        hidden_place,
        digital,
        regional,
        multiple_anchors,
        hybrid,
        related,
        paused_stale,
    )


def _schema_validation_errors(record: dict, root: Path = ROOT) -> list[str]:
    validator = Draft202012Validator(load_schema(root), format_checker=FormatChecker())
    return [
        error.message
        for error in sorted(validator.iter_errors(record), key=lambda item: (list(item.path), item.message))
    ]


def _referenced_source_ids(record: dict) -> Iterable[tuple[str, object]]:
    activity = record.get("activity", {})
    if isinstance(activity, dict):
        yield "activity", activity.get("source_ids", [])
    presence = record.get("presence", {})
    geographic = presence.get("geographic", []) if isinstance(presence, dict) else []
    if isinstance(geographic, list):
        for location in geographic:
            if isinstance(location, dict):
                yield f"geographic location {location.get('id', '<missing>')}", location.get("source_ids", [])
    digital = presence.get("digital", {}) if isinstance(presence, dict) else {}
    if isinstance(digital, dict):
        yield "digital presence", digital.get("source_ids", [])
    relations = record.get("relations", [])
    if isinstance(relations, list):
        for index, relation in enumerate(relations):
            if isinstance(relation, dict):
                yield f"relation {index}", relation.get("source_ids", [])


def _rings(geometry: dict) -> Iterable[list[list[float]]]:
    if geometry.get("type") == "Polygon":
        yield from geometry.get("coordinates", [])
    elif geometry.get("type") == "MultiPolygon":
        for polygon in geometry.get("coordinates", []):
            yield from polygon


def semantic_errors(record: dict) -> list[str]:
    errors: list[str] = []
    provenance = record.get("provenance", {})
    sources = provenance.get("sources", []) if isinstance(provenance, dict) else []
    source_ids = [source.get("id") for source in sources if isinstance(source, dict)] if isinstance(sources, list) else []
    known_source_ids = {identifier for identifier in source_ids if isinstance(identifier, str)}
    if len(source_ids) != len(known_source_ids):
        errors.append("provenance source ids must be unique")

    presence = record.get("presence", {})
    geographic = presence.get("geographic", []) if isinstance(presence, dict) else []
    locations = [item for item in geographic if isinstance(item, dict)] if isinstance(geographic, list) else []
    location_ids = [item.get("id") for item in locations if isinstance(item.get("id"), str)]
    if len(location_ids) != len(set(location_ids)):
        errors.append("geographic location ids must be unique")

    for context, references in _referenced_source_ids(record):
        reference_ids = {item for item in references if isinstance(item, str)} if isinstance(references, list) else set()
        unknown = sorted(reference_ids - known_source_ids)
        if unknown:
            errors.append(f"{context} references unknown provenance sources: {unknown}")

    record_id = record.get("id")
    relations = record.get("relations", [])
    if isinstance(relations, list):
        for relation in relations:
            if isinstance(relation, dict) and relation.get("target_id") == record_id:
                errors.append("relation target_id must not reference the record itself")

    for location in locations:
        geometry = location.get("geometry")
        if not isinstance(geometry, dict):
            continue
        for ring in _rings(geometry):
            if isinstance(ring, list) and ring and ring[0] != ring[-1]:
                errors.append(f"geographic location {location.get('id')} has an unclosed polygon ring")

    curation = record.get("curation", {})
    try:
        reviewed_at = date.fromisoformat(curation["reviewed_at"])
        next_review_at = date.fromisoformat(curation["next_review_at"])
        if next_review_at < reviewed_at:
            errors.append("curation next_review_at must not precede reviewed_at")
        observed_at = date.fromisoformat(record.get("activity", {})["observed_at"])
        if observed_at > reviewed_at:
            errors.append("activity observed_at must not be later than curation reviewed_at")
    except (KeyError, TypeError, ValueError):
        pass

    return errors


def validation_errors(record: dict, root: Path = ROOT) -> list[str]:
    return _schema_validation_errors(record, root) + semantic_errors(record)


def validate_contracts(root: Path = ROOT) -> list[str]:
    path = root / SCHEMA_PATH.relative_to(ROOT)
    if not path.is_file():
        return ["missing CommonProject v3 schema"]
    try:
        schema = load_schema(root)
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        return [f"invalid CommonProject v3 schema: {error}"]

    errors: list[str] = []
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
    print("commonworld CommonProject v3 contract and case-matrix validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
