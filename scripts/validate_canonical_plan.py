#!/usr/bin/env python3
"""Validate that the active repository is aligned to the canonical globe plan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "blueprints" / "commonworld-masterplan.md"

REQUIRED_PLAN_TOKENS = (
    "# Commonworld — kanonischer Globusplan",
    "die einzige Produktwahrheit des Repositories",
    "## Die eine öffentliche Oberfläche",
    "## Semantischer Zoom",
    "### Stufe 1 — Erde",
    "### Stufe 2 — Großregion",
    "### Stufe 3 — Region",
    "### Stufe 4 — Lokal",
    "### Stufe 5 — Fokus",
    "Farbton     = Commons-Art",
    "Intensität  = belegter Umfang oder belegte Dichte",
    "Textur      = Datenabdeckung oder Unsicherheit",
    "### Kalibrierter visueller Semantikvertrag",
    "## Digitale Commons-Sphäre",
    "Digitale Commons erhalten keine erfundenen Koordinaten.",
    "## Hybride Commons",
    "## Lineare Parallelansicht",
    "## CommonProject-Kern",
    "### Kanonischer Aggregations- und Zoomvertrag",
    "## Kanonische Umsetzungsfolge",
    "### Phase 0 — Repository-Neuausrichtung",
    "### Phase 1 — Daten- und Renderingvertrag",
    "### Phase 2 — Globusgrundkörper",
    "### Phase 3 — Reale Vertikalprobe",
    "### Phase 4 — Digitale Sphäre und Hybridität",
    "### Phase 5 — Katalogwachstum",
    "### Phase 6 — Weltgewebe-Übergang",
    "Der Globus liefert den Überblick. Der Zoom liefert Genauigkeit.",
)

FORBIDDEN_ACTIVE_PATHS = (
    "proofs",
    "examples",
    ".github/workflows/claude.yml",
    "contracts/commonworld/aspect.schema.json",
    "contracts/commonworld/catalog-api.contract.json",
    "contracts/commonworld/catalog-export.schema.json",
    "contracts/commonworld/search-index-input.contract.json",
    "docs/blueprints/commonworld-experience-doctrine.md",
    "docs/blueprints/mobile-atlas-shift-interaction-model.md",
    "docs/blueprints/commonproject-projection-contract.md",
    "docs/blueprints/catalog-api-contract.md",
    "docs/blueprints/search-index-input-contract.md",
    "scripts/validate_aether_proof.py",
    "scripts/validate_proof_hub.py",
    "scripts/smoke_map_proof_browser.py",
    "scripts/generate_catalog_export.py",
)

FORBIDDEN_CONTRACT_PROPERTIES = (
    "aspects",
    "projections",
    "search_document",
    "marker_style",
    "animation",
    "zoom_level",
)

EXPECTED_BLUEPRINT_FILES = {"commonworld-masterplan.md"}
EXPECTED_OPS_FILES = {"pages-dns.md"}
EXPECTED_CONTRACT_FILES = {"aggregation-zoom.contract.json", "project.schema.json", "visual-semantics.contract.json"}
EXPECTED_SCRIPT_FILES = {
    "__init__.py",
    "check_pages_dns_target.py",
    "smoke_pages_live.py",
    "validate_canonical_plan.py",
    "validate_contracts.py",
    "validate_public_shell.py",
    "validate_semantic_zoom.py",
    "validate_visual_semantics.py",
}
EXPECTED_TEST_FILES = {
    "test_canonical_plan.py",
    "test_contracts.py",
    "test_pages_dns_target.py",
    "test_pages_live_smoke.py",
    "test_public_shell.py",
    "test_semantic_zoom.py",
    "test_visual_semantics.py",
}
EXPECTED_WORKFLOW_FILES = {"validate.yml"}


def validate_canonical_plan(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    plan = root / PLAN.relative_to(ROOT)
    if not plan.is_file():
        return ["missing canonical globe plan"]

    text = plan.read_text(encoding="utf-8")
    for token in REQUIRED_PLAN_TOKENS:
        if token not in text:
            errors.append(f"canonical globe plan missing required token: {token}")

    controlled_directories = (
        (root / "docs" / "blueprints", EXPECTED_BLUEPRINT_FILES, "blueprint"),
        (root / "docs" / "ops", EXPECTED_OPS_FILES, "ops"),
        (root / "contracts" / "commonworld", EXPECTED_CONTRACT_FILES, "contract"),
        (root / "scripts", EXPECTED_SCRIPT_FILES, "script"),
        (root / "tests", EXPECTED_TEST_FILES, "test"),
        (root / ".github" / "workflows", EXPECTED_WORKFLOW_FILES, "workflow"),
    )
    for directory, expected, label in controlled_directories:
        actual = {path.name for path in directory.iterdir() if path.is_file()} if directory.is_dir() else set()
        if actual != expected:
            errors.append(f"active {label} inventory mismatch: expected {sorted(expected)}, got {sorted(actual)}")

    for relative in FORBIDDEN_ACTIVE_PATHS:
        if (root / relative).exists():
            errors.append(f"obsolete active path must be removed: {relative}")

    for file_name in ("README.md", "AGENTS.md"):
        path = root / file_name
        if not path.is_file():
            errors.append(f"missing repository alignment file: {file_name}")
            continue
        file_text = path.read_text(encoding="utf-8")
        if "docs/blueprints/commonworld-masterplan.md" not in file_text:
            errors.append(f"{file_name} must point to the canonical globe plan")

    schema_path = root / "contracts" / "commonworld" / "project.schema.json"
    if not schema_path.is_file():
        errors.append("missing canonical CommonProject schema")
    else:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"CommonProject schema is invalid JSON: {error}")
        else:
            properties = schema.get("properties", {})
            for name in FORBIDDEN_CONTRACT_PROPERTIES:
                if name in properties:
                    errors.append(f"CommonProject schema must not contain presentation property: {name}")
            if properties.get("schema_version", {}).get("const") != 3:
                errors.append("CommonProject schema_version must be 3")

    requirements = (root / "requirements-dev.txt").read_text(encoding="utf-8") if (root / "requirements-dev.txt").is_file() else ""
    if "playwright" in requirements.casefold():
        errors.append("Playwright dependency must not remain after proof reset")

    workflow = root / ".github" / "workflows" / "validate.yml"
    if workflow.is_file() and "playwright" in workflow.read_text(encoding="utf-8").casefold():
        errors.append("validation workflow must not install or run Playwright after proof reset")

    return errors


def main() -> int:
    errors = validate_canonical_plan(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld canonical globe plan validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
