#!/usr/bin/env python3
"""Run the canonical browser smoke plan and bind the public result to evidence."""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

try:
    from scripts.browser_smoke_plan import materialize_browser_smoke_plan
except ModuleNotFoundError:  # Direct script execution adds scripts/ to sys.path.
    from browser_smoke_plan import materialize_browser_smoke_plan

ROOT = Path(__file__).resolve().parents[1]


def run(argv: tuple[str, ...]) -> None:
    result = subprocess.run(argv, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--public-only',
        action='store_true',
        help='Run only the fresh public smoke and its evidence validator.',
    )
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='commonworld-browser-smoke-') as directory:
        actual = Path(directory) / 'public-smoke.json'
        for command in materialize_browser_smoke_plan(actual, public_only=args.public_only):
            run(command)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
