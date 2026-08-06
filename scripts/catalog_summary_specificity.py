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
    passive_mechanisms = markers.get("passive_mechanism_patterns")
    relation = markers.get("relation")
    if (
        not isinstance(actors, list)
        or not isinstance(mechanisms, list)
        or not isinstance(passive_mechanisms, list)
        or not isinstance(relation, dict)
    ):
        return False
    max_distance = relation.get("max_distance_chars")
    allowed_intervening_pattern = relation.get("allowed_intervening_pattern")
    if (
        not isinstance(max_distance, int)
        or isinstance(max_distance, bool)
        or max_distance < 1
        or not isinstance(allowed_intervening_pattern, str)
        or not allowed_intervening_pattern
        or relation.get("actor_must_precede_mechanism") is not True
        or relation.get("same_sentence") is not True
    ):
        return False
    try:
        allowed_intervening = re.compile(
            allowed_intervening_pattern, re.IGNORECASE
        )
        actor_matches = [
            match
            for pattern in actors
            if isinstance(pattern, str)
            for match in re.finditer(pattern, summary, re.IGNORECASE)
        ]
        mechanism_matches = [
            match
            for pattern in mechanisms
            if isinstance(pattern, str)
            for match in re.finditer(pattern, summary, re.IGNORECASE)
        ]
        passive_mechanism_matches = [
            match
            for pattern in passive_mechanisms
            if isinstance(pattern, str)
            for match in re.finditer(pattern, summary, re.IGNORECASE)
        ]
    except re.error:
        return False
    for actor in actor_matches:
        for mechanism in mechanism_matches:
            if actor.end() > mechanism.start():
                continue
            between = summary[actor.end() : mechanism.start()]
            if (
                len(between) > max_distance
                or re.search(r"[.!?]", between)
                or allowed_intervening.fullmatch(between) is None
            ):
                continue
            return True
    for mechanism in passive_mechanism_matches:
        for actor in actor_matches:
            if mechanism.end() > actor.start():
                continue
            between = summary[mechanism.end() : actor.start()]
            if (
                len(between) > max_distance
                or re.search(r"[.!?]", between)
                or allowed_intervening.fullmatch(between) is None
            ):
                continue
            return True
    return False


def _rule_matches(
    summary: str, rule: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    if rule.get("match") != "casefolded_literal":
        return []
    phrases = rule.get("phrases")
    if not isinstance(phrases, list):
        return []
    folded = _normalized(summary)
    matched = [
        phrase
        for phrase in phrases
        if isinstance(phrase, str) and _normalized(phrase) in folded
    ]
    matched = [
        phrase
        for phrase in matched
        if not any(
            _normalized(phrase) != _normalized(other)
            and _normalized(phrase) in _normalized(other)
            for other in matched
        )
    ]
    if not matched:
        return []
    if rule.get("allow_when_actor_and_mechanism_are_named") is True:
        sentences = re.split(r"(?<=[.!?])\s+", folded)
        remaining: list[str] = []
        for matched_phrase in matched:
            needle = _normalized(matched_phrase)
            matching_sentences = [
                sentence for sentence in sentences if needle in sentence
            ]
            exempt = bool(matching_sentences)
            for sentence in matching_sentences:
                independent_context = sentence
                for phrase in phrases:
                    if isinstance(phrase, str):
                        independent_context = independent_context.replace(
                            _normalized(phrase), " "
                        )
                if not _specific_context_named(independent_context, policy):
                    exempt = False
                    break
            if not exempt:
                remaining.append(matched_phrase)
        return remaining
    return matched


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
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and bool(item.strip()) for item in value
    ):
        return None
    return list(value)


def published_content_languages(contract: dict[str, Any]) -> list[str]:
    """Return catalogue content languages that require specificity policies."""
    declared = contract.get("published_content_languages")
    if isinstance(declared, list) and all(isinstance(item, str) and item for item in declared):
        return list(declared)
    return []


