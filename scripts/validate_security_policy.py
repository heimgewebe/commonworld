#!/usr/bin/env python3
"""Validate Commonworld's vulnerability-disclosure policy and RFC 9116 surface."""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SECURITY_POLICY = Path("SECURITY.md")
SECURITY_TXT = Path(".well-known/security.txt")
JEKYLL_CONFIG = Path("_config.yml")
VALIDATE_WORKFLOW = Path(".github/workflows/validate.yml")
PRODUCTION_READBACK_WORKFLOW = Path(".github/workflows/production-readback.yml")
SECURITY_EXPIRY_WORKFLOW = Path(".github/workflows/security-policy-expiry.yml")
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


def workflow_step(workflow_text: str, step_name: str) -> str | None:
    lines = workflow_text.splitlines()
    marker = f"- name: {step_name}"
    starts = [index for index, line in enumerate(lines) if line.strip() == marker]
    if len(starts) != 1:
        return None
    start = starts[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if len(line) - len(line.lstrip()) == indent and line.strip().startswith("- name:"):
            end = index
            break
    return "\n".join(lines[start:end])


def _require_step(
    workflow_text: str,
    step_name: str,
    markers: tuple[str, ...],
    errors: list[str],
    label: str,
) -> str:
    step = workflow_step(workflow_text, step_name)
    if step is None:
        errors.append(f"{label} must contain exactly one step named {step_name!r}")
        return ""
    for marker in markers:
        if marker not in step:
            errors.append(f"{label} step {step_name!r} is missing: {marker}")
    return step


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
    premerge = _require_step(
        validate_text,
        "Verify private vulnerability reporting before merge",
        (
            "id: security_setting",
            "continue-on-error: true",
            "python3 scripts/validate_security_policy.py",
            "--verify-live-setting",
            '--repository "${{ github.repository }}"',
            '--expected-sha "${{ github.event.pull_request.head.sha || github.sha }}"',
            "artifacts/commonworld-private-vulnerability-reporting-premerge.json",
        ),
        errors,
        "validate workflow",
    )
    if "GITHUB_TOKEN" in premerge or "github.token" in premerge:
        errors.append("pre-merge private reporting readback must remain tokenless")
    _require_step(
        validate_text,
        "Upload pre-merge security receipt",
        (
            "if: always()",
            "actions/upload-artifact@v7",
            "artifacts/commonworld-private-vulnerability-reporting-premerge.json",
        ),
        errors,
        "validate workflow",
    )
    _require_step(
        validate_text,
        "Enforce pre-merge security readback",
        ("if: always() && steps.security_setting.outcome != 'success'", "run: exit 1"),
        errors,
        "validate workflow",
    )

    production_text = (root / PRODUCTION_READBACK_WORKFLOW).read_text(encoding="utf-8")
    production = _require_step(
        production_text,
        "Verify private vulnerability reporting setting",
        (
            "id: security_setting",
            "continue-on-error: true",
            "python3 scripts/validate_security_policy.py",
            "--verify-live-setting",
            '--repository "${{ github.repository }}"',
            '--expected-sha "${{ github.sha }}"',
            "artifacts/commonworld-private-vulnerability-reporting.json",
        ),
        errors,
        "production readback workflow",
    )
    if "GITHUB_TOKEN" in production or "github.token" in production:
        errors.append("private reporting status readback must use the public endpoint without an Actions token")
    _require_step(
        production_text,
        "Upload production readback receipts",
        (
            "if: always()",
            "actions/upload-artifact@v7",
            "artifacts/commonworld-pages-production-readback.json",
            "artifacts/commonworld-private-vulnerability-reporting.json",
        ),
        errors,
        "production readback workflow",
    )
    _require_step(
        production_text,
        "Enforce production readback result",
        (
            "steps.readback.outcome != 'success'",
            "steps.security_setting.outcome != 'success'",
            "run: exit 1",
        ),
        errors,
        "production readback workflow",
    )

    expiry_text = (root / SECURITY_EXPIRY_WORKFLOW).read_text(encoding="utf-8")
    for marker in ('cron: "17 5 * * 1"', "workflow_dispatch:", "contents: read"):
        if marker not in expiry_text:
            errors.append(f"security expiry workflow is incomplete: {marker}")
    expiry = _require_step(
        expiry_text,
        "Verify private vulnerability reporting remains enabled",
        (
            "id: security_setting",
            "if: always()",
            "continue-on-error: true",
            "python3 scripts/validate_security_policy.py",
            "--verify-live-setting",
            '--repository "${{ github.repository }}"',
            '--expected-sha "${{ github.sha }}"',
            "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
        ),
        errors,
        "security expiry workflow",
    )
    if "GITHUB_TOKEN" in expiry or "github.token" in expiry:
        errors.append("scheduled private reporting readback must use the public endpoint without an Actions token")
    _require_step(
        expiry_text,
        "Upload scheduled security receipt",
        (
            "if: always()",
            "actions/upload-artifact@v7",
            "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
        ),
        errors,
        "security expiry workflow",
    )
    _require_step(
        expiry_text,
        "Enforce live reporting result",
        ("if: always() && steps.security_setting.outcome != 'success'", "run: exit 1"),
        errors,
        "security expiry workflow",
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
