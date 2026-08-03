#!/usr/bin/env python3
"""Validate Commonworld catalogue scale evidence and pre-cutover authority."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "commonworld" / "catalog-scale-gates.contract.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "catalog-platform-scaling-v1.json"
CURRENT_STATE_PATH = ROOT / "contracts" / "commonworld" / "current-state.contract.json"
MEASUREMENT_GENERATOR_PATH = ROOT / "scripts" / "measure_catalog_platform_scaling.py"
FIXTURE_GENERATOR_PATH = ROOT / "scripts" / "catalog_scale_fixtures.py"
CATALOG_PATH = ROOT / "catalog" / "catalog.json"
ENGLISH_OVERLAY_PATH = ROOT / "catalog" / "locales" / "en.json"
PROJECT_SCHEMA_PATH = ROOT / "contracts" / "commonworld" / "project.schema.json"
VALIDATE_CONTRACTS_PATH = ROOT / "scripts" / "validate_contracts.py"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

REQUIRED_GATES = [
    "realistic-scale-fixtures",
    "measured-demand-loaded-runtime",
    "bounded-recovery-surface",
    "search-and-map-scale-budgets",
    "shard-growth-policy",
    "failure-and-device-parity",
    "cutover-authority",
    "editorial-boundary-preserved",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_project_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ValueError("source project path must be a string")
    path = Path(relative)
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "projects" or path.suffix != ".json":
        raise ValueError(f"source project path must be a direct catalog/projects JSON file: {relative}")
    project_root = (root / "catalog" / "projects").resolve()
    candidate = (root / "catalog" / path).resolve()
    if candidate.parent != project_root:
        raise ValueError(f"source project path escapes catalog/projects: {relative}")
    return candidate


def expected_shard_state(size: int, warn: int, maximum: int) -> str:
    if size >= maximum:
        return "fail"
    if size >= warn:
        return "warning"
    return "pass"


def deterministic_projection(value: object) -> object:
    if isinstance(value, list):
        return [deterministic_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    projected = {}
    for key, item in value.items():
        if key.endswith("_ms_median") or key == "parse_sample_count":
            continue
        projected[key] = deterministic_projection(item)
    return projected


def recompute_deterministic_evidence(root: Path) -> dict:
    generator_path = root / MEASUREMENT_GENERATOR_PATH.relative_to(ROOT)
    fixture_path = root / FIXTURE_GENERATOR_PATH.relative_to(ROOT)
    previous_path = list(sys.path)
    module_names = ["scripts", "scripts.catalog_scale_fixtures", "scripts.validate_contracts"]
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    for name in module_names:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(root))
    try:
        fixture_spec = importlib.util.spec_from_file_location("scripts.catalog_scale_fixtures", fixture_path)
        if fixture_spec is None or fixture_spec.loader is None:
            raise RuntimeError("unable to load catalogue scale fixture generator")
        fixture_module = importlib.util.module_from_spec(fixture_spec)
        sys.modules["scripts.catalog_scale_fixtures"] = fixture_module
        fixture_spec.loader.exec_module(fixture_module)

        spec = importlib.util.spec_from_file_location("commonworld_catalog_scale_measurement", generator_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load catalogue scale measurement generator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        build_result = getattr(module, "build_result", None)
        if not callable(build_result):
            raise RuntimeError("catalogue scale measurement generator has no build_result")
        return build_result(include_parse_timing=False)
    finally:
        sys.path[:] = previous_path
        for name in module_names:
            sys.modules.pop(name, None)
            previous = previous_modules[name]
            if previous is not None:
                sys.modules[name] = previous


def _positive_payload_metrics(value: object, label: str, errors: list[str], *, require_parse: bool) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label}: payload metrics must be an object")
        return
    for field in ("raw_bytes", "gzip_bytes"):
        if not isinstance(value.get(field), int) or value[field] <= 0:
            errors.append(f"{label}: invalid {field}")
    if require_parse:
        parse_ms = value.get("parse_ms_median")
        if not isinstance(parse_ms, (int, float)) or parse_ms < 0:
            errors.append(f"{label}: invalid parse timing")


def _validate_collection_metrics(value: object, label: str, errors: list[str], *, require_parse: bool) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label}: collection metrics must be an object")
        return
    for field in ("count", "raw_total_bytes", "raw_max_bytes", "gzip_total_bytes", "gzip_max_bytes", "max_entries"):
        if not isinstance(value.get(field), int) or value[field] <= 0:
            errors.append(f"{label}: invalid {field}")
    median = value.get("gzip_median_bytes")
    if not isinstance(median, (int, float)) or median <= 0:
        errors.append(f"{label}: invalid gzip_median_bytes")
    if require_parse:
        parse_ms = value.get("parse_ms_median")
        if not isinstance(parse_ms, (int, float)) or parse_ms < 0:
            errors.append(f"{label}: invalid parse timing")


def validate_catalog_scale_gates(root: Path = ROOT, *, verify_measurements: bool = True) -> list[str]:
    errors: list[str] = []
    paths = [
        root / CONTRACT_PATH.relative_to(ROOT),
        root / EVIDENCE_PATH.relative_to(ROOT),
        root / CURRENT_STATE_PATH.relative_to(ROOT),
        root / MEASUREMENT_GENERATOR_PATH.relative_to(ROOT),
        root / FIXTURE_GENERATOR_PATH.relative_to(ROOT),
        root / CATALOG_PATH.relative_to(ROOT),
        root / ENGLISH_OVERLAY_PATH.relative_to(ROOT),
        root / PROJECT_SCHEMA_PATH.relative_to(ROOT),
        root / VALIDATE_CONTRACTS_PATH.relative_to(ROOT),
    ]
    for path in paths:
        if not path.is_file():
            errors.append(f"missing catalogue scale dependency: {path.relative_to(root)}")
    project_directory = root / "catalog" / "projects"
    if not project_directory.is_dir() or not any(project_directory.glob("*.json")):
        errors.append("missing catalogue scale seed projects")
    if errors:
        return errors

    try:
        contract = load_json(paths[0])
        evidence = load_json(paths[1])
        current_state = load_json(paths[2])
        catalog = load_json(paths[5])
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid catalogue scale dependency: {error}"]

    if contract.get("schema_version") != 1 or contract.get("kind") != "commonworld_catalog_scale_gate_contract":
        errors.append("catalogue scale contract schema or kind mismatch")
    if contract.get("task_id") != "COMMONWORLD-PUBLIC-GLOBE-V1-T028":
        errors.append("catalogue scale contract must remain bound to T028")
    if contract.get("status") != "pre_cutover_gate_active":
        errors.append("catalogue scale contract status must remain pre-cutover")
    if contract.get("required_gates") != REQUIRED_GATES:
        errors.append("catalogue scale required gate inventory mismatch")

    measurement_contract = contract.get("measurement", {})
    scale_tiers = measurement_contract.get("scale_tiers")
    stress_tier = measurement_contract.get("stress_tier")
    if scale_tiers != [1_000, 10_000] or stress_tier != 100_000:
        errors.append("catalogue scale tiers must remain 1k, 10k and 100k stress")
    if measurement_contract.get("representative_fixture_only") is not True:
        errors.append("catalogue scale contract must disclose representative-fixture-only evidence")
    if "synthetic_only" in measurement_contract:
        errors.append("catalogue scale contract must not retain the obsolete synthetic-only model")
    if measurement_contract.get("fixture_kind") != "schema-realistic-derived-fixtures":
        errors.append("catalogue scale contract fixture kind mismatch")
    if measurement_contract.get("source_catalog") != "catalog/catalog.json":
        errors.append("catalogue scale contract source catalogue mismatch")
    if measurement_contract.get("released_locale_overlays") != ["de", "en"]:
        errors.append("catalogue scale contract released locale inventory mismatch")
    if measurement_contract.get("generator") != "scripts/measure_catalog_platform_scaling.py":
        errors.append("catalogue scale contract generator path mismatch")
    if measurement_contract.get("fixture_generator") != "scripts/catalog_scale_fixtures.py":
        errors.append("catalogue scale contract fixture generator path mismatch")

    budgets = contract.get("budgets", {})
    expected_budget_keys = {
        "initial_world_index_max_gzip_bytes",
        "shard_warn_gzip_bytes",
        "shard_max_gzip_bytes",
        "world_index_initial_delivery",
        "shard_prefix_migration",
    }
    if set(budgets) != expected_budget_keys:
        errors.append("catalogue scale budget field inventory mismatch")
    initial_max = budgets.get("initial_world_index_max_gzip_bytes")
    shard_warn = budgets.get("shard_warn_gzip_bytes")
    shard_max = budgets.get("shard_max_gzip_bytes")
    if not all(isinstance(value, int) and value > 0 for value in (initial_max, shard_warn, shard_max)):
        errors.append("catalogue scale byte budgets must be positive integers")
    elif not shard_warn < shard_max:
        errors.append("catalogue shard warning budget must be below maximum")
    if budgets.get("world_index_initial_delivery") != "forbidden_when_over_budget":
        errors.append("full world index must fail closed when over the initial budget")
    if budgets.get("shard_prefix_migration") != "required_before_generated_shard_reaches_maximum":
        errors.append("catalogue scale contract must require prefix migration before shard overflow")

    if evidence.get("kind") != "commonworld.catalog_platform_scaling_evidence" or evidence.get("version") != "2.0":
        errors.append("catalogue scaling evidence schema or version mismatch")
    if evidence.get("representative_fixture_only") is not True:
        errors.append("catalogue scaling evidence must remain explicitly representative-fixture-only")
    if "synthetic_only" in evidence:
        errors.append("catalogue scaling evidence must not retain the obsolete synthetic-only marker")
    if evidence.get("scale_tiers") != scale_tiers or evidence.get("stress_tier") != stress_tier:
        errors.append("catalogue scaling evidence tiers diverge from contract")
    if evidence.get("budgets") != {
        "initial_world_index_max_gzip_bytes": initial_max,
        "shard_warn_gzip_bytes": shard_warn,
        "shard_max_gzip_bytes": shard_max,
    }:
        errors.append("catalogue scaling evidence budgets diverge from contract")
    if evidence.get("shard_strategy") != {"algorithm": "sha256-prefix", "prefix_length": 2}:
        errors.append("catalogue scaling evidence shard strategy mismatch")

    fixture_model = evidence.get("fixture_model", {})
    expected_catalog_sha = hashlib.sha256((root / CATALOG_PATH.relative_to(ROOT)).read_bytes()).hexdigest()
    expected_english_overlay_sha = hashlib.sha256(
        (root / ENGLISH_OVERLAY_PATH.relative_to(ROOT)).read_bytes()
    ).hexdigest()
    project_files = catalog.get("project_files")
    expected_project_set_sha: str | None = None
    if not isinstance(project_files, list):
        errors.append("catalogue scaling source project inventory must be a list")
    else:
        try:
            source_projects = [load_json(source_project_path(root, relative)) for relative in project_files]
            if any(not isinstance(record, dict) or not isinstance(record.get("id"), str) for record in source_projects):
                raise ValueError("source project lacks a string identity")
            expected_project_set_sha = hashlib.sha256(
                (
                    json.dumps(
                        sorted(source_projects, key=lambda record: record["id"]),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
            ).hexdigest()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            errors.append(f"catalogue scaling source project set is invalid: {error}")
    if fixture_model.get("kind") != measurement_contract.get("fixture_kind"):
        errors.append("catalogue scaling fixture model diverges from contract")
    if fixture_model.get("source_catalog") != measurement_contract.get("source_catalog"):
        errors.append("catalogue scaling fixture source diverges from contract")
    if fixture_model.get("source_catalog_sha256") != expected_catalog_sha:
        errors.append("catalogue scaling fixture source digest drift")
    if expected_project_set_sha is not None and fixture_model.get("source_project_set_sha256") != expected_project_set_sha:
        errors.append("catalogue scaling fixture project-set digest drift")
    if fixture_model.get("source_english_overlay_sha256") != expected_english_overlay_sha:
        errors.append("catalogue scaling fixture English overlay digest drift")
    if isinstance(project_files, list) and fixture_model.get("source_entry_count") != len(project_files):
        errors.append("catalogue scaling fixture seed count mismatch")
    if fixture_model.get("project_schema_version") != 4:
        errors.append("catalogue scaling fixture project schema mismatch")
    if fixture_model.get("released_locale_overlays") != ["de", "en"]:
        errors.append("catalogue scaling fixture locale inventory mismatch")
    if fixture_model.get("full_schema_tiers") != scale_tiers or fixture_model.get("compact_only_stress_tier") != stress_tier:
        errors.append("catalogue scaling fixture scope inventory mismatch")

    measurements = evidence.get("measurements")
    if not isinstance(measurements, list):
        errors.append("catalogue scaling evidence measurements must be a list")
        measurements = []
    expected_counts = [*scale_tiers, stress_tier] if isinstance(scale_tiers, list) and isinstance(stress_tier, int) else []
    actual_counts = [item.get("entry_count") for item in measurements if isinstance(item, dict)]
    if actual_counts != expected_counts:
        errors.append("catalogue scaling evidence measurement order or inventory mismatch")

    for item in measurements:
        if not isinstance(item, dict):
            errors.append("catalogue scaling evidence contains a non-object measurement")
            continue
        count = item.get("entry_count")
        expected_scope = "compact-shard-stress" if count == stress_tier else "full-schema-realistic"
        if item.get("fixture_scope") != expected_scope:
            errors.append(f"{count}: fixture scope mismatch")
        if not isinstance(item.get("fixture_sha256"), str) or SHA256_RE.fullmatch(item["fixture_sha256"]) is None:
            errors.append(f"{count}: invalid fixture digest")
        coverage = item.get("coverage", {})
        if not isinstance(coverage, dict):
            errors.append(f"{count}: fixture coverage must be an object")
        else:
            if coverage.get("location_modes") != ["approximate", "exact", "hidden"]:
                errors.append(f"{count}: fixture location-mode coverage mismatch")
            presence_classes = coverage.get("presence_classes", {})
            for name in ("digital_only", "geographic_only", "hybrid", "contains_hidden_location"):
                if not isinstance(presence_classes.get(name), int) or presence_classes[name] <= 0:
                    errors.append(f"{count}: fixture lacks {name} presence coverage")
            if coverage.get("released_locale_overlays") != ["de", "en"]:
                errors.append(f"{count}: fixture locale coverage mismatch")
            if not isinstance(coverage.get("relation_count"), int) or coverage["relation_count"] <= 0:
                errors.append(f"{count}: fixture relation coverage missing")
            if count in scale_tiers and (
                not isinstance(coverage.get("provenance_source_count"), int)
                or coverage["provenance_source_count"] < count
            ):
                errors.append(f"{count}: fixture provenance coverage incomplete")
            if count in scale_tiers and coverage.get("english_overlay_project_count") != count:
                errors.append(f"{count}: fixture English overlay coverage incomplete")
            if count == stress_tier:
                stress_projection = coverage.get("stress_projection")
                if not isinstance(stress_projection, dict):
                    errors.append(f"{count}: stress projection metadata must be an object")
                else:
                    if stress_projection.get("details_materialized") is not False:
                        errors.append(f"{count}: stress projection must disclose unmaterialized details")
                    if stress_projection.get("locale_overlays_materialized") is not False:
                        errors.append(f"{count}: stress projection must disclose unmaterialized locale overlays")
                if coverage.get("english_overlay_project_count") != 0:
                    errors.append(f"{count}: compact stress projection must not claim generated English overlays")
                stress_provenance = coverage.get("provenance_source_count")
                if not isinstance(stress_provenance, int) or stress_provenance < count:
                    errors.append(f"{count}: compact stress provenance projection is incomplete")

        for payload_name in ("manifest", "aggregate", "world_index"):
            _positive_payload_metrics(item.get(payload_name), f"{count}: {payload_name}", errors, require_parse=True)
        _validate_collection_metrics(item.get("shards"), f"{count}: shards", errors, require_parse=True)
        details = item.get("details", {})
        if count in scale_tiers:
            if not isinstance(details, dict) or details.get("count") != count or details.get("materialized") is False:
                errors.append(f"{count}: full-schema fixture details must be materialized")
            else:
                for field in ("raw_total_bytes", "raw_max_bytes", "gzip_total_bytes", "gzip_max_bytes"):
                    if not isinstance(details.get(field), int) or details[field] <= 0:
                        errors.append(f"{count}: invalid detail metric {field}")
                if not isinstance(details.get("parse_ms_median"), (int, float)) or details["parse_ms_median"] < 0:
                    errors.append(f"{count}: invalid detail parse timing")
            locale_payloads = item.get("locale_payloads", {})
            if set(locale_payloads) != {"de", "en"}:
                errors.append(f"{count}: released locale payload metrics missing")
            else:
                for locale in ("de", "en"):
                    _positive_payload_metrics(locale_payloads[locale], f"{count}: locale {locale}", errors, require_parse=True)
        elif not isinstance(details, dict) or details.get("count") != count or details.get("materialized") is not False:
            errors.append(f"{count}: stress detail scope mismatch")

        world = item.get("world_index", {})
        shards = item.get("shards", {})
        gates = item.get("gate_evaluation", {})
        world_gzip = world.get("gzip_bytes") if isinstance(world, dict) else None
        shard_gzip = shards.get("gzip_max_bytes") if isinstance(shards, dict) else None
        if isinstance(world_gzip, int) and isinstance(initial_max, int):
            expected_world_gate = "rejected" if world_gzip > initial_max else "within_budget"
            if gates.get("world_index_initial_delivery") != expected_world_gate:
                errors.append(f"{count}: world-index gate does not match measured size")
            if count in expected_counts and expected_world_gate != "rejected":
                errors.append(f"{count}: measured full index unexpectedly fits initial delivery budget")
        if isinstance(shard_gzip, int) and isinstance(shard_warn, int) and isinstance(shard_max, int):
            state = expected_shard_state(shard_gzip, shard_warn, shard_max)
            if gates.get("shard_gzip") != state:
                errors.append(f"{count}: shard gate does not match measured size")
            if count in scale_tiers and shard_gzip >= shard_max:
                errors.append(f"{count}: cutover scale tier reaches or exceeds hard shard budget")
            if count in scale_tiers and gates.get("shard_gzip") != "pass":
                errors.append(f"{count}: cutover scale tier must remain below shard warning budget")
            if count == stress_tier and gates.get("shard_gzip") != "fail":
                errors.append(f"{count}: fixed two-hex stress tier must preserve the measured hard-budget failure")

        if count == stress_tier:
            migration = item.get("prefix_migration_candidate", {})
            if migration.get("algorithm") != "sha256-prefix" or migration.get("prefix_length") != 3:
                errors.append(f"{count}: prefix migration candidate mismatch")
            if migration.get("runtime_compatible_with_current_manifest") is not False:
                errors.append(f"{count}: prefix migration candidate must disclose current manifest incompatibility")
            if not isinstance(migration.get("required_follow_up"), str) or not migration["required_follow_up"].strip():
                errors.append(f"{count}: prefix migration candidate follow-up missing")
            _positive_payload_metrics(migration.get("manifest"), f"{count}: migration manifest", errors, require_parse=True)
            _positive_payload_metrics(migration.get("aggregate"), f"{count}: migration aggregate", errors, require_parse=True)
            _validate_collection_metrics(migration.get("shards"), f"{count}: migration shards", errors, require_parse=True)
            migration_shards = migration.get("shards", {})
            migration_gzip = migration_shards.get("gzip_max_bytes") if isinstance(migration_shards, dict) else None
            migration_gate = migration.get("gate_evaluation", {}).get("shard_gzip")
            if isinstance(migration_gzip, int) and isinstance(shard_warn, int) and isinstance(shard_max, int):
                if migration_gate != expected_shard_state(migration_gzip, shard_warn, shard_max):
                    errors.append(f"{count}: prefix migration shard gate does not match measured size")
                if migration_gate != "pass":
                    errors.append(f"{count}: three-hex prefix migration candidate must restore shard headroom")

    decision = evidence.get("decision", {})
    if decision.get("full_world_index_initial_delivery") != "rejected_for_all_measured_tiers":
        errors.append("catalogue scaling decision must reject every measured full start index")
    if decision.get("runtime_path") != "small aggregate manifest plus demand-loaded shards and details":
        errors.append("catalogue scaling decision runtime path mismatch")
    if decision.get("scale_cutover_task") != contract.get("task_id"):
        errors.append("catalogue scaling decision task binding mismatch")
    if decision.get("fixture_milestone") != "schema-realistic-scale-fixtures-v1":
        errors.append("catalogue scaling decision fixture milestone mismatch")
    if "fixture_task" in decision:
        errors.append("catalogue scaling evidence must not assert an unpublished fixture task")
    if decision.get("fixed_prefix_stress_state") != "fail":
        errors.append("catalogue scaling decision must expose fixed-prefix stress failure")
    if decision.get("prefix_migration_candidate_state") != "pass":
        errors.append("catalogue scaling decision must expose passing prefix migration candidate")
    if decision.get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("catalogue scaling evidence must keep runtime cutover unauthorized")

    if verify_measurements:
        try:
            recomputed = recompute_deterministic_evidence(root)
        except Exception as error:  # noqa: BLE001 - validation must report generator failures as evidence failures.
            errors.append(f"catalogue scaling evidence could not be recomputed: {error}")
        else:
            if deterministic_projection(evidence) != recomputed:
                errors.append("catalogue scaling evidence deterministic measurement drift")

    authorization = contract.get("current_authorization", {})
    delivery = current_state.get("catalog_delivery", {})
    if authorization.get("cutover_authorized") is not False:
        errors.append("catalogue scale contract must not authorize cutover")
    if delivery.get("runtime_catalogue_cutover_authorized") is not False:
        errors.append("current state must not authorize catalogue cutover")
    if delivery.get("runtime_catalogue_visible_source") != "compact_build_bound_bootstrap":
        errors.append("current visible catalogue source changed before cutover proof")
    if authorization.get("visible_catalogue_source") != delivery.get("runtime_catalogue_visible_source"):
        errors.append("scale contract and current state disagree on visible catalogue source")
    if delivery.get("design") != "compact_build_bound_bootstrap_with_generation_bound_selected_detail_shadow":
        errors.append("current catalogue delivery design changed before T028 cutover")

    policy = contract.get("decision_policy", {})
    if policy.get("backend_by_default") is not False:
        errors.append("catalogue scale contract must remain measurement-first, not backend-first")
    if policy.get("server_search_or_postgis_or_pmtiles") != "introduce_only_after_measured_static_boundary_failure":
        errors.append("catalogue scale infrastructure escalation policy mismatch")

    return errors


def main() -> int:
    errors = validate_catalog_scale_gates()
    if errors:
        print("Catalogue scale gate validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Catalogue scale gate validation passed: schema-realistic 1k and 10k fixtures pass, 100k fixed two-hex shards fail closed, three-hex migration candidate restores headroom, cutover unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
