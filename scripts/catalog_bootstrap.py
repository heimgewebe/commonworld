"""Deterministic compact projection for the public Commonworld startup catalogue."""

from __future__ import annotations

import copy

BOOTSTRAP_OMITTED_FIELDS = frozenset({"handoff"})
CURATION_BOOTSTRAP_FIELDS = ("state", "catalogued_at", "reviewed_at", "next_review_at")
SOURCE_BOOTSTRAP_FIELDS = ("url",)
LINK_BOOTSTRAP_FIELDS = ("type", "label", "url")
DERIVABLE_ACTION_LINK_TYPES = frozenset({
    "homepage", "visit", "use", "borrow", "learn", "contribute", "volunteer",
    "donate", "contact", "replicate",
})
RELATION_BOOTSTRAP_FIELDS = ("target_id", "type")


def bootstrap_record(record: dict) -> dict:
    """Keep startup discovery fields plus one degraded-mode source while deferring full detail."""
    projected = copy.deepcopy(
        {key: value for key, value in record.items() if key not in BOOTSTRAP_OMITTED_FIELDS}
    )
    if isinstance(record.get("provenance"), dict):
        projected["provenance"] = {
            "sources": [
                {key: source[key] for key in SOURCE_BOOTSTRAP_FIELDS if key in source}
                for source in record["provenance"].get("sources", [])[:1]
            ]
        }
    if isinstance(record.get("curation"), dict):
        projected["curation"] = {
            key: record["curation"][key]
            for key in CURATION_BOOTSTRAP_FIELDS
            if key in record["curation"]
        }
    if isinstance(record.get("activity"), dict):
        projected["activity"] = {"status": record["activity"].get("status")}
        if record["activity"].get("status") == "unknown" and "observed_at" in record["activity"]:
            projected["activity"]["observed_at"] = record["activity"]["observed_at"]
    for location in projected.get("presence", {}).get("geographic", []):
        location.pop("source_ids", None)
        location.pop("privacy_note", None)
    digital = projected.get("presence", {}).get("digital")
    if isinstance(digital, dict):
        digital.pop("source_ids", None)
    projected["links"] = [
        {
            key: link[key]
            for key in LINK_BOOTSTRAP_FIELDS
            if key in link and not (key == "label" and link.get("type") in DERIVABLE_ACTION_LINK_TYPES)
        }
        for link in projected.get("links", [])
    ]
    if isinstance(record.get("relations"), list):
        projected["relations"] = [
            {
                **{key: relation[key] for key in RELATION_BOOTSTRAP_FIELDS if key in relation},
                "evidenced": True,
            }
            for relation in record["relations"]
            if isinstance(relation, dict)
            and relation.get("target_id")
            and relation.get("type")
            and isinstance(relation.get("source_ids"), list)
            and len(relation["source_ids"]) > 0
        ]
    if isinstance(projected.get("languages"), dict):
        projected["languages"] = {"codes": projected["languages"].get("codes", [])}
    if isinstance(projected.get("access"), dict):
        projected["access"] = {"type": projected["access"].get("type")}
    return projected
