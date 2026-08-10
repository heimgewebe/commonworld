"""Canonical Commonworld interface-locale registry helpers."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
TAG_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|[0-9]{3}))?$")
ZH_REGION_SCRIPT = {
    "CN": "Hans",
    "SG": "Hans",
    "TW": "Hant",
    "HK": "Hant",
    "MO": "Hant",
}


def requested_script(tag: str) -> str | None:
    parts = tag.split("-")
    if len(parts) >= 2 and len(parts[1]) == 4 and parts[1].isalpha():
        return parts[1].title()
    primary = parts[0].lower()
    region = next((part for part in parts[1:] if (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit())), None)
    if primary == "zh" and region:
        return ZH_REGION_SCRIPT.get(region.upper())
    return None


@lru_cache(maxsize=4)
def load_locale_contract(path: Path = CONTRACT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonicalize_tag(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw or not TAG_RE.fullmatch(raw):
        return None
    parts = raw.split("-")
    canonical = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            canonical.append(part.title())
        elif len(part) == 2 and part.isalpha():
            canonical.append(part.upper())
        else:
            canonical.append(part)
    return "-".join(canonical)


def locale_registry(root: Path = ROOT) -> dict[str, dict]:
    contract = load_locale_contract(root / "docs/architecture/locale-release.contract.json")
    return contract["locale_registry"]


def locales_with_status(*statuses: str, root: Path = ROOT) -> tuple[str, ...]:
    allowed = set(statuses)
    return tuple(tag for tag, entry in locale_registry(root).items() if entry.get("status") in allowed)


def canonical_registry_tag(value: str | None, *, statuses: Iterable[str] | None = None, root: Path = ROOT) -> str | None:
    canonical = canonicalize_tag(value)
    if canonical is None:
        return None
    registry = locale_registry(root)
    allowed = set(statuses) if statuses is not None else None
    for tag, entry in registry.items():
        if tag.casefold() == canonical.casefold() and (allowed is None or entry.get("status") in allowed):
            return tag
    return None


def match_registry_locale(values: Iterable[str], *, statuses: Iterable[str] = ("released",), fallback: str | None = None, root: Path = ROOT) -> str:
    registry = locale_registry(root)
    allowed = set(statuses)
    candidates = [tag for tag, entry in registry.items() if entry.get("status") in allowed]
    for value in values:
        canonical = canonicalize_tag(value)
        if canonical is None:
            continue
        exact = next((tag for tag in candidates if tag.casefold() == canonical.casefold()), None)
        if exact:
            return exact
        parts = canonical.split("-")
        primary = parts[0]
        script = requested_script(canonical)
        if script:
            language_script = f"{primary}-{script}"
            matched = next((tag for tag in candidates if tag.casefold() == language_script.casefold()), None)
            if matched:
                return matched
            scriptless = next(
                (
                    tag
                    for tag in candidates
                    if tag.split("-", 1)[0].casefold() == primary.casefold()
                    and not (len(tag.split("-")) >= 2 and len(tag.split("-")[1]) == 4)
                ),
                None,
            )
            if scriptless:
                return scriptless
            continue
        matched = next((tag for tag in candidates if tag.split("-", 1)[0].casefold() == primary.casefold()), None)
        if matched:
            return matched
    default = fallback or load_locale_contract(root / "docs/architecture/locale-release.contract.json")["decision"]["default_locale"]
    matched_default = canonical_registry_tag(default, statuses=allowed, root=root)
    if matched_default:
        return matched_default
    if candidates:
        return candidates[0]
    # Keep parity with the browser runtime: an empty status class falls back to
    # the configured default instead of crashing.
    return canonical_registry_tag(default, root=root) or canonicalize_tag(default) or "en"


def locale_entry(locale: str, root: Path = ROOT) -> dict:
    tag = canonical_registry_tag(locale, root=root)
    if tag is None:
        raise KeyError(f"unknown interface locale: {locale!r}")
    return locale_registry(root)[tag]


def surface_file(locale: str, surface: str, root: Path = ROOT) -> str:
    entry = locale_entry(locale, root)
    try:
        return entry["surface_files"][surface]
    except KeyError as exc:
        raise KeyError(f"locale {locale!r} has no {surface!r} surface") from exc
