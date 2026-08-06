"""Digest helpers for locale review evidence.

The independent language review is performed before promotion. Promotion changes
only meta.independent_language_review from pending to passed. Normalizing that
field back to pending reconstructs the exact reviewed pack bytes and prevents a
self-invalidating evidence cycle without weakening translation-content binding.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def normalized_review_source_bytes(payload: dict[str, Any]) -> bytes:
    normalized = copy.deepcopy(payload)
    locales = normalized.get("locales")
    if not isinstance(locales, dict) or not locales:
        raise ValueError("locale pack locales must be a non-empty object")
    for tag, locale_pack in locales.items():
        if not isinstance(locale_pack, dict):
            raise ValueError(f"locale pack entry must be an object: {tag}")
        meta = locale_pack.get("meta")
        if not isinstance(meta, dict):
            raise ValueError(f"locale pack meta must be an object: {tag}")
        meta["independent_language_review"] = "pending"
    return (json.dumps(normalized, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def reviewed_source_pack_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("locale pack root must be an object")
    return hashlib.sha256(normalized_review_source_bytes(payload)).hexdigest()
