#!/usr/bin/env python3
"""Declarative, shared browser-smoke execution contract."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PUBLIC_SMOKE_RESULT_TOKEN = "{public_smoke_result}"


@dataclass(frozen=True)
class BrowserSmokeStep:
    identifier: str
    argv: tuple[str, ...]
    required_for_public_only: bool = False


CANONICAL_BROWSER_SMOKE_PLAN = (
    BrowserSmokeStep(
        "public-browser-smoke",
        ("node", "scripts/smoke_public_browser.mjs", "--result", PUBLIC_SMOKE_RESULT_TOKEN),
        True,
    ),
    BrowserSmokeStep(
        "catalog-delivery-evidence-validation",
        (
            "python3",
            "scripts/validate_catalog_delivery_budget.py",
            "--smoke-result",
            PUBLIC_SMOKE_RESULT_TOKEN,
        ),
        True,
    ),
    BrowserSmokeStep("proposal-browser-smoke", ("node", "scripts/smoke_proposal_browser.mjs")),
    BrowserSmokeStep("focus-overlay-browser-smoke", ("node", "scripts/smoke_focus_overlay_browser.mjs")),
    BrowserSmokeStep(
        "accessibility-modes-browser-smoke",
        ("node", "scripts/smoke_accessibility_modes_browser.mjs"),
    ),
)


def materialize_browser_smoke_plan(
    public_smoke_result: Path,
    *,
    public_only: bool = False,
) -> tuple[tuple[str, ...], ...]:
    """Replace the one fresh-result token and optionally select the public evidence path."""
    result = str(public_smoke_result)
    commands: list[tuple[str, ...]] = []
    for step in CANONICAL_BROWSER_SMOKE_PLAN:
        if public_only and not step.required_for_public_only:
            continue
        command = tuple(result if argument == PUBLIC_SMOKE_RESULT_TOKEN else argument for argument in step.argv)
        if PUBLIC_SMOKE_RESULT_TOKEN in command:
            raise ValueError(f"unresolved public smoke result token in step: {step.identifier}")
        commands.append(command)
    return tuple(commands)
