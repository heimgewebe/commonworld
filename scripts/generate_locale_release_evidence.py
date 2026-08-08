#!/usr/bin/env python3
"""Generate digest-bound locale release-evidence scaffolds.

This generator never invents passed independent reviews. Scaffolds stay
``pending``/``candidate`` until real receipt sources exist and are hash-bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.locale_registry import locale_entry
from scripts.locale_review_evidence import reviewed_source_pack_sha256
from scripts.validate_locale_release import load_contract

PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
CATALOG_LOCALE_DIR = ROOT / "catalog/locales"
OUT_DIR = ROOT / "docs/evidence/locale-releases"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def required_receipt_names(entry: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    evidence = contract.get("release_evidence", {})
    names = list(evidence.get("required_receipts", []))
    if entry.get("direction") == "rtl":
        names.extend(evidence.get("rtl_additional_receipts", []))
    return names


def build_scaffold(locale: str, *, root: Path = ROOT) -> dict[str, Any]:
    contract = load_contract(root / "docs/architecture/locale-release.contract.json")
    entry = locale_entry(locale, root)
    if not entry:
        raise SystemExit(f"unknown locale: {locale}")
    surfaces = entry.get("surface_files")
    if not isinstance(surfaces, dict) or not surfaces:
        raise SystemExit(f"locale {locale} has no surface_files")
    pack_path = root / PACK_PATH.relative_to(ROOT)
    pack_digest = sha256_file(pack_path)
    reviewed_pack_digest = reviewed_source_pack_sha256(pack_path)
    catalog_overlay_digest = sha256_file(root / CATALOG_LOCALE_DIR.relative_to(ROOT) / f"{locale}.json")
    surface_sha = {
        surface: sha256_file(root / relative)
        for surface, relative in surfaces.items()
    }
    receipt_names = required_receipt_names(entry, contract)
    required_surfaces = set(contract.get("release_gate", {}).get("required_surfaces", []))
    rtl = entry.get("direction") == "rtl"
    return {
        "schema_version": 2,
        "kind": "commonworld.ui_locale_release_evidence",
        "locale": locale,
        "status": "pending",
        "source_revision": git_head(root),
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_pack_digest,
        "catalog_overlay_sha256": catalog_overlay_digest,
        "surface_sha256": surface_sha,
        "gate_results": {
            "required_surfaces_passed": sorted(required_surfaces),
            "translation_coverage_ratio": 1.0,
            "untranslated_ui_markers": 0,
            "missing_runtime_keys": 0,
            "machine_translation_only": False,
            "independent_language_review_passed": False,
            "keyboard_and_screen_reader_review_passed": False,
            "browser_smoke_passed": False,
            "state_preservation_smoke_passed": False,
            "directional_layout_review": "pending" if rtl else "not_required",
            "mixed_script_review": "pending" if rtl else "not_required",
        },
        "evidence_receipts": {
            name: {
                "source": f"docs/evidence/locale-releases/receipts/{locale}/{name}.json",
                "sha256": "0" * 64,
            }
            for name in receipt_names
        },
        "review_class": {
            "machine_translation_only": False,
            "independent_of_writer": True,
            "model_assisted_editorial_review": True,
            "claims_native_or_human_review": False,
            "digest_bound": True,
            "findings_based": True,
            "post_fix_review_required": True,
        },
        "notes": (
            "Scaffold only. Receipt placeholders use a zero digest and must be "
            "replaced with real source files whose SHA-256 is validated before any "
            "release claim. Status remains pending/candidate until independent "
            "post-fix review passes."
        ),
    }


def write_scaffold(locale: str, *, root: Path = ROOT, force: bool = False) -> Path:
    out = root / OUT_DIR.relative_to(ROOT) / f"{locale}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing evidence without --force: {out}")
    payload = build_scaffold(locale, root=root)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locale", help="Wave-1 or non-baseline locale tag, e.g. es")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing scaffold. Never invents passed receipts.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the scaffold JSON instead of writing docs/evidence/locale-releases/.",
    )
    args = parser.parse_args(argv)
    payload = build_scaffold(args.locale)
    if args.stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    path = write_scaffold(args.locale, force=args.force)
    print(f"wrote pending release-evidence scaffold: {path.relative_to(ROOT)}")
    print("status remains pending; no review receipt is marked passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
