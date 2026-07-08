#!/usr/bin/env python3
"""Validate the commonworld static catalog export contract and proof sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_catalog_export import build_catalog_export, stable_json
DOC_PATH = ROOT / "docs" / "blueprints" / "catalog-export-contract.md"
SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "catalog-export.schema.json"
SAMPLE_PATH = ROOT / "examples" / "commonworld" / "catalog-export.sample.json"
SEED_MANIFEST_PATH = ROOT / "examples" / "commonworld" / "seed-projects.json"

REQUIRED_DOC_PHRASES = (
    "COMMONWORLD-ATLAS-V1-T010",
    "static export first",
    "no API server",
    "no database",
    "no ingestion worker",
    "no public submissions",
    "no write path",
    "CommonProject files = catalog claim source",
    "catalog export      = deterministic read-only projection",
    "Public exports must only include accepted catalog data",
    "Public exports must not publish fixture entries",
    "Public exports must not publish candidate entries as if they were curated",
    "must not contain secrets, credentials, account state, role state or private review notes",
    "must not create a public submission route",
    "must not create a weltgewebe write path",
    "COMMONWORLD-ATLAS-V1-T011 is implemented by `scripts/generate_catalog_export.py`",
    "make generate-catalog-export",
    "make validate",
    "does not introduce API runtime, database selection, ingestion workers or public write paths",
)

FORBIDDEN_DOC_PHRASES = (
    "create api server now",
    "write endpoint",
    "public submissions are enabled",
    "automatic publication is allowed",
)


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_catalog_export_contract(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    doc_path = root / DOC_PATH.relative_to(ROOT)
    schema_path = root / SCHEMA_PATH.relative_to(ROOT)
    sample_path = root / SAMPLE_PATH.relative_to(ROOT)

    for path, label in (
        (doc_path, "catalog export contract doc"),
        (schema_path, "catalog export schema"),
        (sample_path, "catalog export proof sample"),
    ):
        if not path.is_file():
            return [f"missing {label}: {path.relative_to(root)}"]

    doc = doc_path.read_text(encoding="utf-8")
    lowered = doc.casefold()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.casefold() not in lowered:
            errors.append(f"catalog export contract missing required phrase: {phrase}")
    for phrase in FORBIDDEN_DOC_PHRASES:
        if phrase.casefold() in lowered:
            errors.append(f"catalog export contract includes forbidden shortcut: {phrase}")

    schema = load_json(schema_path)
    sample = load_json(sample_path)
    Draft202012Validator.check_schema(schema)
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(sample), key=lambda error: error.path)
    for error in schema_errors:
        path = ".".join(str(part) for part in error.path) or "catalog-export.sample.json"
        errors.append(f"{path}: {error.message}")

    if sample.get("source_manifest_path") != "examples/commonworld/seed-projects.json":
        errors.append("catalog export sample must point at examples/commonworld/seed-projects.json")

    expected_export, manifest_errors = build_catalog_export(root)
    errors.extend(manifest_errors)
    if not manifest_errors and sample != expected_export:
        errors.append("catalog export sample must match deterministic generator output")
    if not manifest_errors and sample.get("entries") != expected_export.get("entries"):
        errors.append("catalog export sample entries must deterministically mirror seed manifest project order and public metadata")
    if not manifest_errors and sample_path.read_text(encoding="utf-8") != stable_json(expected_export):
        errors.append("catalog export sample JSON formatting must match deterministic generator output")

    boundary = sample.get("boundary", {})
    if boundary.get("access") != "read-only":
        errors.append("catalog export sample boundary must be read-only")
    if "no writes" not in boundary.get("write_behavior", ""):
        errors.append("catalog export sample boundary must prohibit writes")

    if sample.get("scope") == "public":
        for entry in sample.get("entries", []):
            if entry.get("curation_state") != "curated":
                errors.append("public catalog exports must contain only curated entries")

    return errors


def main() -> int:
    errors = validate_catalog_export_contract(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld catalog export contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
