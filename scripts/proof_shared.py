#!/usr/bin/env python3
"""Shared-module checks for the static commonworld proofs.

The mixed-node, map and aether proofs render aspect rings, percentages and
curation labels from ``proofs/shared/aspects.js``. These helpers validate that
single implementation and that each proof is actually wired to it, so the proof
validators can assert behaviour (composition, manifest guard, import wiring)
instead of restating a duplicated function body as a literal substring.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHARED_JS_REL = "proofs/shared/aspects.js"
SEED_MANIFEST_LITERAL = "../../examples/commonworld/seed-projects.json"

# Names the shared module must export, with the declaration kind expected.
SHARED_EXPORTS: dict[str, str] = {
    "SEED_MANIFEST_URL": "const",
    "ASPECT_COLORS": "const",
    "ICON_GLYPHS": "const",
    "aspectColor": "function",
    "iconFor": "function",
    "sortAspects": "function",
    "buildSegments": "function",
    "gradientFor": "function",
    "formatPercent": "function",
    "formatConfidence": "function",
    "curationStateLabel": "function",
    "curationBadgeLabel": "function",
    "loadJson": "function",
    "loadSeedProjects": "function",
}

ASPECT_COLOR_TOKENS = (
    "aspect.data",
    "aspect.community",
    "aspect.infrastructure",
    "aspect.repair",
    "aspect.education",
    "aspect.mutual-aid",
)

ICON_TOKENS = (
    "icon.map",
    "icon.people",
    "icon.layers",
    "icon.tool",
    "icon.book-open",
    "icon.hands",
)


def shared_js_path(root: Path = ROOT) -> Path:
    return root / SHARED_JS_REL


def read_shared_js(root: Path = ROOT) -> str:
    return shared_js_path(root).read_text(encoding="utf-8")


def extract_const_object_block(source: str, declaration: str) -> str:
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


def _extract_function_body(source: str, name: str) -> str:
    match = re.search(rf"export\s+(?:async\s+)?function\s+{re.escape(name)}\s*\(", source)
    if match is None:
        return ""
    brace_start = source.find("{", match.end())
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


def imported_shared_names(js: str) -> set[str]:
    """Return the identifiers a proof imports from the shared aspect module."""
    match = re.search(
        r"import\s*\{([^}]*)\}\s*from\s*[\"']\.\./shared/aspects\.js[\"']",
        js,
    )
    if match is None:
        return set()
    return {name.strip() for name in match.group(1).split(",") if name.strip()}


def assert_shared_imports(js: str, required: tuple[str, ...], label: str) -> list[str]:
    imported = imported_shared_names(js)
    errors: list[str] = []
    if not imported:
        errors.append(f"{label} must import shared aspect helpers from {SHARED_JS_REL}")
        return errors
    for name in required:
        if name not in imported:
            errors.append(f"{label} must import {name} from {SHARED_JS_REL}")
    for name in sorted(imported):
        if name not in SHARED_EXPORTS:
            errors.append(f"{label} imports {name}, which the shared aspect module does not export")
    return errors


def validate_shared_module(root: Path = ROOT) -> list[str]:
    path = shared_js_path(root)
    if not path.is_file():
        return [f"missing shared aspect module: {SHARED_JS_REL}"]

    js = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for name, kind in SHARED_EXPORTS.items():
        if kind == "const":
            present = re.search(rf"export\s+const\s+{re.escape(name)}\b", js) is not None
        else:
            present = re.search(rf"export\s+(?:async\s+)?function\s+{re.escape(name)}\b", js) is not None
        if not present:
            errors.append(f"shared aspect module must export {kind} {name}")

    color_block = extract_const_object_block(js, "export const ASPECT_COLORS")
    for token in ASPECT_COLOR_TOKENS:
        css_variable = f"--{token.replace('.', '-')}"
        if f'"{token}": "var({css_variable})"' not in color_block:
            errors.append(f"shared aspect module ASPECT_COLORS missing {token}")

    icon_block = extract_const_object_block(js, "export const ICON_GLYPHS")
    for token in ICON_TOKENS:
        if f'"{token}"' not in icon_block:
            errors.append(f"shared aspect module ICON_GLYPHS missing {token}")

    if SEED_MANIFEST_LITERAL not in js:
        errors.append("shared aspect module must resolve the shared seed manifest URL")
    if "Seed manifest must contain project_paths." not in js:
        errors.append("shared aspect module must guard the seed manifest project_paths list")

    # Behavioural expectations for the unified percentage/confidence output.
    format_percent = _extract_function_body(js, "formatPercent")
    for marker in ('"<1%"', ".toFixed(1)", "Math.round(percent)"):
        if marker not in format_percent:
            errors.append(f"shared formatPercent must keep the {marker} rendering branch")

    format_confidence = _extract_function_body(js, "formatConfidence")
    if "formatPercent(" not in format_confidence or "confidence" not in format_confidence:
        errors.append("shared formatConfidence must compose formatPercent so confidence output stays unified")

    curation_state = _extract_function_body(js, "curationStateLabel")
    if "Synthetic fixture" not in curation_state:
        errors.append("shared curationStateLabel must render the Synthetic fixture label")
    curation_badge = _extract_function_body(js, "curationBadgeLabel")
    if "Curation:" not in curation_badge:
        errors.append("shared curationBadgeLabel must render the Curation state badge")

    return errors
