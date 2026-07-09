#!/usr/bin/env python3
"""Validate the static commonworld proof hub."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_proof_surfaces import load_proof_surfaces, validate_proof_surface_registry

CATALOG_EXPORT_PATH = Path("examples/commonworld/catalog-export.sample.json")
SEARCH_INDEX_INPUT_PATH = Path("examples/commonworld/search-index-input.sample.json")
EXPECTED_CATALOG_METRICS = (
    ("entries", "Entries"),
    ("curation.fixture", "Fixture"),
    ("curation.candidate", "Candidate"),
    ("curation.curated", "Curated"),
    ("curation.archived", "Archived"),
    ("location.approximate", "Approximate location"),
    ("location.exact", "Exact location"),
    ("location.hidden", "Hidden location"),
)


def load_project_preview_entries(root: Path = ROOT) -> list[dict]:
    path = root / SEARCH_INDEX_INPUT_PATH
    with path.open(encoding="utf-8") as handle:
        search_input = json.load(handle)
    return list(search_input.get("entries", []))


def _title_case_label(value: str) -> str:
    return value.replace("-", " ").title()


def load_catalog_snapshot_metrics(root: Path = ROOT) -> dict[str, int]:
    path = root / CATALOG_EXPORT_PATH
    with path.open(encoding="utf-8") as handle:
        export = json.load(handle)
    entries = export.get("entries", [])
    curation = Counter(entry.get("curation_state") for entry in entries)
    locations = Counter(entry.get("location_mode") for entry in entries)
    return {
        "entries": len(entries),
        "curation.fixture": curation.get("fixture", 0),
        "curation.candidate": curation.get("candidate", 0),
        "curation.curated": curation.get("curated", 0),
        "curation.archived": curation.get("archived", 0),
        "location.approximate": locations.get("approximate", 0),
        "location.exact": locations.get("exact", 0),
        "location.hidden": locations.get("hidden", 0),
    }


@dataclass
class ProofCard:
    href: str
    role: str
    texts: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)

    @property
    def visible_text(self) -> str:
        return " ".join(text for text in self.texts if text)

    @property
    def heading_text(self) -> str:
        return " ".join(text for text in self.headings if text)


class ProofCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, ProofCard] = {}
        self.duplicates: set[str] = set()
        self.current_proof_id: str | None = None
        self.in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2" and self.current_proof_id:
            self.in_heading = True
            return
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
            card = self.cards[self.current_proof_id]
            card.texts.append(text)
            if self.in_heading:
                card.headings.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self.in_heading = False
        if tag == "a":
            self.current_proof_id = None
            self.in_heading = False


@dataclass
class ProjectPreviewCard:
    attrs: dict[str, str]
    texts: list[str] = field(default_factory=list)

    @property
    def visible_text(self) -> str:
        return " ".join(text for text in self.texts if text)


class ProjectPreviewParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, ProjectPreviewCard] = {}
        self.duplicates: set[str] = set()
        self.current_project_id: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "article" and "project-preview-card" in values.get("class", ""):
            project_id = values.get("data-project-id")
            if not project_id:
                return
            if project_id in self.cards:
                self.duplicates.add(project_id)
            self.current_project_id = project_id
            self.cards[project_id] = ProjectPreviewCard(attrs=values)

    def handle_data(self, data: str) -> None:
        if not self.current_project_id:
            return
        text = " ".join(data.split())
        if text:
            self.cards[self.current_project_id].texts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "article":
            self.current_project_id = None


def extract_project_preview_cards(html: str) -> tuple[dict[str, ProjectPreviewCard], set[str]]:
    parser = ProjectPreviewParser()
    parser.feed(html)
    return parser.cards, parser.duplicates


def extract_proof_cards(html: str) -> tuple[dict[str, ProofCard], set[str]]:
    parser = ProofCardParser()
    parser.feed(html)
    return parser.cards, parser.duplicates


def extract_proof_links(html: str) -> tuple[dict[str, str], set[str]]:
    cards, duplicates = extract_proof_cards(html)
    return {proof_id: card.href for proof_id, card in cards.items()}, duplicates



def validate_catalog_snapshot_panel(html: str, css: str, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    catalog_path = root / CATALOG_EXPORT_PATH
    if not catalog_path.is_file():
        return [f"proof hub catalog snapshot source missing: {CATALOG_EXPORT_PATH}"]
    if 'class="catalog-snapshot"' not in html:
        errors.append("proof hub catalog snapshot panel missing")
    if 'data-catalog-source="examples/commonworld/catalog-export.sample.json"' not in html:
        errors.append("proof hub catalog snapshot source missing or drifted")
    if "Static catalog facts before runtime." not in html:
        errors.append("proof hub catalog snapshot title missing")
    if "not a live API, ranking system or publication queue" not in html:
        errors.append("proof hub catalog snapshot boundary missing")
    metrics = load_catalog_snapshot_metrics(root)
    for key, label in EXPECTED_CATALOG_METRICS:
        expected = metrics[key]
        token = f'data-catalog-metric="{key}">{expected}</'
        expected_occurrences = 2 if key == "entries" else 1
        actual_occurrences = html.count(token)
        if actual_occurrences != expected_occurrences:
            errors.append(
                f"proof hub catalog metric mismatch for {key}: expected {expected} in {expected_occurrences} places, got {actual_occurrences}"
            )
        if label not in html:
            errors.append(f"proof hub catalog metric label missing: {label}")
    for token in (".catalog-snapshot", ".catalog-metrics"):
        if token.startswith(".") and token not in css:
            errors.append(f"proof hub CSS missing {token}")
    return errors


def validate_project_preview_panel(html: str, css: str, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    search_path = root / SEARCH_INDEX_INPUT_PATH
    if not search_path.is_file():
        return [f"proof hub project preview source missing: {SEARCH_INDEX_INPUT_PATH}"]
    if 'class="project-preview-grid"' not in html:
        errors.append("proof hub project preview grid missing")
    if 'data-project-preview-source="examples/commonworld/search-index-input.sample.json"' not in html:
        errors.append("proof hub project preview source missing or drifted")
    cards, duplicates = extract_project_preview_cards(html)
    for duplicate_id in sorted(duplicates):
        errors.append(f"proof hub duplicate project preview card: {duplicate_id}")
    entries = load_project_preview_entries(root)
    expected_ids = [entry.get("id") for entry in entries]
    if len(cards) != len(entries):
        errors.append(f"proof hub project preview count mismatch: expected {len(entries)}, got {len(cards)}")
    if list(cards.keys()) != expected_ids:
        errors.append(f"proof hub project preview order mismatch: expected {expected_ids}, got {list(cards.keys())}")
    for entry in entries:
        project_id = entry.get("id", "")
        card = cards.get(project_id)
        if card is None:
            errors.append(f"proof hub project preview missing: {project_id}")
            continue
        expected_attrs = {
            "data-project-curation": entry.get("curation_state", ""),
            "data-project-location-mode": entry.get("location_mode", ""),
            "data-project-path": entry.get("project_path", ""),
        }
        for attr, expected in expected_attrs.items():
            actual = card.attrs.get(attr, "")
            if actual != expected:
                errors.append(f"proof hub project preview {attr} mismatch for {project_id}: expected {expected}, got {actual}")
        visible = card.visible_text
        for token in (
            entry.get("title", ""),
            entry.get("summary", ""),
            entry.get("location_label", ""),
            _title_case_label(entry.get("curation_state", "")),
            f"{_title_case_label(entry.get('location_mode', ''))} location",
            f"Handoff {entry.get('profile_handoff_state', '')}",
        ):
            if token and token not in visible:
                errors.append(f"proof hub project preview visible token missing for {project_id}: {token}")
        for aspect in entry.get("aspects", []):
            label = aspect.get("label", "")
            if label and label not in visible:
                errors.append(f"proof hub project preview aspect missing for {project_id}: {label}")
    for token in (".project-preview-grid", ".project-preview-card", ".project-preview-meta", ".project-preview-aspects"):
        if token not in css:
            errors.append(f"proof hub CSS missing {token}")
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
    proof_cards, duplicate_proof_links = extract_proof_cards(html)
    registered_proof_ids = {surface["id"] for surface in surfaces}
    for duplicate_id in sorted(duplicate_proof_links):
        errors.append(f"proof hub duplicate data-proof-link: {duplicate_id}")
    for extra_id in sorted(set(proof_cards) - registered_proof_ids):
        errors.append(f"proof hub unregistered data-proof-link: {extra_id}")
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
            if card.heading_text != expected_title:
                errors.append(
                    f"proof hub heading mismatch for {proof_id}: expected {expected_title}, got {card.heading_text}"
                )
            visible_text = card.visible_text
            if expected_role not in visible_text:
                errors.append(f"proof hub visible role missing for {proof_id}: expected {expected_role}")
            if "Surface type" not in visible_text:
                errors.append(f"proof hub surface type missing for {proof_id}")
            if "Evidence mode" not in visible_text:
                errors.append(f"proof hub evidence mode missing for {proof_id}")
        target_index = root / surface["target_index"]
        if not target_index.is_file():
            errors.append(f"proof hub link target missing: {target_index.relative_to(root)}")

    required_html_tokens = (
        "COMMONWORLD-ATLAS-V1-T007",
        "Project profile",
        "Map",
        "Aether",
        "Search",
        "Understand one CommonProject",
        "Role: understand one CommonProject",
        "Role: render location-safe CommonProjects",
        "Role: focus digital, hidden-location and hybrid Aether projections",
        "Role: filter static search index input",
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
        "Surface taxonomy",
        "Different proofs answer different questions.",
        "Visual explanation",
        "Location rendering",
        "Projection focus",
        "Static data-quality check",
        "Surface type",
        "Evidence mode",
        "Static fixture profile",
        "Static map plus offline smoke",
        "Static Aether branch",
        "Search input and query fixtures",
    )
    for token in required_html_tokens:
        if token not in html:
            errors.append(f"proof hub HTML missing {token}")
    errors.extend(validate_catalog_snapshot_panel(html, css, root))
    errors.extend(validate_project_preview_panel(html, css, root))

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
        ".proof-classification",
        ".surface-taxonomy",
        ".catalog-snapshot",
        ".catalog-metrics",
        ".project-preview-grid",
        ".project-preview-card",
        ".project-preview-meta",
        ".project-preview-aspects",
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
