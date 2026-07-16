#!/usr/bin/env python3
"""Validate the T007 intent-oriented Commonworld discovery surface."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("contracts/commonworld/intent-search-discovery.contract.json")
RESULT = Path("docs/research/intent-search-discovery-v1.result.json")
FILTERS = ["presence", "action", "language", "access", "freshness", "curation"]
ACTIONS = {"visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"}
NONCLAIMS = [
    "semantic AI or LLM search",
    "inferred project capabilities or locations",
    "complete language or access metadata",
    "catalog completeness",
    "million-scale delivery architecture",
    "server-side search",
    "WCAG conformance",
]
HASHED_PATHS = [
    "assets/commonworld-core.mjs",
    "assets/commonworld-app.js",
    "contracts/commonworld/project.schema.json",
    "contracts/commonworld/intent-search-discovery.contract.json",
    "scripts/render_public_shell.py",
    "scripts/smoke_public_browser.mjs",
    "scripts/validate_public_catalog.py",
    "index.css",
    "index.html",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((root / "catalog/projects").glob("*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def node_probe(root: Path) -> tuple[dict | None, str | None]:
    script = r"""
import fs from 'node:fs';
import {
  filterRecords,
  prepareIntentSearchIndex,
  publicMapFeatureCollection,
  publicProjectNavigationTarget,
  searchFromState,
  stateFromSearch,
} from './assets/commonworld-core.mjs';
const manifest = JSON.parse(fs.readFileSync('./catalog/catalog.json', 'utf8'));
const records = manifest.project_files.map((path) => JSON.parse(fs.readFileSync('./catalog/' + path, 'utf8')));
const index = prepareIntentSearchIndex(records);
const ids = (query, filters = {}) => filterRecords(records, { query, ...filters, searchIndex: index }).map((record) => record.id);
const mapData = publicMapFeatureCollection(records);
const serialized = searchFromState({
  camera: { lng: 9.9, lat: 53.5, zoom: 4, bearing: 0, pitch: 0 },
  query: 'mitmachen', presence: 'hybrid', action: 'volunteer', language: 'de',
  access: 'public', freshness: 'current', curation: 'listed',
});
const roundtrip = stateFromSearch(serialized, records.map((record) => record.id));
const synthetic = Array.from({ length: 50000 }, (_, position) => ({
  id: 'common-' + String(position).padStart(5, '0'),
  title: 'Commons ' + position,
  summary: position === 49999 ? 'Ein seltener Leuchtturmbegriff.' : 'Gemeinschaftliche Infrastruktur.',
  kind: 'digital', themes: ['infrastructure'], actions: ['use'],
  presence: { geographic: [], digital: { available: true, reach: 'global', label: 'Digitale Präsenz' } },
  activity: { status: 'active' }, curation: { state: 'listed', next_review_at: '2027-01-01' }, links: [],
}));
const syntheticIndex = prepareIntentSearchIndex(synthetic);
console.log(JSON.stringify({
  indexedRecords: index.indexedRecordCount,
  indexedTerms: index.indexedTermCount,
  germanContribution: ids('ich möchte mitmachen'),
  publicPlace: ids('Anderlecht'),
  hiddenPhrase: ids('private heimrouter'),
  hybridVolunteer: ids('', { presence: 'hybrid', action: 'volunteer' }),
  digitalTarget: publicProjectNavigationTarget(mapData, 'debian'),
  geographicTarget: publicProjectNavigationTarget(mapData, 'cltb-le-nid'),
  hiddenTarget: publicProjectNavigationTarget(mapData, 'freifunk-hamburg-private-routers'),
  roundtrip: {
    query: roundtrip.query, presence: roundtrip.presence, action: roundtrip.action,
    language: roundtrip.language, access: roundtrip.access,
    freshness: roundtrip.freshness, curation: roundtrip.curation,
  },
  syntheticRecords: syntheticIndex.indexedRecordCount,
  syntheticResult: syntheticIndex.search({ query: 'leuchtturmbegriff' }).map((record) => record.id),
}));
"""
    process = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if process.returncode:
        return None, process.stderr.strip() or process.stdout.strip()
    try:
        return json.loads(process.stdout), None
    except json.JSONDecodeError as error:
        return None, f"invalid Node probe output: {error}"


def validate_intent_search_discovery(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        CONTRACT,
        RESULT,
        Path("docs/research/intent-search-discovery-v1.md"),
        Path("contracts/commonworld/project.schema.json"),
        Path("assets/commonworld-core.mjs"),
        Path("assets/commonworld-app.js"),
        Path("scripts/smoke_public_browser.mjs"),
        Path("scripts/render_public_shell.py"),
        Path("scripts/validate_public_catalog.py"),
        Path("index.html"),
        Path("index.css"),
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing T007 file: {relative}")
    if errors:
        return errors

    try:
        contract = load(root / CONTRACT)
        result = load(root / RESULT)
        schema = load(root / "contracts/commonworld/project.schema.json")
        manifest = load(root / "catalog/catalog.json")
        records = [load(root / "catalog" / relative) for relative in manifest["project_files"]]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        return [f"T007 control or catalog data is invalid: {error}"]

    if (contract.get("schema_version"), contract.get("kind")) != (1, "commonworld_intent_search_discovery_contract"):
        errors.append("T007 contract identity mismatch")
    if contract.get("source_contract") != {
        "id": "https://commonworld.net/contracts/commonworld/project.schema.json",
        "schema_version": 3,
        "identity_key": "CommonProject.id",
    }:
        errors.append("T007 source contract binding mismatch")
    if contract.get("truth_boundary") != {
        "catalog_is_only_persistent_project_truth": True,
        "persistent_search_document_forbidden": True,
        "runtime_index_is_derived_and_ephemeral": True,
        "hidden_geographic_values_excluded_from_index": True,
        "invented_project_facts_forbidden": True,
    }:
        errors.append("T007 truth boundary mismatch")
    if contract.get("filters") != FILTERS:
        errors.append("T007 filter contract mismatch")
    if contract.get("nonclaims") != NONCLAIMS:
        errors.append("T007 nonclaims mismatch")
    scalability = contract.get("scalability", {})
    if scalability.get("probe_record_count") != 50000:
        errors.append("T007 scalability probe contract mismatch")
    if scalability.get("million_scale_delivery_claimed") is not False:
        errors.append("T007 must not claim million-scale delivery")
    if contract.get("spatial_navigation", {}).get("hidden_locations_never_produce_navigation_targets") is not True:
        errors.append("T007 hidden-location navigation protection missing")
    if contract.get("action_links") != {
        "one_direct_link_per_claimed_action": True,
        "same_type_as_claimed_action": True,
        "https_required": True,
        "source_ids_required": True,
        "unknown_source_ids_forbidden": True,
    }:
        errors.append("T007 action-link contract mismatch")

    properties = schema.get("properties", {})
    schema_actions = set(properties.get("actions", {}).get("items", {}).get("enum", []))
    schema_link_types = set(schema.get("$defs", {}).get("link", {}).get("properties", {}).get("type", {}).get("enum", []))
    if schema_actions != ACTIONS:
        errors.append("T007 action vocabulary must cover the complete CommonProject action enum")
    if not schema_actions.issubset(schema_link_types):
        errors.append("T007 every CommonProject action must be an allowed direct link type")
    for field in ("languages", "access"):
        if field not in properties:
            errors.append(f"T007 CommonProject schema missing discovery field: {field}")
    if "search_document" in properties:
        errors.append("T007 must not create a persistent search_document truth")

    for record in records:
        identifier = record.get("id")
        if "search_document" in record:
            errors.append(f"T007 record {identifier} contains forbidden search_document")
        source_ids = {
            source.get("id")
            for source in record.get("provenance", {}).get("sources", [])
            if isinstance(source, dict) and isinstance(source.get("id"), str)
        }
        actions = [action for action in record.get("actions", []) if isinstance(action, str)]
        action_links = [
            link for link in record.get("links", [])
            if isinstance(link, dict) and link.get("type") in ACTIONS
        ]
        for action in actions:
            matching = [link for link in action_links if link.get("type") == action]
            if len(matching) != 1:
                errors.append(f"T007 project {identifier} action {action} must have exactly one direct action link")
                continue
            link = matching[0]
            if not str(link.get("url", "")).startswith("https://"):
                errors.append(f"T007 project {identifier} action {action} link must use HTTPS")
            linked = link.get("source_ids")
            if not isinstance(linked, list) or not linked or not set(linked).issubset(source_ids):
                errors.append(f"T007 project {identifier} action {action} link must resolve to known sources")
        for link in action_links:
            if link.get("type") not in actions:
                errors.append(f"T007 project {identifier} publishes an unclaimed action link")

    probe, probe_error = node_probe(root)
    if probe_error:
        errors.append(f"T007 Node probe failed: {probe_error}")
    elif probe is not None:
        expected_rank = [
            "debian", "freifunk", "freifunk-hamburg", "libreoffice", "mastodon",
            "openstreetmap", "wikidata", "wikimedia-commons", "wikipedia",
        ]
        if probe.get("indexedRecords") != 12 or probe.get("indexedTerms", 0) <= 0:
            errors.append("T007 runtime index does not cover the current catalog")
        if probe.get("germanContribution") != expected_rank:
            errors.append("T007 German intent ranking mismatch")
        if probe.get("publicPlace") != ["cltb-le-nid"]:
            errors.append("T007 public place query mismatch")
        if probe.get("hiddenPhrase") != []:
            errors.append("T007 hidden geographic values leaked into search")
        if probe.get("hybridVolunteer") != ["freifunk-hamburg"]:
            errors.append("T007 combined filter identity mismatch")
        if probe.get("digitalTarget") is not None:
            errors.append("T007 digital Commons acquired a spatial navigation target")
        if probe.get("geographicTarget", {}).get("kind") != "bounds":
            errors.append("T007 geographic Commons lacks a public navigation target")
        if probe.get("hiddenTarget") is not None:
            errors.append("T007 hidden location acquired a navigation target")
        if probe.get("roundtrip") != {
            "query": "mitmachen", "presence": "hybrid", "action": "volunteer",
            "language": "de", "access": "public", "freshness": "current", "curation": "listed",
        }:
            errors.append("T007 query/filter URL roundtrip mismatch")
        if probe.get("syntheticRecords") != 50000 or probe.get("syntheticResult") != ["common-49999"]:
            errors.append("T007 50,000-record inverted-index probe mismatch")

    shell = (root / "index.html").read_text(encoding="utf-8")
    for token in (
        'id="discovery-panel"', 'id="discovery-list"', 'id="discovery-empty"',
        'data-intent-filter="presence"', 'data-intent-filter="action"',
        'data-intent-filter="language"', 'data-intent-filter="access"',
        'data-intent-filter="freshness"', 'data-intent-filter="curation"',
        '<option value="borrow">Ausleihen</option>', 'data-action-type=',
    ):
        if token not in shell:
            errors.append(f"T007 public shell missing token: {token}")
    browser = (root / "scripts/smoke_public_browser.mjs").read_text(encoding="utf-8")
    for scenario in contract.get("browser_evidence", {}).get("required_scenarios", []):
        if scenario not in browser:
            errors.append(f"T007 browser evidence missing scenario: {scenario}")

    if (result.get("schema_version"), result.get("kind")) != (1, "commonworld_intent_search_discovery_research"):
        errors.append("T007 research result identity mismatch")
    if result.get("checked_at") != "2026-07-16" or result.get("status") != "verified_for_publication":
        errors.append("T007 research result status mismatch")
    verification = result.get("implementation_verification", {})
    evidence = verification.get("file_evidence", {})
    for relative in HASHED_PATHS:
        if evidence.get(relative) != sha256(root / relative):
            errors.append(f"T007 research evidence hash mismatch: {relative}")
    if verification.get("catalog_projects_sha256") != catalog_digest(root):
        errors.append("T007 catalog evidence hash mismatch")
    if verification.get("browser", {}).get("receipt_sha256") != "9d05ae9ec7a3467c4d22b46b6d5cda682d7b7459442f9521d2f2473d9345bf1e":
        errors.append("T007 browser receipt binding mismatch")
    if result.get("does_not_establish") != NONCLAIMS:
        errors.append("T007 research nonclaims mismatch")
    return errors


def main() -> int:
    errors = validate_intent_search_discovery(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld intent search and discovery validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
