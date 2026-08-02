#!/usr/bin/env python3
"""Validate Commonworld's staged interface-language release contract."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.catalog_summary_specificity import (
    SummarySpecificityContractError,
    load_contract as load_summary_specificity_contract,
    validate_contract as validate_summary_specificity_contract,
)

CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
REGISTRY_MODULE_PATH = ROOT / "assets/commonworld-locale-registry.mjs"
PACK_PATH = ROOT / "assets/locales/wave1-candidates.json"

ARRAY_EXPORT_RE = re.compile(
    r"export const (?P<name>[A-Z_]+) = Object\.freeze\((?P<value>\[[^\n]*\])\);"
)
SCALAR_EXPORT_RE = re.compile(
    r"export const (?P<name>DEFAULT_LOCALE|FALLBACK_LOCALE) = (?P<value>\"[^\"]+\");"
)
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_]+\}")
BIDI_CONTROL_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")


class LocaleReleaseContractError(ValueError):
    """Raised when the release contract cannot be read or parsed."""


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocaleReleaseContractError(
            f"cannot read locale release contract: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise LocaleReleaseContractError(
            "locale release contract root must be an object"
        )
    return value


def runtime_locale_state(
    root: Path = ROOT,
) -> tuple[list[str], list[str], list[str], str, str]:
    path = root / REGISTRY_MODULE_PATH.relative_to(ROOT)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LocaleReleaseContractError(
            f"cannot read generated locale registry module: {exc}"
        ) from exc
    arrays = {
        match.group("name"): json.loads(match.group("value"))
        for match in ARRAY_EXPORT_RE.finditer(source)
    }
    scalars = {
        match.group("name"): json.loads(match.group("value"))
        for match in SCALAR_EXPORT_RE.finditer(source)
    }
    required_arrays = {
        "KNOWN_UI_LOCALES",
        "RELEASED_LOCALES",
        "CANDIDATE_LOCALES",
    }
    if not required_arrays.issubset(arrays) or {
        "DEFAULT_LOCALE",
        "FALLBACK_LOCALE",
    } - scalars.keys():
        raise LocaleReleaseContractError(
            "generated runtime locale declarations are missing or changed shape"
        )
    return (
        arrays["RELEASED_LOCALES"],
        arrays["CANDIDATE_LOCALES"],
        arrays["KNOWN_UI_LOCALES"],
        scalars["DEFAULT_LOCALE"],
        scalars["FALLBACK_LOCALE"],
    )


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _safe_path(root: Path, relative: str, label: str) -> tuple[Path | None, str | None]:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, f"{label} escapes repository root"
    return candidate, None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _surface_errors(
    tag: str,
    entry: dict[str, Any],
    root: Path,
    *,
    candidate: bool,
) -> list[str]:
    errors: list[str] = []
    surfaces = entry.get("surface_files")
    if not isinstance(surfaces, dict):
        return [f"locale {tag} must define surface_files"]
    _require(
        errors,
        set(surfaces) == {"index", "method", "proposal"},
        f"locale {tag} must cover index, method and proposal surfaces",
    )
    direction = entry.get("direction")
    for surface, relative in surfaces.items():
        if not isinstance(relative, str):
            errors.append(f"surface path for {tag}/{surface} must be a string")
            continue
        path, path_error = _safe_path(
            root, relative, f"surface path for {tag}/{surface}"
        )
        if path_error:
            errors.append(path_error)
            continue
        assert path is not None
        if not path.is_file():
            errors.append(f"locale surface is missing: {tag}/{surface} -> {relative}")
            continue
        markup = path.read_text(encoding="utf-8")
        _require(
            errors,
            bool(
                re.search(
                    rf"<html\b[^>]*\blang=['\"]{re.escape(tag)}['\"]",
                    markup,
                    re.IGNORECASE,
                )
            ),
            f"surface {relative} does not declare lang={tag}",
        )
        if candidate:
            _require(
                errors,
                bool(
                    re.search(
                        rf"<html\b[^>]*\bdir=['\"]{re.escape(str(direction))}['\"]",
                        markup,
                        re.IGNORECASE,
                    )
                ),
                f"candidate surface {relative} does not declare dir={direction}",
            )
            _require(
                errors,
                'meta name="robots" content="noindex,nofollow"' in markup,
                f"candidate surface {relative} is not noindex,nofollow",
            )
            _require(
                errors,
                'class="locale-candidate-banner"' in markup,
                f"candidate surface {relative} lacks the candidate notice",
            )
            _require(
                errors,
                "[missing:" not in markup,
                f"candidate surface {relative} contains missing-translation markers",
            )
    return errors


def _release_evidence_errors(
    tag: str,
    entry: dict[str, Any],
    contract: dict[str, Any],
    root: Path,
    required_surfaces: set[str],
) -> list[str]:
    errors: list[str] = []
    pointer = entry.get("release_evidence")
    if not isinstance(pointer, dict):
        return [f"released non-baseline locale {tag} must define release_evidence"]
    if set(pointer) != {"path", "sha256"}:
        return [f"release evidence pointer for {tag} must contain path and sha256"]
    relative = pointer.get("path")
    digest = pointer.get("sha256")
    if not (
        isinstance(relative, str)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        return [f"release evidence pointer is invalid for {tag}"]
    path, path_error = _safe_path(root, relative, f"release evidence for {tag}")
    if path_error:
        return [path_error]
    assert path is not None
    if not path.is_file():
        return [f"release evidence artifact is missing for {tag}"]
    if _sha256(path) != digest:
        return [f"release evidence artifact is stale for {tag}: sha256 mismatch"]
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"release evidence artifact is invalid JSON for {tag}: {exc}"]
    if not isinstance(evidence, dict):
        return [f"release evidence artifact root must be an object for {tag}"]
    _require(
        errors,
        evidence.get("schema_version") == 1,
        f"release evidence schema_version must be 1 for {tag}",
    )
    _require(
        errors,
        evidence.get("kind") == "commonworld.ui_locale_release_evidence",
        f"release evidence kind is invalid for {tag}",
    )
    _require(
        errors,
        evidence.get("locale") == tag,
        f"release evidence locale mismatch for {tag}",
    )
    revision = evidence.get("source_revision")
    _require(
        errors,
        isinstance(revision, str)
        and re.fullmatch(r"[0-9a-f]{40,64}", revision) is not None,
        f"release evidence source_revision is invalid for {tag}",
    )
    hashes = evidence.get("surface_sha256")
    surfaces = entry.get("surface_files")
    valid_hash_scope = (
        isinstance(hashes, dict)
        and isinstance(surfaces, dict)
        and set(hashes) == set(surfaces)
    )
    _require(
        errors,
        valid_hash_scope,
        f"release evidence surface hash scope mismatch for {tag}",
    )
    if valid_hash_scope:
        assert isinstance(hashes, dict) and isinstance(surfaces, dict)
        for surface, relative_surface in surfaces.items():
            surface_path = root / relative_surface
            _require(
                errors,
                isinstance(hashes.get(surface), str)
                and surface_path.is_file()
                and _sha256(surface_path) == hashes[surface],
                f"release evidence surface digest is stale for {tag}/{surface}",
            )
    results = evidence.get("gate_results")
    _require(
        errors,
        isinstance(results, dict),
        f"release evidence gate_results are missing for {tag}",
    )
    if isinstance(results, dict):
        _require(
            errors,
            set(results.get("required_surfaces_passed", [])) == required_surfaces,
            f"release evidence required surface outcomes are incomplete for {tag}",
        )
        expected = {
            "translation_coverage_ratio": 1.0,
            "untranslated_ui_markers": 0,
            "missing_runtime_keys": 0,
            "machine_translation_only": False,
            "independent_language_review_passed": True,
            "keyboard_and_screen_reader_review_passed": True,
            "browser_smoke_passed": True,
            "state_preservation_smoke_passed": True,
            "directional_layout_review": (
                "passed" if entry.get("direction") == "rtl" else "not_required"
            ),
            "mixed_script_review": (
                "passed" if entry.get("direction") == "rtl" else "not_required"
            ),
        }
        for field, expected_value in expected.items():
            _require(
                errors,
                results.get(field) == expected_value,
                f"release evidence gate {field} did not pass for {tag}",
            )
    receipt_contract = contract.get("release_evidence", {})
    required_receipts = set(receipt_contract.get("required_receipts", []))
    if entry.get("direction") == "rtl":
        required_receipts.update(
            receipt_contract.get("rtl_additional_receipts", [])
        )
    receipts = evidence.get("evidence_receipts")
    _require(
        errors,
        isinstance(receipts, dict) and set(receipts) == required_receipts,
        f"release evidence receipts are incomplete for {tag}",
    )
    if isinstance(receipts, dict):
        for gate_name in required_receipts:
            receipt = receipts.get(gate_name)
            valid_receipt = (
                isinstance(receipt, dict)
                and set(receipt) == {"source", "sha256"}
                and isinstance(receipt.get("source"), str)
                and bool(receipt["source"].strip())
                and isinstance(receipt.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) is not None
            )
            _require(
                errors,
                valid_receipt,
                f"release evidence receipt is invalid for {tag}/{gate_name}",
            )
    return errors


def _candidate_evidence_errors(
    tag: str,
    entry: dict[str, Any],
    root: Path,
    pack_digest: str | None,
) -> list[str]:
    errors: list[str] = []
    relative = entry.get("candidate_evidence_path")
    if not isinstance(relative, str):
        return [f"candidate locale {tag} must define candidate_evidence_path"]
    path, path_error = _safe_path(root, relative, f"candidate evidence for {tag}")
    if path_error:
        return [path_error]
    assert path is not None
    if not path.is_file():
        return [f"candidate evidence artifact is missing for {tag}"]
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"candidate evidence artifact is invalid JSON for {tag}"]
    _require(
        errors,
        isinstance(evidence, dict),
        f"candidate evidence artifact root must be an object for {tag}",
    )
    if not isinstance(evidence, dict):
        return errors
    expected = {
        "schema_version": 1,
        "kind": "commonworld.ui_locale_candidate_evidence",
        "locale": tag,
        "status": "candidate",
        "release_ready": False,
    }
    for field, value in expected.items():
        _require(
            errors,
            evidence.get(field) == value,
            f"candidate evidence {field} is invalid for {tag}",
        )
    _require(
        errors,
        pack_digest is not None
        and evidence.get("source_pack_sha256") == pack_digest,
        f"candidate evidence pack digest is stale for {tag}",
    )
    review = evidence.get("independent_language_review")
    _require(
        errors,
        isinstance(review, dict)
        and review.get("status") == "pending"
        and not review.get("reviewer"),
        f"candidate evidence must record pending independent language review for {tag}",
    )
    technical = evidence.get("technical_gates")
    _require(
        errors,
        isinstance(technical, dict),
        f"candidate evidence technical_gates are missing for {tag}",
    )
    if isinstance(technical, dict):
        required = {
            "translation_structure",
            "runtime_key_coverage",
            "surface_generation",
            "noindex_enforcement",
            "bcp47_matching",
            "state_preservation",
        }
        if entry.get("direction") == "rtl":
            required.update({"rtl_structure", "mixed_script_structure"})
        _require(
            errors,
            set(technical) == required,
            f"candidate evidence technical gate scope mismatch for {tag}",
        )
        _require(
            errors,
            all(value == "passed" for value in technical.values()),
            f"candidate technical gates have not all passed for {tag}",
        )
    blockers = evidence.get("activation_blockers")
    _require(
        errors,
        isinstance(blockers, list)
        and "independent_language_review" in blockers,
        f"candidate evidence must keep independent language review as a blocker for {tag}",
    )
    _require(
        errors,
        "release_evidence" not in evidence,
        f"candidate evidence must not masquerade as release evidence for {tag}",
     )
    return errors


def _pack_errors(
    contract: dict[str, Any],
    root: Path,
) -> tuple[list[str], str | None]:
    errors: list[str] = []
    path = root / PACK_PATH.relative_to(ROOT)
    if not path.is_file():
        return ["Wave-1 candidate locale pack is missing"], None
    digest = _sha256(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Wave-1 candidate locale pack is invalid JSON: {exc}"], digest
    _require(errors, payload.get("schema_version") == 1, "candidate pack schema_version must be 1")
    _require(errors, payload.get("source_locale") == "en", "candidate pack source_locale must be en")
    _require(errors, payload.get("candidate_only") is True, "candidate pack must be candidate_only")
    locales = payload.get("locales")
    if not isinstance(locales, dict):
        return errors + ["candidate pack locales must be an object"], digest
    registry = contract.get("locale_registry", {})
    expected = {
        tag
        for tag, entry in registry.items()
        if isinstance(entry, dict) and entry.get("status") == "candidate"
    }
    _require(
        errors,
        set(locales) == expected,
        "candidate pack locales must exactly match candidate registry entries",
    )
    required_sections = {
        "meta",
        "ui",
        "themes",
        "static",
        "shell",
        "method",
        "proposal",
        "proposal_runtime",
        "taxonomy",
        "actions",
    }
    for tag, pack in locales.items():
        _require(
            errors,
            isinstance(pack, dict) and set(pack) == required_sections,
            f"candidate pack section scope mismatch for {tag}",
        )
        if not isinstance(pack, dict):
            continue
        meta = pack.get("meta")
        _require(
            errors,
            isinstance(meta, dict)
            and meta.get("draft_origin") == "machine_translation_assisted"
            and meta.get("independent_language_review") == "pending",
            f"candidate pack provenance is invalid for {tag}",
        )
        for section in required_sections - {"meta"}:
            values = pack.get(section)
            _require(
                errors,
                isinstance(values, dict)
                and all(isinstance(value, str) and value.strip() for value in values.values()),
                f"candidate pack section {tag}/{section} must contain non-empty strings",
            )
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                if BIDI_CONTROL_RE.search(value):
                    errors.append(
                        f"candidate pack contains forbidden bidi control: {tag}/{section}/{key}"
                    )
        if tag == "ar":
            joined = " ".join(
                value
                for section, values in pack.items()
                if section != "meta" and isinstance(values, dict)
                for value in values.values()
            )
            _require(
                errors,
                bool(re.search(r"[\u0600-\u06ff]", joined)),
                "Arabic candidate pack must contain Arabic script",
            )
    return errors, digest


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
    evidence_contract = contract.get("release_evidence")
    for value, name in (
        (decision, "decision"),
        (registry, "locale_registry"),
        (rollout, "rollout"),
        (tag_policy, "tag_policy"),
        (content_policy, "content_language_policy"),
        (gate, "release_gate"),
        (evidence_contract, "release_evidence"),
    ):
        _require(errors, isinstance(value, dict), f"{name} must be an object")
    if errors:
        return errors
    assert isinstance(decision, dict)
    assert isinstance(registry, dict)
    assert isinstance(rollout, dict)
    assert isinstance(tag_policy, dict)
    assert isinstance(content_policy, dict)
    assert isinstance(gate, dict)
    assert isinstance(evidence_contract, dict)

    released = decision.get("released_locales")
    baseline = decision.get("baseline_locales")
    released_tags = (
        list(released)
        if isinstance(released, list) and all(isinstance(tag, str) for tag in released)
        else []
    )
    baseline_tags = (
        list(baseline)
        if isinstance(baseline, list) and all(isinstance(tag, str) for tag in baseline)
        else []
    )
    _require(errors, bool(released_tags), "released_locales must be a non-empty string list")
    _require(errors, len(released_tags) == len(set(released_tags)), "released_locales must not contain duplicates")
    _require(errors, bool(baseline_tags), "baseline_locales must be a non-empty string list")
    _require(errors, set(baseline_tags).issubset(released_tags), "baseline_locales must be a subset of released_locales")

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
        tag_policy.get("matching_order")
        == ["exact", "language_script", "primary_language", "default_locale"],
        "matching order must prefer exact and script-aware matches before primary-language fallback",
    )

    pack_errors, pack_digest = _pack_errors(contract, root)
    errors.extend(pack_errors)
    candidate_tags: list[str] = []
    planned_tags: list[str] = []
    for tag, entry in registry.items():
        _require(
            errors,
            isinstance(tag, str) and bool(tag_pattern.fullmatch(tag)),
            f"locale tag is not canonical: {tag!r}",
        )
        _require(errors, isinstance(entry, dict), f"locale registry entry must be an object: {tag}")
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        _require(
            errors,
            status in {"released", "candidate", "planned"},
            f"locale {tag} has invalid status",
        )
        _require(errors, entry.get("direction") in {"ltr", "rtl"}, f"locale {tag} has invalid direction")
        for field in ("native_name", "english_name"):
            _require(
                errors,
                isinstance(entry.get(field), str) and bool(entry[field].strip()),
                f"locale {tag} must define non-empty {field}",
            )
        if status == "released":
            _require(errors, tag in released_tags, f"released registry locale {tag} is absent from released_locales")
            errors.extend(_surface_errors(tag, entry, root, candidate=False))
            if tag in baseline_tags:
                _require(errors, "release_evidence" not in entry, f"baseline locale {tag} must not claim post-baseline release evidence")
            else:
                errors.extend(
                    _release_evidence_errors(
                        tag, entry, contract, root, set(gate.get("required_surfaces", []))
                    )
                )
        elif status == "candidate":
            candidate_tags.append(tag)
            _require(errors, tag not in released_tags, f"candidate locale {tag} must not be released")
            _require(errors, "release_evidence" not in entry, f"candidate locale {tag} must not claim release evidence")
            errors.extend(_surface_errors(tag, entry, root, candidate=True))
            errors.extend(_candidate_evidence_errors(tag, entry, root, pack_digest))
        else:
            planned_tags.append(tag)
            _require(errors, tag not in released_tags, f"planned locale {tag} must not be released")
            _require(errors, "surface_files" not in entry, f"planned locale {tag} must not claim surfaces")
            _require(errors, "candidate_evidence_path" not in entry, f"planned locale {tag} must not claim candidate evidence")

    for tag in released_tags:
        _require(errors, tag in registry and registry[tag].get("status") == "released", f"released locale {tag} must have released registry status")
    _require(errors, decision.get("default_locale") in released_tags, "default_locale must be released")
    _require(errors, decision.get("fallback_locale") in released_tags, "fallback_locale must be released")

    try:
        runtime_released, runtime_candidates, runtime_known, runtime_default, runtime_fallback = runtime_locale_state(root)
    except LocaleReleaseContractError as exc:
        errors.append(str(exc))
    else:
        _require(errors, runtime_released == released_tags, "runtime released locales must match the contract")
        _require(errors, runtime_candidates == candidate_tags, "runtime candidate locales must match the contract")
        _require(errors, runtime_known == list(registry), "runtime known locales must match registry order")
        _require(errors, runtime_default == decision.get("default_locale"), "runtime default locale must match the contract")
        _require(errors, runtime_fallback == decision.get("fallback_locale"), "runtime fallback locale must match the contract")

    automatic = decision.get("automatic_selection")
    _require(errors, isinstance(automatic, dict), "automatic_selection must be an object")
    if isinstance(automatic, dict):
        _require(
            errors,
            automatic.get("precedence")
            == ["explicit_url", "stored_preference", "browser_language_order", "default_locale"],
            "automatic locale precedence must remain explicit URL, storage, browser order, default",
        )
        _require(errors, automatic.get("geolocation_must_not_influence_locale") is True, "geolocation must not influence locale")
        _require(errors, automatic.get("explicit_surface_must_resist_stored_override") is True, "explicit locale surfaces must resist stored overrides")
        _require(errors, automatic.get("preserve_query_and_fragment") is True, "locale navigation must preserve query and fragment")

    wave_1 = rollout.get("wave_1")
    wave_2 = rollout.get("wave_2")
    wave_1_tags = list(wave_1) if isinstance(wave_1, list) and all(isinstance(tag, str) for tag in wave_1) else []
    wave_2_tags = list(wave_2) if isinstance(wave_2, list) and all(isinstance(tag, str) for tag in wave_2) else []
    rollout_tags = wave_1_tags + wave_2_tags
    _require(errors, len(rollout_tags) == len(set(rollout_tags)), "rollout waves must not contain duplicates")
    _require(errors, set(rollout_tags) == set(candidate_tags + planned_tags), "rollout waves must cover every non-released locale exactly once")
    _require(errors, set(wave_1_tags) == set(candidate_tags), "Wave 1 must exactly contain current candidate locales")
    _require(errors, set(wave_2_tags) == set(planned_tags), "Wave 2 must exactly contain current planned locales")
    for field in (
        "promotion_is_evidence_bound",
        "wave_order_may_follow_observed_demand",
        "planned_locales_must_not_be_selectable",
        "candidate_locales_must_not_be_selectable",
        "candidate_surfaces_must_be_noindex",
    ):
        _require(errors, rollout.get(field) is True, f"rollout must require {field}")

    for field in (
        "independent_from_interface_locales",
        "valid_bcp47_tags_allowed",
        "must_not_be_rewritten_to_interface_locale",
        "unknown_language_must_remain_explicit",
    ):
        _require(errors, content_policy.get(field) is True, f"content language policy must require {field}")

    required_surfaces = {
        "globe",
        "text",
        "method",
        "proposal",
        "runtime_labels",
        "catalog_localization",
        "metadata_and_navigation",
    }
    _require(errors, set(gate.get("required_surfaces", [])) == required_surfaces, "release gate must cover every public language surface")
    _require(errors, gate.get("translation_coverage_ratio") == 1.0, "translation coverage must be 100%")
    _require(errors, gate.get("untranslated_ui_markers_max") == 0, "untranslated UI markers must be zero")
    _require(errors, gate.get("missing_runtime_keys_max") == 0, "missing runtime keys must be zero")
    _require(
        errors,
        gate.get("catalog_summary_specificity_policy_required") is True,
        "release gate must require a locale-aware catalog summary specificity policy",
    )
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
    _require(errors, registry.get("ar", {}).get("direction") == "rtl", "Arabic must exercise the RTL contract")

    expected_evidence = {
        "baseline_locales_may_precede_digest_receipts": True,
        "required_for_non_baseline_release": True,
        "path_template": "docs/evidence/locale-releases/{locale}.json",
        "digest_algorithm": "sha256",
        "registry_pointer_field": "release_evidence",
        "required_receipts": [
            "independent_language_review",
            "keyboard_and_screen_reader_review",
            "browser_smoke",
            "state_preservation_smoke",
        ],
        "rtl_additional_receipts": [
            "directional_layout_review",
            "mixed_script_review",
        ],
        "candidate_evidence_path_template": "docs/evidence/locale-candidates/{locale}.json",
        "candidate_evidence_is_not_release_evidence": True,
    }
    _require(
        errors,
        evidence_contract == expected_evidence,
        "release_evidence contract does not match the fail-closed digest-bound schema",
    )

    try:
        summary_specificity_contract = load_summary_specificity_contract(root)
    except SummarySpecificityContractError as exc:
        errors.append(str(exc))
    else:
        errors.extend(
            validate_summary_specificity_contract(
                summary_specificity_contract, released_tags
            )
        )
        _require(
            errors,
            summary_specificity_contract.get("canonical_locale")
            == decision.get("fallback_locale"),
            "summary specificity canonical_locale must match fallback_locale",
        )

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
