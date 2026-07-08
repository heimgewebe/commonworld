#!/usr/bin/env python3
"""Validate the shared commonworld proof aspect module."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.proof_shared import validate_shared_module


def main() -> int:
    errors = validate_shared_module(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld shared aspect module validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
