#!/usr/bin/env python3
"""Check whether commonworld.net DNS points at GitHub Pages."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Iterable

APEX = "commonworld.net"
WWW = "www.commonworld.net"
EXPECTED_APEX_A = (
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
)
EXPECTED_APEX_AAAA = (
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
)
EXPECTED_WWW_CNAME = "heimgewebe.github.io."
FORBIDDEN_PARKING_A = "185.181.104.242"


@dataclass(frozen=True)
class ObservedDns:
    apex_a: tuple[str, ...]
    apex_aaaa: tuple[str, ...]
    apex_cname: tuple[str, ...]
    www_a: tuple[str, ...]
    www_aaaa: tuple[str, ...]
    www_cname: tuple[str, ...]


@dataclass(frozen=True)
class DnsTargetReceipt:
    check_id: str
    domain: str
    expected_apex_a: tuple[str, ...]
    expected_apex_aaaa: tuple[str, ...]
    expected_www_cname: str
    observed: ObservedDns


def normalize(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(value.strip() for value in values if value.strip()))


def dig_short(name: str, record_type: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["dig", "+short", name, record_type],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"dig failed for {name} {record_type}: {completed.stderr.strip()}")
    return normalize(completed.stdout.splitlines())


def observe_dns() -> ObservedDns:
    return ObservedDns(
        apex_a=dig_short(APEX, "A"),
        apex_aaaa=dig_short(APEX, "AAAA"),
        apex_cname=dig_short(APEX, "CNAME"),
        www_a=dig_short(WWW, "A"),
        www_aaaa=dig_short(WWW, "AAAA"),
        www_cname=dig_short(WWW, "CNAME"),
    )


def validate_observed(observed: ObservedDns) -> list[str]:
    errors: list[str] = []
    if observed.apex_a != normalize(EXPECTED_APEX_A):
        errors.append(f"apex A mismatch: expected {list(EXPECTED_APEX_A)}, got {list(observed.apex_a)}")
    if observed.apex_aaaa != normalize(EXPECTED_APEX_AAAA):
        errors.append(f"apex AAAA mismatch: expected {list(EXPECTED_APEX_AAAA)}, got {list(observed.apex_aaaa)}")
    if observed.apex_cname:
        errors.append(f"apex must not have CNAME records: got {list(observed.apex_cname)}")
    if observed.www_cname != (EXPECTED_WWW_CNAME,):
        errors.append(f"www CNAME mismatch: expected {EXPECTED_WWW_CNAME}, got {list(observed.www_cname)}")
    if observed.www_a:
        errors.append(f"www must not have A records when CNAME is used: got {list(observed.www_a)}")
    if observed.www_aaaa:
        errors.append(f"www must not have AAAA records when CNAME is used: got {list(observed.www_aaaa)}")
    if FORBIDDEN_PARKING_A in observed.apex_a or FORBIDDEN_PARKING_A in observed.www_a:
        errors.append(f"INWX parking A record still present: {FORBIDDEN_PARKING_A}")
    return errors


def receipt_for(observed: ObservedDns) -> DnsTargetReceipt:
    return DnsTargetReceipt(
        check_id="commonworld.pages-dns-target.v1",
        domain=APEX,
        expected_apex_a=EXPECTED_APEX_A,
        expected_apex_aaaa=EXPECTED_APEX_AAAA,
        expected_www_cname=EXPECTED_WWW_CNAME,
        observed=observed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check commonworld.net DNS target records for GitHub Pages.")
    parser.add_argument("--json", action="store_true", help="Print JSON receipt even on success")
    args = parser.parse_args()
    try:
        observed = observe_dns()
        errors = validate_observed(observed)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if errors:
        print("ERROR: commonworld Pages DNS target validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(json.dumps(asdict(receipt_for(observed)), indent=2, sort_keys=True))
        return 1
    if args.json:
        print(json.dumps(asdict(receipt_for(observed)), indent=2, sort_keys=True))
    else:
        print("commonworld Pages DNS target validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
