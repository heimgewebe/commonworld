#!/usr/bin/env python3
"""Deterministic offline smoke for the static proof hub.

This is intentionally not a browser screenshot test. It models the visible hub
contract from committed HTML, CSS and the proof-surface registry while keeping
CI offline and free of runtime dependencies.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_proof_hub import extract_project_preview_cards, extract_proof_cards, load_project_preview_entries, validate_proof_hub
from scripts.validate_proof_surfaces import load_proof_surfaces

EXPECTED_SURFACE_TYPES = {
    "project-profile": "Visual explanation",
    "map": "Location rendering",
    "aether": "Projection focus",
    "search": "Static data-quality check",
}

EXPECTED_EVIDENCE_MODES = {
    "project-profile": "Static fixture profile",
    "map": "Static map plus offline smoke",
    "aether": "Static Aether branch",
    "search": "Search input and query fixtures",
}

EXPECTED_BOUNDARY_NEGATIONS = (
    "No backend.",
    "No public submissions.",
    "No user accounts.",
    "No weltgewebe write path.",
    "No governance or handoff action.",
)

EXPECTED_TRUST_STATES = ("Fixture", "Candidate", "Curated", "Archived")

FORBIDDEN_RUNTIME_TOKENS = (
    "<script",
    "<form",
    "type=\"submit\"",
    "type='submit'",
    "method=\"post\"",
    "method='post'",
    "login",
    "signup",
    "localStorage",
    "indexedDB",
    "fetch(\"/",
    "fetch('/",
)


@dataclass(frozen=True)
class HubSurfaceSmokeCard:
    proof_id: str
    title: str
    href: str
    role: str
    surface_type: str
    evidence_mode: str


@dataclass(frozen=True)
class HubOfflineSmokeReport:
    smoke_id: str
    network_mode: str
    browser_mode: str
    surfaces: tuple[HubSurfaceSmokeCard, ...]
    taxonomy_entries: tuple[str, ...]
    trust_states: tuple[str, ...]
    boundary_negations: tuple[str, ...]
    assertions: tuple[str, ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _between(text: str, left: str, right: str) -> str:
    start = text.find(left)
    if start < 0:
        return ""
    start += len(left)
    end = text.find(right, start)
    if end < 0:
        return text[start:]
    return text[start:end]


def _extract_classification_value(card_text: str, label: str) -> str:
    dl_text = _between(card_text, '<dl class="proof-classification">', "</dl>")
    value = _between(dl_text, f"<dt>{label}</dt><dd>", "</dd>")
    return _normalise(value)


def expected_hub_cards(root: Path = ROOT) -> tuple[HubSurfaceSmokeCard, ...]:
    html = _read(root / "index.html")
    cards, duplicates = extract_proof_cards(html)
    if duplicates:
        raise ValueError(f"duplicate proof cards: {sorted(duplicates)}")
    output: list[HubSurfaceSmokeCard] = []
    for surface in load_proof_surfaces(root):
        proof_id = surface["id"]
        card = cards.get(proof_id)
        if card is None:
            raise ValueError(f"missing proof card: {proof_id}")
        card_html = _between(html, f'data-proof-link="{proof_id}"', "</a>")
        output.append(
            HubSurfaceSmokeCard(
                proof_id=proof_id,
                title=surface["title"],
                href=card.href,
                role=card.role,
                surface_type=_extract_classification_value(card_html, "Surface type"),
                evidence_mode=_extract_classification_value(card_html, "Evidence mode"),
            )
        )
    return tuple(output)


def smoke_report(root: Path = ROOT) -> HubOfflineSmokeReport:
    html = _read(root / "index.html")
    taxonomy_section = _between(html, '<section class="surface-taxonomy"', "</section>")
    trust_section = _between(html, '<section class="trust-panel"', "</section>")
    boundary_section = _between(html, '<section class="boundary-panel"', "</section>")
    taxonomy_entries = tuple(
        entry for entry in EXPECTED_SURFACE_TYPES.values() if entry in taxonomy_section
    )
    trust_states = tuple(state for state in EXPECTED_TRUST_STATES if f"<strong>{state}</strong>" in trust_section)
    boundary_negations = tuple(item for item in EXPECTED_BOUNDARY_NEGATIONS if item in boundary_section)
    return HubOfflineSmokeReport(
        smoke_id="commonworld.proof-hub.offline-surface-smoke.v1",
        network_mode="offline-static",
        browser_mode="not-started",
        surfaces=expected_hub_cards(root),
        taxonomy_entries=taxonomy_entries,
        trust_states=trust_states,
        boundary_negations=boundary_negations,
        assertions=(
            "all registered proof surfaces appear as visible cards",
            "each card exposes a surface type and evidence mode",
            "taxonomy panel explains the four surface categories",
            "visual hierarchy separates proof surfaces, catalog facts and project previews",
            "static catalog snapshot remains tied to the committed catalog export",
            "static project preview cards remain tied to committed search-index input",
            "trust and boundary panels remain visible",
            "hub introduces no script, form, account or submission affordance",
        ),
    )


def validate_offline_hub_smoke(root: Path = ROOT) -> list[str]:
    errors = validate_proof_hub(root)
    html_path = root / "index.html"
    css_path = root / "index.css"
    if not html_path.is_file():
        return errors + ["offline hub smoke missing index.html"]
    if not css_path.is_file():
        return errors + ["offline hub smoke missing index.css"]

    html = _read(html_path)
    css = _read(css_path)
    lowered_html = html.casefold()
    for token in FORBIDDEN_RUNTIME_TOKENS:
        if token.casefold() in lowered_html:
            errors.append(f"offline hub smoke forbids runtime affordance: {token}")

    for token in (
        "hub-shell",
        "surface-taxonomy",
        "proof-surfaces",
        "section-heading",
        "proof-grid",
        "proof-card",
        "trust-panel",
        "catalog-snapshot",
        "catalog-metrics",
        "project-preview-heading",
        "project-preview-grid",
        "project-preview-card",
        "boundary-panel",
    ):
        if token not in html:
            errors.append(f"offline hub smoke HTML missing landmark: {token}")
    for token in (
        ".hub-shell",
        ".surface-taxonomy",
        ".proof-surfaces",
        ".section-heading",
        ".proof-grid",
        ".proof-card",
        ".proof-classification",
        ".catalog-snapshot",
        ".catalog-metrics",
        ".project-preview-heading",
        ".project-preview-grid",
        ".project-preview-card",
        ":focus-visible",
    ):
        if token not in css:
            errors.append(f"offline hub smoke CSS missing token: {token}")

    try:
        cards = expected_hub_cards(root)
    except ValueError as error:
        errors.append(f"offline hub smoke card extraction failed: {error}")
        return errors
    if len(cards) != len(load_proof_surfaces(root)):
        errors.append("offline hub smoke card count does not match proof-surface registry")
    seen_ids = {card.proof_id for card in cards}
    for proof_id, expected_type in EXPECTED_SURFACE_TYPES.items():
        if proof_id not in seen_ids:
            errors.append(f"offline hub smoke missing proof card: {proof_id}")
            continue
        card = next(item for item in cards if item.proof_id == proof_id)
        if card.surface_type != expected_type:
            errors.append(
                f"offline hub smoke surface type mismatch for {proof_id}: expected {expected_type}, got {card.surface_type}"
            )
        expected_evidence = EXPECTED_EVIDENCE_MODES[proof_id]
        if card.evidence_mode != expected_evidence:
            errors.append(
                f"offline hub smoke evidence mode mismatch for {proof_id}: expected {expected_evidence}, got {card.evidence_mode}"
            )

    preview_cards, preview_duplicates = extract_project_preview_cards(html)
    if preview_duplicates:
        errors.append(f"offline hub smoke duplicate project previews: {sorted(preview_duplicates)}")
    expected_preview_ids = [entry.get("id") for entry in load_project_preview_entries(root)]
    if list(preview_cards.keys()) != expected_preview_ids:
        errors.append(
            f"offline hub smoke project preview order mismatch: expected {expected_preview_ids}, got {list(preview_cards.keys())}"
        )

    report = smoke_report(root)
    if report.taxonomy_entries != tuple(EXPECTED_SURFACE_TYPES.values()):
        errors.append(
            f"offline hub smoke taxonomy entries mismatch: expected {tuple(EXPECTED_SURFACE_TYPES.values())}, got {report.taxonomy_entries}"
        )
    if report.trust_states != EXPECTED_TRUST_STATES:
        errors.append(f"offline hub smoke trust states mismatch: expected {EXPECTED_TRUST_STATES}, got {report.trust_states}")
    if report.boundary_negations != EXPECTED_BOUNDARY_NEGATIONS:
        errors.append(
            f"offline hub smoke boundary negations mismatch: expected {EXPECTED_BOUNDARY_NEGATIONS}, got {report.boundary_negations}"
        )
    return errors


def main() -> int:
    errors = validate_offline_hub_smoke(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = smoke_report(ROOT)
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
