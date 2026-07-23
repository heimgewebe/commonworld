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
EXPECTED_RESULT_SHA256 = "7085139444d298e41a3bc9fbda4af3e6e75c02f2c90cc173e52c48deab34245f"
FILTERS = ["commons_type", "presence", "action", "language", "access", "freshness", "curation"]
COMMONS_TYPES = ["knowledge", "software", "culture", "food-seeds", "water", "energy", "housing-land", "health-care", "tools-repair", "community-network", "other"]
COMMONS_TYPE_LABELS = {
    "knowledge": "Wissen und Daten",
    "software": "Software und Infrastruktur",
    "culture": "Kultur und Medien",
    "food-seeds": "Saatgut und Ernährung",
    "water": "Wasser und Bewässerung",
    "energy": "Energie",
    "housing-land": "Boden und Wohnen",
    "health-care": "Pflege und Gesundheit",
    "tools-repair": "Werkzeuge, Reparatur und Fertigung",
    "community-network": "Gemeinschaftsnetz",
    "other": "Andere",
}
COMMONS_TYPE_LABELS_EN = {
    "knowledge": "Knowledge and Data",
    "software": "Software and Infrastructure",
    "culture": "Culture and Media",
    "food-seeds": "Seeds and Food",
    "water": "Water and Irrigation",
    "energy": "Energy",
    "housing-land": "Land and Housing",
    "health-care": "Care and Health",
    "tools-repair": "Tools, Repair and Making",
    "community-network": "Community Network",
    "other": "Other",
}
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

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
  query: 'mitmachen', commons_type: 'community-network', presence: ['geographic', 'digital'], action: 'volunteer', language: 'de',
  access: 'public', freshness: 'current', curation: 'listed',
});
const roundtrip = stateFromSearch(serialized, records.map((record) => record.id));
const synthetic = Array.from({ length: 50000 }, (_, position) => ({
  id: 'common-' + String(position).padStart(5, '0'),
  title: 'Commons ' + position,
  summary: position === 49999 ? 'Ein seltener Leuchtturmbegriff.' : 'Gemeinschaftliche Infrastruktur.',
  themes: ['infrastructure'], actions: ['use'],
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
  dualPresenceVolunteer: ids('', { presence: ['geographic', 'digital'], action: 'volunteer' }),
  digitalTarget: publicProjectNavigationTarget(mapData, 'debian'),
  geographicTarget: publicProjectNavigationTarget(mapData, 'cltb-le-nid'),
  hiddenTarget: publicProjectNavigationTarget(mapData, 'freifunk-hamburg-private-routers'),
  roundtrip: {
    query: roundtrip.query, commons_type: roundtrip.commons_type, presence: roundtrip.presence, action: roundtrip.action,
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
        Path("contracts/commonworld/proposal.schema.json"),
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
        proposal_schema = load(root / "contracts/commonworld/proposal.schema.json")
        manifest = load(root / "catalog/catalog.json")
        records = [load(root / "catalog" / relative) for relative in manifest["project_files"]]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        return [f"T007 control or catalog data is invalid: {error}"]

    if (contract.get("schema_version"), contract.get("kind")) != (1, "commonworld_intent_search_discovery_contract"):
        errors.append("T007 contract identity mismatch")
    if contract.get("source_contract") != {
        "id": "https://commonworld.net/contracts/commonworld/project.schema.json",
        "schema_version": 4,
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
    filter_semantics = contract.get("filter_semantics", {})
    if filter_semantics.get("commons_type_values_follow_proposal_vocabulary") is not True:
        errors.append("T007 Commons type vocabulary binding missing")
    if filter_semantics.get("commons_type_is_deterministically_derived_from_catalog_themes_when_absent") is not True:
        errors.append("T007 Commons type derivation boundary missing")
    if filter_semantics.get("commons_type_source_vocabulary") != "contracts/commonworld/proposal.schema.json#/properties/project/properties/commons_type":
        errors.append("T007 Commons type vocabulary pointer mismatch")
    if filter_semantics.get("commons_type_fallback") != "other":
        errors.append("T007 Commons type fallback mismatch")
    proposal_types = proposal_schema.get("properties", {}).get("project", {}).get("properties", {}).get("commons_type", {}).get("enum", [])
    if proposal_types != COMMONS_TYPES:
        errors.append("T007 Commons type filter must exactly follow the proposal vocabulary")
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
        expected_contribution = sorted(
            record["id"]
            for record in records
            if "contribute" in record.get("actions", [])
        )
        expected_dual_presence_volunteer = sorted(
            record["id"]
            for record in records
            if bool(record.get("presence", {}).get("geographic"))
            and record.get("presence", {}).get("digital", {}).get("available") is True
            and "volunteer" in record.get("actions", [])
        )
        if probe.get("indexedRecords") != manifest.get("entry_count") or probe.get("indexedTerms", 0) <= 0:
            errors.append("T007 runtime index does not cover the current catalog")
        if sorted(probe.get("germanContribution", [])) != expected_contribution:
            errors.append("T007 German contribution intent does not match claimed actions")
        if probe.get("publicPlace") != ["cltb-le-nid"]:
            errors.append("T007 public place query mismatch")
        if probe.get("hiddenPhrase") != []:
            errors.append("T007 hidden geographic values leaked into search")
        if probe.get("dualPresenceVolunteer") != expected_dual_presence_volunteer:
            errors.append("T007 combined dual_presence-volunteer filter does not match claimed actions")
        if probe.get("digitalTarget") is not None:
            errors.append("T007 digital Commons acquired a spatial navigation target")
        if probe.get("geographicTarget", {}).get("kind") != "bounds":
            errors.append("T007 geographic Commons lacks a public navigation target")
        if probe.get("hiddenTarget") is not None:
            errors.append("T007 hidden location acquired a navigation target")
        if probe.get("roundtrip") != {
            "query": "mitmachen", "commons_type": "community-network", "presence": ["geographic", "digital"], "action": "volunteer",
            "language": "de", "access": "public", "freshness": "current", "curation": "listed",
        }:
            errors.append("T007 query/filter URL roundtrip mismatch")
        if probe.get("syntheticRecords") != 50000 or probe.get("syntheticResult") != ["common-49999"]:
            errors.append("T007 50,000-record inverted-index probe mismatch")

    shell = (root / "index.html").read_text(encoding="utf-8")
    german_shell_path = root / "de.html"
    german_shell = german_shell_path.read_text(encoding="utf-8") if german_shell_path.is_file() else None
    for token in (
        'id="discovery-panel"', 'id="discovery-list"', 'id="discovery-empty"',
        'class="filter-commons-type"', 'id="filter-commons-type"',
        'data-intent-filter="commons_type"', 'data-intent-filter="presence"', 'data-intent-filter="action"',
        'data-intent-filter="language"', 'data-intent-filter="access"',
        'data-intent-filter="freshness"', 'data-intent-filter="curation"',
        '<option value="borrow">Borrow</option>', 'data-action-type=',
    ):
        if token not in shell:
            errors.append(f"T007 English public shell missing token: {token}")
    if german_shell is not None and '<option value="borrow">Ausleihen</option>' not in german_shell:
        errors.append('T007 German public shell missing borrow action label')
    for commons_type, label in COMMONS_TYPE_LABELS_EN.items():
        token = f'<option value="{commons_type}">{label}</option>'
        if shell.count(token) != 1:
            errors.append(f"T007 English public shell must emit exactly one Commons type option: {commons_type}")
    if german_shell is not None:
        for commons_type, label in COMMONS_TYPE_LABELS.items():
            token = f'<option value="{commons_type}">{label}</option>'
            if german_shell.count(token) != 1:
                errors.append(f"T007 German public shell must emit exactly one Commons-Art option: {commons_type}")
    browser = (root / "scripts/smoke_public_browser.mjs").read_text(encoding="utf-8")
    for scenario in contract.get("browser_evidence", {}).get("required_scenarios", []):
        if scenario not in browser:
            errors.append(f"T007 browser evidence missing scenario: {scenario}")

    if (result.get("schema_version"), result.get("kind")) != (1, "commonworld_intent_search_discovery_research"):
        errors.append("T007 research result identity mismatch")
    if result.get("checked_at") != "2026-07-16" or result.get("status") != "verified_for_publication":
        errors.append("T007 research result status mismatch")
    verification = result.get("implementation_verification", {})
    if sha256(root / RESULT) != EXPECTED_RESULT_SHA256:
        errors.append("T007 historical research result was rewritten")
    if verification.get("browser", {}).get("receipt_sha256") != "abf7a1f353935dd34999dd9898c2ec69f0c263bbcfd55af178e6461c5ebf7301":
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
