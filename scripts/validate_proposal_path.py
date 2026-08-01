#!/usr/bin/env python3
"""Validate the static Commonworld proposal, editorial and diversity contracts."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

try:
    from scripts.static_surface_parser import find_css_block, find_media_block, find_media_blocks, parse_stylesheet_links
except ModuleNotFoundError as exc:  # direct script execution puts the scripts dir on sys.path
    # Only fall back when the 'scripts' package itself is unreachable; a missing
    # dependency inside static_surface_parser must stay visible.
    if exc.name not in {"scripts", "scripts.static_surface_parser"}:
        raise
    from static_surface_parser import find_css_block, find_media_block, find_media_blocks, parse_stylesheet_links

ROOT = Path(__file__).resolve().parents[1]
REJECTION_CODES = {
    "not_a_commons", "insufficient_sources", "duplicate", "private_location_risk",
    "commercial_listing_only", "project_inactive", "action_claim_unverified", "out_of_scope",
}
EXPECTED_STATUSES = {"submitted", "needs_information", "under_review", "accepted", "rejected", "withdrawn", "published", "superseded"}
SENSITIVE_CONTEXT_PATTERN = re.compile(r"\b(?:latitude|longitude|coordinates?|gps)\b", re.I)
DECIMAL_POINT_COORDINATE_PATTERN = re.compile(r"(?:^|[^\d])[-+]?\d{1,3}\.\d{3,}\s*[,;/ ]\s*[-+]?\d{1,3}\.\d{3,}(?:[^\d]|$)")
DECIMAL_COMMA_COORDINATE_PATTERN = re.compile(r"(?:^|[^\d])[-+]?\d{1,3},\d{3,}\s*[;/]\s*[-+]?\d{1,3},\d{3,}(?:[^\d]|$)")
DMS_COORDINATE_PATTERN = re.compile(r"\d{1,3}\s*°\s*\d{1,2}\s*[′']\s*\d{1,2}(?:[.,]\d+)?\s*(?:[″\"]|[′']{2})\s*[NS](?:\s*[,;]\s*|\s+)\d{1,3}\s*°\s*\d{1,2}\s*[′']\s*\d{1,2}(?:[.,]\d+)?\s*(?:[″\"]|[′']{2})\s*[EW]", re.I)
LETTER_OR_MARK = r"(?:[^\W\d_]|[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f])"
WORD = rf"{LETTER_OR_MARK}(?:{LETTER_OR_MARK}|['’.-])*"
HOUSE_NUMBER = r"\d{1,5}[a-z]?(?:[-/]\d{1,5}[a-z]?)?"
ATTACHED_STREET_SUFFIX = r"(?:straße|strasse|weg|gasse|allee|platz)"
STREET_WORD = r"(?:street|road|avenue|boulevard|lane|drive|way|straße|strasse|rue|calle|via|viale|corso|ulica|prospekt|st\.?|rd\.?|ave\.?|blvd\.?|ln\.?|dr\.?)"
ADDRESS_PATTERNS = (
    re.compile(rf"(?:^|[^\w])(?:{WORD}\s+){{0,5}}{WORD}{ATTACHED_STREET_SUFFIX}\s+{HOUSE_NUMBER}(?=$|[^\w])", re.I),
    re.compile(rf"(?:^|[^\w])(?:{WORD}\s+){{1,5}}{STREET_WORD}\s+{HOUSE_NUMBER}(?=$|[^\w])", re.I),
    re.compile(rf"(?:^|[^\w])(?:rue|calle|via|viale|corso|avenue|boulevard)\s+(?:{WORD}\s+){{0,4}}{WORD}\s+{HOUSE_NUMBER}(?=$|[^\w])", re.I),
    re.compile(rf"(?:^|[^\w]){HOUSE_NUMBER}\s+(?:{WORD}\s+){{0,5}}{STREET_WORD}(?=$|[^\w])", re.I),
)
PUBLIC_TEXT_FIELDS = ("name", "description", "region", "editorial_note")


def contains_sensitive_location(value: object) -> bool:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return bool(
        SENSITIVE_CONTEXT_PATTERN.search(normalized)
        or DECIMAL_POINT_COORDINATE_PATTERN.search(normalized)
        or DECIMAL_COMMA_COORDINATE_PATTERN.search(normalized)
        or DMS_COORDINATE_PATTERN.search(normalized)
        or any(pattern.search(normalized) for pattern in ADDRESS_PATTERNS)
    )


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate_fixture(value: dict, schema: dict) -> list[str]:
    errors = [error.message for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]
    project = value.get("project", {}) if isinstance(value, dict) else {}
    for key in ("official_website",):
        raw = project.get(key)
        parsed = urlparse(raw) if isinstance(raw, str) else None
        if not parsed or parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{key} must be safe HTTPS")
    for raw in project.get("sources", []) if isinstance(project.get("sources"), list) else []:
        parsed = urlparse(raw) if isinstance(raw, str) else None
        if not parsed or parsed.scheme != "https" or not parsed.netloc:
            errors.append("source must be safe HTTPS")
    for key in PUBLIC_TEXT_FIELDS:
        raw = project.get(key)
        if isinstance(raw, str) and contains_sensitive_location(raw):
            errors.append(f"{key} contains precise or private location material")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        "propose.html", "propose.de.html", "assets/commonworld-proposal.js", "contracts/commonworld/proposal.schema.json",
        "contracts/commonworld/editorial-review.contract.json", "contracts/commonworld/proposal-path.contract.json",
        "contracts/commonworld/catalog-diversity.contract.json", ".github/ISSUE_TEMPLATE/commons-proposal.yml",
    ]
    for relative in required:
        if not (root / relative).is_file(): errors.append(f"missing proposal surface: {relative}")
    if errors: return errors

    schema = load("contracts/commonworld/proposal.schema.json")
    editorial = load("contracts/commonworld/editorial-review.contract.json")
    path = load("contracts/commonworld/proposal-path.contract.json")
    diversity = load("contracts/commonworld/catalog-diversity.contract.json")
    manifest = load("catalog/catalog.json")
    project_ids = {Path(item).stem for item in manifest["project_files"]}

    if schema.get("additionalProperties") is not False: errors.append("proposal schema must reject unknown top-level fields")
    project_schema = schema.get("properties", {}).get("project", {})
    if project_schema.get("additionalProperties") is not False: errors.append("proposal project schema must reject unknown fields")
    if "contact" in project_schema.get("properties", {}): errors.append("public proposal schema must not collect direct contact data")

    statuses = set(editorial.get("statuses", []))
    if statuses != EXPECTED_STATUSES: errors.append("editorial statuses mismatch")
    if set(editorial.get("transitions", {})) != EXPECTED_STATUSES: errors.append("every editorial status needs an explicit transition list")
    if set(editorial.get("rejection_reason_codes", [])) != REJECTION_CODES: errors.append("editorial rejection codes mismatch")
    if editorial.get("publication_boundary", {}).get("automatic_publication") is not False: errors.append("proposal path must forbid automatic publication")
    if editorial.get("publication_boundary", {}).get("catalog_change_requires_reviewed_repository_commit") is not True: errors.append("publication must require a reviewed repository commit")

    architecture = path.get("architecture", {})
    if architecture.get("hosting") != "github_pages_static" or architecture.get("commonworld_backend") is not False or architecture.get("commonworld_write_api") is not False: errors.append("proposal architecture crossed the static read-only boundary")
    privacy = path.get("privacy", {})
    if privacy.get("contact_field_collected") is not False or privacy.get("proposal_content_stored_by_commonworld") is not False: errors.append("proposal path collects or stores unnecessary personal data")

    if manifest.get("entry_count", 0) < diversity.get("minimum_catalog_size", 30): errors.append("catalog size is below the Phase 5 minimum")
    if diversity.get("growth_policy") != "minimum_not_exact_ceiling": errors.append("diversity contract must not impose a fixed future ceiling")
    for group_name in ("required_regions", "required_domains"):
        for name, representatives in diversity.get(group_name, {}).items():
            if not representatives: errors.append(f"diversity group {name} has no representative")
            missing = sorted(set(representatives) - project_ids)
            if missing: errors.append(f"diversity group {name} references missing projects: {missing}")

    page = (root / "propose.html").read_text(encoding="utf-8")
    german_page = (root / "propose.de.html").read_text(encoding="utf-8")
    script = (root / "assets/commonworld-proposal.js").read_text(encoding="utf-8")
    for marker in ("not published automatically", "public GitHub issue", "private address", "proposal-catalog-index", "proposal-download"):
        if marker.casefold() not in page.casefold(): errors.append(f"proposal page missing marker: {marker}")
    for marker in ("nicht automatisch veröffentlicht", "öffentliches GitHub-Issue", "private Adresse"):
        if marker.casefold() not in german_page.casefold(): errors.append(f"German proposal page missing marker: {marker}")
    if 'href="./propose.de.html?ui_lang=de"' not in page or 'href="./propose.html?ui_lang=en"' not in german_page:
        errors.append("proposal locale switch must connect English and German surfaces")
    for surface, name in ((page, "propose.html"), (german_page, "propose.de.html")):
        for marker in (
            'data-locale-choice="auto"',
            'data-locale-choice="en"',
            'data-locale-choice="de"',
            'data-locale-effective',
        ):
            if marker not in surface: errors.append(f"{name} locale control missing marker: {marker}")

    proposal_css_path = root / "assets/proposal.css"
    if not proposal_css_path.is_file():
        errors.append("missing proposal surface: assets/proposal.css")
    else:
        proposal_css = proposal_css_path.read_text(encoding="utf-8")
        index_link = "./index.css"
        proposal_link = "./assets/proposal.css"
        links = [link.split("?", 1)[0] for link in parse_stylesheet_links(page)]
        if index_link not in links or proposal_link not in links:
            errors.append("propose.html must load index.css and assets/proposal.css")
        elif links.index(index_link) >= links.index(proposal_link):
            errors.append("propose.html must load assets/proposal.css after index.css")

        body_match = find_css_block(proposal_css, "body.proposal-page")
        if body_match is None:
            errors.append("assets/proposal.css must style body.proposal-page")
        else:
            block = body_match[1]
            if "overflow-y: auto" not in block:
                errors.append("assets/proposal.css body.proposal-page must set overflow-y: auto")
            if "overflow-x: hidden" not in block:
                errors.append("assets/proposal.css body.proposal-page must set overflow-x: hidden")
            if "-webkit-overflow-scrolling: touch" not in block:
                errors.append("assets/proposal.css body.proposal-page must set -webkit-overflow-scrolling: touch")
            if not re.search(r"overscroll-behavior(-y)?:\s*contain", block):
                errors.append("assets/proposal.css body.proposal-page must set overscroll-behavior(-y): contain")
            if "overflow: hidden" in block or "overflow-y: hidden" in block:
                errors.append("assets/proposal.css body.proposal-page must not reintroduce overflow-y: hidden")

        honeypot_match = find_css_block(proposal_css, ".honeypot")
        if honeypot_match is None:
            errors.append("assets/proposal.css must visually hide the proposal honeypot")
        else:
            block = honeypot_match[1]
            for token in ("position: absolute", "width: 1px", "height: 1px", "overflow: hidden", "clip-path: inset(50%)"):
                if token not in block:
                    errors.append(f"proposal honeypot hiding contract missing token: {token}")
            if re.search(r"(?:^|[;{])\s*(?:left|right|inset-inline-(?:start|end))\s*:", block):
                errors.append("proposal honeypot must not use direction-sensitive offscreen positioning")

        forced = find_media_block(proposal_css, ("forced-colors: active",))
        if forced is None:
            errors.append("assets/proposal.css must define a forced-colors: active contract")
        else:
            block = forced[1]
            for token in ("CanvasText", "FieldText", "ButtonText", "Highlight", ".proposal-errors", ":disabled"):
                if token not in block:
                    errors.append(f"proposal forced-colors contract missing token: {token}")

        reduced_motion = find_media_blocks(proposal_css, ("prefers-reduced-motion: reduce",))
        if not reduced_motion:
            errors.append("assets/proposal.css must define a prefers-reduced-motion: reduce contract")
        elif not any("transition: none !important" in block for _, block in reduced_motion):
            errors.append("proposal reduced-motion contract must disable transitions")

        contrast = find_media_block(proposal_css, ("prefers-contrast: more",))
        if contrast is None:
            errors.append("assets/proposal.css must define a prefers-contrast: more contract")
        else:
            block = contrast[1]
            for token in ("outline: 4px", "border-width: 2px", "input:checked"):
                if token not in block:
                    errors.append(f"proposal increased-contrast contract missing token: {token}")
    for forbidden in ("api_key", "client_secret", "authorization: bearer", "innerhtml", "document.cookie"):
        if forbidden in script.casefold(): errors.append(f"proposal client contains forbidden material: {forbidden}")
    if "javascript" not in script.casefold() or "containsSensitiveLocation" not in script: errors.append("proposal client lacks explicit dangerous URL or sensitive-location checks")
    if "sessionStorage" not in script or "60_000" not in script: errors.append("proposal client lacks bounded repeated-preparation control")
    if "window.open" not in script or "downloadJson" not in script: errors.append("proposal client lacks GitHub handoff or JSON fallback")

    sensitive_cases = load("tests/fixtures/proposals/sensitive-location-cases.json")
    for case in sensitive_cases.get("blocked", []):
        if not contains_sensitive_location(case.get("value", "")): errors.append(f"sensitive-location blocked fixture accepted: {case.get('id')}")
    for case in sensitive_cases.get("allowed", []):
        if contains_sensitive_location(case.get("value", "")): errors.append(f"sensitive-location allowed fixture rejected: {case.get('id')}")
    for fixture in ("valid.json", "digital-only-valid.json"):
        if validate_fixture(load(f"tests/fixtures/proposals/{fixture}"), schema): errors.append(f"valid proposal fixture is rejected: {fixture}")
    for fixture in ("missing-source.json", "javascript-url.json", "private-coordinates.json", "geographic-missing-region.json"):
        if not validate_fixture(load(f"tests/fixtures/proposals/{fixture}"), schema): errors.append(f"invalid proposal fixture accepted: {fixture}")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors: print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld proposal, editorial and diversity contracts ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