def validate_contract(
    contract: dict[str, Any],
    content_languages: Iterable[str] | None = None,
) -> list[str]:
    """Validate policies for published catalogue content languages.

    Interface UI locales must not force policy copies. Pass the catalogue content
    languages (today predominantly ``de``/``en``), not every released UI locale.
    """
    errors: list[str] = []
    if content_languages is None:
        content_languages = published_content_languages(contract)
    required = list(content_languages)
    if not required or not all(isinstance(locale, str) and locale for locale in required):
        return ["summary specificity content_languages must be a non-empty string list"]
    if len(required) != len(set(required)):
        errors.append("summary specificity content_languages must not contain duplicates")

    if contract.get("schema_version") != 1:
        errors.append("summary specificity schema_version must be 1")
    if contract.get("kind") != "commonworld.catalog_summary_specificity_contract":
        errors.append(
            "summary specificity kind must be commonworld.catalog_summary_specificity_contract"
        )

    declared = contract.get("published_content_languages")
    if not isinstance(declared, list) or not declared or not all(
        isinstance(item, str) and item for item in declared
    ):
        errors.append(
            "summary specificity published_content_languages must be a non-empty string list"
        )
    elif list(declared) != required and set(declared) != set(required):
        # Callers may pass an explicit subset for tests; live validation uses the contract list.
        pass

    canonical_locale = contract.get("canonical_locale")
    if not isinstance(canonical_locale, str) or not canonical_locale:
        errors.append("summary specificity canonical_locale must be a non-empty string")
    elif canonical_locale not in required:
        errors.append(
            "summary specificity canonical_locale must be a published content language"
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
    if gate.get("every_published_content_language_requires_policy") is not True:
        errors.append(
            "summary specificity release gate must require a policy for every published content language"
        )
    if gate.get("planned_content_languages_may_omit_policy") is not True:
        errors.append(
            "summary specificity release gate must allow planned content languages to remain unpublished"
        )
    if gate.get("ui_locales_do_not_require_content_policy_copies") is not True:
        errors.append(
            "summary specificity release gate must keep content policies independent from UI locales"
        )

    minimum_rules = gate.get("minimum_rules_per_published_content_language")
    minimum_allowed = gate.get("minimum_allowed_examples_per_published_content_language")
    minimum_rejected = gate.get("minimum_rejected_examples_per_rule")
    for field, value in (
        ("minimum_rules_per_published_content_language", minimum_rules),
        ("minimum_allowed_examples_per_published_content_language", minimum_allowed),
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

    for locale in required:
        policy = policies.get(locale)
        if not isinstance(policy, dict):
            errors.append(
                f"summary specificity policy missing for published content language {locale}"
            )
            continue

        markers = policy.get("specificity_markers")
        if not isinstance(markers, dict):
            errors.append(
                f"summary specificity locale {locale} specificity_markers must be an object"
            )
            markers = {}
        for marker_kind in (
            "actor_patterns",
            "mechanism_patterns",
            "passive_mechanism_patterns",
        ):
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

        relation = markers.get("relation")
        if not isinstance(relation, dict):
            errors.append(
                f"summary specificity locale {locale} relation must be an object"
            )
        else:
            max_distance = relation.get("max_distance_chars")
            if (
                not isinstance(max_distance, int)
                or isinstance(max_distance, bool)
                or not 1 <= max_distance <= 500
            ):
                errors.append(
                    f"summary specificity locale {locale} relation max_distance_chars must be an integer from 1 to 500"
                )
            if relation.get("actor_must_precede_mechanism") is not True:
                errors.append(
                    f"summary specificity locale {locale} relation must require actor before mechanism"
                )
            if relation.get("same_sentence") is not True:
                errors.append(
                    f"summary specificity locale {locale} relation must require one sentence"
                )
            allowed_intervening_pattern = relation.get(
                "allowed_intervening_pattern"
            )
            if (
                not isinstance(allowed_intervening_pattern, str)
                or not allowed_intervening_pattern
            ):
                errors.append(
                    f"summary specificity locale {locale} relation allowed_intervening_pattern must be a non-empty regex"
                )
            else:
                try:
                    re.compile(allowed_intervening_pattern)
                except re.error as exc:
                    errors.append(
                        f"summary specificity locale {locale} relation allowed_intervening_pattern is invalid: {exc}"
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
