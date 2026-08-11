#!/usr/bin/env python3
"""Build bounded DE/EN catalogue recovery pages from canonical records."""

from pathlib import Path
import sys

ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from scripts.catalog_recovery import ROOT, build_recovery


def main() -> int:
    written = build_recovery(ROOT)
    print(f"built {len(written)} bounded DE/EN catalogue recovery pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
