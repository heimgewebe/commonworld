#!/usr/bin/env python3
"""Validate the static commonworld proof hub."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROOF_LINKS = {
    "project-profile": "./proofs/mixed-node/",
    "map": "./proofs/map/",
    "aether": "./proofs/aether/",
}


def validate_proof_hub(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    html_path = root / "index.html"
    css_path = root / "index.css"

    if not html_path.is_file():
        return ["missing proof hub: index.html"]
    if not css_path.is_file():
        errors.append("missing proof hub stylesheet: index.css")
        return errors

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")

    for proof_id, href in PROOF_LINKS.items():
        if f'data-proof-link="{proof_id}"' not in html:
            errors.append(f"proof hub missing data-proof-link for {proof_id}")
        if f'href="{href}"' not in html:
            errors.append(f"proof hub missing href for {proof_id}: {href}")
        target_index = root / href.replace("./", "") / "index.html"
        if not target_index.is_file():
            errors.append(f"proof hub link target missing: {target_index.relative_to(root)}")

    required_html_tokens = (
        "COMMONWORLD-ATLAS-V1-T007",
        "Project profile",
        "Map",
        "Aether",
        "Understand one CommonProject",
        "No backend",
        "No public submissions",
        "No user accounts",
        "No weltgewebe write path",
        "No governance or handoff action",
        "Curation states",
        "Fixture",
        "Candidate",
        "Curated",
        "Archived",
        "Trust state is visible before action",
    )
    for token in required_html_tokens:
        if token not in html:
            errors.append(f"proof hub HTML missing {token}")

    forbidden_terms = (
        "form action",
        "method=\"post\"",
        "type=\"submit\"",
        "login",
        "signup",
    )
    lowered = html.casefold()
    for term in forbidden_terms:
        if term in lowered:
            errors.append(f"proof hub must not introduce interactive runtime affordance: {term}")

    required_css_tokens = (
        ".hub-shell",
        ".hub-hero",
        ".proof-grid",
        ".proof-card",
        ".trust-panel",
        ".boundary-panel",
        ":focus-visible",
    )
    for token in required_css_tokens:
        if token not in css:
            errors.append(f"proof hub CSS missing {token}")

    return errors


def main() -> int:
    errors = validate_proof_hub(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld proof hub validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
