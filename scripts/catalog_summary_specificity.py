"""Locale-aware specificity checks for public catalogue summaries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("contracts/commonworld/catalog-summary-specificity.contract.json")


class SummarySpecificityContractError(ValueError):
    """Raised when the summary-specificity contract cannot be read."""


def load_contract(root: Path = ROOT) -> dict[str, Any]:
    path = root / CONTRACT_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SummarySpecificityContractError(
            f"cannot read catalogue summary specificity contract: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SummarySpecificityContractError(
            "catalogue summary specificity contract root must be an object"
        )
    return value


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _specific_context_named(summary: str, policy: dict[str, Any]) -> bool:
    markers = policy.get("specificity_markers")
    if not isinstance(markers, dict):
        return False
    actors = markers.get("actor_patterns")
    mechanisms = markers.get("mechanism_patterns")
    if not isinstance(actors, list) or not isinstance(mechanisms, list):
        return False
    try:
        actor_named = any(
            isinstance(pattern, str)
            and re.search(pattern, summary, re.IGNORECASE) is not None
            for pattern in actors
        )
        mechanism_named = any(
            isinstance(pattern, str)
            and re.search(pattern, summary, re.IGNORECASE) is not None
            for pattern in mechanisms
        )
    except re.error:
        return False
    return actor_named and mechanism_named


def _rule_matches(
    summary: str, rule: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    if rule.get("match") != "casefolded_literal":
        return []
    if (
        rule.get("allow_when_actor_and_mechanism_are_named") is True
        and _specific_context_named(summary, policy)
    ):
        return []
    folded = _normalized(summary)
    phrases = rule.get("phrases")
    if not isinstance(phrases, list):
        return []
    matched = [
        phrase
        for phrase in phrases
        if isinstance(phrase, str) and _normalized(phrase) in folded
    ]
    return [
        phrase
        for phrase in matched
        if not any(
            _normalized(phrase) != _normalized(other)
            and _normalized(phrase) in _normalized(other)
            for other in matched
        )
    ]


def specificity_errors(
    record: dict[str, Any],
    locale: str,
    contract: dict[str, Any],
) -> list[str]:
    identifier = record.get("id", "unknown")
    summary = record.get("summary")
    if not isinstance(summary, str):
        return []
    policies = contract.get("locale_policies")
    policy = policies.get(locale) if isinstance(policies, dict) else None
    if not isinstance(policy, dict):
        # Contract validation reports this once at locale level. Avoid one
        # redundant error per catalogue record.
        return []
    errors: list[str] = []
    rules = policy.get("rules")
    if not isinstance(rules, list):
        # The structural contract error is authoritative and already exact.
        return []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id", "unknown-rule")
        for phrase in _rule_matches(summary, rule, policy):
            errors.append(
                "public catalog project "
                f"{identifier} locale={locale} summary repeats generic Commons framing "
                f"rule={rule_id} matched={phrase!r}"
            )
    return errors


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and bool(item.strip()) for item in value
    ):
        return None
    return list(value)


def validate_contract(
    contract: dict[str, Any],
    released_locales: Iterable[str],
) -> list[str]:
    errors: list[str] = []
    released = list(released_locales)
    if not released or not all(isinstance(locale, str) and locale for locale in released):
        return ["summary specificity released_locales must be a non-empty string list"]
    if len(released) != len(set(released)):
        errors.append("summary specificity released_locales must not contain duplicates")

    if contract.get("schema_version") != 1:
        errors.append("summary specificity schema_version must be 1")
    if contract.get("kind") != "commonworld.catalog_summary_specificity_contract":
        errors.append(
            "summary specificity kind must be commonworld.catalog_summary_specificity_contract"
        )

    canonical_locale = contract.get("canonical_locale")
    if not isinstance(canonical_locale, str) or not canonical_locale:
        errors.append("summary specificity canonical_locale must be a non-empty string")
    elif canonical_locale not in released:
        errors.append(
            "summary specificity canonical_locale must be a released interface locale"
        )

    interpretation = contract.get("interpretation")
    if not isinstance(interpretation, dict):
        errors.append("summary specificity interpretation must be an object")
    else:
        for field in ("goal", "reject_when", "allow_when", "non_goal"):
            value = interpretation.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"summary specificity interpretation must define {field}"
                )

    gate = contract.get("release_gate")
    if not isinstance(gate, dict):
        errors.append("summary specificity release_gate must be an object")
        gate = {}
    if gate.get("every_released_locale_requires_policy") is not True:
        errors.append(
            "summary specificity release gate must require a policy for every released locale"
        )
    if gate.get("planned_locales_may_omit_policy") is not True:
        errors.append(
            "summary specificity release gate must allow planned locales to remain unpublished"
        )

    minimum_rules = gate.get("minimum_rules_per_released_locale")
    minimum_allowed = gate.get("minimum_allowed_examples_per_released_locale")
    minimum_rejected = gate.get("minimum_rejected_examples_per_rule")
    for field, value in (
        ("minimum_rules_per_released_locale", minimum_rules),
        ("minimum_allowed_examples_per_released_locale", minimum_allowed),
        ("minimum_rejected_examples_per_rule", minimum_rejected),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"summary specificity {field} must be a positive integer")
    safe_minimum_rules = minimum_rules if isinstance(minimum_rules, int) else 1
    safe_minimum_allowed = minimum_allowed if isinstance(minimum_allowed, int) else 1
    safe_minimum_rejected = minimum_rejected if isinstance(minimum_rejected, int) else 1

    policies = contract.get("locale_policies")
    if not isinstance(policies, dict):
        errors.append("summary specificity locale_policies must be an object")
        return errors

    for locale in released:
        policy = policies.get(locale)
        if not isinstance(policy, dict):
            errors.append(
                f"summary specificity policy missing for released locale {locale}"
            )
            continue

        markers = policy.get("specificity_markers")
        if not isinstance(markers, dict):
            errors.append(
                f"summary specificity locale {locale} specificity_markers must be an object"
            )
            markers = {}
        for marker_kind in ("actor_patterns", "mechanism_patterns"):
            patterns = _string_list(markers.get(marker_kind))
            if patterns is None:
                errors.append(
                    f"summary specificity locale {locale} {marker_kind} must be a non-empty string list"
                )
                continue
            for pattern in patterns:
                try:
                    re.compile(pattern, re.IGNORECASE)
                except re.error as exc:
                    errors.append(
                        f"summary specificity locale {locale} {marker_kind} contains invalid regex {pattern!r}: {exc}"
                    )

        rules = policy.get("rules")
        if not isinstance(rules, list):
            errors.append(f"summary specificity locale {locale} rules must be a list")
            continue
        if len(rules) < safe_minimum_rules:
            errors.append(
                f"summary specificity locale {locale} must define at least {safe_minimum_rules} rules"
            )

        rule_by_id: dict[str, dict[str, Any]] = {}
        for rule in rules:
            if not isinstance(rule, dict):
                errors.append(
                    f"summary specificity locale {locale} rule must be an object"
                )
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id.strip():
                errors.append(
                    f"summary specificity locale {locale} rule id must be non-empty"
                )
                continue
            if rule_id in rule_by_id:
                errors.append(
                    f"summary specificity locale {locale} rule id is duplicated: {rule_id}"
                )
                continue
            rule_by_id[rule_id] = rule
            if rule.get("match") != "casefolded_literal":
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} must use casefolded_literal"
                )
            if rule.get("allow_when_actor_and_mechanism_are_named") is not True:
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} must preserve concrete actor-and-mechanism statements"
                )
            phrases = _string_list(rule.get("phrases"))
            if phrases is None:
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} phrases must be a non-empty string list"
                )
            elif len({_normalized(phrase) for phrase in phrases}) != len(phrases):
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} phrases must be unique after normalization"
                )
            rationale = rule.get("rationale")
            if not isinstance(rationale, str) or not rationale.strip():
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} must explain its rationale"
                )

        allowed_examples = _string_list(policy.get("allowed_examples"))
        if allowed_examples is None:
            errors.append(
                f"summary specificity locale {locale} allowed_examples must be a non-empty string list"
            )
        else:
            if len(allowed_examples) < safe_minimum_allowed:
                errors.append(
                    f"summary specificity locale {locale} must define at least {safe_minimum_allowed} allowed examples"
                )
            for index, summary in enumerate(allowed_examples, start=1):
                matched = [
                    rule_id
                    for rule_id, rule in rule_by_id.items()
                    if _rule_matches(summary, rule, policy)
                ]
                if matched:
                    errors.append(
                        f"summary specificity locale {locale} allowed example {index} matches forbidden rules: {matched}"
                    )

        rejected_examples = policy.get("rejected_examples")
        if not isinstance(rejected_examples, list):
            errors.append(
                f"summary specificity locale {locale} rejected_examples must be a list"
            )
            rejected_examples = []
        rejected_counts = {rule_id: 0 for rule_id in rule_by_id}
        for index, example in enumerate(rejected_examples, start=1):
            if not isinstance(example, dict):
                errors.append(
                    f"summary specificity locale {locale} rejected example {index} must be an object"
                )
                continue
            summary = example.get("summary")
            expected_rule_id = example.get("expected_rule_id")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(
                    f"summary specificity locale {locale} rejected example {index} must define summary"
                )
                continue
            rule = rule_by_id.get(expected_rule_id)
            if rule is None:
                errors.append(
                    f"summary specificity locale {locale} rejected example {index} references unknown rule {expected_rule_id!r}"
                )
                continue
            if not _rule_matches(summary, rule, policy):
                errors.append(
                    f"summary specificity locale {locale} rejected example {index} does not exercise rule {expected_rule_id}"
                )
                continue
            rejected_counts[expected_rule_id] += 1
        for rule_id, count in rejected_counts.items():
            if count < safe_minimum_rejected:
                errors.append(
                    f"summary specificity locale {locale} rule {rule_id} needs at least {safe_minimum_rejected} rejected examples"
                )

    return errors
