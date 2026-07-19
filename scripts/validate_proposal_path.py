#!/usr/bin/env python3
"""Validate the static Commonworld proposal, editorial and diversity contracts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REJECTION_CODES = {
    "not_a_commons", "insufficient_sources", "duplicate", "private_location_risk",
    "commercial_listing_only", "project_inactive", "action_claim_unverified", "out_of_scope",
}
EXPECTED_STATUSES = {"submitted", "needs_information", "under_review", "accepted", "rejected", "withdrawn", "published", "superseded"}
PRIVATE_PATTERN = re.compile(r"(?:\b(?:latitude|longitude|coordinates?|gps|street|straße|strasse|router|roof|dach|wohnung|apartment|household|haushalt)\b|[-+]?\d{1,3}\.\d{3,}\s*[,;/ ]\s*[-+]?\d{1,3}\.\d{3,})", re.I)


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
    if PRIVATE_PATTERN.search(str(project.get("region", ""))):
        errors.append("region contains precise or private location material")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        "propose.html", "assets/commonworld-proposal.js", "contracts/commonworld/proposal.schema.json",
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
    script = (root / "assets/commonworld-proposal.js").read_text(encoding="utf-8")
    for marker in ("nicht automatisch veröffentlicht", "öffentliches GitHub-Issue", "keine private Adresse", "proposal-catalog-index", "proposal-download"):
        if marker.casefold() not in page.casefold(): errors.append(f"proposal page missing marker: {marker}")

    proposal_css_path = root / "assets/proposal.css"
    if not proposal_css_path.is_file():
        errors.append("missing proposal surface: assets/proposal.css")
    else:
        from html.parser import HTMLParser

        class LinkParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.links: list[str] = []
            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag == 'link':
                    attr_dict = dict(attrs)
                    if attr_dict.get('rel') == 'stylesheet' and attr_dict.get('href'):
                        self.links.append(attr_dict['href'])

        def find_css_block(css: str, prefix: str) -> tuple[str, str] | None:
            in_string = None
            in_comment = False
            i = 0
            length = len(css)
            while i < length:
                if in_comment:
                    if css[i:i+2] == '*/':
                        in_comment = False
                        i += 2
                    else:
                        i += 1
                    continue
                if in_string:
                    if css[i] == '\\':
                        i += 2
                    elif css[i] == in_string:
                        in_string = None
                        i += 1
                    else:
                        i += 1
                    continue
                if css[i:i+2] == '/*':
                    in_comment = True
                    i += 2
                    continue
                if css[i] in ("'", '"'):
                    in_string = css[i]
                    i += 1
                    continue
                if css[i:].startswith(prefix):
                    start_idx = i
                    brace_idx = -1
                    while i < length:
                        if in_comment:
                            if css[i:i+2] == '*/':
                                in_comment = False
                                i += 2
                            else:
                                i += 1
                            continue
                        if in_string:
                            if css[i] == '\\':
                                i += 2
                            elif css[i] == in_string:
                                in_string = None
                                i += 1
                            else:
                                i += 1
                            continue
                        if css[i:i+2] == '/*':
                            in_comment = True
                            i += 2
                            continue
                        if css[i] in ("'", '"'):
                            in_string = css[i]
                            i += 1
                            continue
                        if css[i] == '{':
                            brace_idx = i
                            break
                        i += 1
                    if brace_idx == -1:
                        return None
                    selector_str = css[start_idx:brace_idx].strip()
                    block_start = brace_idx + 1
                    brace_count = 1
                    i = block_start
                    while i < length:
                        if in_comment:
                            if css[i:i+2] == '*/':
                                in_comment = False
                                i += 2
                            else:
                                i += 1
                            continue
                        if in_string:
                            if css[i] == '\\':
                                i += 2
                            elif css[i] == in_string:
                                in_string = None
                                i += 1
                            else:
                                i += 1
                            continue
                        if css[i:i+2] == '/*':
                            in_comment = True
                            i += 2
                            continue
                        if css[i] in ("'", '"'):
                            in_string = css[i]
                            i += 1
                            continue
                        if css[i] == '{':
                            brace_count += 1
                        elif css[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                return (selector_str, css[block_start:i])
                        i += 1
                    return None
                i += 1
            return None

        proposal_css = proposal_css_path.read_text(encoding="utf-8")
        index_link = "./index.css"
        proposal_link = "./assets/proposal.css"
        
        link_parser = LinkParser()
        link_parser.feed(page)
        
        if index_link not in link_parser.links or proposal_link not in link_parser.links:
            errors.append("propose.html must load index.css and assets/proposal.css")
        elif link_parser.links.index(index_link) >= link_parser.links.index(proposal_link):
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
    for forbidden in ("api_key", "client_secret", "authorization: bearer", "innerhtml", "document.cookie"):
        if forbidden in script.casefold(): errors.append(f"proposal client contains forbidden material: {forbidden}")
    if "javascript" not in script.casefold() or "containsSensitiveLocation" not in script: errors.append("proposal client lacks explicit dangerous URL or sensitive-location checks")
    if "sessionStorage" not in script or "60_000" not in script: errors.append("proposal client lacks bounded repeated-preparation control")
    if "window.open" not in script or "downloadJson" not in script: errors.append("proposal client lacks GitHub handoff or JSON fallback")

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
