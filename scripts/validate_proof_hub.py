#!/usr/bin/env python3
"""Validate the static commonworld proof hub."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROOF_SURFACES_PATH = "proofs/proof-surfaces.json"
REQUIRED_SURFACE_IDS = ["project-profile", "map", "aether"]


class ProofLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: dict[str, str] = {}
        self.duplicates: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        proof_id = values.get("data-proof-link")
        if not proof_id:
            return
        if proof_id in self.links:
            self.duplicates.add(proof_id)
        self.links[proof_id] = values.get("href") or ""


def extract_proof_links(html: str) -> tuple[dict[str, str], set[str]]:
    parser = ProofLinkParser()
    parser.feed(html)
    return parser.links, parser.duplicates


def target_index_for_href(href: str) -> str:
    stripped = href.removeprefix("./").rstrip("/")
    return f"{stripped}/index.html"


def proof_surfaces_path(root: Path = ROOT) -> Path:
    return root / PROOF_SURFACES_PATH


def load_proof_surfaces(root: Path = ROOT) -> list[dict[str, str]]:
    path = proof_surfaces_path(root)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("surfaces", [])


def validate_proof_surface_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    path = proof_surfaces_path(root)
    if not path.is_file():
        return [f"missing proof surface registry: {PROOF_SURFACES_PATH}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["proof surface registry is not valid JSON"]
    if data.get("schema_version") != 1:
        errors.append("proof surface registry must use schema_version 1")
    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list):
        return errors + ["proof surface registry must contain a surfaces list"]
    seen_ids: set[str] = set()
    actual_ids: list[str] = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            errors.append(f"proof surface registry surfaces[{index}] must be an object")
            continue
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"proof surface registry surfaces[{index}] needs id")
            continue
        actual_ids.append(surface_id)
        if surface_id in seen_ids:
            errors.append(f"proof surface registry duplicate id: {surface_id}")
        seen_ids.add(surface_id)
        for field in ("title", "href", "target_index", "role"):
            if not isinstance(surface.get(field), str) or not surface[field]:
                errors.append(f"proof surface registry {surface_id} needs {field}")
        href = surface.get("href")
        if isinstance(href, str) and (not href.startswith("./proofs/") or ".." in Path(href).parts):
            errors.append(f"proof surface registry {surface_id} href must stay under ./proofs/")
        target_index = surface.get("target_index")
        if isinstance(href, str) and isinstance(target_index, str):
            expected_target_index = target_index_for_href(href)
            if target_index != expected_target_index:
                errors.append(
                    f"proof surface registry {surface_id} target_index must match href target: {expected_target_index}"
                )
        if isinstance(target_index, str):
            if not target_index.startswith("proofs/") or ".." in Path(target_index).parts:
                errors.append(f"proof surface registry {surface_id} target_index must stay under proofs/")
            elif not (root / target_index).is_file():
                errors.append(f"proof surface registry target missing for {surface_id}: {target_index}")
    if actual_ids != REQUIRED_SURFACE_IDS:
        errors.append("proof surface registry must list project-profile, map and aether in hub order")
    return errors


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

    registry_errors = validate_proof_surface_registry(root)
    errors.extend(registry_errors)
    surfaces = [] if registry_errors else load_proof_surfaces(root)
    proof_links, duplicate_proof_links = extract_proof_links(html)
    for duplicate_id in sorted(duplicate_proof_links):
        errors.append(f"proof hub duplicate data-proof-link: {duplicate_id}")
    for surface in surfaces:
        proof_id = surface["id"]
        href = surface["href"]
        actual_href = proof_links.get(proof_id)
        if actual_href is None:
            errors.append(f"proof hub missing data-proof-link for {proof_id}")
        elif actual_href != href:
            errors.append(f"proof hub href mismatch for {proof_id}: expected {href}, got {actual_href}")
        target_index = root / surface["target_index"]
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
