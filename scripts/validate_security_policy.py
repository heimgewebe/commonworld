#!/usr/bin/env python3
"""Validate Commonworld's vulnerability-disclosure policy and RFC 9116 surface."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SECURITY_POLICY = Path("SECURITY.md")
SECURITY_TXT = Path(".well-known/security.txt")
JEKYLL_CONFIG = Path("_config.yml")
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
RFC3339_DATE_TIME = re.compile(
    r"^(?P<date>\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))"
    r"[Tt](?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d|60)"
    r"(?P<fraction>\.\d+)?(?P<offset>[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _https_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _parse_rfc3339_datetime(value: str) -> datetime:
    match = RFC3339_DATE_TIME.fullmatch(value)
    if match is None:
        raise ValueError("not RFC 3339 date-time")
    second = match.group("second")
    offset = match.group("offset")
    normalized_offset = "+00:00" if offset in {"Z", "z"} else offset
    normalized_second = "59" if second == "60" else second
    normalized = (
        f"{match.group('date')}T{match.group('hour')}:{match.group('minute')}:{normalized_second}"
        f"{match.group('fraction') or ''}{normalized_offset}"
    )
    parsed = datetime.fromisoformat(normalized)
    if second == "60":
        parsed += timedelta(seconds=1)
    return parsed


def parse_security_txt(text: str) -> tuple[dict[str, list[str]], list[str]]:
    fields: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"security.txt line {number} has no field separator")
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if name not in ALLOWED_FIELDS:
            errors.append(f"security.txt field is not reviewed: {name}")
            continue
        if not value:
            errors.append(f"security.txt field is empty: {name}")
            continue
        fields[name].append(value)
    return dict(fields), errors


def validate_security_policy(root: Path = ROOT, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    now = now or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    for path in (SECURITY_POLICY, SECURITY_TXT, JEKYLL_CONFIG, PRODUCTION_READBACK_WORKFLOW, SECURITY_EXPIRY_WORKFLOW):
        if not (root / path).is_file():
            errors.append(f"missing security disclosure file: {path}")
    if errors:
        return errors

    security_bytes = (root / SECURITY_TXT).read_bytes()
    if len(security_bytes) > MAX_BYTES:
        errors.append("security.txt exceeds the RFC 9116 defensive size bound")
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
        values = fields.get(name, [])
        if values != [expected]:
            errors.append(f"security.txt {name} must equal the reviewed value")
    for name in ("Contact", "Canonical", "Policy"):
        for value in fields.get(name, []):
            if not _https_uri(value):
                errors.append(f"security.txt {name} must be an HTTPS URI without userinfo")

    expires_values = fields.get("Expires", [])
    if len(expires_values) != 1:
        errors.append("security.txt must contain exactly one Expires field")
    else:
        value = expires_values[0]
        try:
            expires = _parse_rfc3339_datetime(value)
        except ValueError:
            errors.append("security.txt Expires must be strict RFC 3339")
        else:
            remaining = expires.astimezone(timezone.utc) - now
            if remaining <= MIN_REMAINING_VALIDITY:
                errors.append("security.txt Expires must remain more than 30 days in the future")
            if remaining > MAX_REMAINING_VALIDITY:
                errors.append("security.txt Expires must be no more than 366 days in the future")


    policy_text = (root / SECURITY_POLICY).read_text(encoding="utf-8")
    required_policy_phrases = (
        EXPECTED_CONTACT,
        "Do not use public issues",
        "no response-time SLA",
        "no bug bounty",
        "no promise of payment",
    )
    for phrase in required_policy_phrases:
        if phrase not in policy_text:
            errors.append(f"SECURITY.md is missing reviewed policy language: {phrase}")
    if "mailto:" in policy_text.lower() or "mailto:" in security_text.lower():
        errors.append("security disclosure surface must not invent an email contact")

    config_text = (root / JEKYLL_CONFIG).read_text(encoding="utf-8")
    if config_text != "include:\n  - .well-known\n":
        errors.append("Jekyll configuration must expose only the reviewed .well-known directory")
    if (root / ".nojekyll").exists():
        errors.append(".nojekyll would publish an unnecessarily broad dotfile surface")

    workflow_text = (root / PRODUCTION_READBACK_WORKFLOW).read_text(encoding="utf-8")
    workflow_markers = (
        "--verify-live-setting",
        '--expected-sha "${{ github.sha }}"',
        "artifacts/commonworld-private-vulnerability-reporting.json",
        "steps.security_setting.outcome != 'success'",
    )
    for marker in workflow_markers:
        if marker not in workflow_text:
            errors.append(f"production readback does not enforce private reporting: {marker}")
    security_step = workflow_text.split("- name: Verify private vulnerability reporting setting", 1)[-1].split("- name: Upload production readback receipts", 1)[0]
    if "GITHUB_TOKEN" in security_step or "github.token" in security_step:
        errors.append("private reporting status readback must use the public endpoint without an Actions token")

    expiry_workflow_text = (root / SECURITY_EXPIRY_WORKFLOW).read_text(encoding="utf-8")
    expiry_markers = (
        'cron: "17 5 * * 1"',
        "workflow_dispatch:",
        "contents: read",
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "python3 scripts/validate_security_policy.py",
        "--verify-live-setting",
        "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
        "actions/upload-artifact@v7",
        "steps.security_setting.outcome != 'success'",
    )
    for marker in expiry_markers:
        if marker not in expiry_workflow_text:
            errors.append(f"security expiry workflow is incomplete: {marker}")
    if "GITHUB_TOKEN" in expiry_workflow_text or "github.token" in expiry_workflow_text:
        errors.append("scheduled private reporting readback must use the public endpoint without an Actions token")
    return errors


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def github_api_get_private_reporting(repository: str, timeout_seconds: int = 20) -> object:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/private-vulnerability-reporting",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "commonworld-security-policy/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"private vulnerability reporting readback failed: {error}") from error


def verify_live_private_reporting(
    repository: str,
    expected_sha: str,
    *,
    api_get=None,
    now=utc_timestamp,
) -> dict[str, object]:
    errors: list[str] = []
    if not repository or repository.count("/") != 1:
        errors.append("repository must be in owner/name form")
    if len(expected_sha) != 40 or any(character not in "0123456789abcdef" for character in expected_sha.lower()):
        errors.append("expected SHA must be a full hexadecimal commit id")
    enabled = None
    if not errors:
        request = api_get or (lambda: github_api_get_private_reporting(repository))
        try:
            response = request()
        except RuntimeError as error:
            errors.append(str(error))
        else:
            if not isinstance(response, dict) or not isinstance(response.get("enabled"), bool):
                errors.append("private vulnerability reporting response must contain boolean enabled")
            else:
                enabled = response["enabled"]
                if enabled is not True:
                    errors.append("private vulnerability reporting must be enabled before publication")
    timestamp = now()
    return {
        "schema_version": 1,
        "kind": "commonworld_private_vulnerability_reporting_readback",
        "repository": repository,
        "expected_sha": expected_sha,
        "endpoint": f"https://api.github.com/repos/{repository}/private-vulnerability-reporting",
        "observed_at": timestamp,
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
        receipt = verify_live_private_reporting(
            arguments.repository,
            arguments.expected_sha,
        )
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
