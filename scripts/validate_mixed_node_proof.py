#!/usr/bin/env python3
"""Validate the static commonworld mixed-node proof."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_contracts import iter_project_examples, validate_all
from scripts.validate_seed_manifest import expected_seed_paths, seed_manifest_path, validate_seed_manifest

WEIGHT_TOLERANCE = 0.001


@dataclass(frozen=True)
class Segment:
    aspect_id: str
    label: str
    icon_token: str
    color_token: str
    confidence: float
    evidence_count: int
    start: float
    end: float
    span: float


def proof_dir(root: Path = ROOT) -> Path:
    return root / "proofs" / "mixed-node"


def expected_proof_files(root: Path = ROOT) -> tuple[Path, ...]:
    directory = proof_dir(root)
    return (
        directory / "index.html",
        directory / "mixed-node.css",
        directory / "mixed-node.js",
        directory / "README.md",
    )


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_projects(root: Path = ROOT) -> list[dict[str, Any]]:
    return [load_json(path) for path in iter_project_examples(root)]


def ordered_aspects(project: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        project["aspects"],
        key=lambda aspect: (-float(aspect["weight"]), aspect["label"].casefold(), aspect["id"]),
    )


def build_segments(project: dict[str, Any]) -> list[Segment]:
    aspects = ordered_aspects(project)
    total = sum(float(aspect["weight"]) for aspect in aspects)
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise ValueError(f"{project['id']} aspect weights must sum to 1.0, got {total:.3f}")

    cursor = 0.0
    segments: list[Segment] = []
    for index, aspect in enumerate(aspects):
        start = cursor
        end = 1.0 if index == len(aspects) - 1 else cursor + float(aspect["weight"])
        span = end - start
        segments.append(
            Segment(
                aspect_id=aspect["id"],
                label=aspect["label"],
                icon_token=aspect["icon_token"],
                color_token=aspect["color_token"],
                confidence=float(aspect["confidence"]),
                evidence_count=len(aspect["evidence"]),
                start=round(start, 6),
                end=round(end, 6),
                span=round(span, 6),
            )
        )
        cursor = end
    return segments


def _contains_string_literal(source: str, value: str) -> bool:
    return f'"{value}"' in source or f"'{value}'" in source


def _contains_css_custom_property(css: str, variable: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(variable)}\s*:", css) is not None


def _extract_const_object_block(source: str, declaration: str) -> str:
    start = source.find(declaration)
    if start < 0:
        return ""
    brace_start = source.find("{", start)
    if brace_start < 0:
        return ""
    depth = 0
    for index, character in enumerate(source[brace_start:], start=brace_start):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : index + 1]
    return ""


def validate_token_coverage(projects: list[dict[str, Any]], css: str, js: str) -> list[str]:
    errors: list[str] = []
    color_mapping = _extract_const_object_block(js, "const ASPECT_COLORS")
    icon_mapping = _extract_const_object_block(js, "const ICON_GLYPHS")
    seen_color_tokens: set[str] = set()
    seen_icon_tokens: set[str] = set()

    for project in projects:
        for aspect in project["aspects"]:
            color_token = aspect["color_token"]
            icon_token = aspect["icon_token"]

            if color_token not in seen_color_tokens:
                seen_color_tokens.add(color_token)
                css_variable = f"--{color_token.replace('.', '-')}"
                if f'"{color_token}": "var({css_variable})"' not in color_mapping:
                    errors.append(f"proof JS color mapping missing {color_token}")
                if not _contains_css_custom_property(css, css_variable):
                    errors.append(f"proof CSS variable missing {css_variable}")

            if icon_token not in seen_icon_tokens:
                seen_icon_tokens.add(icon_token)
                if not _contains_string_literal(icon_mapping, icon_token):
                    errors.append(f"proof JS icon mapping missing {icon_token}")

    return errors


def validate_rendered_segments(project: dict[str, Any], segments: list[Segment]) -> list[str]:
    errors: list[str] = []
    if not segments:
        return [f"{project['id']} has no renderable segments"]

    if abs(segments[0].start - 0.0) > WEIGHT_TOLERANCE:
        errors.append(f"{project['id']} first segment must start at 0.0")
    if abs(segments[-1].end - 1.0) > WEIGHT_TOLERANCE:
        errors.append(f"{project['id']} last segment must end at 1.0")

    aspects_by_id = {aspect["id"]: aspect for aspect in project["aspects"]}
    previous_end = 0.0
    for segment in segments:
        expected_span = float(aspects_by_id[segment.aspect_id]["weight"])
        if segment.start < previous_end - WEIGHT_TOLERANCE:
            errors.append(f"{project['id']} segment {segment.aspect_id} overlaps previous segment")
        if abs(segment.start - previous_end) > WEIGHT_TOLERANCE:
            errors.append(f"{project['id']} segment {segment.aspect_id} does not continue previous segment")
        if abs(segment.span - expected_span) > WEIGHT_TOLERANCE:
            errors.append(f"{project['id']} segment {segment.aspect_id} span does not match aspect weight")
        if not segment.label:
            errors.append(f"{project['id']} segment {segment.aspect_id} has no label")
        if not segment.icon_token:
            errors.append(f"{project['id']} segment {segment.aspect_id} has no icon token")
        if segment.evidence_count < 1:
            errors.append(f"{project['id']} segment {segment.aspect_id} has no evidence")
        if not 0 <= segment.confidence <= 1:
            errors.append(f"{project['id']} segment {segment.aspect_id} confidence out of range")
        previous_end = segment.end

    return errors


def validate_proof(root: Path = ROOT) -> list[str]:
    errors = validate_all(root)

    missing_files: list[Path] = []
    for path in expected_proof_files(root):
        if not path.is_file():
            errors.append(f"missing proof file: {path.relative_to(root)}")
            missing_files.append(path)

    if missing_files:
        return errors

    errors.extend(validate_seed_manifest(root))

    directory = proof_dir(root)
    html = (directory / "index.html").read_text(encoding="utf-8")
    css = (directory / "mixed-node.css").read_text(encoding="utf-8")
    js = (directory / "mixed-node.js").read_text(encoding="utf-8")

    manifest_path = seed_manifest_path(root)
    manifest_text = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
    for seed_path in expected_seed_paths(root):
        if seed_path not in manifest_text:
            errors.append(f"shared seed manifest does not load seed example {seed_path}")

    if "prefers-reduced-motion" not in css:
        errors.append("proof CSS must include prefers-reduced-motion")

    required_js_names = (
        "SEED_MANIFEST_URL",
        "ASPECT_COLORS",
        "ICON_GLYPHS",
        "requiredElement",
        "sortAspects",
        "buildSegments",
        "renderEvidence",
        "formatPercent",
        "formatConfidence",
        "setExpandedButton",
        "closeDetail",
        "loadSeedProjects",
    )
    for required_js_name in required_js_names:
        if required_js_name not in js:
            errors.append(f"proof JS missing {required_js_name}")

    required_html_tokens = (
        'id="project-detail"',
        "data-detail-surface",
        'tabindex="-1"',
        'aria-live="polite"',
    )
    for required_html_token in required_html_tokens:
        if required_html_token not in html:
            errors.append(f"proof HTML missing {required_html_token}")

    required_js_a11y_tokens = (
        "aria-controls",
        "project-detail",
        "aria-expanded",
        "closeDetail",
        "Escape",
        "activeNodeButton.focus",
    )
    for token in required_js_a11y_tokens:
        if token not in js:
            errors.append(f"proof JS missing accessibility behavior token {token}")

    if errors:
        return errors

    projects = load_projects(root)
    curation_states = {project.get("curation", {}).get("state") for project in projects}
    if "fixture" in curation_states:
        if "Synthetic fixture" not in js:
            errors.append("fixture projects must render the Synthetic fixture label")
        if ".node-badge" not in css:
            errors.append("fixture label must have node-badge CSS")
    if any(state and state != "fixture" for state in curation_states):
        if "Curation:" not in js:
            errors.append("non-fixture projects must render a curation state badge")
        if "curationBadgeLabel" not in js:
            errors.append("mixed-node proof must use curationBadgeLabel")

    errors.extend(validate_token_coverage(projects, css, js))

    for project in projects:
        try:
            segments = build_segments(project)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{project.get('id', '<unknown project>')} cannot build rendered segments: {exc}")
            continue
        errors.extend(validate_rendered_segments(project, segments))

    return errors


def main() -> int:
    errors = validate_proof(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld mixed-node proof validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
