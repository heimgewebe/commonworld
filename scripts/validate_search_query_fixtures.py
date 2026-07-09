#!/usr/bin/env python3
"""Validate static search proof query fixtures against the T017 local ranking model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEARCH_INPUT_PATH = ROOT / "examples" / "commonworld" / "search-index-input.sample.json"
QUERY_FIXTURES_PATH = ROOT / "examples" / "commonworld" / "search-query-fixtures.sample.json"
SEARCH_JS_PATH = ROOT / "proofs" / "search" / "search.js"

FIELD_WEIGHTS = [
    ("title", "Title", 40),
    ("summary", "Summary", 20),
    ("aspect", "Aspect", 24),
    ("location", "Location", 12),
    ("curation", "Curation", 8),
    ("source", "Source path", 4),
    ("handoff", "Handoff state", 2),
]

REQUIRED_BOUNDARY = {
    "implementation": "no search service",
    "runtime_dependency": "none",
    "writes": False,
    "submissions": False,
    "authority": "not a ranking authority or curation decision",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalise(value: object) -> str:
    return str(value or "").lower()


def searchable_value(entry: dict[str, Any], field: str) -> str:
    if field == "title":
        return entry["title"]
    if field == "summary":
        return entry["summary"]
    if field == "aspect":
        return " ".join(value for aspect in entry["aspects"] for value in (aspect["id"], aspect["label"]))
    if field == "location":
        return f"{entry['location_label']} {entry['location_mode']}"
    if field == "curation":
        return entry["curation_state"]
    if field == "source":
        return entry["project_path"]
    if field == "handoff":
        return entry["profile_handoff_state"]
    raise ValueError(f"unsupported search field: {field}")


def explain_match(entry: dict[str, Any], query: str) -> dict[str, Any]:
    clean_query = normalise(query.strip())
    if clean_query == "":
        return {"matches": True, "score": 0, "reason_fields": ["all"]}
    terms = [term for term in clean_query.split() if term]
    score = 0
    reason_fields: list[str] = []
    for field, _label, weight in FIELD_WEIGHTS:
        haystack = normalise(searchable_value(entry, field))
        matched_terms = [term for term in terms if term in haystack]
        if not matched_terms:
            continue
        term_factor = len(matched_terms) / len(terms)
        exact_boost = 1.5 if haystack == clean_query else 1
        score += round(weight * term_factor * exact_boost)
        reason_fields.append(field)
    return {"matches": bool(reason_fields), "score": score, "reason_fields": reason_fields}


def ranked_results(entries: list[dict[str, Any]], query: str, filters: dict[str, str]) -> list[dict[str, Any]]:
    results = []
    curation = filters.get("curation", "all")
    location = filters.get("location", "all")
    for entry in entries:
        if curation != "all" and entry["curation_state"] != curation:
            continue
        if location != "all" and entry["location_mode"] != location:
            continue
        explanation = explain_match(entry, query)
        if not explanation["matches"]:
            continue
        results.append({"entry": entry, **explanation})
    return sorted(results, key=lambda result: (-result["score"], result["entry"]["title"].lower()))


def validate_search_js_model(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    js_path = root / SEARCH_JS_PATH.relative_to(ROOT)
    if not js_path.is_file():
        return ["missing static search proof JS"]
    js = js_path.read_text(encoding="utf-8")
    for field, label, weight in FIELD_WEIGHTS:
        if f'field: "{field}"' not in js or f'label: "{label}"' not in js or f"weight: {weight}" not in js:
            errors.append(f"search query fixtures model drift: JS missing {field}/{label}/{weight}")
    for token in ("explainMatch", "rankResults", "local proof points", "not a server ranking or authority signal"):
        if token not in js:
            errors.append(f"search query fixtures require JS token: {token}")
    return errors


def validate_fixture_payload(payload: dict[str, Any], entries: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("search query fixtures must use schema_version 1")
    if payload.get("task") != "COMMONWORLD-ATLAS-V1-T018":
        errors.append("search query fixtures must declare COMMONWORLD-ATLAS-V1-T018")
    if payload.get("kind") != "commonworld.static_search_query_fixtures":
        errors.append("search query fixtures must use kind commonworld.static_search_query_fixtures")
    if payload.get("status") != "static-fixture-only":
        errors.append("search query fixtures must remain static-fixture-only")
    if payload.get("source_input") != "examples/commonworld/search-index-input.sample.json":
        errors.append("search query fixtures must point at the static search input sample")
    boundary = payload.get("boundary")
    if boundary != REQUIRED_BOUNDARY:
        errors.append("search query fixtures boundary must keep no-runtime/no-authority semantics")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        return errors + ["search query fixtures must contain a non-empty fixtures list"]

    known_ids = {entry["id"] for entry in entries}
    seen_ids: set[str] = set()
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            errors.append(f"search query fixture {index} must be an object")
            continue
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id:
            errors.append(f"search query fixture {index} needs id")
            continue
        if fixture_id in seen_ids:
            errors.append(f"search query fixture duplicate id: {fixture_id}")
        seen_ids.add(fixture_id)
        query = fixture.get("query")
        if not isinstance(query, str):
            errors.append(f"search query fixture {fixture_id} needs query")
            continue
        filters = fixture.get("filters", {"curation": "all", "location": "all"})
        if filters == {}:
            filters = {"curation": "all", "location": "all"}
        if not isinstance(filters, dict):
            errors.append(f"search query fixture {fixture_id} filters must be an object")
            continue
        expected_top_ids = fixture.get("expected_top_ids")
        if not isinstance(expected_top_ids, list) or not expected_top_ids:
            errors.append(f"search query fixture {fixture_id} needs expected_top_ids")
            continue
        unknown_expected = sorted(set(expected_top_ids) - known_ids)
        if unknown_expected:
            errors.append(f"search query fixture {fixture_id} references unknown expected ids: {unknown_expected}")
            continue
        ranked = ranked_results(entries, query, filters)
        ranked_ids = [result["entry"]["id"] for result in ranked]
        if ranked_ids[: len(expected_top_ids)] != expected_top_ids:
            errors.append(
                f"search query fixture {fixture_id} expected top ids {expected_top_ids}, got {ranked_ids[:len(expected_top_ids)]}"
            )
        min_result_count = fixture.get("min_result_count")
        if not isinstance(min_result_count, int) or min_result_count < 1:
            errors.append(f"search query fixture {fixture_id} needs positive min_result_count")
        elif len(ranked) < min_result_count:
            errors.append(f"search query fixture {fixture_id} expected at least {min_result_count} results, got {len(ranked)}")
        min_top_score = fixture.get("min_top_score")
        if min_top_score is not None:
            if not isinstance(min_top_score, int) or min_top_score < 0:
                errors.append(f"search query fixture {fixture_id} min_top_score must be a non-negative integer")
            elif not ranked or ranked[0]["score"] < min_top_score:
                got = ranked[0]["score"] if ranked else None
                errors.append(f"search query fixture {fixture_id} expected top score >= {min_top_score}, got {got}")
        expected_reason_fields = fixture.get("expected_reason_fields", {})
        if not isinstance(expected_reason_fields, dict):
            errors.append(f"search query fixture {fixture_id} expected_reason_fields must be an object")
            continue
        result_by_id = {result["entry"]["id"]: result for result in ranked}
        for expected_id, fields in expected_reason_fields.items():
            if expected_id not in result_by_id:
                errors.append(f"search query fixture {fixture_id} cannot inspect reasons for missing result {expected_id}")
                continue
            if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
                errors.append(f"search query fixture {fixture_id} reason fields for {expected_id} must be a string list")
                continue
            actual_fields = result_by_id[expected_id]["reason_fields"]
            missing_fields = [field for field in fields if field not in actual_fields]
            if missing_fields:
                errors.append(
                    f"search query fixture {fixture_id} expected reason fields {missing_fields} for {expected_id}, got {actual_fields}"
                )
    return errors


def validate_search_query_fixtures(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors = validate_search_js_model(root)
    input_path = root / SEARCH_INPUT_PATH.relative_to(ROOT)
    fixture_path = root / QUERY_FIXTURES_PATH.relative_to(ROOT)
    if not input_path.is_file():
        return errors + ["missing static search input sample"]
    if not fixture_path.is_file():
        return errors + ["missing search query fixtures sample"]
    search_input = load_json(input_path)
    if search_input.get("kind") != "commonworld.static_search_index_input":
        errors.append("search query fixtures must validate against commonworld.static_search_index_input")
    entries = search_input.get("entries")
    if not isinstance(entries, list) or not entries:
        return errors + ["static search input sample must contain entries"]
    payload = load_json(fixture_path)
    errors.extend(validate_fixture_payload(payload, entries))
    return errors


def main() -> int:
    errors = validate_search_query_fixtures(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld search query fixtures validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
