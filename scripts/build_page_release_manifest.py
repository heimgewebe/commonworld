#!/usr/bin/env python3
"""Build the tiny cache-bypassed manifest used to detect stale public HTML."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_cache import page_build_metadata

PUBLIC_PAGES = (
    "index.html",
    "de.html",
    "method.html",
    "method.de.html",
    "propose.html",
    "propose.de.html",
)
TARGET = ROOT / "assets/commonworld-page-builds.json"


def build_manifest(root: Path = ROOT) -> dict[str, object]:
    pages: dict[str, str] = {}
    for relative in PUBLIC_PAGES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing rendered public page: {relative}")
        declared_page, build = page_build_metadata(path.read_text(encoding="utf-8"))
        if declared_page != relative:
            raise ValueError(f"public page identity mismatch: {relative} declares {declared_page}")
        pages[relative] = build
    return {
        "kind": "commonworld.page_build_manifest",
        "pages": pages,
        "schema_version": 1,
    }


def main() -> int:
    payload = json.dumps(build_manifest(ROOT), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    TARGET.write_text(payload, encoding="utf-8")
    print("commonworld deterministic public page-build manifest generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
