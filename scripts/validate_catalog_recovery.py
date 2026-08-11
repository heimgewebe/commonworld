#!/usr/bin/env python3
"""Validate bounded T028 catalogue recovery artifacts and scale evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.catalog_recovery import (
    GENERATED_MARKER,
    PAGE_SIZE,
    RECOVERY_LOCALES,
    index_relative_path,
    load_records,
    page_count,
    project_relative_path,
    project_url,
    render_index,
    render_project,
)
from scripts.commonworld_i18n import localize_records
from scripts.measure_catalog_recovery import build_result, canonical_json

CONTRACT_PATH = Path("contracts/commonworld/catalog-recovery.contract.json")
EVIDENCE_PATH = Path("docs/evidence/catalog-recovery-scale-v1.json")
CURRENT_STATE_PATH = Path("contracts/commonworld/current-state.contract.json")
SCALE_GATE_PATH = Path("contracts/commonworld/catalog-scale-gates.contract.json")
CARD_ID_RE = re.compile(r'<article class="catalog-card"[^>]*data-commonproject-id="([a-z][a-z0-9-]{2,95})"')


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def generated_paths(root: Path) -> set[Path]:
    paths = {Path("catalog/index.html")}
    if (root / "catalog/pages").is_dir():
        paths.update(path.relative_to(root) for path in (root / "catalog/pages").glob("*.html"))
    paths.update(path.relative_to(root) for path in (root / "catalog/projects").glob("*.html"))
    if (root / "catalog/de").is_dir():
        paths.update(path.relative_to(root) for path in (root / "catalog/de").rglob("*.html"))
    return {path for path in paths if (root / path).is_file()}


def validate_catalog_recovery(root: Path = ROOT, *, verify_measurements: bool = True) -> list[str]:
    errors: list[str] = []
    required = [CONTRACT_PATH, EVIDENCE_PATH, CURRENT_STATE_PATH, SCALE_GATE_PATH]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing catalogue recovery dependency: {relative}")
    if errors:
        return errors
    try:
        contract = load_json(root / CONTRACT_PATH)
        evidence = load_json(root / EVIDENCE_PATH)
        current_state = load_json(root / CURRENT_STATE_PATH)
        scale_gate = load_json(root / SCALE_GATE_PATH)
        records = load_records(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"invalid catalogue recovery dependency: {error}"]

    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_catalog_recovery_contract":
        errors.append("catalogue recovery contract schema or kind mismatch")
    if contract.get("task_id") != "COMMONWORLD-PUBLIC-GLOBE-V1-T028":
        errors.append("catalogue recovery contract must remain bound to T028")
    if contract.get("status") != "de_en_bounded_recovery_proven":
        errors.append("catalogue recovery status mismatch")
    if contract.get("locales") != list(RECOVERY_LOCALES) or contract.get("scale_tiers") != [1000, 10000]:
        errors.append("catalogue recovery locale or scale-tier inventory mismatch")
    routing = contract.get("routing", {})
    if routing.get("page_size") != PAGE_SIZE or routing.get("ordering") != "CommonProject.id ascending":
        errors.append("catalogue recovery routing is not deterministically bounded")
    budgets = contract.get("budgets", {})
    if budgets.get("index_page_max_entries") != PAGE_SIZE or budgets.get("landing_recovery_max_entries") != PAGE_SIZE:
        errors.append("catalogue recovery entry budgets diverge from the generator")
    for key in (
        "index_page_max_raw_bytes",
        "index_page_max_gzip_bytes",
        "index_page_max_start_tags",
        "project_page_max_raw_bytes",
        "project_page_max_gzip_bytes",
        "project_page_max_start_tags",
    ):
        if not isinstance(budgets.get(key), int) or budgets[key] <= 0:
            errors.append(f"catalogue recovery budget must be a positive integer: {key}")
    invariants = contract.get("invariants", {})
    expected_invariants = {
        "javascript_required": False,
        "runtime_write_path": False,
        "account_required": False,
        "telemetry_added": False,
        "hidden_location_geometry_rendered": False,
        "generated_fixture_is_public_catalog": False,
        "every_catalog_identity_has_project_page": True,
        "every_index_identity_appears_once_per_locale": True,
    }
    if invariants != expected_invariants:
        errors.append("catalogue recovery safety or editorial invariants mismatch")

    authorization = contract.get("authorization", {})
    if authorization.get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("catalogue recovery must not authorize runtime cutover")
    if current_state.get("catalog_delivery", {}).get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("current state unexpectedly authorizes runtime cutover")
    if scale_gate.get("current_authorization", {}).get("cutover_authorized") is not False:
        errors.append("catalogue scale gate unexpectedly authorizes runtime cutover")

    identifiers = [record["id"] for record in records]
    expected_paths = {
        index_relative_path(locale, number)
        for locale in RECOVERY_LOCALES
        for number in range(1, page_count(len(records)) + 1)
    } | {
        project_relative_path(locale, identifier)
        for locale in RECOVERY_LOCALES
        for identifier in identifiers
    }
    actual_paths = generated_paths(root)
    if actual_paths != expected_paths:
        missing = sorted(path.as_posix() for path in expected_paths - actual_paths)
        extra = sorted(path.as_posix() for path in actual_paths - expected_paths)
        errors.append(f"catalogue recovery artifact inventory mismatch: missing={missing[:3]} extra={extra[:3]}")

    for locale in RECOVERY_LOCALES:
        localized = sorted(localize_records(records, locale, root), key=lambda record: record["id"])
        localized_by_id = {record["id"]: record for record in localized}
        seen: list[str] = []
        for number in range(1, page_count(len(records)) + 1):
            relative = index_relative_path(locale, number)
            path = root / relative
            if not path.is_file():
                continue
            markup = path.read_text(encoding="utf-8")
            if markup != render_index(localized, locale, number, root):
                errors.append(f"catalogue recovery page is not the deterministic canonical projection: {relative}")
            page_ids = CARD_ID_RE.findall(markup)
            seen.extend(page_ids)
            if len(page_ids) > PAGE_SIZE:
                errors.append(f"catalogue recovery page exceeds entry bound: {relative}")
            if f'data-recovery-page="{number}" data-recovery-page-size="{PAGE_SIZE}"' not in markup:
                errors.append(f"catalogue recovery page metadata mismatch: {relative}")
            if GENERATED_MARKER not in markup or "<script" in markup.casefold() or "<form" in markup.casefold():
                errors.append(f"catalogue recovery page is not a static read-only surface: {relative}")
        if seen != identifiers:
            errors.append(f"catalogue recovery {locale} index identity order or completeness mismatch")
        for identifier in identifiers:
            relative = project_relative_path(locale, identifier)
            path = root / relative
            if not path.is_file():
                continue
            markup = path.read_text(encoding="utf-8")
            if markup != render_project(localized_by_id[identifier], locale, root):
                errors.append(f"catalogue recovery project is not the deterministic canonical projection: {relative}")
            if GENERATED_MARKER not in markup or f"<code>{identifier}</code>" not in markup:
                errors.append(f"catalogue recovery project identity mismatch: {relative}")
            if f'/catalog/projects/{identifier}.json' not in markup:
                errors.append(f"catalogue recovery project lacks canonical JSON link: {relative}")
            alternate_locale = "de" if locale == "en" else "en"
            if f'<link rel="canonical" href="{project_url(locale, identifier)}" />' not in markup:
                errors.append(f"catalogue recovery project canonical locale mismatch: {relative}")
            if f'<link rel="alternate" hreflang="{alternate_locale}" href="{project_url(alternate_locale, identifier)}" />' not in markup:
                errors.append(f"catalogue recovery project alternate locale mismatch: {relative}")
            if '"coordinates"' in markup or "<script" in markup.casefold() or "<form" in markup.casefold():
                errors.append(f"catalogue recovery project violates static privacy boundary: {relative}")

    for page_name, locale in (("index.html", "en"), ("de.html", "de")):
        path = root / page_name
        if not path.is_file():
            errors.append(f"missing bounded recovery landing page: {page_name}")
            continue
        markup = path.read_text(encoding="utf-8")
        fallback = markup.split('id="static-catalog-fallback"', 1)[-1]
        if len(CARD_ID_RE.findall(fallback)) != min(PAGE_SIZE, len(records)):
            errors.append(f"bounded landing recovery count mismatch: {page_name}")
        expected_link = 'href="catalog/"' if locale == "en" else 'href="catalog/de/"'
        if expected_link not in fallback:
            errors.append(f"bounded landing recovery index link missing: {page_name}")

    if evidence.get("kind") != "commonworld.catalog_recovery_scale_evidence" or evidence.get("version") != "1.0":
        errors.append("catalogue recovery evidence schema or version mismatch")
    if evidence.get("task_id") != contract.get("task_id") or evidence.get("scale_tiers") != contract.get("scale_tiers"):
        errors.append("catalogue recovery evidence task or scale-tier binding mismatch")
    if evidence.get("page_size") != PAGE_SIZE or evidence.get("locales") != list(RECOVERY_LOCALES):
        errors.append("catalogue recovery evidence page-size or locale binding mismatch")
    source_catalog = root / "catalog/catalog.json"
    source_overlay = root / "catalog/locales/en.json"
    if evidence.get("source_catalog_sha256") != hashlib.sha256(source_catalog.read_bytes()).hexdigest():
        errors.append("catalogue recovery source catalog digest drift")
    if evidence.get("source_english_overlay_sha256") != hashlib.sha256(source_overlay.read_bytes()).hexdigest():
        errors.append("catalogue recovery English overlay digest drift")
    measurements = [evidence.get("current_catalog"), *evidence.get("measurements", [])]
    for measurement in measurements:
        if not isinstance(measurement, dict):
            errors.append("catalogue recovery evidence contains an invalid measurement")
            continue
        if measurement.get("page_size") != PAGE_SIZE:
            errors.append("catalogue recovery measurement page size mismatch")
        count = measurement.get("entry_count")
        for locale in RECOVERY_LOCALES:
            locale_metrics = measurement.get("locales", {}).get(locale, {})
            index_max = locale_metrics.get("index_page_max", {})
            project_max = locale_metrics.get("project_page_sample_max", {})
            landing = locale_metrics.get("landing_page", {})
            checks = (
                (index_max.get("catalog_cards"), budgets.get("index_page_max_entries"), "index entries"),
                (index_max.get("raw_bytes"), budgets.get("index_page_max_raw_bytes"), "index raw bytes"),
                (index_max.get("gzip_bytes"), budgets.get("index_page_max_gzip_bytes"), "index gzip bytes"),
                (index_max.get("start_tags"), budgets.get("index_page_max_start_tags"), "index start tags"),
                (project_max.get("raw_bytes"), budgets.get("project_page_max_raw_bytes"), "project raw bytes"),
                (project_max.get("gzip_bytes"), budgets.get("project_page_max_gzip_bytes"), "project gzip bytes"),
                (project_max.get("start_tags"), budgets.get("project_page_max_start_tags"), "project start tags"),
                (landing.get("catalog_cards"), budgets.get("landing_recovery_max_entries"), "landing entries"),
            )
            for actual, maximum, label in checks:
                if not isinstance(actual, int) or not isinstance(maximum, int) or actual > maximum:
                    errors.append(f"{count} {locale} catalogue recovery {label} exceeds or lacks budget: {actual} > {maximum}")
            expected_pages = page_count(count) if isinstance(count, int) and count > 0 else None
            if locale_metrics.get("index_page_count") != expected_pages or locale_metrics.get("project_page_count") != count:
                errors.append(f"{count} {locale} catalogue recovery artifact count mismatch")
    decision = evidence.get("decision", {})
    if decision.get("bounded_recovery_surface") != "pass_de_en" or decision.get("landing_embeds_complete_catalog") is not False:
        errors.append("catalogue recovery evidence decision mismatch")
    if decision.get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("catalogue recovery evidence unexpectedly authorizes cutover")

    if verify_measurements:
        try:
            recomputed = build_result(root)
        except Exception as error:  # noqa: BLE001 - evidence failures must be reported, not hidden.
            errors.append(f"catalogue recovery evidence could not be recomputed: {error}")
        else:
            if canonical_json(evidence) != canonical_json(recomputed):
                errors.append("catalogue recovery deterministic measurement drift")
    return errors


def main() -> int:
    errors = validate_catalog_recovery(ROOT)
    if errors:
        print("Catalogue recovery validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Catalogue recovery validation passed: DE/EN landing recovery is bounded to 24 entries with complete paginated indexes and canonical project pages at 1k/10k; runtime cutover remains unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
