#!/usr/bin/env python3
"""Deterministic offline smoke for the static map proof.

This is intentionally not a live MapLibre/tile-provider test. It models the
browser-visible marker contract from committed proof files and seed data while
stubbing all external map dependencies. The smoke is meant to satisfy the
COMMONWORLD-ATLAS-V1-T006 evidence gap without making CI depend on a CDN,
MapLibre runtime, or CARTO tile availability.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_map_proof import classify_project, load_projects, proof_dir, validate_map_proof
from scripts.validate_mixed_node_proof import load_json


@dataclass(frozen=True)
class SmokeMarker:
    project_id: str
    mode: str
    title: str
    lat: float
    lon: float
    has_approximate_halo: bool
    privacy_badge: str


@dataclass(frozen=True)
class OfflineSmokeReport:
    smoke_id: str
    network_mode: str
    external_dependencies_stubbed: tuple[str, ...]
    renderable_markers: tuple[SmokeMarker, ...]
    skipped_project_ids: tuple[str, ...]
    assertions: tuple[str, ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_contains(text: str, token: str, label: str, errors: list[str]) -> None:
    if token not in text:
        errors.append(f"{label} missing token: {token}")


def expected_markers(root: Path = ROOT) -> tuple[SmokeMarker, ...]:
    markers: list[SmokeMarker] = []
    for project in load_projects(root):
        projection = classify_project(project)
        if not projection.renderable:
            continue
        coordinates = project["location"]["coordinates"]
        markers.append(
            SmokeMarker(
                project_id=project["id"],
                mode=projection.mode,
                title=project["title"],
                lat=float(coordinates["lat"]),
                lon=float(coordinates["lon"]),
                has_approximate_halo=projection.requires_halo,
                privacy_badge="Exact" if projection.mode == "exact" else "Approximate",
            )
        )
    return tuple(sorted(markers, key=lambda item: item.project_id))


def skipped_project_ids(root: Path = ROOT) -> tuple[str, ...]:
    skipped: list[str] = []
    for project in load_projects(root):
        if not classify_project(project).renderable:
            skipped.append(project["id"])
    return tuple(sorted(skipped))


def smoke_report(root: Path = ROOT) -> OfflineSmokeReport:
    markers = expected_markers(root)
    skipped = skipped_project_ids(root)
    return OfflineSmokeReport(
        smoke_id="commonworld.map-proof.offline-browser-smoke.v1",
        network_mode="offline-stubbed",
        external_dependencies_stubbed=("maplibre-gl", "carto-raster-tiles"),
        renderable_markers=markers,
        skipped_project_ids=skipped,
        assertions=(
            "exact and approximate seed projects produce marker models",
            "approximate projects require an approximate halo",
            "exact projects do not require an approximate halo",
            "hidden projects produce no marker model",
            "MapLibre and tile-provider dependencies are not fetched by this smoke",
        ),
    )


def validate_offline_map_smoke(root: Path = ROOT) -> list[str]:
    errors = validate_map_proof(root)
    directory = proof_dir(root)
    html = _read(directory / "index.html")
    js = _read(directory / "map.js")
    css = _read(directory / "map.css")
    map_source: dict[str, Any] = load_json(directory / "map-source.json")

    for token in (
        "data-load-state",
        "id=\"map\"",
        "data-detail-surface",
        "data-detail-privacy",
        "data-detail-curation",
    ):
        _assert_contains(html, token, "map proof HTML", errors)

    for token in (
        "function createMapMarkerElement(project)",
        "new maplibre.Marker({ element: createMapMarkerElement(project) })",
        "setLngLat([lon, lat])",
        "project.location.mode === \"approximate\"",
        "project.location.mode === \"exact\" ? \"Exact\" : \"Approximate\"",
        "skippedProjects.length",
    ):
        _assert_contains(js, token, "map proof JS", errors)

    for token in (
        ".map-marker",
        ".approximate-halo",
        ".privacy-badge--exact",
        ".privacy-badge--approximate",
    ):
        _assert_contains(css, token, "map proof CSS", errors)

    source_library = map_source.get("library", {})
    basemap = map_source.get("basemap", {})
    if not str(source_library.get("script_url", "")).endswith("/dist/maplibre-gl.js"):
        errors.append("offline smoke requires explicit MapLibre script dependency to stub")
    if basemap.get("kind") != "raster-style":
        errors.append("offline smoke requires raster-style basemap dependency to stub")

    markers = expected_markers(root)
    marker_by_id = {marker.project_id: marker for marker in markers}
    exact = marker_by_id.get("solidarity-kitchen-fixture")
    approximate = marker_by_id.get("neighborhood-repair-circle-fixture")
    if exact is None:
        errors.append("offline smoke expected exact solidarity-kitchen fixture marker")
    elif exact.has_approximate_halo:
        errors.append("exact solidarity-kitchen fixture must not have approximate halo")
    if approximate is None:
        errors.append("offline smoke expected approximate neighborhood-repair-circle fixture marker")
    elif not approximate.has_approximate_halo:
        errors.append("approximate neighborhood-repair-circle fixture must have approximate halo")
    if "openstreetmap" not in skipped_project_ids(root):
        errors.append("hidden openstreetmap project must be skipped by offline smoke")
    if len(markers) < 2:
        errors.append("offline smoke expected at least exact and approximate renderable markers")
    return errors


def main() -> int:
    errors = validate_offline_map_smoke(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = smoke_report(ROOT)
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
