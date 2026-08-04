#!/usr/bin/env python3
"""Deterministic hierarchical catalogue runtime candidate for Commonworld.

This module builds a versioned v2 manifest and aggregate hierarchy from the
existing compact runtime fixtures.  It deliberately does not change the public
v1 runtime default.  The hierarchy is a migration candidate whose cutover stays
fail-closed until the browser and physical-device gates are complete.
"""

from __future__ import annotations

import copy
from collections import defaultdict

try:
    from scripts.catalog_scale_fixtures import (
        SPATIAL_CELL_DEGREES,
        _runtime_from_compact_records,
        canonical_bytes,
        sha256,
        shard_key,
    )
except ModuleNotFoundError:  # Direct script execution adds scripts/ to sys.path.
    from catalog_scale_fixtures import (
        SPATIAL_CELL_DEGREES,
        _runtime_from_compact_records,
        canonical_bytes,
        sha256,
        shard_key,
    )

MANIFEST_VERSION = "2.0"
AGGREGATE_VERSION = "2.0"
SHARD_INDEX_VERSION = "2.0"
AGGREGATE_SEGMENT_VERSION = "2.0"
DEFAULT_MANIFEST_VERSION = "1.0"
DEFAULT_SHARD_PREFIX_LENGTH = 2
LEAF_PREFIX_LENGTH = 3
INDEX_PREFIX_LENGTH = 1
REQUIRED_CUTOVER_GATES = [
    "deterministic-fixtures",
    "browser-transfer-budget",
    "physical-device",
]


def _descriptor(payload: bytes, url: str, **extra: object) -> dict:
    return {
        **extra,
        "url": url,
        "sha256": sha256(payload),
        "bytes": len(payload),
    }


