#!/usr/bin/env python3
"""Validate the commonworld-to-weltgewebe handoff doctrine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "blueprints" / "weltgewebe-handoff-contract.md"
PROJECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"


def validate_weltgewebe_handoff_contract(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    doc_path = root / DOC_PATH.relative_to(ROOT)
    schema_path = root / PROJECT_SCHEMA_PATH.relative_to(ROOT)

    if not doc_path.is_file():
        return ["missing weltgewebe handoff contract doc"]
    if not schema_path.is_file():
        return ["missing CommonProject schema"]

    text = doc_path.read_text(encoding="utf-8")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    handoff = schema.get("$defs", {}).get("handoff", {})

    required_doc_tokens = (
        "COMMONWORLD-ATLAS-V1-T008",
        "static/read-only",
        "no implicit auth sharing",
        "no weltgewebe write path",
        "Disabled handoffs must not expose `project_id`, `url` or `action_label`",
        "Enabled handoffs require `system: weltgewebe`",
        "Enabled handoffs require a concrete `project_id`",
        "Enabled handoffs require a concrete `url`",
        "Enabled handoffs require `curation.state: curated`",
        "Archived entries must not expose enabled handoffs",
        "Fixture and candidate entries must not expose enabled handoffs",
        "Handoff labels must stay neutral until authorization is modeled",
        "join",
        "coordinate",
        "manage",
        "decide",
        "administer",
        "submit",
    )
    for token in required_doc_tokens:
        if token not in text:
            errors.append(f"weltgewebe handoff contract missing doctrine token: {token}")

    enabled_requirements: set[str] = set()
    for branch in handoff.get("allOf", []):
        if branch.get("if", {}).get("properties", {}).get("enabled", {}).get("const") is True:
            enabled_requirements.update(branch.get("then", {}).get("required", []))

    for key in ("system", "project_id", "action_label", "url"):
        if key not in enabled_requirements:
            errors.append(f"enabled handoff schema must require {key}")

    system_enum = handoff.get("properties", {}).get("system", {}).get("enum", [])
    if system_enum != ["weltgewebe"]:
        errors.append("handoff system enum must be exactly ['weltgewebe']")

    return errors


def main() -> int:
    errors = validate_weltgewebe_handoff_contract(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld weltgewebe handoff contract validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
