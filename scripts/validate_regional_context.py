#!/usr/bin/env python3
"""Validate source-bound non-geometric public contexts independently of hidden geography."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
INDEX = Path("catalog/regional-contexts.v1.json")
SCHEMA = Path("contracts/commonworld/regional-context.schema.json")
CATALOG = Path("catalog/catalog.json")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def project_index(root: Path) -> dict[str, dict]:
    manifest = read_json(root / CATALOG)
    return {
        project["id"]: project
        for filename in manifest["project_files"]
        for project in [read_json(root / "catalog" / filename)]
    }


def validation_errors(
    contexts: dict,
    projects: dict[str, dict],
    schema: dict,
    *,
    current_date: date | None = None,
) -> list[str]:
    """Return explicit errors without creating inferred coordinates or release data."""
    current_date = current_date or date.today()
    errors = []
    for failure in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contexts):
        location = "/".join(map(str, failure.absolute_path)) or "root"
        errors.append(f"schema {location}: {failure.message}")

    # Do not turn schema-broken data into synthetic representations.
    if errors:
        return sorted(errors)

    seen_ids = set()
    seen_pairs = set()
    seen_view_ids = set()
    for entry in contexts["contexts"]:
        context_id = entry["id"]
        project_id = entry["project_id"]
        reference = entry["reference"]
        if context_id in seen_ids:
            errors.append(f"{context_id}: duplicate context id")
        seen_ids.add(context_id)
        pair = (project_id, reference["id"])
        if pair in seen_pairs:
            errors.append(f"{context_id}: duplicate project/reference relationship")
        seen_pairs.add(pair)

        project = projects.get(project_id)
        if project is None:
            errors.append(f"{context_id}: unknown canonical project {project_id}")
            continue

        # A public context must be independently sourced to a published project.
        # Hidden geographic labels and privacy notes have no source authority.
        sources = {s["id"]: s for s in project.get("provenance", {}).get("sources", [])}
        for source_id in entry["source_ids"]:
            source = sources.get(source_id)
            if source is None:
                errors.append(f"{context_id}: unknown official source {source_id}")
            elif source.get("type") != "official-source":
                errors.append(f"{context_id}: source is not official {source_id}")
            elif urlsplit(str(source.get("url", ""))).scheme != "https":
                errors.append(f"{context_id}: official source URL is not HTTPS {source_id}")
        try:
            reviewed_at = date.fromisoformat(entry["source_reviewed_at"])
        except ValueError:
            errors.append(f"{context_id}: invalid source review date")
        else:
            if reviewed_at > current_date:
                errors.append(f"{context_id}: source reviewed in the future")

        for view in entry.get("navigation_views", []):
            view_id = view["id"]
            if view_id in seen_view_ids:
                errors.append(f"{context_id}: duplicate orientation view id {view_id}")
            seen_view_ids.add(view_id)
            west, south, east, north = view["view_bounds"]
            if not (west < east and south < north):
                errors.append(f"{context_id}: invalid orientation viewport {view_id}")
            if not set(view["association_source_ids"]).issubset(entry["source_ids"]):
                errors.append(f"{context_id}: unbound orientation association source {view_id}")
            if not urlsplit(view["source_url"]).netloc:
                errors.append(f"{context_id}: invalid geographic reference URL {view_id}")
            if date.fromisoformat(view["reviewed_at"]) > current_date:
                errors.append(f"{context_id}: orientation reference reviewed in the future {view_id}")

        # No context can substitute a map representation for a hidden location.
        # We never read or export hidden geometry, members or endpoints here.
        if entry["coverage_claim"] != "none":
            errors.append(f"{context_id}: regional association is not an extent")
    return sorted(errors)


def main() -> int:
    root = ROOT
    errors = validation_errors(
        read_json(root / INDEX),
        project_index(root),
        read_json(root / SCHEMA),
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld public regional-context pilot valid: source-bound, non-geometric")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