def aggregate_bucket(dimension: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("aggregate index value must be a non-empty string")
    if dimension == "themes":
        return value[:3]
    if dimension == "spatial_cells":
        x, separator, _y = value.partition(":")
        if separator != ":" or len(x) != 2 or not x.isdigit():
            raise ValueError(f"invalid spatial cell value: {value}")
        return x
    if dimension == "digital":
        if value not in {"available", "unavailable"}:
            raise ValueError(f"invalid digital index value: {value}")
        return "all"
    raise ValueError(f"unsupported aggregate dimension: {dimension}")


def _build_shard_indexes(flat_runtime: dict, *, index_prefix_length: int, leaf_prefix_length: int) -> tuple[dict, dict, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in flat_runtime["manifest"]["shards"]["entries"]:
        grouped[entry["key"][:index_prefix_length]].append(copy.deepcopy(entry))

    objects: dict[str, dict] = {}
    payloads: dict[str, bytes] = {}
    descriptors: list[dict] = []
    for index_key in sorted(grouped):
        entries = sorted(grouped[index_key], key=lambda item: item["key"])
        value = {
            "kind": "commonworld.catalog_shard_index",
            "version": SHARD_INDEX_VERSION,
            "generation": flat_runtime["manifest"]["generation"],
            "source_catalog_sha256": flat_runtime["manifest"]["source_catalog_sha256"],
            "index_key": index_key,
            "index_prefix_length": index_prefix_length,
            "leaf_prefix_length": leaf_prefix_length,
            "entry_count": sum(item["entry_count"] for item in entries),
            "shard_count": len(entries),
            "entries": entries,
        }
        payload = canonical_bytes(value)
        objects[index_key] = value
        payloads[index_key] = payload
        descriptors.append(
            _descriptor(
                payload,
                f"catalog/runtime/shard-indexes/{index_key}.v2.json",
                key=index_key,
                entry_count=value["entry_count"],
                shard_count=value["shard_count"],
            )
        )
    return objects, payloads, descriptors


def _build_aggregate_segments(flat_runtime: dict) -> tuple[dict, dict, dict[str, list[dict]]]:
    aggregate = flat_runtime["aggregate"]
    objects: dict[str, dict] = {}
    payloads: dict[str, bytes] = {}
    descriptors: dict[str, list[dict]] = {
        "themes": [],
        "spatial_cells": [],
        "digital": [],
    }
    for dimension in descriptors:
        grouped: dict[str, dict[str, list[str]]] = defaultdict(dict)
        for value, keys in sorted(aggregate[dimension].items()):
            grouped[aggregate_bucket(dimension, value)][value] = sorted(keys)
        for key in sorted(grouped):
            index = {value: grouped[key][value] for value in sorted(grouped[key])}
            segment_id = f"{dimension}:{key}"
            value = {
                "kind": "commonworld.catalog_aggregate_segment",
                "version": AGGREGATE_SEGMENT_VERSION,
                "generation": flat_runtime["manifest"]["generation"],
                "source_catalog_sha256": flat_runtime["manifest"]["source_catalog_sha256"],
                "dimension": dimension,
                "key": key,
                "entry_count": flat_runtime["manifest"]["entry_count"],
                "value_count": len(index),
                "shard_reference_count": sum(len(keys) for keys in index.values()),
                "index": index,
            }
            payload = canonical_bytes(value)
            objects[segment_id] = value
            payloads[segment_id] = payload
            descriptors[dimension].append(
                _descriptor(
                    payload,
                    f"catalog/runtime/aggregate-segments/{dimension}/{key}.v2.json",
                    dimension=dimension,
                    key=key,
                    value_count=value["value_count"],
                    shard_reference_count=value["shard_reference_count"],
                )
            )
    return objects, payloads, descriptors


def build_hierarchical_runtime_fixture(
    runtime: dict,
    *,
    leaf_prefix_length: int = LEAF_PREFIX_LENGTH,
    index_prefix_length: int = INDEX_PREFIX_LENGTH,
) -> dict:
    if not isinstance(leaf_prefix_length, int) or not 2 <= leaf_prefix_length <= 8:
        raise ValueError("leaf prefix length must be between 2 and 8")
    if not isinstance(index_prefix_length, int) or not 1 <= index_prefix_length < leaf_prefix_length:
        raise ValueError("index prefix length must be positive and shorter than the leaf prefix")
    source_manifest = runtime.get("manifest")
    compact_records = runtime.get("compact_records")
    if not isinstance(source_manifest, dict) or not isinstance(compact_records, list):
        raise ValueError("source runtime must expose a manifest and compact records")

    flat_runtime = _runtime_from_compact_records(
        compact_records,
        source_catalog_sha256=source_manifest["source_catalog_sha256"],
        detail_set_sha256=source_manifest["details"]["detail_set_sha256"],
        generation=source_manifest["generation"],
        prefix_length=leaf_prefix_length,
    )
    shard_index_objects, shard_index_payloads, shard_index_descriptors = _build_shard_indexes(
        flat_runtime,
        index_prefix_length=index_prefix_length,
        leaf_prefix_length=leaf_prefix_length,
    )
    aggregate_segment_objects, aggregate_segment_payloads, aggregate_segment_descriptors = _build_aggregate_segments(flat_runtime)

    aggregate = {
        "kind": "commonworld.catalog_aggregate",
        "version": AGGREGATE_VERSION,
        "generation": source_manifest["generation"],
        "entry_count": source_manifest["entry_count"],
        "source_catalog_sha256": source_manifest["source_catalog_sha256"],
        "spatial_cell_degrees": SPATIAL_CELL_DEGREES,
        "segments": aggregate_segment_descriptors,
    }
    aggregate_bytes = canonical_bytes(aggregate)
    manifest = {
        "kind": "commonworld.catalog_runtime_manifest",
        "version": MANIFEST_VERSION,
        "generation": source_manifest["generation"],
        "entry_count": source_manifest["entry_count"],
        "world_index": copy.deepcopy(flat_runtime["manifest"]["world_index"]),
        "aggregate": _descriptor(aggregate_bytes, "catalog/runtime/aggregate.v2.json"),
        "details": copy.deepcopy(source_manifest["details"]),
        "shards": {
            "strategy": "sha256-prefix-hierarchy",
            "index_prefix_length": index_prefix_length,
            "leaf_prefix_length": leaf_prefix_length,
            "indexes": shard_index_descriptors,
        },
        "migration_guard": {
            "default_manifest_version": DEFAULT_MANIFEST_VERSION,
            "default_shard_prefix_length": DEFAULT_SHARD_PREFIX_LENGTH,
            "candidate_manifest_version": MANIFEST_VERSION,
            "cutover_authorized": False,
            "rollback_manifest_url": "catalog/runtime/manifest.v1.json",
            "required_gates": REQUIRED_CUTOVER_GATES,
        },
        "source_catalog_sha256": source_manifest["source_catalog_sha256"],
    }
    result = {
        **flat_runtime,
        "manifest": manifest,
        "manifest_bytes": canonical_bytes(manifest),
        "aggregate": aggregate,
        "aggregate_bytes": aggregate_bytes,
        "shard_index_objects": shard_index_objects,
        "shard_index_payloads": shard_index_payloads,
        "aggregate_segment_objects": aggregate_segment_objects,
        "aggregate_segment_payloads": aggregate_segment_payloads,
    }
    validate_hierarchical_runtime_fixture(result)
    return result


def _validate_descriptor(descriptor: object, payload: bytes, *, label: str, expected_url: str) -> None:
    if not isinstance(descriptor, dict):
        raise ValueError(f"{label} descriptor must be an object")
    if descriptor.get("url") != expected_url:
        raise ValueError(f"{label} descriptor URL mismatch")
    if descriptor.get("bytes") != len(payload):
        raise ValueError(f"{label} descriptor byte length mismatch")
    if descriptor.get("sha256") != sha256(payload):
        raise ValueError(f"{label} descriptor digest mismatch")


def validate_hierarchical_runtime_fixture(runtime: dict) -> None:
    manifest = runtime.get("manifest")
    aggregate = runtime.get("aggregate")
    if not isinstance(manifest, dict) or manifest.get("kind") != "commonworld.catalog_runtime_manifest" or manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("hierarchical manifest header mismatch")
    if not isinstance(aggregate, dict) or aggregate.get("kind") != "commonworld.catalog_aggregate" or aggregate.get("version") != AGGREGATE_VERSION:
        raise ValueError("hierarchical aggregate header mismatch")
    if aggregate.get("generation") != manifest.get("generation"):
        raise ValueError("hierarchical aggregate generation mismatch")
    if aggregate.get("entry_count") != manifest.get("entry_count"):
        raise ValueError("hierarchical aggregate entry count mismatch")
    if aggregate.get("source_catalog_sha256") != manifest.get("source_catalog_sha256"):
        raise ValueError("hierarchical aggregate source mismatch")
    _validate_descriptor(
        manifest.get("aggregate"),
        runtime["aggregate_bytes"],
        label="aggregate root",
        expected_url="catalog/runtime/aggregate.v2.json",
    )

    shards = manifest.get("shards")
    if not isinstance(shards, dict) or shards.get("strategy") != "sha256-prefix-hierarchy":
        raise ValueError("hierarchical shard strategy mismatch")
    index_prefix_length = shards.get("index_prefix_length")
    leaf_prefix_length = shards.get("leaf_prefix_length")
    if not isinstance(index_prefix_length, int) or not isinstance(leaf_prefix_length, int) or not 1 <= index_prefix_length < leaf_prefix_length <= 8:
        raise ValueError("hierarchical shard prefix lengths are invalid")
    if "entries" in shards:
        raise ValueError("hierarchical manifest must not embed flat shard entries")
    descriptors = shards.get("indexes")
    if not isinstance(descriptors, list) or not descriptors:
        raise ValueError("hierarchical manifest must declare shard indexes")
    if descriptors != sorted(descriptors, key=lambda item: item.get("key", "")):
        raise ValueError("hierarchical shard index descriptors are not canonical")

    known_shards: set[str] = set()
    total_entries = 0
    for descriptor in descriptors:
        key = descriptor.get("key") if isinstance(descriptor, dict) else None
        if not isinstance(key, str) or len(key) != index_prefix_length or any(character not in "0123456789abcdef" for character in key):
            raise ValueError("hierarchical shard index key is invalid")
        payload = runtime["shard_index_payloads"].get(key)
        value = runtime["shard_index_objects"].get(key)
        if not isinstance(payload, bytes) or not isinstance(value, dict):
            raise ValueError(f"hierarchical shard index is missing: {key}")
        _validate_descriptor(
            descriptor,
            payload,
            label=f"shard index {key}",
            expected_url=f"catalog/runtime/shard-indexes/{key}.v2.json",
        )
        expected_header = {
            "kind": "commonworld.catalog_shard_index",
            "version": SHARD_INDEX_VERSION,
            "generation": manifest["generation"],
            "source_catalog_sha256": manifest["source_catalog_sha256"],
            "index_key": key,
            "index_prefix_length": index_prefix_length,
            "leaf_prefix_length": leaf_prefix_length,
        }
        for field, expected in expected_header.items():
            if value.get(field) != expected:
                raise ValueError(f"hierarchical shard index {key} {field} mismatch")
        entries = value.get("entries")
        if not isinstance(entries, list) or entries != sorted(entries, key=lambda item: item.get("key", "")):
            raise ValueError(f"hierarchical shard index {key} entries are not canonical")
        if value.get("shard_count") != len(entries) or descriptor.get("shard_count") != len(entries):
            raise ValueError(f"hierarchical shard index {key} shard count mismatch")
        index_entry_count = 0
        for entry in entries:
            leaf_key = entry.get("key") if isinstance(entry, dict) else None
            if not isinstance(leaf_key, str) or len(leaf_key) != leaf_prefix_length or not leaf_key.startswith(key):
                raise ValueError(f"hierarchical shard index {key} contains an invalid leaf key")
            if leaf_key in known_shards:
                raise ValueError(f"hierarchical shard is declared more than once: {leaf_key}")
            payload = runtime["shard_payloads"].get(leaf_key)
            shard = runtime["shard_objects"].get(leaf_key)
            if not isinstance(payload, bytes) or not isinstance(shard, dict):
                raise ValueError(f"hierarchical shard payload is missing: {leaf_key}")
            _validate_descriptor(
                entry,
                payload,
                label=f"leaf shard {leaf_key}",
                expected_url=f"catalog/runtime/shards/{leaf_key}.v1.json",
            )
            records = shard.get("records")
            if shard.get("key") != leaf_key or not isinstance(records, list) or entry.get("entry_count") != len(records):
                raise ValueError(f"hierarchical shard {leaf_key} entry count mismatch")
            for record in records:
                if not isinstance(record, dict) or shard_key(record.get("id"), leaf_prefix_length) != leaf_key:
                    raise ValueError(f"hierarchical shard {leaf_key} contains a foreign identity")
            known_shards.add(leaf_key)
            index_entry_count += len(records)
        if value.get("entry_count") != index_entry_count or descriptor.get("entry_count") != index_entry_count:
            raise ValueError(f"hierarchical shard index {key} entry count mismatch")
        total_entries += index_entry_count
    if total_entries != manifest.get("entry_count"):
        raise ValueError("hierarchical shard entry count sum mismatch")

    segments = aggregate.get("segments")
    if not isinstance(segments, dict) or set(segments) != {"themes", "spatial_cells", "digital"}:
        raise ValueError("hierarchical aggregate segment inventory mismatch")
    declared_segment_ids: set[str] = set()
    for dimension in ("themes", "spatial_cells", "digital"):
        dimension_descriptors = segments.get(dimension)
        if not isinstance(dimension_descriptors, list):
            raise ValueError(f"hierarchical aggregate dimension inventory is invalid: {dimension}")
        if dimension_descriptors != sorted(dimension_descriptors, key=lambda item: item.get("key", "")):
            raise ValueError(f"hierarchical aggregate descriptors are not canonical: {dimension}")
        for descriptor in dimension_descriptors:
            key = descriptor.get("key") if isinstance(descriptor, dict) else None
            if descriptor.get("dimension") != dimension or not isinstance(key, str) or not key:
                raise ValueError(f"hierarchical aggregate descriptor is invalid: {dimension}")
            segment_id = f"{dimension}:{key}"
            if segment_id in declared_segment_ids:
                raise ValueError(f"hierarchical aggregate segment is duplicated: {segment_id}")
            declared_segment_ids.add(segment_id)
            payload = runtime["aggregate_segment_payloads"].get(segment_id)
            value = runtime["aggregate_segment_objects"].get(segment_id)
            if not isinstance(payload, bytes) or not isinstance(value, dict):
                raise ValueError(f"hierarchical aggregate segment is missing: {segment_id}")
            _validate_descriptor(
                descriptor,
                payload,
                label=f"aggregate segment {segment_id}",
                expected_url=f"catalog/runtime/aggregate-segments/{dimension}/{key}.v2.json",
            )
            expected_header = {
                "kind": "commonworld.catalog_aggregate_segment",
                "version": AGGREGATE_SEGMENT_VERSION,
                "generation": manifest["generation"],
                "source_catalog_sha256": manifest["source_catalog_sha256"],
                "dimension": dimension,
                "key": key,
                "entry_count": manifest["entry_count"],
            }
            for field, expected in expected_header.items():
                if value.get(field) != expected:
                    raise ValueError(f"aggregate segment {segment_id} {field} mismatch")
            index = value.get("index")
            if not isinstance(index, dict) or list(index) != sorted(index):
                raise ValueError(f"aggregate segment {segment_id} index is not canonical")
            if value.get("value_count") != len(index) or descriptor.get("value_count") != len(index):
                raise ValueError(f"aggregate segment {segment_id} value count mismatch")
            reference_count = 0
            for index_value, keys in index.items():
                if aggregate_bucket(dimension, index_value) != key:
                    raise ValueError(f"aggregate segment {segment_id} contains a foreign value")
                if not isinstance(keys, list) or keys != sorted(set(keys)) or not set(keys).issubset(known_shards):
                    raise ValueError(f"aggregate segment {segment_id} references an unknown shard")
                reference_count += len(keys)
            if value.get("shard_reference_count") != reference_count or descriptor.get("shard_reference_count") != reference_count:
                raise ValueError(f"aggregate segment {segment_id} reference count mismatch")

    guard = manifest.get("migration_guard")
    expected_guard = {
        "default_manifest_version": DEFAULT_MANIFEST_VERSION,
        "default_shard_prefix_length": DEFAULT_SHARD_PREFIX_LENGTH,
        "candidate_manifest_version": MANIFEST_VERSION,
        "cutover_authorized": False,
        "rollback_manifest_url": "catalog/runtime/manifest.v1.json",
        "required_gates": REQUIRED_CUTOVER_GATES,
    }
    if guard != expected_guard:
        raise ValueError("hierarchical migration guard mismatch")


__all__ = [
    "AGGREGATE_SEGMENT_VERSION",
    "AGGREGATE_VERSION",
    "INDEX_PREFIX_LENGTH",
    "LEAF_PREFIX_LENGTH",
    "MANIFEST_VERSION",
    "REQUIRED_CUTOVER_GATES",
    "aggregate_bucket",
    "build_hierarchical_runtime_fixture",
    "validate_hierarchical_runtime_fixture",
]
