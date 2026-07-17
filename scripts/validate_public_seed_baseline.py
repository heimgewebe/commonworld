#!/usr/bin/env python3
"""Preserve the historical ten-project digital seed catalog as a scoped regression baseline."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_public_catalog import _is_https_url, derive_digital_layer

MANIFEST_PATH = Path("catalog/catalog.json")
CONTRACT_PATH = Path("contracts/commonworld/digital-sphere.contract.json")
EXPECTED_SEED_IDS = [
    "debian",
    "freifunk",
    "libreoffice",
    "mastodon",
    "openstreetmap",
    "wikibooks",
    "wikidata",
    "wikimedia-commons",
    "wikipedia",
    "wikiversity",
]
EXPECTED_SEED_DATE = date(2026, 7, 12)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parsed(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_public_seed_baseline(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / MANIFEST_PATH
    contract_path = root / CONTRACT_PATH
    if not manifest_path.is_file():
        return ["missing public catalog manifest"]
    if not contract_path.is_file():
        return ["missing digital sphere contract"]
    try:
        manifest = _load(manifest_path)
        contract = _load(contract_path)
    except (OSError, json.JSONDecodeError) as error:
        return [f"public seed control file is invalid: {error}"]

    baseline = manifest.get("seed_baseline")
    if baseline != {"published_at": "2026-07-12", "project_ids": EXPECTED_SEED_IDS}:
        errors.append("public seed baseline declaration mismatch")

    layers: list[str] = []
    expected_layers = set(contract.get("layer_model", {}).get("order", []))
    for identifier in EXPECTED_SEED_IDS:
        path = root / "catalog" / "projects" / f"{identifier}.json"
        if not path.is_file():
            errors.append(f"public seed project missing: {identifier}")
            continue
        try:
            record = _load(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"public seed project {identifier} is invalid JSON: {error}")
            continue
        if record.get("id") != identifier:
            errors.append(f"public seed project file must retain identity: {identifier}")

        presence = record.get("presence", {}) if isinstance(record.get("presence"), dict) else {}
        digital = presence.get("digital", {}) if isinstance(presence.get("digital"), dict) else {}
        if presence.get("geographic") != []:
            errors.append(f"public seed project {identifier} must remain without geographic locations")
        if digital.get("available") is not True:
            errors.append(f"public seed project {identifier} must retain available digital presence")
        if record.get("relations") not in (None, []):
            errors.append(f"public seed project {identifier} must remain relation-free")
        if record.get("handoff") != {"enabled": False}:
            errors.append(f"public seed project {identifier} must keep Weltgewebe handoff disabled")
        if any(key in record for key in ("layer", "derived_layer", "presentation_layer", "semantic_zoom")):
            errors.append(f"public seed project {identifier} must not store presentation or zoom assignments")

        curation = record.get("curation", {}) if isinstance(record.get("curation"), dict) else {}
        if curation.get("state") != "listed" or curation.get("reviewed_by") != "Commonworld editorial review":
            errors.append(f"public seed project {identifier} must retain its editorial listing")
        if _parsed(curation.get("reviewed_at")) != EXPECTED_SEED_DATE:
            errors.append(f"public seed project {identifier} review date drifted")
        next_review = _parsed(curation.get("next_review_at"))
        if next_review is None or next_review <= EXPECTED_SEED_DATE:
            errors.append(f"public seed project {identifier} next review is invalid")

        activity = record.get("activity", {}) if isinstance(record.get("activity"), dict) else {}
        if activity.get("status") != "active" or _parsed(activity.get("observed_at")) != EXPECTED_SEED_DATE:
            errors.append(f"public seed project {identifier} activity baseline drifted")

        sources = record.get("provenance", {}).get("sources", []) if isinstance(record.get("provenance"), dict) else []
        if not isinstance(sources, list) or not sources:
            errors.append(f"public seed project {identifier} must retain provenance")
        else:
            for source in sources:
                if not isinstance(source, dict) or source.get("type") != "official-source":
                    errors.append(f"public seed project {identifier} must retain official-source provenance")
                    continue
                if not _is_https_url(source.get("url")):
                    errors.append(f"public seed project {identifier} source URL must remain HTTPS")
                if _parsed(source.get("retrieved_at")) != EXPECTED_SEED_DATE:
                    errors.append(f"public seed project {identifier} source retrieval date drifted")

        layer = derive_digital_layer(record, contract)
        if layer is None:
            errors.append(f"public seed project {identifier} lost its derived digital layer")
        else:
            layers.append(layer)

    if set(layers) != expected_layers:
        errors.append(
            f"public seed baseline must retain every digital presentation layer: expected {sorted(expected_layers)}, got {sorted(set(layers))}"
        )
    return errors


def main() -> int:
    errors = validate_public_seed_baseline(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld digital seed baseline validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
