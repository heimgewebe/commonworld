#!/usr/bin/env python3
"""Validate Commonworld's staged interface-language release contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
I18N_MODULE_PATH = ROOT / "assets/commonworld-i18n.mjs"

SUPPORTED_RE = re.compile(
    r"export const SUPPORTED_LOCALES = Object\.freeze\(\[(?P<body>.*?)\]\);",
    re.DOTALL,
)
DEFAULT_RE = re.compile(r"export const DEFAULT_LOCALE = ['\"](?P<value>[^'\"]+)['\"];")
FALLBACK_RE = re.compile(r"export const FALLBACK_LOCALE = ['\"](?P<value>[^'\"]+)['\"];")
QUOTED_VALUE_RE = re.compile(r"['\"](?P<value>[^'\"]+)['\"]")


class LocaleReleaseContractError(ValueError):
    """Raised when the release contract cannot be read or parsed."""


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocaleReleaseContractError(f"cannot read locale release contract: {exc}") from exc
    if not isinstance(value, dict):
        raise LocaleReleaseContractError("locale release contract root must be an object")
    return value


def runtime_locale_state(root: Path = ROOT) -> tuple[list[str], str, str]:
    path = root / I18N_MODULE_PATH.relative_to(ROOT)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LocaleReleaseContractError(f"cannot read runtime i18n module: {exc}") from exc

    supported_match = SUPPORTED_RE.search(source)
    default_match = DEFAULT_RE.search(source)
    fallback_match = FALLBACK_RE.search(source)
    if not supported_match or not default_match or not fallback_match:
        raise LocaleReleaseContractError("runtime locale declarations are missing or changed shape")

    supported = [match.group("value") for match in QUOTED_VALUE_RE.finditer(supported_match.group("body"))]
    if not supported:
        raise LocaleReleaseContractError("runtime supported locale list must not be empty")
    return supported, default_match.group("value"), fallback_match.group("value")


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _canonical_ui_tag(tag: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.fullmatch(tag))


def validate_contract(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    _require(errors, contract.get("schema_version") == 1, "schema_version must be 1")
    _require(
        errors,
        contract.get("kind") == "commonworld.ui_locale_release_contract",
        "kind must be commonworld.ui_locale_release_contract",
    )

    decision = contract.get("decision")
    registry = contract.get("locale_registry")
    rollout = contract.get("rollout")
    tag_policy = contract.get("tag_policy")
    content_policy = contract.get("content_language_policy")
    gate = contract.get("release_gate")

    _require(errors, isinstance(decision, dict), "decision must be an object")
    _require(errors, isinstance(registry, dict), "locale_registry must be an object")
    _require(errors, isinstance(rollout, dict), "rollout must be an object")
    _require(errors, isinstance(tag_policy, dict), "tag_policy must be an object")
    _require(errors, isinstance(content_policy, dict), "content_language_policy must be an object")
    _require(errors, isinstance(gate, dict), "release_gate must be an object")
    if errors:
        return errors

    assert isinstance(decision, dict)
    assert isinstance(registry, dict)
    assert isinstance(rollout, dict)
    assert isinstance(tag_policy, dict)
    assert isinstance(content_policy, dict)
    assert isinstance(gate, dict)

    released = decision.get("released_locales")
    released_is_string_list = isinstance(released, list) and all(isinstance(tag, str) for tag in released)
    _require(errors, released_is_string_list, "released_locales must be a string list")
    released_tags = list(released) if released_is_string_list else []
    _require(errors, len(released_tags) == len(set(released_tags)), "released_locales must not contain duplicates")

    pattern_text = tag_policy.get("canonical_ui_tag_pattern")
    try:
        tag_pattern = re.compile(pattern_text) if isinstance(pattern_text, str) else re.compile(r"(?!)")
    except re.error as exc:
        errors.append(f"canonical_ui_tag_pattern is invalid: {exc}")
        tag_pattern = re.compile(r"(?!)")

    _require(errors, tag_policy.get("standard") == "BCP 47", "tag policy must name BCP 47")
    _require(errors, tag_policy.get("case_insensitive_input") is True, "locale input must be case-insensitive")
    _require(errors, tag_policy.get("canonical_output_required") is True, "canonical locale output must be required")
    _require(errors, tag_policy.get("script_and_region_must_be_preserved") is True, "script and region subtags must be preserved")
    _require(
        errors,
        tag_policy.get("matching_order") == ["exact", "language_script", "primary_language", "default_locale"],
        "matching order must prefer exact and script-aware matches before primary-language fallback",
    )

    registry_tags = list(registry)
    for tag, entry in registry.items():
        _require(errors, isinstance(tag, str) and _canonical_ui_tag(tag, tag_pattern), f"locale tag is not canonical for this registry: {tag!r}")
        _require(errors, isinstance(entry, dict), f"locale registry entry must be an object: {tag}")
        if not isinstance(entry, dict):
            continue
        _require(errors, entry.get("status") in {"released", "planned"}, f"locale {tag} has invalid status")
        _require(errors, entry.get("direction") in {"ltr", "rtl"}, f"locale {tag} has invalid direction")
        _require(
            errors,
            isinstance(entry.get("native_name"), str) and bool(entry["native_name"].strip()),
            f"locale {tag} must define a non-empty native_name",
        )
        _require(
            errors,
            isinstance(entry.get("english_name"), str) and bool(entry["english_name"].strip()),
            f"locale {tag} must define a non-empty english_name",
        )
        if entry.get("status") == "released":
            _require(errors, tag in released_tags, f"released registry locale {tag} is absent from released_locales")
            surfaces = entry.get("surface_files")
            _require(errors, isinstance(surfaces, dict), f"released locale {tag} must define surface_files")
            if isinstance(surfaces, dict):
                _require(errors, set(surfaces) == {"index", "method", "proposal"}, f"released locale {tag} must cover index, method and proposal surfaces")
                for surface, relative_path in surfaces.items():
                    _require(errors, isinstance(relative_path, str), f"surface path for {tag}/{surface} must be a string")
                    if not isinstance(relative_path, str):
                        continue
                    page_path = root / relative_path
                    _require(errors, page_path.is_file(), f"released locale surface is missing: {tag}/{surface} -> {relative_path}")
                    if page_path.is_file():
                        markup = page_path.read_text(encoding="utf-8")
                        language_declaration = re.compile(
                            rf"<html\b[^>]*\blang=['\"]{re.escape(tag)}['\"]",
                            re.IGNORECASE,
                        )
                        _require(
                            errors,
                            bool(language_declaration.search(markup)),
                            f"surface {relative_path} does not declare lang={tag}",
                        )
        else:
            _require(errors, tag not in released_tags, f"planned locale {tag} must not be listed as released")
            _require(errors, "surface_files" not in entry, f"planned locale {tag} must not claim released surfaces")

    for tag in released_tags:
        _require(errors, tag in registry, f"released locale {tag} is absent from locale_registry")
        if tag in registry and isinstance(registry[tag], dict):
            _require(errors, registry[tag].get("status") == "released", f"released locale {tag} must have released status")

    _require(errors, decision.get("default_locale") in released_tags, "default_locale must be released")
    _require(errors, decision.get("fallback_locale") in released_tags, "fallback_locale must be released")

    try:
        runtime_supported, runtime_default, runtime_fallback = runtime_locale_state(root)
    except LocaleReleaseContractError as exc:
        errors.append(str(exc))
    else:
        _require(errors, runtime_supported == released_tags, "runtime SUPPORTED_LOCALES must exactly match released_locales in order")
        _require(errors, runtime_default == decision.get("default_locale"), "runtime DEFAULT_LOCALE must match the contract")
        _require(errors, runtime_fallback == decision.get("fallback_locale"), "runtime FALLBACK_LOCALE must match the contract")

    automatic = decision.get("automatic_selection")
    _require(errors, isinstance(automatic, dict), "automatic_selection must be an object")
    if isinstance(automatic, dict):
        _require(
            errors,
            automatic.get("precedence") == ["explicit_url", "stored_preference", "browser_language_order", "default_locale"],
            "automatic locale precedence must remain explicit URL, storage, browser order, default",
        )
        _require(errors, automatic.get("geolocation_must_not_influence_locale") is True, "geolocation must not influence locale")
        _require(errors, automatic.get("explicit_surface_must_resist_stored_override") is True, "explicit locale surfaces must resist stored overrides")
        _require(errors, automatic.get("preserve_query_and_fragment") is True, "locale navigation must preserve query and fragment")

    wave_1 = rollout.get("wave_1")
    wave_2 = rollout.get("wave_2")
    wave_1_is_string_list = isinstance(wave_1, list) and all(isinstance(tag, str) for tag in wave_1)
    wave_2_is_string_list = isinstance(wave_2, list) and all(isinstance(tag, str) for tag in wave_2)
    _require(errors, wave_1_is_string_list, "wave_1 must be a string list")
    _require(errors, wave_2_is_string_list, "wave_2 must be a string list")
    wave_1_tags = list(wave_1) if wave_1_is_string_list else []
    wave_2_tags = list(wave_2) if wave_2_is_string_list else []
    planned = [*wave_1_tags, *wave_2_tags]
    _require(errors, len(planned) == len(set(planned)), "rollout waves must not contain duplicate locales")
    _require(errors, set(planned).isdisjoint(released_tags), "released locales must not remain in rollout waves")
    _require(errors, set(planned).issubset(registry_tags), "all rollout locales must exist in locale_registry")
    planned_registry_tags = {
        tag for tag, entry in registry.items()
        if isinstance(entry, dict) and entry.get("status") == "planned"
    }
    _require(errors, set(planned) == planned_registry_tags, "rollout waves must cover every planned locale exactly once")
    for tag in planned:
        entry = registry.get(tag)
        if isinstance(entry, dict):
            _require(errors, entry.get("status") == "planned", f"rollout locale {tag} must remain planned until all gates pass")
    _require(errors, rollout.get("promotion_is_evidence_bound") is True, "locale promotion must be evidence-bound")
    _require(errors, rollout.get("wave_order_may_follow_observed_demand") is True, "wave order changes must follow observed demand")
    _require(errors, rollout.get("planned_locales_must_not_be_selectable") is True, "planned locales must not be selectable")

    _require(errors, content_policy.get("independent_from_interface_locales") is True, "content languages must be independent from interface locales")
    _require(errors, content_policy.get("valid_bcp47_tags_allowed") is True, "valid BCP 47 content tags must be allowed")
    _require(errors, content_policy.get("must_not_be_rewritten_to_interface_locale") is True, "content tags must not be rewritten to the interface locale")
    _require(errors, content_policy.get("unknown_language_must_remain_explicit") is True, "unknown content language must remain explicit")

    required_surfaces = {"globe", "text", "method", "proposal", "runtime_labels", "catalog_localization", "metadata_and_navigation"}
    surfaces = gate.get("required_surfaces")
    surfaces_are_strings = isinstance(surfaces, list) and all(isinstance(surface, str) for surface in surfaces)
    _require(
        errors,
        surfaces_are_strings and set(surfaces) == required_surfaces,
        "release gate must cover every public language surface",
    )
    _require(errors, gate.get("translation_coverage_ratio") == 1.0, "translation coverage must be 100%")
    _require(errors, gate.get("untranslated_ui_markers_max") == 0, "untranslated UI markers must be zero")
    _require(errors, gate.get("missing_runtime_keys_max") == 0, "missing runtime keys must be zero")
    for field in (
        "machine_translation_only_forbidden",
        "independent_language_review_required",
        "keyboard_and_screen_reader_review_required",
        "browser_smoke_required",
        "state_preservation_smoke_required",
        "production_activation_requires_all_checks",
    ):
        _require(errors, gate.get(field) is True, f"release gate must require {field}")
    _require(errors, gate.get("directional_layout_review_for") == ["rtl"], "RTL locales must require directional layout review")
    ar_entry = registry.get("ar")
    _require(errors, isinstance(ar_entry, dict) and ar_entry.get("direction") == "rtl", "Arabic must exercise the RTL contract")

    return errors


def main() -> int:
    try:
        contract = load_contract()
        errors = validate_contract(contract)
    except LocaleReleaseContractError as exc:
        print(f"locale release contract: FAIL: {exc}")
        return 1
    if errors:
        print("locale release contract: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("locale release contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
