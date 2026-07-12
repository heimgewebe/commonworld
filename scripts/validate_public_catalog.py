#!/usr/bin/env python3
"""Validate the public Commonworld seed catalog and its linear shell projection."""

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

from scripts.validate_contracts import validation_errors

CATALOG_PATH = Path("catalog/catalog.json")
PROJECT_DIRECTORY = Path("catalog/projects")
DIGITAL_CONTRACT_PATH = Path("contracts/commonworld/digital-sphere.contract.json")
PUBLIC_STATES = {"listed"}
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


def validate_public_catalog(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / CATALOG_PATH
    project_directory = root / PROJECT_DIRECTORY
    contract_path = root / DIGITAL_CONTRACT_PATH
    shell_path = root / "index.html"

    for path, label in (
        (manifest_path, "public catalog manifest"),
        (contract_path, "digital sphere contract"),
        (shell_path, "public shell"),
    ):
        if not path.is_file():
            errors.append(f"missing {label}: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        manifest = _load_json(manifest_path)
        contract = _load_json(contract_path)
    except (json.JSONDecodeError, OSError) as error:
        return [f"public catalog control file is invalid: {error}"]

    expected_publication = {
        "public": True,
        "source_policy": "official-sources-only",
        "curation_state": "listed",
        "engine_selected": True,
        "selected_engine": "maplibre_gl_js",
        "production_architecture_authorized": False,
        "public_runtime_uses_selected_engine": False,
    }
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "commonworld_public_catalog":
        errors.append("public catalog manifest schema or kind mismatch")
    if manifest.get("language") != "de":
        errors.append("public catalog language must be de")
    if manifest.get("publication") != expected_publication:
        errors.append("public catalog publication boundary mismatch")

    try:
        published_at = date.fromisoformat(manifest["published_at"])
    except (KeyError, TypeError, ValueError):
        published_at = None
        errors.append("public catalog published_at must be an ISO date")

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
    if not 8 <= len(normalized_files) <= 12:
        errors.append("public seed catalog must contain between 8 and 12 projects")
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
    layer_ids: list[str] = []
    record_layers: dict[str, str] = {}
    layer_labels = {
        entry.get("id"): entry.get("label_de")
        for entry in contract.get("layer_model", {}).get("layers", [])
    }
    expected_layers = set(contract.get("layer_model", {}).get("order", []))

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

        if record.get("kind") != "digital":
            errors.append(f"public seed project {relative.name} must be digital")
        presence = record.get("presence", {})
        if not isinstance(presence, dict):
            presence = {}
        digital = presence.get("digital", {})
        if not isinstance(digital, dict):
            digital = {}
        if presence.get("geographic") != []:
            errors.append(f"digital public seed project {relative.name} must not contain geographic locations")
        if digital.get("available") is not True:
            errors.append(f"public seed project {relative.name} must have an available digital presence")
        if any(key in record for key in ("layer", "derived_layer", "presentation_layer")):
            errors.append(f"public seed project {relative.name} must not store a presentation layer")
        if record.get("relations") not in (None, []):
            errors.append(f"public seed project {relative.name} must not publish unreviewed relations")
        if record.get("handoff") != {"enabled": False}:
            errors.append(f"public seed project {relative.name} must keep Weltgewebe handoff disabled")

        curation = record.get("curation", {})
        if not isinstance(curation, dict):
            curation = {}
        if curation.get("state") not in PUBLIC_STATES:
            errors.append(f"public seed project {relative.name} must be explicitly listed")
        if curation.get("reviewed_by") != "Commonworld editorial review":
            errors.append(f"public seed project {relative.name} must name the editorial reviewer")
        try:
            reviewed_at = date.fromisoformat(curation["reviewed_at"])
            next_review_at = date.fromisoformat(curation["next_review_at"])
            if published_at and reviewed_at != published_at:
                errors.append(f"public seed project {relative.name} review date must equal catalog publication date")
            if next_review_at <= reviewed_at:
                errors.append(f"public seed project {relative.name} next review must follow editorial review")
        except (KeyError, TypeError, ValueError):
            errors.append(f"public seed project {relative.name} has invalid curation dates")

        activity = record.get("activity", {})
        if not isinstance(activity, dict):
            activity = {}
        if activity.get("status") != "active":
            errors.append(f"public seed project {relative.name} must have directly observed active status")
        try:
            observed_at = date.fromisoformat(activity["observed_at"])
            if published_at and observed_at != published_at:
                errors.append(f"public seed project {relative.name} activity observation must equal publication date")
        except (KeyError, TypeError, ValueError):
            errors.append(f"public seed project {relative.name} has invalid activity date")

        provenance = record.get("provenance", {})
        if not isinstance(provenance, dict):
            provenance = {}
        sources = provenance.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        if not sources:
            errors.append(f"public seed project {relative.name} must include provenance")
        for source in sources:
            if not isinstance(source, dict):
                errors.append(f"public seed project {relative.name} contains a malformed source")
                continue
            if source.get("type") != "official-source":
                errors.append(f"public seed project {relative.name} must use official sources only")
            if not _is_https_url(source.get("url")):
                errors.append(f"public seed project {relative.name} source URL must use HTTPS")
            try:
                retrieved_at = date.fromisoformat(source["retrieved_at"])
                if published_at and retrieved_at != published_at:
                    errors.append(f"public seed project {relative.name} source retrieval must equal publication date")
            except (KeyError, TypeError, ValueError):
                errors.append(f"public seed project {relative.name} has invalid source retrieval date")

        homepage = _homepage(record)
        if homepage is None or not _is_https_url(homepage):
            errors.append(f"public seed project {relative.name} must have exactly one HTTPS homepage")

        searchable_text = json.dumps(record, ensure_ascii=False).casefold()
        for forbidden in FORBIDDEN_PUBLIC_TEXT:
            if forbidden in searchable_text:
                errors.append(f"public seed project {relative.name} contains test-only language: {forbidden}")

        layer = derive_digital_layer(record, contract)
        if layer is None:
            errors.append(f"public seed project {relative.name} has no derived digital layer")
        else:
            layer_ids.append(layer)
            if isinstance(identifier, str):
                record_layers[identifier] = layer

    if len(identifiers) != len(set(identifiers)):
        errors.append("public catalog CommonProject ids must be unique")
    if len(titles) != len(set(titles)):
        errors.append("public catalog titles must be unique")
    if set(layer_ids) != expected_layers:
        errors.append(
            f"public seed catalog must cover every digital presentation layer: expected {sorted(expected_layers)}, got {sorted(set(layer_ids))}"
        )

    shell = shell_path.read_text(encoding="utf-8")
    cards = CARD_PATTERN.findall(shell)
    card_ids = [identifier for identifier, _body in cards]
    card_bodies = {identifier: body for identifier, body in cards}
    if sorted(card_ids) != sorted(identifiers) or len(card_ids) != len(set(card_ids)):
        errors.append("public shell card identities must match the public catalog exactly once")
    if './catalog/catalog.json' not in shell:
        errors.append("public shell must link to the canonical public catalog manifest")
    for record in records:
        identifier = record.get("id")
        title = record.get("title")
        summary = record.get("summary")
        homepage = _homepage(record)
        if not all(isinstance(value, str) for value in (identifier, title, summary, homepage)):
            continue
        card = card_bodies.get(identifier, "")
        layer = record_layers.get(identifier)
        layer_label = layer_labels.get(layer)
        expected_values = [
            (html.escape(title), "title"),
            (html.escape(summary), "summary"),
            (f'href="{html.escape(homepage, quote=True)}"', "homepage"),
        ]
        if isinstance(layer_label, str):
            expected_values.append((f"Digital · {html.escape(layer_label)}", "derived German layer label"))
        for value, label in expected_values:
            if value not in card:
                errors.append(f"public shell is missing {label} for {identifier}")

    return errors


def main() -> int:
    errors = validate_public_catalog(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld public seed catalog validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
