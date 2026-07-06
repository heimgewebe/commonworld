#!/usr/bin/env python3
"""Validate the static commonworld privacy-aware map proof."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_contracts import iter_project_examples, validate_all
from scripts.validate_mixed_node_proof import load_json


@dataclass(frozen=True)
class MapProjection:
    project_id: str
    mode: str
    renderable: bool
    requires_halo: bool
    reason: str


def proof_dir(root: Path = ROOT) -> Path:
    return root / "proofs" / "map"


def expected_proof_files(root: Path = ROOT) -> tuple[Path, ...]:
    directory = proof_dir(root)
    return (
        directory / "index.html",
        directory / "map.css",
        directory / "map.js",
        directory / "README.md",
    )


def load_projects(root: Path = ROOT) -> list[dict[str, Any]]:
    return [load_json(path) for path in iter_project_examples(root)]


def classify_project(project: dict[str, Any]) -> MapProjection:
    location = project.get("location", {})
    mode = location.get("mode", "")
    coordinates = location.get("coordinates")

    if mode == "hidden":
        return MapProjection(project["id"], mode, False, False, "hidden location")
    if not coordinates:
        return MapProjection(project["id"], mode, False, False, "missing coordinates")
    if mode == "approximate":
        return MapProjection(project["id"], mode, True, True, "approximate location")
    if mode == "exact":
        return MapProjection(project["id"], mode, True, False, "exact location")
    return MapProjection(project["id"], mode, False, False, "unsupported location mode")


def validate_map_projection(projects: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    projections = {projection.project_id: projection for projection in map(classify_project, projects)}

    for project in projects:
        projection = projections[project["id"]]
        location = project.get("location", {})
        if projection.renderable:
            coordinates = location.get("coordinates", {})
            if "lat" not in coordinates or "lon" not in coordinates:
                errors.append(f"{project['id']} renderable map project must include lat/lon")
        if location.get("mode") == "hidden" and projection.renderable:
            errors.append(f"{project['id']} hidden project must not be map-renderable")

    if "openstreetmap" in projections and projections["openstreetmap"].renderable:
        errors.append("openstreetmap must stay hidden in the map proof")

    fixture_projection = projections.get("neighborhood-repair-circle-fixture")
    if fixture_projection:
        if not fixture_projection.renderable:
            errors.append("neighborhood-repair-circle-fixture must be renderable in the map proof")
        if not fixture_projection.requires_halo:
            errors.append("neighborhood-repair-circle-fixture must require an approximate-location halo")

    return errors


def validate_scope_text(readme: str, html: str, js: str) -> list[str]:
    errors: list[str] = []
    forbidden_terms = (
        "public submissions",
        "weltgewebe write path",
        "SvelteKit commitment",
    )
    boundary_text = readme.casefold()
    for term in forbidden_terms:
        if term.casefold() not in boundary_text:
            errors.append(f"map proof README must state boundary: {term}")

    if "CDN" not in readme or "tile" not in readme:
        errors.append("map proof README must document CDN and tile dependencies")
    if "hidden digital projects are skipped" not in html.casefold():
        errors.append("map proof HTML must explain hidden digital projects are skipped")
    if "location privacy" not in html.casefold():
        errors.append("map proof HTML must describe location privacy")
    if "isMapRenderable" not in js or 'mode !== "hidden"' not in js:
        errors.append("map proof JS must include an explicit hidden-location filter")
    if "approximate-halo" not in js:
        errors.append("map proof JS must add approximate-halo for approximate locations")
    if "Seed manifest must contain project_paths." not in js:
        errors.append("map proof JS must validate the seed manifest project_paths list")

    return errors


def validate_map_proof(root: Path = ROOT) -> list[str]:
    errors = validate_all(root)

    missing_files: list[Path] = []
    for path in expected_proof_files(root):
        if not path.is_file():
            errors.append(f"missing map proof file: {path.relative_to(root)}")
            missing_files.append(path)
    if missing_files:
        return errors

    directory = proof_dir(root)
    html = (directory / "index.html").read_text(encoding="utf-8")
    css = (directory / "map.css").read_text(encoding="utf-8")
    js = (directory / "map.js").read_text(encoding="utf-8")
    readme = (directory / "README.md").read_text(encoding="utf-8")

    required_html_tokens = (
        "map-container",
        "data-load-state",
        "data-detail-surface",
        "data-detail-privacy",
        "MapLibre",
        "maplibre-gl.js",
        "loads MapLibre from a CDN",
        "raster map tiles from CARTO",
    )
    for token in required_html_tokens:
        if token not in html:
            errors.append(f"map proof HTML missing {token}")

    required_css_tokens = (
        ".map-container",
        ".map-marker",
        ".approximate-halo",
        ".privacy-badge",
        ".map-shell .detail-surface",
        "grid-column: auto",
        "isolation: isolate",
        "z-index: 0",
        "top: 50%",
        "left: 50%",
        "transform: translate(-50%, -50%)",
    )
    for token in required_css_tokens:
        if token not in css:
            errors.append(f"map proof CSS missing {token}")
    if "z-index: -1" in css:
        errors.append("map proof CSS must not hide the approximate halo behind the map")

    required_js_tokens = (
        "window.maplibregl",
        "MapLibre did not load from the CDN.",
        "SEED_MANIFEST_URL",
        "../mixed-node/seed-projects.json",
        "isMapRenderable",
        "project.location?.mode !== \"hidden\"",
        "approximate-halo",
        "privacy-badge",
        "createMapMarkerElement",
        "setExpandedMarkerButton",
        "aria-controls",
        "aria-expanded",
        "try {\n    const map = createMap();",
        "Number.isFinite(coordinates?.lat)",
        "Number.isFinite(coordinates?.lon)",
    )
    for token in required_js_tokens:
        if token not in js:
            errors.append(f"map proof JS missing {token}")
    if "maplibre-gl.esm.js" in js:
        errors.append("map proof JS must not import the missing MapLibre ESM bundle")

    errors.extend(validate_scope_text(readme, html, js))
    errors.extend(validate_map_projection(load_projects(root)))
    return errors


def main() -> int:
    errors = validate_map_proof(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld map proof validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
