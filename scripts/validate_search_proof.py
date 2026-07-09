#!/usr/bin/env python3
"""Validate the static commonworld search proof surface."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEARCH_DIR = ROOT / "proofs" / "search"
REQUIRED_FILES = [
    SEARCH_DIR / "index.html",
    SEARCH_DIR / "search.css",
    SEARCH_DIR / "search.js",
    SEARCH_DIR / "README.md",
]
REQUIRED_HTML_TOKENS = (
    "COMMONWORLD-ATLAS-V1-T016",
    "Static search proof",
    "Search can be useful before it becomes runtime.",
    "data-search-query",
    "data-curation-filter",
    "data-location-filter",
    "data-reset-search",
    "data-result-grid",
    "data-result-template",
    "data-ranking-note",
    "data-query-fixtures",
    "data-query-fixture-state",
    "Try these searches",
    "Representative T018 query fixtures",
    "data-card-score",
    "data-card-reasons",
    "transparent proof score",
    "search-index-input.sample.json",
    "No server, no database, no crawler and no API route.",
    "not join, manage or submit actions",
    "type=\"search\"",
    "type=\"button\"",
    "./search.js",
)
REQUIRED_JS_TOKENS = (
    "../../examples/commonworld/search-index-input.sample.json",
    "../../examples/commonworld/search-query-fixtures.sample.json",
    "commonworld.static_search_index_input",
    "commonworld.static_search_query_fixtures",
    "static-sample-only",
    "no search service",
    "ALLOWED_ENTRY_KEYS",
    "FORBIDDEN_ENTRY_KEYS",
    "coordinates",
    "provenance",
    "private_review_notes",
    "validateSearchInput",
    "entry_count",
    "searchableFields",
    "explainMatch",
    "rankResults",
    "validateQueryFixturePayload",
    "renderQueryFixtures",
    "applyQueryFixture",
    "data-search-query",
    "data-result-grid",
    "data-ranking-note",
    "data-card-score",
    "data-card-reasons",
    "addEventListener(\"input\"",
    "addEventListener(\"change\"",
)
REQUIRED_CSS_TOKENS = (
    ".search-shell",
    ".search-intro",
    ".search-rules",
    ".search-panel",
    ".search-controls",
    ".search-field",
    ".filter-row",
    ".result-grid",
    ".search-card",
    ".aspect-pill",
    ".reason-pill",
    ".score-pill",
    ".fixture-panel",
    ".fixture-button",
    ".fixture-list",
    ":focus-visible",
)
REQUIRED_README_TOKENS = (
    "COMMONWORLD-ATLAS-V1-T016",
    "search-index-input.sample.json",
    "does not introduce a search endpoint",
    "transparent match reasons",
    "not a server ranking",
    "try-search buttons",
    "vector database",
    "public submissions",
    "weltgewebe write path",
)
FORBIDDEN_HTML_TOKENS = (
    "<form",
    "method=\"post\"",
    "type=\"submit\"",
    "login",
    "signup",
    "join now",
    "manage project",
)
FORBIDDEN_JS_TOKENS = (
    "fetch(\"/",
    "fetch('/",
    "localStorage",
    "indexedDB",
    "navigator.sendBeacon",
    "XMLHttpRequest",
    "method: \"POST\"",
    "method: 'POST'",
    "method: \"PUT\"",
    "method: 'PUT'",
    "method: \"PATCH\"",
    "method: 'PATCH'",
    "method: \"DELETE\"",
    "method: 'DELETE'",
)


def contains_all(text: str, tokens: tuple[str, ...], label: str, errors: list[str]) -> None:
    for token in tokens:
        if token not in text:
            errors.append(f"search proof {label} missing required token: {token}")


def contains_none(text: str, tokens: tuple[str, ...], label: str, errors: list[str]) -> None:
    lowered = text.casefold()
    for token in tokens:
        if token.casefold() in lowered:
            errors.append(f"search proof {label} must not include forbidden token: {token}")


def validate_search_proof(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    files = [root / path.relative_to(ROOT) for path in REQUIRED_FILES]
    for file_path in files:
        if not file_path.is_file():
            errors.append(f"missing search proof file: {file_path.relative_to(root)}")
    if errors:
        return errors

    html = (root / "proofs" / "search" / "index.html").read_text(encoding="utf-8")
    css = (root / "proofs" / "search" / "search.css").read_text(encoding="utf-8")
    js = (root / "proofs" / "search" / "search.js").read_text(encoding="utf-8")
    readme = (root / "proofs" / "search" / "README.md").read_text(encoding="utf-8")

    contains_all(html, REQUIRED_HTML_TOKENS, "HTML", errors)
    contains_none(html, FORBIDDEN_HTML_TOKENS, "HTML", errors)
    contains_all(css, REQUIRED_CSS_TOKENS, "CSS", errors)
    contains_all(js, REQUIRED_JS_TOKENS, "JS", errors)
    contains_none(js, FORBIDDEN_JS_TOKENS, "JS", errors)
    contains_all(readme, REQUIRED_README_TOKENS, "README", errors)

    if "loadJson(SEARCH_INPUT_URL)" not in js:
        errors.append("search proof JS must only use shared loadJson with explicit sample URL")
    if "data-card-path" not in html or "project_path" not in js:
        errors.append("search proof must expose source project_path for traceability")
    if "data-card-handoff" not in html or "profile_handoff_state" not in js:
        errors.append("search proof must expose profile_handoff_state as read-only marker")
    if "data-card-score" not in html or "local proof points" not in js:
        errors.append("search proof must expose a local proof score without server ranking")
    if "data-card-reasons" not in html or "renderReasonPill" not in js:
        errors.append("search proof must expose transparent match reasons")
    if "data-query-fixtures" not in html or "renderQueryFixtures" not in js:
        errors.append("search proof must expose static query fixture buttons")
    if "QUERY_FIXTURES_URL" not in js or "loadJson(QUERY_FIXTURES_URL)" not in js:
        errors.append("search proof must load static T018 query fixtures through shared loadJson")
    if "applyQueryFixture" not in js or 'button.type = "button"' not in js:
        errors.append("search proof query fixture actions must remain local button actions")

    return errors


def main() -> int:
    errors = validate_search_proof(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld static search proof validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
