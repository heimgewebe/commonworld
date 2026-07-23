"""Shared public-geography validation helpers for Commonworld build tooling."""
from __future__ import annotations


def valid_position(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def valid_ring(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 4
        and all(valid_position(position) for position in value)
        and value[0] == value[-1]
    )


def public_location(location: object) -> bool:
    if not isinstance(location, dict) or location.get("mode") == "hidden":
        return False
    geometry = location.get("geometry")
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    valid_geometry = (
        (geometry_type == "Point" and valid_position(coordinates))
        or (geometry_type == "Polygon" and isinstance(coordinates, list) and bool(coordinates) and all(valid_ring(ring) for ring in coordinates))
        or (
            geometry_type == "MultiPolygon"
            and isinstance(coordinates, list)
            and bool(coordinates)
            and all(isinstance(polygon, list) and bool(polygon) and all(valid_ring(ring) for ring in polygon) for polygon in coordinates)
        )
    )
    if not valid_geometry:
        return False
    mode = location.get("mode")
    if mode == "approximate":
        uncertainty = location.get("uncertainty_meters_min")
        return (
            geometry_type == "Point"
            and isinstance(uncertainty, (int, float))
            and not isinstance(uncertainty, bool)
            and uncertainty > 0
        )
    return mode == "exact"


def public_locations(record: dict) -> list[dict]:
    presence = record.get("presence", {}) if isinstance(record.get("presence"), dict) else {}
    locations = presence.get("geographic", [])
    if not isinstance(locations, list):
        return []
    return [location for location in locations if public_location(location)]


def publicly_mappable(record: dict) -> bool:
    return bool(public_locations(record))
