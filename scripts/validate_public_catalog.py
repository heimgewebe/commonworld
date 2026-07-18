#!/usr/bin/env python3
"""Validate the scalable public Commonworld catalog and its text projections."""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_public_shell import public_locations
from scripts.digital_taxonomy import derive_project_path, load_taxonomy, path_label
from scripts.validate_contracts import validation_errors

CATALOG_PATH = Path("catalog/catalog.json")
PROJECT_DIRECTORY = Path("catalog/projects")
DIGITAL_RING_CONTRACT_PATH = Path("contracts/commonworld/digital-ring-taxonomy.contract.json")
PUBLIC_STATES = {"listed", "verified", "featured"}
PUBLIC_ACTIVITY_STATES = {"active", "paused", "seasonal"}
PUBLIC_SOURCE_TYPES = {"official-source", "public-registry"}
ACTION_LINK_TYPES = {"visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"}
FORBIDDEN_PUBLIC_TEXT = ("reference-only", "test-only", "synthetic", "acceptance-only")
CARD_PATTERN = re.compile(
    r'<article class="catalog-card"[^>]*data-commonproject-id="([a-z][a-z0-9-]{2,95})"[^>]*>(.*?)</article>',
    re.DOTALL,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _safe_project_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        return None
    if len(path.parts) != 2 or path.parts[0] != "projects":
        return None
    return path


def derive_digital_layer(record: dict, contract: dict) -> str | None:
    presence = record.get("presence", {})
    if not isinstance(presence, dict):
        return None
    digital = presence.get("digital", {})
    if not isinstance(digital, dict) or digital.get("available") is not True:
        return None
    raw_themes = record.get("themes", [])
    themes = set(raw_themes) if isinstance(raw_themes, list) else set()
    layers = [entry for entry in contract.get("layer_model", {}).get("layers", []) if entry.get("id") != "mixed_other"]
    scores = [(entry.get("id"), len(themes.intersection(entry.get("derived_from", [])))) for entry in layers]
    maximum = max((score for _, score in scores), default=0)
    winners = [identifier for identifier, score in scores if score == maximum and score > 0]
    return winners[0] if len(winners) == 1 else "mixed_other"


def _homepage(record: dict) -> str | None:
    links = record.get("links", [])
    if not isinstance(links, list):
        return None
    homepages = [
        link.get("url")
        for link in links
        if isinstance(link, dict) and link.get("type") == "homepage"
    ]
    return homepages[0] if len(homepages) == 1 and isinstance(homepages[0], str) else None


def _card_label(record: dict, taxonomy: dict) -> str:
    has_geo = bool(public_locations(record))
    has_dig = record.get("presence", {}).get("digital", {}).get("available", False)

    if has_geo and not has_dig:
        return "Vor Ort"
    if not has_geo and not has_dig:
        return "Commons"
    derived = derive_project_path(record, taxonomy)
    label = path_label(derived["path"], taxonomy) if derived else "Digitale Commons"
    if has_geo and has_dig:
        return f"Vor Ort · Digital · {label}"
    return f"Digital · {label}"


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_public_catalog(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / CATALOG_PATH
    project_directory = root / PROJECT_DIRECTORY
    contract_path = root / DIGITAL_RING_CONTRACT_PATH
    shell_path = root / "index.html"

    for path, label in (
        (manifest_path, "public catalog manifest"),
        (contract_path, "digital ring taxonomy contract"),
        (shell_path, "public shell"),
    ):
        if not path.is_file():
            errors.append(f"missing {label}: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        manifest = _load_json(manifest_path)
        contract = load_taxonomy(root)
    except (json.JSONDecodeError, OSError) as error:
        return [f"public catalog control file is invalid: {error}"]

    expected_publication = {
        "public": True,
        "source_policy": "official-and-public-registry-sources",
        "curation_state": "listed",
        "engine_selected": True,
        "production_architecture_authorized": True,
        "selected_engine": "maplibre_gl_js",
        "public_runtime_uses_selected_engine": True,
        "production_delivery": "github_pages_static",
        "basemap_provider_boundary": "openfreemap_public_best_effort_noncritical",
    }
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "commonworld_public_catalog":
        errors.append("public catalog manifest schema or kind mismatch")
    if manifest.get("language") != "de":
        errors.append("public catalog language must be de")
    if manifest.get("catalog_profile") != "curated-public-mixed-presence-v1":
        errors.append("public catalog profile must allow curated mixed presence")
    if manifest.get("publication") != expected_publication:
        errors.append("public catalog publication boundary mismatch")
    expected_machine_surface = {
        "access": "static_read_only",
        "manifest": "catalog/catalog.json",
        "project_base": "catalog/projects/",
        "project_schema": "contracts/commonworld/project.schema.json",
        "identity_field": "CommonProject.id",
        "api_runtime": False,
        "write_path": False,
        "standalone_cli": False,
    }
    if manifest.get("machine_surface") != expected_machine_surface:
        errors.append("public catalog machine-readable surface boundary mismatch")

    published_at = _parse_date(manifest.get("published_at"))
    if published_at is None:
        errors.append("public catalog published_at must be an ISO date")

    seed_baseline = manifest.get("seed_baseline")
    if not isinstance(seed_baseline, dict):
        errors.append("public catalog must declare its preserved seed baseline")
    else:
        seed_ids = seed_baseline.get("project_ids")
        if not isinstance(seed_ids, list) or seed_ids != sorted(seed_ids) or len(seed_ids) != len(set(seed_ids)):
            errors.append("public catalog seed baseline project_ids must be a sorted unique list")
        if _parse_date(seed_baseline.get("published_at")) is None:
            errors.append("public catalog seed baseline published_at must be an ISO date")

    raw_files = manifest.get("project_files")
    if not isinstance(raw_files, list):
        raw_files = []
        errors.append("public catalog project_files must be a list")
    safe_files: list[PurePosixPath] = []
    for value in raw_files:
        safe = _safe_project_path(value)
        if safe is None:
            errors.append(f"public catalog project path is unsafe or malformed: {value!r}")
        else:
            safe_files.append(safe)
    normalized_files = [path.as_posix() for path in safe_files]
    if normalized_files != sorted(normalized_files):
        errors.append("public catalog project_files must be sorted")
    if len(normalized_files) != len(set(normalized_files)):
        errors.append("public catalog project_files must be unique")
    if not 1 <= len(normalized_files) <= 10000:
        errors.append("public catalog must contain between 1 and 10000 projects")
    if manifest.get("entry_count") != len(normalized_files):
        errors.append("public catalog entry_count must match project_files")

    actual_files = (
        sorted(path.relative_to(root / "catalog").as_posix() for path in project_directory.glob("*.json"))
        if project_directory.is_dir()
        else []
    )
    if normalized_files != actual_files:
        errors.append("public catalog manifest and project file inventory differ")

    records: list[dict] = []
    identifiers: list[str] = []
    titles: list[str] = []
    for relative in safe_files:
        path = root / "catalog" / Path(*relative.parts)
        if not path.is_file():
            errors.append(f"public catalog project file missing: {relative.as_posix()}")
            continue
        try:
            record = _load_json(path)
        except (json.JSONDecodeError, OSError) as error:
            errors.append(f"public catalog project {relative.name} is invalid JSON: {error}")
            continue
        if not isinstance(record, dict):
            errors.append(f"public catalog project {relative.name} must contain a JSON object")
            continue
        records.append(record)
        identifier = record.get("id")
        title = record.get("title")
        if identifier != relative.stem:
            errors.append(f"public catalog file {relative.name} must match CommonProject.id")
        if isinstance(identifier, str):
            identifiers.append(identifier)
        if isinstance(title, str):
            titles.append(title)

        for message in validation_errors(record, root):
            errors.append(f"public catalog project {relative.name} invalid: {message}")


        if any(key in record for key in ("layer", "derived_layer", "presentation_layer", "semantic_zoom", "digital_path")):
            errors.append(f"public catalog project {relative.name} must not store presentation or zoom assignments")

        curation = record.get("curation", {}) if isinstance(record.get("curation"), dict) else {}
        if curation.get("state") not in PUBLIC_STATES:
            errors.append(f"public catalog project {relative.name} must be in a public curation state")
        if curation.get("reviewed_by") != "Commonworld editorial review":
            errors.append(f"public catalog project {relative.name} must name the editorial reviewer")
        reviewed_at = _parse_date(curation.get("reviewed_at"))
        next_review_at = _parse_date(curation.get("next_review_at"))
        if reviewed_at is None or next_review_at is None:
            errors.append(f"public catalog project {relative.name} has invalid curation dates")
        else:
            if next_review_at <= reviewed_at:
                errors.append(f"public catalog project {relative.name} next review must follow editorial review")
            if published_at and reviewed_at > published_at:
                errors.append(f"public catalog project {relative.name} review date must not be after catalog publication")

        activity = record.get("activity", {}) if isinstance(record.get("activity"), dict) else {}
        if activity.get("status") not in PUBLIC_ACTIVITY_STATES:
            errors.append(f"public catalog project {relative.name} must have a publishable observed activity state")
        observed_at = _parse_date(activity.get("observed_at"))
        if observed_at is None:
            errors.append(f"public catalog project {relative.name} has invalid activity date")
        elif published_at and observed_at > published_at:
            errors.append(f"public catalog project {relative.name} activity observation must not be after catalog publication")

        provenance = record.get("provenance", {}) if isinstance(record.get("provenance"), dict) else {}
        sources = provenance.get("sources", []) if isinstance(provenance.get("sources"), list) else []
        if not sources:
            errors.append(f"public catalog project {relative.name} must include provenance")
        for source in sources:
            if not isinstance(source, dict):
                errors.append(f"public catalog project {relative.name} contains a malformed source")
                continue
            if source.get("type") not in PUBLIC_SOURCE_TYPES:
                errors.append(f"public catalog project {relative.name} must use official or public-registry sources")
            if not _is_https_url(source.get("url")):
                errors.append(f"public catalog project {relative.name} source URL must use HTTPS")
            retrieved_at = _parse_date(source.get("retrieved_at"))
            if retrieved_at is None:
                errors.append(f"public catalog project {relative.name} has invalid source retrieval date")
            elif published_at and retrieved_at > published_at:
                errors.append(f"public catalog project {relative.name} source retrieval must not be after catalog publication")

        source_ids = {
            source.get("id")
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("id"), str)
        }
        actions = record.get("actions", []) if isinstance(record.get("actions"), list) else []
        action_set = {action for action in actions if isinstance(action, str)}
        links = record.get("links", []) if isinstance(record.get("links"), list) else []
        action_links: dict[str, list[dict]] = {}
        for link_entry in links:
            if not isinstance(link_entry, dict):
                continue
            link_type = link_entry.get("type")
            if link_type not in ACTION_LINK_TYPES:
                continue
            action_links.setdefault(link_type, []).append(link_entry)
            if link_type not in action_set:
                errors.append(
                    f"public catalog project {relative.name} publishes action link {link_type} without claiming that action"
                )
            if not _is_https_url(link_entry.get("url")):
                errors.append(f"public catalog project {relative.name} action link {link_type} must use HTTPS")
            link_source_ids = link_entry.get("source_ids")
            if not isinstance(link_source_ids, list) or not link_source_ids:
                errors.append(
                    f"public catalog project {relative.name} action link {link_type} must be source-bound"
                )
            elif not set(link_source_ids).issubset(source_ids):
                errors.append(
                    f"public catalog project {relative.name} action link {link_type} references unknown sources"
                )
        for action in sorted(action_set):
            matching_links = action_links.get(action, [])
            if len(matching_links) != 1:
                errors.append(
                    f"public catalog project {relative.name} action {action} must have exactly one direct action link"
                )

        for evidence_name in ("languages", "access"):
            evidence = record.get(evidence_name)
            if evidence is None:
                continue
            evidence_source_ids = evidence.get("source_ids") if isinstance(evidence, dict) else None
            if not isinstance(evidence_source_ids, list) or not evidence_source_ids:
                errors.append(
                    f"public catalog project {relative.name} {evidence_name} evidence must be source-bound"
                )
            elif not set(evidence_source_ids).issubset(source_ids):
                errors.append(
                    f"public catalog project {relative.name} {evidence_name} evidence references unknown sources"
                )

        homepage = _homepage(record)
        if homepage is None or not _is_https_url(homepage):
            errors.append(f"public catalog project {relative.name} must have exactly one HTTPS homepage")

        searchable_text = json.dumps(record, ensure_ascii=False).casefold()
        for forbidden in FORBIDDEN_PUBLIC_TEXT:
            if forbidden in searchable_text:
                errors.append(f"public catalog project {relative.name} contains test-only language: {forbidden}")

    if len(identifiers) != len(set(identifiers)):
        errors.append("public catalog CommonProject ids must be unique")
    if len(titles) != len(set(titles)):
        errors.append("public catalog titles must be unique")

    known_ids = set(identifiers)
    for record in records:
        for relation in record.get("relations", []) if isinstance(record.get("relations"), list) else []:
            target_id = relation.get("target_id") if isinstance(relation, dict) else None
            if target_id not in known_ids:
                errors.append(f"public catalog project {record.get('id')} relation target is not a published CommonProject: {target_id}")
            if target_id == record.get("id"):
                errors.append(f"public catalog project {record.get('id')} must not relate to itself")

    if isinstance(seed_baseline, dict) and isinstance(seed_baseline.get("project_ids"), list):
        missing_seed = sorted(set(seed_baseline["project_ids"]) - known_ids)
        if missing_seed:
            errors.append(f"public catalog is missing preserved seed identities: {missing_seed}")

    shell = shell_path.read_text(encoding="utf-8")
    cards = CARD_PATTERN.findall(shell)
    card_ids = [identifier for identifier, _body in cards]
    card_bodies: dict[str, list[str]] = {}
    for identifier, body in cards:
        card_bodies.setdefault(identifier, []).append(body)
    if sorted(card_ids) != sorted(identifiers + identifiers) or any(card_ids.count(identifier) != 2 for identifier in identifiers):
        errors.append("public shell card identities must match the public catalog once in Text and once in the no-JavaScript fallback")
    if './catalog/catalog.json' not in shell:
        errors.append("public shell must link to the canonical public catalog manifest")
    if './contracts/commonworld/project.schema.json' not in shell:
        errors.append("public shell must link to the CommonProject schema")
    for record in records:
        identifier = record.get("id")
        title = record.get("title")
        summary = record.get("summary")
        homepage = _homepage(record)
        if not all(isinstance(value, str) for value in (identifier, title, summary, homepage)):
            continue
        bodies = card_bodies.get(identifier, [])
        expected_values = [
            (html.escape(title), "title"),
            (html.escape(summary), "summary"),
            (f'href="{html.escape(homepage, quote=True)}"', "homepage"),
            (html.escape(_card_label(record, contract)), "derived German presentation label"),
        ]
        for value, label in expected_values:
            if not bodies or any(value not in body for body in bodies):
                errors.append(f"public shell is missing {label} for {identifier} in at least one text projection")

    return errors


def main() -> int:
    errors = validate_public_catalog(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld scalable public catalog validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
