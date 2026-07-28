#!/usr/bin/env python3
"""Validate Commonworld's vulnerability-disclosure surface and live reporting setting."""

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
FORBIDDEN_LINE_CHARACTERS = {"\x0b", "\x0c", "\x85", "\u2028", "\u2029"}
RFC3339_RE = re.compile(
    r"^(?P<date>\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))"
    r"T(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)"
    r"(?P<fraction>\.\d+)?(?P<offset>Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
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


def _private_reporting_endpoint(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}/private-vulnerability-reporting"


def _https_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _parse_rfc3339(value: str) -> datetime:
    match = RFC3339_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid RFC 3339 grammar")
    offset = "+00:00" if match.group("offset") == "Z" else match.group("offset")
    normalized = (
        f"{match.group('date')}T{match.group('hour')}:{match.group('minute')}:{match.group('second')}"
        f"{match.group('fraction') or ''}{offset}"
    )
    return datetime.fromisoformat(normalized)


def _valid_comment_line(raw_line: str) -> bool:
    """Return whether one RFC 9116 comment line uses only permitted characters."""
    return raw_line.startswith("#") and all(
        character in {"\t", " "}
        or 0x21 <= ord(character) <= 0x7E
        or 0x80 <= ord(character) <= 0xFFFFF
        for character in raw_line[1:]
    )


def parse_security_txt(text: str) -> tuple[dict[str, list[str]], list[str]]:
    fields: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []
    if any(character in text for character in FORBIDDEN_LINE_CHARACTERS):
        errors.append("security.txt may use only LF line separators")
    for number, raw_line in enumerate(text.split("\n"), start=1):
        if not raw_line or all(character in {"\t", " "} for character in raw_line):
            continue
        if raw_line.startswith("#"):
            if not _valid_comment_line(raw_line):
                errors.append(f"security.txt comment line {number} contains a forbidden character")
            continue
        match = FIELD_LINE_RE.fullmatch(raw_line)
        if match is None:
            errors.append(f"security.txt line {number} must use exact 'Field: value' grammar")
            continue
        name, value = match.group("name"), match.group("value")
        if name not in ALLOWED_FIELDS:
            errors.append(f"security.txt field is not reviewed: {name}")
            continue
        fields[name].append(value)
    return dict(fields), errors


def validate_security_policy(root: Path = ROOT, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    observed = now or utc_now()
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    observed = observed.astimezone(timezone.utc)

    required = (SECURITY_POLICY, SECURITY_TXT, JEKYLL_CONFIG, PRODUCTION_READBACK_WORKFLOW, SECURITY_EXPIRY_WORKFLOW)
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing security disclosure file: {relative}")
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
    except UnicodeDecodeError:
        return ["security.txt is not UTF-8"]
    if len(security_text.splitlines()) > MAX_LINES:
        errors.append("security.txt exceeds the RFC 9116 defensive line bound")

    fields, parse_errors = parse_security_txt(security_text)
    errors.extend(parse_errors)
    expected = {
        "Contact": EXPECTED_CONTACT,
        "Preferred-Languages": EXPECTED_LANGUAGES,
        "Canonical": EXPECTED_CANONICAL,
        "Policy": EXPECTED_POLICY,
    }
    for name, reviewed_value in expected.items():
        if fields.get(name, []) != [reviewed_value]:
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
            expires = _parse_rfc3339(expires_values[0])
        except ValueError:
            errors.append("security.txt Expires must be strict RFC 3339")
        else:
            remaining = expires.astimezone(timezone.utc) - observed
            if remaining <= MIN_REMAINING_VALIDITY:
                errors.append("security.txt Expires must remain more than 30 days in the future")
            if remaining > MAX_REMAINING_VALIDITY:
                errors.append("security.txt Expires must be no more than 366 days in the future")

    policy_text = (root / SECURITY_POLICY).read_text(encoding="utf-8")
    for phrase in (EXPECTED_CONTACT, "Do not use public issues", "no response-time SLA", "no bug bounty", "no promise of payment"):
        if phrase not in policy_text:
            errors.append(f"SECURITY.md is missing reviewed policy language: {phrase}")
    if "mailto:" in policy_text.casefold() or "mailto:" in security_text.casefold():
        errors.append("security disclosure surface must not invent an email contact")

    if (root / JEKYLL_CONFIG).read_text(encoding="utf-8") != "include:\n  - .well-known\n":
        errors.append("Jekyll configuration must expose only the reviewed .well-known directory")
    if (root / ".nojekyll").exists():
        errors.append(".nojekyll would publish an unnecessarily broad dotfile surface")

    production = (root / PRODUCTION_READBACK_WORKFLOW).read_text(encoding="utf-8")
    for marker in (
        "Verify private vulnerability reporting setting",
        "--verify-live-setting",
        "artifacts/commonworld-private-vulnerability-reporting.json",
        "steps.security_setting.outcome != 'success'",
    ):
        if marker not in production:
            errors.append(f"production readback is missing reviewed security marker: {marker}")

    weekly = (root / SECURITY_EXPIRY_WORKFLOW).read_text(encoding="utf-8")
    for marker in (
        'cron: "17 5 * * 1"',
        "Validate disclosure policy and expiry",
        "Verify private vulnerability reporting remains enabled",
        "if: always()",
        "artifacts/commonworld-private-vulnerability-reporting-scheduled.json",
        "steps.policy.outcome != 'success'",
        "steps.security_setting.outcome != 'success'",
    ):
        if marker not in weekly:
            errors.append(f"weekly security check is missing reviewed marker: {marker}")
    return errors


def _decode_json_body(raw: bytes) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def github_api_get_private_reporting(repository: str, timeout_seconds: int = 20) -> PrivateReportingFetch:
    endpoint = _private_reporting_endpoint(repository)
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "commonworld-security-policy/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            return PrivateReportingFetch(endpoint, response.geturl(), int(response.status), _decode_json_body(raw))
    except urllib.error.HTTPError as error:
        try:
            raw = error.read()
        except (OSError, http.client.HTTPException):
            raw = b""
        return PrivateReportingFetch(endpoint, error.geturl() or endpoint, int(error.code), _decode_json_body(raw))
    except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError) as error:
        raise RuntimeError(f"private vulnerability reporting transport failed: {type(error).__name__}") from error


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
    if len(expected_sha) != 40 or any(character not in "0123456789abcdef" for character in expected_sha.casefold()):
        errors.append("expected SHA must be a full hexadecimal commit id")

    if not errors:
        try:
            fetch = (api_get or (lambda: github_api_get_private_reporting(repository)))()
            if not isinstance(fetch, PrivateReportingFetch):
                raise RuntimeError("private reporting fetch shape mismatch")
            requested_url, final_url, status = fetch.requested_url, fetch.final_url, fetch.status
            if requested_url != endpoint or final_url != endpoint:
                errors.append("private vulnerability reporting endpoint redirected or mismatched")
            if status != 200:
                errors.append("private vulnerability reporting endpoint did not return HTTP 200")
            if not isinstance(fetch.payload, dict) or not isinstance(fetch.payload.get("enabled"), bool):
                errors.append("private vulnerability reporting response must contain boolean enabled")
            else:
                enabled = fetch.payload["enabled"]
                if enabled is not True:
                    errors.append("private vulnerability reporting must be enabled before publication")
        except RuntimeError as error:
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
        "does_not_establish": [
            "workflow trust or branch protection",
            "response-time SLA",
            "bug bounty",
            "payment promise",
            "broad legal safe harbor",
        ],
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
