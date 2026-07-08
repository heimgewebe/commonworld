#!/usr/bin/env python3
"""Validate the static commonworld proof hub."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_proof_surfaces import load_proof_surfaces, validate_proof_surface_registry


@dataclass
class ProofCard:
    href: str
    role: str
    texts: list[str] = field(default_factory=list)

    @property
    def visible_text(self) -> str:
        return " ".join(text for text in self.texts if text)


class ProofCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, ProofCard] = {}
        self.duplicates: set[str] = set()
        self.current_proof_id: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        proof_id = values.get("data-proof-link")
        if not proof_id:
            return
        if proof_id in self.cards:
            self.duplicates.add(proof_id)
        self.current_proof_id = proof_id
        self.cards[proof_id] = ProofCard(
            href=values.get("href") or "",
            role=values.get("data-proof-role") or "",
        )

    def handle_data(self, data: str) -> None:
        if not self.current_proof_id:
            return
        text = " ".join(data.split())
        if text:
            self.cards[self.current_proof_id].texts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.current_proof_id = None


def extract_proof_cards(html: str) -> tuple[dict[str, ProofCard], set[str]]:
    parser = ProofCardParser()
    parser.feed(html)
    return parser.cards, parser.duplicates


def extract_proof_links(html: str) -> tuple[dict[str, str], set[str]]:
    cards, duplicates = extract_proof_cards(html)
    return {proof_id: card.href for proof_id, card in cards.items()}, duplicates


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
    proof_cards, duplicate_proof_links = extract_proof_cards(html)
    for duplicate_id in sorted(duplicate_proof_links):
        errors.append(f"proof hub duplicate data-proof-link: {duplicate_id}")
    for surface in surfaces:
        proof_id = surface["id"]
        expected_href = surface["href"]
        expected_title = surface["title"]
        expected_role = surface["role"]
        card = proof_cards.get(proof_id)
        if card is None:
            errors.append(f"proof hub missing data-proof-link for {proof_id}")
        else:
            if card.href != expected_href:
                errors.append(f"proof hub href mismatch for {proof_id}: expected {expected_href}, got {card.href}")
            if card.role != expected_role:
                errors.append(f"proof hub role mismatch for {proof_id}: expected {expected_role}, got {card.role}")
            visible_text = card.visible_text
            if expected_title not in visible_text:
                errors.append(f"proof hub title mismatch for {proof_id}: expected visible title {expected_title}")
            if expected_role not in visible_text:
                errors.append(f"proof hub visible role missing for {proof_id}: expected {expected_role}")
        target_index = root / surface["target_index"]
        if not target_index.is_file():
            errors.append(f"proof hub link target missing: {target_index.relative_to(root)}")

    required_html_tokens = (
        "COMMONWORLD-ATLAS-V1-T007",
        "Project profile",
        "Map",
        "Aether",
        "Understand one CommonProject",
        "Role: understand one CommonProject",
        "Role: render location-safe CommonProjects",
        "Role: focus digital, hidden-location and hybrid Aether projections",
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
        ".proof-role",
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
