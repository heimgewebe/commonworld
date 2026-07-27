#!/usr/bin/env python3
"""Validate Commonworld's vulnerability-disclosure policy and RFC 9116 surface."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SECURITY_POLICY = Path("SECURITY.md")
SECURITY_TXT = Path(".well-known/security.txt")
JEKYLL_CONFIG = Path("_config.yml")
EXPECTED_CONTACT = "https://github.com/heimgewebe/commonworld/security/advisories/new"
EXPECTED_POLICY = "https://github.com/heimgewebe/commonworld/security/policy"
EXPECTED_CANONICAL = "https://commonworld.net/.well-known/security.txt"
EXPECTED_LANGUAGES = "en, de"
ALLOWED_FIELDS = {"Contact", "Expires", "Preferred-Languages", "Canonical", "Policy"}
MAX_BYTES = 32 * 1024
MAX_LINES = 1000
MIN_REMAINING_VALIDITY = timedelta(days=30)
MAX_REMAINING_VALIDITY = timedelta(days=366)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _https_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


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

    for path in (SECURITY_POLICY, SECURITY_TXT, JEKYLL_CONFIG):
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
            expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            errors.append("security.txt Expires must be RFC 3339")
        else:
            if expires.tzinfo is None:
                errors.append("security.txt Expires must include a timezone")
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
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    errors = validate_security_policy(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld security disclosure policy validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
