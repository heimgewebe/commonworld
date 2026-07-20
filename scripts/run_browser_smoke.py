#!/usr/bin/env python3
"""Run the complete browser smoke suite and bind the public result to evidence."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> None:
    result = subprocess.run(argv, cwd=ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='commonworld-browser-smoke-') as directory:
        actual = Path(directory) / 'public-smoke.json'
        run(['node', 'scripts/smoke_public_browser.mjs', '--result', str(actual)])
        run(['python3', 'scripts/validate_catalog_delivery_budget.py', '--smoke-result', str(actual)])
    run(['node', 'scripts/smoke_proposal_browser.mjs'])
    run(['node', 'scripts/smoke_focus_overlay_browser.mjs'])
    run(['node', 'scripts/smoke_accessibility_modes_browser.mjs'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
