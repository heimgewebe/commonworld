#!/usr/bin/env python3
"""Validate Commonworld's vulnerability-disclosure policy and RFC 9116 surface."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import shlex
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

ROOT = Path(__file__).resolve().parents[1]
SECURITY_POLICY = Path("SECURITY.md")
SECURITY_TXT = Path(".well-known/security.txt")
JEKYLL_CONFIG = Path("_config.yml")
VALIDATE_WORKFLOW = Path(".github/workflows/validate.yml")
PRODUCTION_READBACK_WORKFLOW = Path(".github/workflows/production-readback.yml")
SECURITY_EXPIRY_WORKFLOW = Path(".github/workflows/security-policy-expiry.yml")
EXPECTED_WORKFLOW_SHA256 = {
    VALIDATE_WORKFLOW: "fe02ff290cde4bdabdfd6ef92ec4b6d94977125f8bf7980b8c3663d695ae61ed",
    PRODUCTION_READBACK_WORKFLOW: "553c04d7eb0b814d14453e7c59093a147153a10af96e92a84e4d8be55eaed628",
    SECURITY_EXPIRY_WORKFLOW: "1f5e132ce88792380d6eace0140ab62bb29c514d9743d6d52a1be0d965ae12cc",
}
EXPECTED_CONTACT = "https://github.com/heimgewebe/commonworld/security/advisories/new"
EXPECTED_POLICY = "https://github.com/heimgewebe/commonworld/security/policy"
EXPECTED_CANONICAL = "https://commonworld.net/.well-known/security.txt"
EXPECTED_LANGUAGES = "en, de"
ALLOWED_FIELDS = {"Contact", "Expires", "Preferred-Languages", "Canonical", "Policy"}
MAX_BYTES = 32 * 1024
MAX_LINES = 1000
MIN_REMAINING_VALIDITY = timedelta(days=30)
MAX_REMAINING_VALIDITY = timedelta(days=366)
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
FIELD_LINE_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9-]*): (?P<value>\S(?:.*\S)?)$")
RFC3339_DATE_TIME = re.compile(
    r"^(?P<date>\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))"
    r"[Tt](?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)"
    r"(?P<fraction>\.\d+)?(?P<offset>[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


@dataclass(frozen=True)
class PrivateReportingFetch:
    requested_url: str
    final_url: str
    status: int
    payload: object


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def _https_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _parse_rfc3339_datetime(value: str) -> datetime:
    match = RFC3339_DATE_TIME.fullmatch(value)
    if match is None:
        raise ValueError("not RFC 3339 date-time")
    normalized_offset = "+00:00" if match.group("offset") in {"Z", "z"} else match.group("offset")
    normalized = (
        f"{match.group('date')}T{match.group('hour')}:{match.group('minute')}:{match.group('second')}"
        f"{match.group('fraction') or ''}{normalized_offset}"
    )
    return datetime.fromisoformat(normalized)


def parse_security_txt(text: str) -> tuple[dict[str, list[str]], list[str]]:
    fields: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        if raw_line == "" or raw_line.startswith("#"):
            continue
        match = FIELD_LINE_RE.fullmatch(raw_line)
        if match is None:
            errors.append(f"security.txt line {number} must use exact 'Field: value' grammar")
            continue
        name = match.group("name")
        value = match.group("value")
        if name not in ALLOWED_FIELDS:
            errors.append(f"security.txt field is not reviewed: {name}")
            continue
        fields[name].append(value)
    return dict(fields), errors


@dataclass(frozen=True)
class WorkflowStep:
    raw: str
    fields: dict[str, str]
    with_fields: dict[str, str]
    env_fields: dict[str, str]
    run_text: str
    run_style: str | None
    run_argv: tuple[str, ...]
    parse_errors: tuple[str, ...]


def _yaml_scalar_node_value(node: Node) -> str | None:
    if not isinstance(node, ScalarNode):
        return None
    value = node.value
    if node.style in {"|", ">"}:
        value = value.rstrip("\n")
    return value


def _yaml_mapping_entries(node: Node, errors: list[str], scope: str) -> dict[str, Node]:
    if not isinstance(node, MappingNode):
        errors.append(f"{scope} must be a YAML mapping")
        return {}
    result: dict[str, Node] = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, ScalarNode):
            errors.append(f"{scope} contains a non-scalar mapping key")
            continue
        key = key_node.value
        if key in result:
            errors.append(f"duplicate {scope} field: {key}")
            continue
        result[key] = value_node
    return result


def _compose_workflow(workflow_text: str) -> Node | None:
    try:
        return yaml.compose(workflow_text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return None


def _workflow_step_nodes(root: Node) -> list[MappingNode]:
    errors: list[str] = []
    root_entries = _yaml_mapping_entries(root, errors, "workflow")
    jobs = root_entries.get("jobs")
    if not isinstance(jobs, MappingNode):
        return []
    result: list[MappingNode] = []
    for _, job_node in jobs.value:
        if not isinstance(job_node, MappingNode):
            continue
        job_entries = _yaml_mapping_entries(job_node, [], "job")
        steps = job_entries.get("steps")
        if not isinstance(steps, SequenceNode):
            continue
        result.extend(item for item in steps.value if isinstance(item, MappingNode))
    return result


def parse_workflow_step(workflow_text: str, step_name: str) -> WorkflowStep | None:
    root = _compose_workflow(workflow_text)
    if root is None:
        return None
    matches: list[MappingNode] = []
    for step_node in _workflow_step_nodes(root):
        entries = _yaml_mapping_entries(step_node, [], "step")
        name = _yaml_scalar_node_value(entries.get("name")) if entries.get("name") is not None else None
        if name == step_name:
            matches.append(step_node)
    if len(matches) != 1:
        return None

    step_node = matches[0]
    parse_errors: list[str] = []
    entries = _yaml_mapping_entries(step_node, parse_errors, "step")
    fields: dict[str, str] = {}
    with_fields: dict[str, str] = {}
    env_fields: dict[str, str] = {}
    run_text = ""
    run_style: str | None = None
    for key, value_node in entries.items():
        if key in {"with", "env"}:
            fields[key] = ""
            nested = _yaml_mapping_entries(value_node, parse_errors, key)
            target = with_fields if key == "with" else env_fields
            for nested_key, nested_value_node in nested.items():
                nested_value = _yaml_scalar_node_value(nested_value_node)
                if nested_value is None:
                    parse_errors.append(f"{key} field {nested_key} must be a scalar")
                else:
                    target[nested_key] = nested_value
            continue
        value = _yaml_scalar_node_value(value_node)
        if value is None:
            parse_errors.append(f"step field {key} must be a scalar")
            continue
        fields[key] = value
        if key == "run":
            run_text = value
            run_style = value_node.style

    try:
        run_argv = tuple(shlex.split(run_text)) if run_text and "\n" not in run_text else ()
    except ValueError:
        run_argv = ()
    raw = workflow_text[step_node.start_mark.index:step_node.end_mark.index]
    return WorkflowStep(
        raw=raw,
        fields=fields,
        with_fields=with_fields,
        env_fields=env_fields,
        run_text=run_text,
        run_style=run_style,
        run_argv=run_argv,
        parse_errors=tuple(parse_errors),
    )


def workflow_step(workflow_text: str, step_name: str) -> str | None:
    parsed = parse_workflow_step(workflow_text, step_name)
    return None if parsed is None else parsed.raw


def _require_structured_step(
    workflow_text: str,
    step_name: str,
    errors: list[str],
    label: str,
    *,
    fields: dict[str, str] | None = None,
    run_argv: tuple[str, ...] | None = None,
    with_fields: dict[str, str] | None = None,
    env_fields: dict[str, str] | None = None,
    forbidden_fields: tuple[str, ...] = (),
    exact_fields: bool = True,
) -> WorkflowStep | None:
    step = parse_workflow_step(workflow_text, step_name)
    if step is None:
        errors.append(f"{label} must contain exactly one step named {step_name!r}")
        return None
    for parse_error in step.parse_errors:
        errors.append(f"{label} step {step_name!r}: {parse_error}")
    for key, expected in (fields or {}).items():
        actual = step.fields.get(key)
        if actual != expected:
            errors.append(f"{label} step {step_name!r} field {key!r} must equal {expected!r}, got {actual!r}")
    if exact_fields:
        allowed_fields = {"name"}
        allowed_fields.update((fields or {}).keys())
        if run_argv is not None:
            allowed_fields.add("run")
        if with_fields is not None:
            allowed_fields.add("with")
        if env_fields is not None:
            allowed_fields.add("env")
        for key in sorted(set(step.fields) - allowed_fields):
            errors.append(f"{label} step {step_name!r} contains unreviewed field {key!r}")
    effective_forbidden = set(forbidden_fields)
    if run_argv is not None:
        effective_forbidden.add("shell")
    for key in sorted(effective_forbidden):
        if key in step.fields:
            errors.append(f"{label} step {step_name!r} must not define field {key!r}")
    if run_argv is not None and (step.run_argv != run_argv or "\n" in step.run_text):
        errors.append(f"{label} step {step_name!r} command mismatch")
    for key, expected in (with_fields or {}).items():
        actual = step.with_fields.get(key)
        if actual != expected:
            errors.append(f"{label} step {step_name!r} with.{key} must equal {expected!r}, got {actual!r}")
    if env_fields is not None and step.env_fields != env_fields:
        errors.append(
            f"{label} step {step_name!r} env must equal {env_fields!r}, got {step.env_fields!r}"
        )
    return step


def _reject_inherited_shell_override(
    entries: dict[str, Node],
    errors: list[str],
    scope: str,
) -> None:
    defaults = entries.get("defaults")
    if defaults is None:
        return
    defaults_entries = _yaml_mapping_entries(defaults, errors, f"{scope} defaults")
    run = defaults_entries.get("run")
    if run is None:
        return
    run_entries = _yaml_mapping_entries(run, errors, f"{scope} defaults.run")
    if "shell" in run_entries:
        errors.append(f"{scope} must not define defaults.run.shell")


def _require_executable_job_for_steps(
    workflow_text: str,
    step_names: tuple[str, ...],
    errors: list[str],
    label: str,
    *,
    expected_job_name: str | None = None,
    expected_job_fields: dict[str, str] | None = None,
    expected_workflow_fields: set[str] | None = None,
) -> None:
    root = _compose_workflow(workflow_text)
    if root is None:
        errors.append(f"{label} must be valid YAML")
        return

    structural_errors: list[str] = []
    root_entries = _yaml_mapping_entries(root, structural_errors, f"{label} workflow")
    if expected_workflow_fields is not None and set(root_entries) != expected_workflow_fields:
        structural_errors.append(
            f"{label} workflow fields must equal {sorted(expected_workflow_fields)!r}, got {sorted(root_entries)!r}"
        )
    _reject_inherited_shell_override(root_entries, structural_errors, f"{label} workflow")
    jobs_node = root_entries.get("jobs")
    jobs = _yaml_mapping_entries(jobs_node, structural_errors, f"{label} jobs") if jobs_node is not None else {}
    if jobs_node is None:
        structural_errors.append(f"{label} must define jobs")

    matches: dict[str, list[tuple[str, dict[str, Node], int]]] = {name: [] for name in step_names}
    for job_name, job_node in jobs.items():
        job_entries = _yaml_mapping_entries(job_node, structural_errors, f"{label} job {job_name!r}")
        steps = job_entries.get("steps")
        if not isinstance(steps, SequenceNode):
            continue
        for index, step_node in enumerate(steps.value, start=1):
            step_entries = _yaml_mapping_entries(
                step_node,
                structural_errors,
                f"{label} job {job_name!r} step {index}",
            )
            name_node = step_entries.get("name")
            name = _yaml_scalar_node_value(name_node) if name_node is not None else None
            if name in matches:
                matches[name].append((job_name, job_entries, index))

    resolved: list[tuple[str, dict[str, Node], int]] = []
    for step_name in step_names:
        locations = matches[step_name]
        if len(locations) != 1:
            structural_errors.append(
                f"{label} step {step_name!r} must belong to exactly one executable job"
            )
        else:
            resolved.append(locations[0])

    if len(resolved) == len(step_names):
        job_names = {job_name for job_name, _, _ in resolved}
        if len(job_names) != 1:
            structural_errors.append(
                f"{label} security-critical steps must belong to the same executable job"
            )
        else:
            job_name = next(iter(job_names))
            job_entries = resolved[0][1]
            indices = [index for _, _, index in resolved]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                structural_errors.append(
                    f"{label} security-critical steps must be consecutive and in reviewed order"
                )
            if expected_job_name is not None and job_name != expected_job_name:
                structural_errors.append(
                    f"{label} security-critical steps must belong to job {expected_job_name!r}, got {job_name!r}"
                )
            if expected_job_fields is not None:
                allowed_job_fields = {"steps", *expected_job_fields.keys()}
                if set(job_entries) != allowed_job_fields:
                    structural_errors.append(
                        f"{label} job {job_name!r} fields must equal {sorted(allowed_job_fields)!r}, got {sorted(job_entries)!r}"
                    )
                for key, expected in expected_job_fields.items():
                    value_node = job_entries.get(key)
                    actual = _yaml_scalar_node_value(value_node) if value_node is not None else None
                    if actual != expected:
                        structural_errors.append(
                            f"{label} job {job_name!r} field {key!r} must equal {expected!r}, got {actual!r}"
                        )
            for key in ("if", "continue-on-error", "needs"):
                if key in job_entries:
                    structural_errors.append(
                        f"{label} job {job_name!r} for security-critical steps must not define field {key!r}"
                    )
            _reject_inherited_shell_override(
                job_entries,
                structural_errors,
                f"{label} job {job_name!r}",
            )

    errors.extend(structural_errors)


def _require_executable_job_for_step(
    workflow_text: str,
    step_name: str,
    errors: list[str],
    label: str,
) -> None:
    _require_executable_job_for_steps(workflow_text, (step_name,), errors, label)


def _validate_expiry_triggers(workflow_text: str, errors: list[str]) -> None:
    root = _compose_workflow(workflow_text)
    if root is None:
        errors.append("security expiry workflow must be valid YAML")
        return
    structural_errors: list[str] = []
    root_entries = _yaml_mapping_entries(root, structural_errors, "top-level")
    on_node = root_entries.get("on")
    on_entries = _yaml_mapping_entries(on_node, structural_errors, "on") if on_node is not None else {}
    schedule = on_entries.get("schedule")
    if not isinstance(schedule, SequenceNode) or len(schedule.value) != 1:
        structural_errors.append("security expiry workflow must define exactly one on.schedule")
    else:
        item_entries = _yaml_mapping_entries(schedule.value[0], structural_errors, "cron item")
        cron = _yaml_scalar_node_value(item_entries.get("cron")) if item_entries.get("cron") is not None else None
        duplicate_cron = any(error.startswith("duplicate cron item field: cron") for error in structural_errors)
        if duplicate_cron:
            structural_errors.append("security expiry workflow cron item must not contain duplicate or additional mapping keys")
        if set(item_entries) != {"cron"} or cron != "17 5 * * 1" or duplicate_cron:
            structural_errors.append('security expiry workflow on.schedule must contain exactly one cron "17 5 * * 1" and no duplicate keys')
    dispatch = on_entries.get("workflow_dispatch")
    if dispatch is None or not isinstance(dispatch, ScalarNode):
        structural_errors.append("security expiry workflow must define exactly one on.workflow_dispatch")

    permissions = root_entries.get("permissions")
    permission_entries = _yaml_mapping_entries(permissions, structural_errors, "permissions") if permissions is not None else {}
    contents = _yaml_scalar_node_value(permission_entries.get("contents")) if permission_entries.get("contents") is not None else None
    if (
        set(permission_entries) != {"contents"}
        or contents != "read"
        or any(error.startswith("duplicate permissions field: contents") for error in structural_errors)
    ):
        structural_errors.append("security expiry workflow permissions must contain exactly contents: read and no conflicting keys")
    errors.extend(structural_errors)


def validate_security_policy(root: Path = ROOT, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    now = (now or utc_now()).astimezone(timezone.utc)
    required = (
        SECURITY_POLICY,
        SECURITY_TXT,
        JEKYLL_CONFIG,
        VALIDATE_WORKFLOW,
        PRODUCTION_READBACK_WORKFLOW,
        SECURITY_EXPIRY_WORKFLOW,
    )
    for path in required:
        if not (root / path).is_file():
            errors.append(f"missing security disclosure file: {path}")
    if errors:
        return errors

    for relative, expected_sha256 in EXPECTED_WORKFLOW_SHA256.items():
        actual_sha256 = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if actual_sha256 != expected_sha256:
            errors.append(
                f"security workflow bytes changed without reviewed digest update: {relative}; "
                f"expected {expected_sha256}, got {actual_sha256}"
            )

    security_bytes = (root / SECURITY_TXT).read_bytes()
    if len(security_bytes) > MAX_BYTES:
        errors.append("security.txt exceeds the RFC 9116 defensive size bound")
    if not security_bytes.endswith(b"\n"):
        errors.append("security.txt must end with LF")
    if b"\r" in security_bytes:
        errors.append("security.txt must use LF line separators")
    try:
        security_text = security_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"security.txt is not UTF-8: {exc}"]
    if len(security_text.splitlines()) > MAX_LINES:
        errors.append("security.txt exceeds the RFC 9116 defensive line bound")

    fields, parse_errors = parse_security_txt(security_text)
    errors.extend(parse_errors)
    expected_singletons = {
        "Contact": EXPECTED_CONTACT,
        "Preferred-Languages": EXPECTED_LANGUAGES,
        "Canonical": EXPECTED_CANONICAL,
        "Policy": EXPECTED_POLICY,
    }
    for name, expected in expected_singletons.items():
        if fields.get(name, []) != [expected]:
            errors.append(f"security.txt {name} must equal the reviewed value")
    for name in ("Contact", "Canonical", "Policy"):
        for value in fields.get(name, []):
            if not _https_uri(value):
                errors.append(f"security.txt {name} must be an HTTPS URI without userinfo")

    expires_values = fields.get("Expires", [])
    if len(expires_values) != 1:
        errors.append("security.txt must contain exactly one Expires field")
    else:
        try:
            expires = _parse_rfc3339_datetime(expires_values[0])
        except ValueError:
            errors.append("security.txt Expires must be strict RFC 3339")
        else:
            remaining = expires.astimezone(timezone.utc) - now
            if remaining <= MIN_REMAINING_VALIDITY:
                errors.append("security.txt Expires must remain more than 30 days in the future")
            if remaining > MAX_REMAINING_VALIDITY:
                errors.append("security.txt Expires must be no more than 366 days in the future")

    policy_text = (root / SECURITY_POLICY).read_text(encoding="utf-8")
    for phrase in (
        EXPECTED_CONTACT,
        "Do not use public issues",
        "no response-time SLA",
        "no bug bounty",
        "no promise of payment",
    ):
        if phrase not in policy_text:
            errors.append(f"SECURITY.md is missing reviewed policy language: {phrase}")
    if "mailto:" in policy_text.lower() or "mailto:" in security_text.lower():
        errors.append("security disclosure surface must not invent an email contact")

    if (root / JEKYLL_CONFIG).read_text(encoding="utf-8") != "include:\n  - .well-known\n":
        errors.append("Jekyll configuration must expose only the reviewed .well-known directory")
    if (root / ".nojekyll").exists():
        errors.append(".nojekyll would publish an unnecessarily broad dotfile surface")

    validate_text = (root / VALIDATE_WORKFLOW).read_text(encoding="utf-8")
    _require_executable_job_for_steps(
        validate_text,
        (
            "Verify private vulnerability reporting before merge",
            "Upload pre-merge security receipt",
            "Enforce pre-merge security readback",
        ),
        errors,
        "validate workflow",
        expected_job_name="contracts",
        expected_job_fields={"runs-on": "ubuntu-latest"},
        expected_workflow_fields={"name", "on", "permissions", "jobs"},
    )
    premerge = _require_structured_step(
        validate_text,
        "Verify private vulnerability reporting before merge",
        errors,
        "validate workflow",
        fields={"id": "security_setting", "continue-on-error": "true"},
        run_argv=(
            "python3", "scripts/validate_security_policy.py", "--verify-live-setting",
            "--repository", "${{ github.repository }}", "--expected-sha",
            "${{ github.event.pull_request.head.sha || github.sha }}", "--receipt",
            "artifacts/commonworld-private-vulnerability-reporting-premerge.json",
        ),
    )
    if premerge and ("GITHUB_TOKEN" in premerge.raw or "github.token" in premerge.raw):
        errors.append("pre-merge private reporting readback must remain tokenless")
    _require_structured_step(
        validate_text,
        "Upload pre-merge security receipt",
        errors,
        "validate workflow",
        fields={"if": "always()", "uses": "actions/upload-artifact@v7"},
        with_fields={
            "path": "artifacts/commonworld-private-vulnerability-reporting-premerge.json",
            "if-no-files-found": "error", "retention-days": "30",
        },
        forbidden_fields=("continue-on-error", "shell"),
    )
    _require_structured_step(
        validate_text,
        "Enforce pre-merge security readback",
        errors,
        "validate workflow",
        fields={"if": "always() && steps.security_setting.outcome != 'success'"},
        run_argv=("exit", "1"),
        forbidden_fields=("continue-on-error",),
    )

    production_text = (root / PRODUCTION_READBACK_WORKFLOW).read_text(encoding="utf-8")
    _require_executable_job_for_steps(
        production_text,
        (
            "Install security validation dependencies",
            "Verify exact Pages deployment and public content",
            "Verify private vulnerability reporting setting",
            "Upload production readback receipts",
            "Enforce production readback result",
        ),
        errors,
        "production readback workflow",
        expected_job_name="verify-exact-pages-deployment",
        expected_job_fields={"runs-on": "ubuntu-latest", "timeout-minutes": "20"},
        expected_workflow_fields={"name", "on", "permissions", "concurrency", "jobs"},
    )
    _require_structured_step(
        production_text,
        "Install security validation dependencies",
        errors,
        "production readback workflow",
        run_argv=("python", "-m", "pip", "install", "-r", "requirements-dev.txt"),
        forbidden_fields=("continue-on-error", "if"),
    )
    _require_structured_step(
        production_text,
        "Verify exact Pages deployment and public content",
        errors,
        "production readback workflow",
        fields={"id": "readback", "continue-on-error": "true"},
        run_argv=(
            "python3", "scripts/verify_pages_deployment.py",
            "--repository", "${{ github.repository }}",
            "--sha", "${{ github.sha }}",
            "--source-ref", "main",
            "--receipt", "artifacts/commonworld-pages-production-readback.json",
            "--deployment-timeout-seconds", "600",
            "--deployment-poll-seconds", "10",
            "--live-timeout-seconds", "5",
            "--live-retry-delays-seconds", "0,30,90",
        ),
        env_fields={
            "GITHUB_TOKEN": "${{ github.token }}",
            "COMMONWORLD_PAGES_URL": "https://commonworld.net/",
        },
        forbidden_fields=("if",),
    )
    production = _require_structured_step(
        production_text,
        "Verify private vulnerability reporting setting",
        errors,
        "production readback workflow",
        fields={"id": "security_setting", "continue-on-error": "true"},
        run_argv=(
            "python3", "scripts/validate_security_policy.py", "--verify-live-setting",
            "--repository", "${{ github.repository }}", "--expected-sha", "${{ github.sha }}",
            "--receipt", "artifacts/commonworld-private-vulnerability-reporting.json",
        ),
    )
    if production and ("GITHUB_TOKEN" in production.raw or "github.token" in production.raw):
        errors.append("private reporting status readback must use the public endpoint without an Actions token")
    _require_structured_step(
        production_text,
        "Upload production readback receipts",
        errors,
        "production readback workflow",
        fields={"if": "always()", "uses": "actions/upload-artifact@v7"},
        with_fields={
            "path": "artifacts/commonworld-pages-production-readback.json\nartifacts/commonworld-private-vulnerability-reporting.json",
            "if-no-files-found": "error", "retention-days": "30",
        },
        forbidden_fields=("continue-on-error", "shell"),
    )
    _require_structured_step(
        production_text,
        "Enforce production readback result",
        errors,
        "production readback workflow",
        fields={"if": "always() && (steps.readback.outcome != 'success' || steps.security_setting.outcome != 'success')"},
        run_argv=("exit", "1"),
        forbidden_fields=("continue-on-error",),
    )

    expiry_text = (root / SECURITY_EXPIRY_WORKFLOW).read_text(encoding="utf-8")
    _validate_expiry_triggers(expiry_text, errors)
    _require_executable_job_for_steps(
        expiry_text,
        (
            "Install security validation dependencies",
            "Validate disclosure policy and expiry",
            "Verify private vulnerability reporting remains enabled",
            "Upload scheduled security receipt",
            "Enforce live reporting result",
        ),
        errors,
        "security expiry workflow",
        expected_job_name="validate-security-policy-expiry",
        expected_job_fields={"runs-on": "ubuntu-latest", "timeout-minutes": "5"},
        expected_workflow_fields={"name", "on", "permissions", "concurrency", "jobs"},
    )
    _require_structured_step(
        expiry_text,
        "Install security validation dependencies",
        errors,
        "security expiry workflow",
        run_argv=("python", "-m", "pip", "install", "-r", "requirements-dev.txt"),
        forbidden_fields=("continue-on-error", "if"),
    )
    _require_structured_step(
        expiry_text,
        "Validate disclosure policy and expiry",
        errors,
        "security expiry workflow",
        run_argv=("python3", "scripts/validate_security_policy.py"),
        forbidden_fields=("continue-on-error", "if"),
    )
    expiry = _require_structured_step(
        expiry_text,
        "Verify private vulnerability reporting remains enabled",
        errors,
        "security expiry workflow",
        fields={"id": "security_setting", "if": "always()", "continue-on-error": "true"},
        run_argv=(
            "python3", "scripts/validate_security_policy.py", "--verify-live-setting",
            "--repository", "${{ github.repository }}", "--expected-sha", "${{ github.sha }}",
            "--receipt", "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
        ),
    )
    if expiry and ("GITHUB_TOKEN" in expiry.raw or "github.token" in expiry.raw):
        errors.append("scheduled private reporting readback must use the public endpoint without an Actions token")
    _require_structured_step(
        expiry_text,
        "Upload scheduled security receipt",
        errors,
        "security expiry workflow",
        fields={"if": "always()", "uses": "actions/upload-artifact@v7"},
        with_fields={
            "path": "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
            "if-no-files-found": "error", "retention-days": "30",
        },
        forbidden_fields=("continue-on-error", "shell"),
    )
    _require_structured_step(
        expiry_text,
        "Enforce live reporting result",
        errors,
        "security expiry workflow",
        fields={"if": "always() && steps.security_setting.outcome != 'success'"},
        run_argv=("exit", "1"),
        forbidden_fields=("continue-on-error",),
    )
    return errors


def _private_reporting_endpoint(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}/private-vulnerability-reporting"


def github_api_get_private_reporting(repository: str, timeout_seconds: int = 20) -> PrivateReportingFetch:
    endpoint = _private_reporting_endpoint(repository)
    try:
        request = urllib.request.Request(
            endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "commonworld-security-policy/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            status = int(response.status)
            final_url = response.geturl()
        payload = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            raw = error.read()
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except (OSError, http.client.HTTPException, UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        return PrivateReportingFetch(endpoint, error.geturl() or endpoint, int(error.code), payload)
    except (
        OSError,
        ValueError,
        urllib.error.URLError,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(f"private vulnerability reporting readback failed: {error}") from error
    return PrivateReportingFetch(endpoint, final_url, status, payload)


def verify_live_private_reporting(
    repository: str,
    expected_sha: str,
    *,
    api_get=None,
    now=utc_timestamp,
) -> dict[str, object]:
    errors: list[str] = []
    endpoint: str | None = None
    requested_url: str | None = None
    final_url: str | None = None
    status: int | None = None
    enabled: bool | None = None
    if REPOSITORY_RE.fullmatch(repository) is None:
        errors.append("repository must be in owner/name form")
    else:
        endpoint = _private_reporting_endpoint(repository)
    if len(expected_sha) != 40 or any(character not in "0123456789abcdef" for character in expected_sha.lower()):
        errors.append("expected SHA must be a full hexadecimal commit id")
    if not errors:
        try:
            fetch = (api_get or (lambda: github_api_get_private_reporting(repository)))()
            if not isinstance(fetch, PrivateReportingFetch):
                raise RuntimeError("private reporting fetch must include endpoint metadata")
            requested_url = fetch.requested_url
            final_url = fetch.final_url
            status = fetch.status
            if requested_url != endpoint or final_url != endpoint:
                errors.append("private vulnerability reporting endpoint redirected or mismatched")
            if status != 200:
                errors.append(f"private vulnerability reporting status must be 200, got {status}")
            if not isinstance(fetch.payload, dict) or not isinstance(fetch.payload.get("enabled"), bool):
                errors.append("private vulnerability reporting response must contain boolean enabled")
            else:
                enabled = fetch.payload["enabled"]
                if enabled is not True:
                    errors.append("private vulnerability reporting must be enabled before publication")
        except (RuntimeError, OSError, ValueError, http.client.HTTPException) as error:
            errors.append(str(error))
    return {
        "schema_version": 1,
        "kind": "commonworld_private_vulnerability_reporting_readback",
        "repository": repository,
        "expected_sha": expected_sha,
        "endpoint": endpoint,
        "requested_url": requested_url,
        "final_url": final_url,
        "status": status,
        "observed_at": now(),
        "enabled": enabled,
        "verdict": "pass" if not errors else "fail",
        "errors": errors,
        "does_not_establish": ["response-time SLA", "bug bounty", "payment promise", "broad legal safe harbor"],
    }


def write_json_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-live-setting", action="store_true")
    parser.add_argument("--repository", default="")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--receipt", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.verify_live_setting:
        if arguments.receipt is None:
            parser.error("--receipt is required with --verify-live-setting")
        receipt = verify_live_private_reporting(arguments.repository, arguments.expected_sha)
        write_json_receipt(arguments.receipt, receipt)
        if receipt["verdict"] != "pass":
            for error in receipt["errors"]:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("commonworld private vulnerability reporting readback ok")
        return 0

    errors = validate_security_policy(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld security disclosure policy validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
