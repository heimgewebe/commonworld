#!/usr/bin/env python3
"""Deterministic schema-realistic catalogue fixtures for Commonworld scale gates.

The 1k and 10k fixtures are derived from the current canonical catalogue. They
remain measurement fixtures, not public catalogue entries: no generated project
is written below ``catalog/projects`` and no cutover authority follows from
these artifacts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_contracts import validation_errors

CATALOG_PATH = Path("catalog/catalog.json")
ENGLISH_OVERLAY_PATH = Path("catalog/locales/en.json")
CURRENT_SHARD_PREFIX_LENGTH = 2
SPATIAL_CELL_DEGREES = 10
DETAIL_DESCRIPTOR_VERSION = "1.0"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed_project_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ValueError("canonical project path must be a string")
    path = Path(relative)
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "projects" or path.suffix != ".json":
        raise ValueError(f"canonical project path must be a direct catalog/projects JSON file: {relative}")
    project_root = (root / "catalog" / "projects").resolve()
    candidate = (root / "catalog" / path).resolve()
    if candidate.parent != project_root:
        raise ValueError(f"canonical project path escapes catalog/projects: {relative}")
    return candidate


def load_seed_records(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / CATALOG_PATH).read_text(encoding="utf-8"))
    project_files = manifest.get("project_files") if isinstance(manifest, dict) else None
    if not isinstance(project_files, list) or not project_files:
        raise ValueError("canonical catalogue project_files must be a non-empty list")
    if len(set(project_files)) != len(project_files):
        raise ValueError("canonical catalogue project paths must be unique")
    records = [
        json.loads(seed_project_path(root, relative).read_text(encoding="utf-8"))
        for relative in project_files
    ]
    if any(not isinstance(record, dict) or not isinstance(record.get("id"), str) for record in records):
        raise ValueError("canonical seed projects must be objects with string identities")
    records.sort(key=lambda record: record["id"])
    identifiers = [record["id"] for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("canonical seed project identities must be unique")
    return records


def load_english_overlay(root: Path = ROOT) -> dict:
    return json.loads((root / ENGLISH_OVERLAY_PATH).read_text(encoding="utf-8"))


def generated_identifier(index: int) -> str:
    if index < 0:
        raise ValueError("fixture index must not be negative")
    return f"scale-{index:06x}"


def generated_title(title: str, index: int) -> str:
    suffix = f" · {index + 1:06d}"
    available = 140 - len(suffix)
    prefix = title[:available].rstrip()
    return f"{prefix}{suffix}"


def _seed_positions(seeds: list[dict]) -> dict[str, int]:
    return {record["id"]: index for index, record in enumerate(seeds)}


def _target_index(*, source_index: int, target_seed_id: str, seed_positions: dict[str, int], seed_count: int, count: int) -> int:
    target_position = seed_positions[target_seed_id]
    cohort = source_index // seed_count
    candidate = cohort * seed_count + target_position
    return candidate if candidate < count else target_position


def _rewrite_relations(record: dict, *, source_index: int, seed_positions: dict[str, int], seed_count: int, count: int) -> None:
    relations = record.get("relations")
    if not isinstance(relations, list):
        return
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        target_seed_id = relation.get("target_id")
        if target_seed_id not in seed_positions:
            raise ValueError(f"canonical relation target is not a seed: {target_seed_id}")
        relation["target_id"] = generated_identifier(
            _target_index(
                source_index=source_index,
                target_seed_id=target_seed_id,
                seed_positions=seed_positions,
                seed_count=seed_count,
                count=count,
            )
        )


def representative_records(count: int, root: Path = ROOT, *, validate: bool = True) -> list[dict]:
    if not isinstance(count, int) or count < 1:
        raise ValueError("fixture count must be a positive integer")
    seeds = load_seed_records(root)
    if count < len(seeds):
        raise ValueError(f"fixture count must be at least the canonical seed count ({len(seeds)})")
    seed_positions = _seed_positions(seeds)
    seed_count = len(seeds)
    records: list[dict] = []
    for index in range(count):
        seed = seeds[index % seed_count]
        record = copy.deepcopy(seed)
        record["id"] = generated_identifier(index)
        record["title"] = generated_title(seed["title"], index)
        _rewrite_relations(
            record,
            source_index=index,
            seed_positions=seed_positions,
            seed_count=seed_count,
            count=count,
        )
        records.append(record)
    if validate:
        validate_fixture_records(records, root)
    return records


def representative_english_overlay(records: list[dict], root: Path = ROOT) -> dict:
    seeds = load_seed_records(root)
    seed_count = len(seeds)
    source = load_english_overlay(root)
    source_projects = source.get("projects") if isinstance(source, dict) else None
    seed_ids = {seed["id"] for seed in seeds}
    if not isinstance(source_projects, dict) or set(source_projects) != seed_ids:
        raise ValueError("canonical English overlay identities must match canonical seed projects exactly")
    projects: dict[str, dict] = {}
    for index, record in enumerate(records):
        seed = seeds[index % seed_count]
        translation = copy.deepcopy(source_projects.get(seed["id"], {}))
        translation["title"] = generated_title(translation.get("title", seed["title"]), index)
        translation["summary"] = translation.get("summary", seed["summary"])
        projects[record["id"]] = translation
    overlay = {
        "schema_version": source.get("schema_version"),
        "locale": source.get("locale"),
        "fallback_locale": source.get("fallback_locale"),
        "contract": copy.deepcopy(source.get("contract")),
        "taxonomy_labels": copy.deepcopy(source.get("taxonomy_labels")),
        "projects": projects,
    }
    validate_fixture_locale_overlay(overlay, records)
    return overlay


def validate_fixture_records(records: list[dict], root: Path = ROOT) -> None:
    if not isinstance(records, list) or not records:
        raise ValueError("fixture records must be a non-empty list")
    identifiers = [record.get("id") for record in records if isinstance(record, dict)]
    titles = [record.get("title") for record in records if isinstance(record, dict)]
    if len(identifiers) != len(records) or len(set(identifiers)) != len(records):
        raise ValueError("fixture project identities must be unique")
    if len(titles) != len(records) or len(set(titles)) != len(records):
        raise ValueError("fixture project titles must be unique")
    known_ids = set(identifiers)
    for record in records:
        errors = validation_errors(record, root)
        if errors:
            raise ValueError(f"fixture project {record.get('id')} invalid: {errors[0]}")
        for relation in record.get("relations", []) if isinstance(record.get("relations"), list) else []:
            target_id = relation.get("target_id") if isinstance(relation, dict) else None
            if target_id not in known_ids:
                raise ValueError(f"fixture relation target is not present: {target_id}")
            if target_id == record["id"]:
                raise ValueError(f"fixture project relates to itself: {record['id']}")


def validate_fixture_locale_overlay(overlay: dict, records: list[dict]) -> None:
    if overlay.get("schema_version") != 1 or overlay.get("locale") != "en" or overlay.get("fallback_locale") != "de":
        raise ValueError("fixture English locale overlay header mismatch")
    projects = overlay.get("projects")
    if not isinstance(projects, dict):
        raise ValueError("fixture English locale projects must be an object")
    records_by_id = {record["id"]: record for record in records}
    if set(projects) != set(records_by_id):
        raise ValueError("fixture English locale identities must match fixture records exactly")
    for identifier, translation in projects.items():
        if not isinstance(translation, dict):
            raise ValueError(f"fixture locale entry is not an object: {identifier}")
        for field in ("title", "summary"):
            if not isinstance(translation.get(field), str) or not translation[field].strip():
                raise ValueError(f"fixture locale entry lacks {field}: {identifier}")
        geographic_labels = translation.get("geographic_labels", {})
        if geographic_labels is not None:
            if not isinstance(geographic_labels, dict):
                raise ValueError(f"fixture locale geographic labels are invalid: {identifier}")
            known_location_ids = {
                location.get("id")
                for location in records_by_id[identifier].get("presence", {}).get("geographic", [])
                if isinstance(location, dict)
            }
            unknown = set(geographic_labels) - known_location_ids
            if unknown:
                raise ValueError(f"fixture locale references unknown geographic labels: {identifier}: {sorted(unknown)}")


def public_points(record: dict) -> list[dict]:
    result = []
    for location in record.get("presence", {}).get("geographic", []):
        if location.get("mode") == "hidden" or "geometry" not in location:
            continue
        result.append({"mode": location["mode"], "geometry": copy.deepcopy(location["geometry"])})
    return result


def compact_projection(record: dict, detail: dict) -> dict:
    digital = record.get("presence", {}).get("digital", {})
    return {
        "id": record["id"],
        "title": record["title"],
        "themes": list(record.get("themes", [])),
        "actions": list(record.get("actions", [])),
        "languages": list(record.get("languages", {}).get("codes", [])),
        "access": record.get("access", {}).get("type"),
        "presence": {
            "geographic": public_points(record),
            "digital": bool(digital.get("available")),
        },
        "activity": record.get("activity", {}).get("status", "unknown"),
        "detail": detail,
    }


def shard_key(identifier: str, prefix_length: int = CURRENT_SHARD_PREFIX_LENGTH) -> str:
    if not isinstance(prefix_length, int) or not 1 <= prefix_length <= 8:
        raise ValueError("shard prefix length must be between 1 and 8")
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:prefix_length]


def spatial_cell(coordinates: list[float]) -> str:
    longitude, latitude = coordinates
    x = min(35, max(0, int((longitude + 180) // SPATIAL_CELL_DEGREES)))
    y = min(17, max(0, int((latitude + 90) // SPATIAL_CELL_DEGREES)))
    return f"{x:02d}:{y:02d}"


def _runtime_from_compact_records(
    compact_records: list[dict],
    *,
    source_catalog_sha256: str,
    detail_set_sha256: str,
    generation: str,
    prefix_length: int = CURRENT_SHARD_PREFIX_LENGTH,
) -> dict:
    records = sorted(compact_records, key=lambda record: record["id"])
    world = {"kind": "commonworld.world_index", "version": "1.0", "records": records}
    world_bytes = canonical_bytes(world)
    shard_payloads: dict[str, bytes] = {}
    shard_objects: dict[str, dict] = {}
    shards: dict[str, list[dict]] = {}
    for record in records:
        shards.setdefault(shard_key(record["id"], prefix_length), []).append(record)
    shard_entries = []
    for key, shard_records in sorted(shards.items()):
        payload_object = {"kind": "commonworld.catalog_shard", "version": "1.0", "key": key, "records": shard_records}
        payload = canonical_bytes(payload_object)
        shard_objects[key] = payload_object
        shard_payloads[key] = payload
        shard_entries.append({
            "key": key,
            "url": f"catalog/runtime/shards/{key}.v1.json",
            "sha256": sha256(payload),
            "bytes": len(payload),
            "entry_count": len(shard_records),
        })

    indexes: dict[str, dict] = {"themes": {}, "spatial_cells": {}, "digital": {"available": [], "unavailable": []}}
    for record in records:
        key = shard_key(record["id"], prefix_length)
        for theme in record["themes"]:
            indexes["themes"].setdefault(theme, set()).add(key)
        indexes["digital"]["available" if record["presence"]["digital"] else "unavailable"].append(key)
        for location in record["presence"]["geographic"]:
            geometry = location.get("geometry", {})
            if geometry.get("type") == "Point" and len(geometry.get("coordinates", [])) >= 2:
                indexes["spatial_cells"].setdefault(spatial_cell(geometry["coordinates"]), set()).add(key)
    aggregate = {
        "kind": "commonworld.catalog_aggregate",
        "version": "1.0",
        "entry_count": len(records),
        "source_catalog_sha256": source_catalog_sha256,
        "spatial_cell_degrees": SPATIAL_CELL_DEGREES,
        "themes": {name: sorted(keys) for name, keys in sorted(indexes["themes"].items())},
        "spatial_cells": {name: sorted(keys) for name, keys in sorted(indexes["spatial_cells"].items())},
        "digital": {name: sorted(set(keys)) for name, keys in indexes["digital"].items()},
    }
    aggregate_bytes = canonical_bytes(aggregate)
    manifest = {
        "kind": "commonworld.catalog_runtime_manifest",
        "version": "1.0",
        "generation": generation,
        "entry_count": len(records),
        "world_index": {"url": "catalog/runtime/world.v1.json", "sha256": sha256(world_bytes), "bytes": len(world_bytes)},
        "aggregate": {"url": "catalog/runtime/aggregate.v1.json", "sha256": sha256(aggregate_bytes), "bytes": len(aggregate_bytes)},
        "details": {
            "strategy": "content-addressed-shard-descriptors",
            "descriptor_version": DETAIL_DESCRIPTOR_VERSION,
            "url_template": "catalog/runtime/details/{sha256}.v1.json",
            "entry_count": len(records),
            "detail_set_sha256": detail_set_sha256,
            "project_schema_version": 4,
        },
        "shards": {"strategy": "sha256-prefix", "prefix_length": prefix_length, "entries": shard_entries},
        "source_catalog_sha256": source_catalog_sha256,
    }
    return {
        "manifest": manifest,
        "manifest_bytes": canonical_bytes(manifest),
        "aggregate": aggregate,
        "aggregate_bytes": aggregate_bytes,
        "world": world,
        "world_bytes": world_bytes,
        "shard_objects": shard_objects,
        "shard_payloads": shard_payloads,
        "compact_records": records,
    }


def build_runtime_fixture(records: list[dict], root: Path = ROOT, *, validate: bool = True) -> dict:
    if validate:
        validate_fixture_records(records, root)
    detail_payloads = {record["id"]: canonical_bytes(record) for record in records}
    detail_seed_entries = sorted(
        (
            {
                "identity": identifier,
                "url": f"catalog/runtime/details/{sha256(payload)}.v1.json",
                "sha256": sha256(payload),
                "bytes": len(payload),
            }
            for identifier, payload in detail_payloads.items()
        ),
        key=lambda entry: entry["identity"],
    )
    records_sha256 = sha256(canonical_bytes(records))
    source_catalog_sha256 = sha256(canonical_bytes({"entry_count": len(records), "records_sha256": records_sha256}))
    detail_set_sha256 = sha256(canonical_bytes(detail_seed_entries))
    generation = sha256(canonical_bytes({
        "schema_version": "2.0",
        "source_catalog_sha256": source_catalog_sha256,
        "detail_set_sha256": detail_set_sha256,
        "project_schema_version": 4,
        "detail_descriptor_version": DETAIL_DESCRIPTOR_VERSION,
    }))
    descriptors = {
        seed["identity"]: {
            "version": DETAIL_DESCRIPTOR_VERSION,
            "identity": seed["identity"],
            "generation": generation,
            "url": seed["url"],
            "sha256": seed["sha256"],
            "bytes": seed["bytes"],
        }
        for seed in detail_seed_entries
    }
    compact_records = [compact_projection(record, descriptors[record["id"]]) for record in records]
    result = _runtime_from_compact_records(
        compact_records,
        source_catalog_sha256=source_catalog_sha256,
        detail_set_sha256=detail_set_sha256,
        generation=generation,
    )
    result.update({
        "detail_payloads": detail_payloads,
        "detail_descriptors": descriptors,
        "records_sha256": records_sha256,
    })
    validate_runtime_fixture(result, records)
    return result


def build_compact_stress_fixture(
    count: int,
    root: Path = ROOT,
    *,
    prefix_length: int = CURRENT_SHARD_PREFIX_LENGTH,
) -> dict:
    if not isinstance(count, int) or count < 1:
        raise ValueError("stress fixture count must be a positive integer")
    seeds = load_seed_records(root)
    compact_seeds = [compact_projection(record, {}) for record in seeds]
    detail_seeds = []
    provisional: list[dict] = []
    for index in range(count):
        seed = copy.deepcopy(compact_seeds[index % len(compact_seeds)])
        identifier = generated_identifier(index)
        seed["id"] = identifier
        seed["title"] = generated_title(seed["title"], index)
        placeholder_payload = canonical_bytes({"fixture": "compact-stress", "identity": identifier, "seed": seeds[index % len(seeds)]["id"]})
        detail_seeds.append({
            "identity": identifier,
            "url": f"catalog/runtime/details/{sha256(placeholder_payload)}.v1.json",
            "sha256": sha256(placeholder_payload),
            "bytes": len(placeholder_payload),
        })
        provisional.append(seed)
    source_catalog_sha256 = sha256(canonical_bytes({"entry_count": count, "fixture": "compact-stress", "seed_count": len(seeds)}))
    detail_set_sha256 = sha256(canonical_bytes(detail_seeds))
    generation = sha256(canonical_bytes({
        "schema_version": "2.0",
        "source_catalog_sha256": source_catalog_sha256,
        "detail_set_sha256": detail_set_sha256,
        "project_schema_version": 4,
        "detail_descriptor_version": DETAIL_DESCRIPTOR_VERSION,
        "stress_only": True,
    }))
    for record, detail in zip(provisional, detail_seeds, strict=True):
        record["detail"] = {
            "version": DETAIL_DESCRIPTOR_VERSION,
            "identity": detail["identity"],
            "generation": generation,
            "url": detail["url"],
            "sha256": detail["sha256"],
            "bytes": detail["bytes"],
        }
    return _runtime_from_compact_records(
        provisional,
        source_catalog_sha256=source_catalog_sha256,
        detail_set_sha256=detail_set_sha256,
        generation=generation,
        prefix_length=prefix_length,
    )


def repartition_runtime_fixture(runtime: dict, *, prefix_length: int) -> dict:
    manifest = runtime.get("manifest", {})
    return _runtime_from_compact_records(
        runtime["compact_records"],
        source_catalog_sha256=manifest["source_catalog_sha256"],
        detail_set_sha256=manifest["details"]["detail_set_sha256"],
        generation=manifest["generation"],
        prefix_length=prefix_length,
    )


def validate_runtime_fixture(runtime: dict, records: list[dict]) -> None:
    manifest = runtime["manifest"]
    if manifest["entry_count"] != len(records):
        raise ValueError("fixture runtime manifest entry count mismatch")
    if manifest["world_index"]["sha256"] != sha256(runtime["world_bytes"]):
        raise ValueError("fixture world index digest mismatch")
    if manifest["aggregate"]["sha256"] != sha256(runtime["aggregate_bytes"]):
        raise ValueError("fixture aggregate digest mismatch")
    shard_entries = {entry["key"]: entry for entry in manifest["shards"]["entries"]}
    if sum(entry["entry_count"] for entry in shard_entries.values()) != len(records):
        raise ValueError("fixture shard entry count sum mismatch")
    for key, payload in runtime["shard_payloads"].items():
        descriptor = shard_entries.get(key)
        if descriptor is None or descriptor["sha256"] != sha256(payload) or descriptor["bytes"] != len(payload):
            raise ValueError(f"fixture shard descriptor mismatch: {key}")
    records_by_id = {record["id"]: record for record in records}
    for compact in runtime["compact_records"]:
        identifier = compact["id"]
        detail = compact["detail"]
        payload = runtime["detail_payloads"].get(identifier)
        if payload is None or detail["sha256"] != sha256(payload) or detail["bytes"] != len(payload):
            raise ValueError(f"fixture detail descriptor mismatch: {identifier}")
        if json.loads(payload) != records_by_id[identifier]:
            raise ValueError(f"fixture detail payload identity mismatch: {identifier}")
        expected = compact_projection(records_by_id[identifier], detail)
        if compact != expected:
            raise ValueError(f"fixture compact/detail parity mismatch: {identifier}")
    known_shards = set(shard_entries)
    for index_name in ("themes", "spatial_cells"):
        for keys in runtime["aggregate"][index_name].values():
            if not set(keys).issubset(known_shards):
                raise ValueError(f"fixture aggregate {index_name} references unknown shard")
    for keys in runtime["aggregate"]["digital"].values():
        if not set(keys).issubset(known_shards):
            raise ValueError("fixture aggregate digital index references unknown shard")


def fixture_coverage(records: list[dict], overlay: dict | None = None) -> dict:
    location_modes: set[str] = set()
    presence_classes: Counter[str] = Counter()
    themes: set[str] = set()
    actions: set[str] = set()
    languages: set[str] = set()
    access: set[str] = set()
    activity: set[str] = set()
    relation_count = 0
    source_count = 0
    handoff_states: Counter[str] = Counter()
    for record in records:
        geographic = record.get("presence", {}).get("geographic", [])
        digital = record.get("presence", {}).get("digital", {}).get("available") is True
        public_geographic = any(location.get("mode") != "hidden" for location in geographic if isinstance(location, dict))
        hidden_geographic = any(location.get("mode") == "hidden" for location in geographic if isinstance(location, dict))
        location_modes.update(location.get("mode") for location in geographic if isinstance(location, dict) and isinstance(location.get("mode"), str))
        if digital and public_geographic:
            presence_classes["hybrid"] += 1
        elif digital:
            presence_classes["digital_only"] += 1
        elif public_geographic:
            presence_classes["geographic_only"] += 1
        if hidden_geographic:
            presence_classes["contains_hidden_location"] += 1
        themes.update(record.get("themes", []))
        actions.update(record.get("actions", []))
        languages.update(record.get("languages", {}).get("codes", []))
        access_type = record.get("access", {}).get("type")
        if isinstance(access_type, str):
            access.add(access_type)
        status = record.get("activity", {}).get("status")
        if isinstance(status, str):
            activity.add(status)
        relation_count += len(record.get("relations", [])) if isinstance(record.get("relations"), list) else 0
        source_count += len(record.get("provenance", {}).get("sources", []))
        handoff = record.get("handoff")
        if isinstance(handoff, dict):
            handoff_states["enabled" if handoff.get("enabled") is True else "disabled"] += 1
        else:
            handoff_states["absent"] += 1
    return {
        "location_modes": sorted(location_modes),
        "presence_classes": dict(sorted(presence_classes.items())),
        "themes": sorted(themes),
        "actions": sorted(actions),
        "languages": sorted(languages),
        "access": sorted(access),
        "activity": sorted(activity),
        "relation_count": relation_count,
        "provenance_source_count": source_count,
        "handoff_states": dict(sorted(handoff_states.items())),
        "released_locale_overlays": ["de", "en"],
        "english_overlay_project_count": len(overlay.get("projects", {})) if isinstance(overlay, dict) else 0,
    }


def fixture_digest(records: list[dict], english_overlay: dict) -> str:
    return sha256(canonical_bytes({"records": records, "locales": {"en": english_overlay}}))


def compact_fixture_coverage(count: int, root: Path = ROOT) -> dict:
    seeds = load_seed_records(root)
    repeats, remainder = divmod(count, len(seeds))
    seed_coverage = fixture_coverage(seeds, load_english_overlay(root))
    partial_coverage = fixture_coverage(seeds[:remainder]) if remainder else {
        "presence_classes": {},
        "relation_count": 0,
        "provenance_source_count": 0,
        "handoff_states": {},
    }
    seed_coverage["presence_classes"] = {
        name: amount * repeats + partial_coverage.get("presence_classes", {}).get(name, 0)
        for name, amount in seed_coverage["presence_classes"].items()
    }
    seed_coverage["relation_count"] = (
        seed_coverage["relation_count"] * repeats + partial_coverage.get("relation_count", 0)
    )
    seed_coverage["provenance_source_count"] = (
        seed_coverage["provenance_source_count"] * repeats
        + partial_coverage.get("provenance_source_count", 0)
    )
    seed_coverage["handoff_states"] = {
        name: amount * repeats + partial_coverage.get("handoff_states", {}).get(name, 0)
        for name, amount in seed_coverage["handoff_states"].items()
    }
    seed_coverage["english_overlay_project_count"] = 0
    seed_coverage["stress_projection"] = {
        "seed_count": len(seeds),
        "full_seed_repetitions": repeats,
        "partial_seed_count": remainder,
        "details_materialized": False,
        "locale_overlays_materialized": False,
    }
    return seed_coverage
