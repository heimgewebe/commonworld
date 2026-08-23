#!/usr/bin/env python3
"""Validate Commonworld catalogue delivery budgets and benchmark evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from scripts.measure_catalog_delivery import measure
except ModuleNotFoundError:  # Direct script execution adds scripts/ to sys.path.
    from measure_catalog_delivery import measure

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / 'contracts/commonworld/catalog-delivery-budget.contract.json'
EVIDENCE_PATH = ROOT / 'docs/evidence/catalog-delivery-benchmark-v1.json'
SMOKE_EVIDENCE_PATH = ROOT / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json'
OPTIONS_PATH = ROOT / 'docs/catalog-delivery-options.md'
SMOKE_SCRIPT_PATH = ROOT / 'scripts/smoke_public_browser.mjs'
SMOKE_RUNNER_PATH = ROOT / 'scripts/run_browser_smoke.py'
SMOKE_PLAN_PATH = ROOT / 'scripts/browser_smoke_plan.py'
RELEASE_MANIFEST_PATH = ROOT / 'assets/commonworld-page-builds.json'
CATALOGUE_NETWORK_BLOCKED_SCENARIO = 'catalogue-network-blocked'
BOOTSTRAP_ASSET_FAILURE_SCENARIO = 'bootstrap-asset-failure-fallback'
POST_RENDER_FAILURE_SCENARIO = 'post-render-failure-preserves-fallback'


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def release_ids_from_requests(requests: list[str]) -> set[str]:
    release_ids: set[str] = set()
    prefix = '/releases/'
    for request_path in requests:
        if not isinstance(request_path, str) or not request_path.startswith(prefix):
            continue
        release_id = request_path[len(prefix):].split('/', 1)[0]
        if release_id:
            release_ids.add(release_id)
    return release_ids


def scenario_map(value: dict) -> tuple[list[str], dict[str, dict], list[str]]:
    errors: list[str] = []
    identifiers: list[str] = []
    scenarios: dict[str, dict] = {}
    raw_scenarios = value.get('scenarios', [])
    if not isinstance(raw_scenarios, list):
        return identifiers, scenarios, ['browser smoke scenarios are not an array']
    for item in raw_scenarios:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            errors.append('browser smoke contains a scenario without a string id')
            continue
        identifier = item['id']
        identifiers.append(identifier)
        if identifier in scenarios:
            errors.append(f'browser smoke contains duplicate scenario id: {identifier}')
        scenarios[identifier] = item
    return identifiers, scenarios, errors


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_blocked_catalog_requests(scenarios: dict[str, dict], label: str) -> list[str]:
    scenario = scenarios.get(CATALOGUE_NETWORK_BLOCKED_SCENARIO)
    if scenario is None:
        return [f'{label} missing required scenario: {CATALOGUE_NETWORK_BLOCKED_SCENARIO}']
    if 'blockedCatalogRequests' not in scenario:
        return [
            f'{label} scenario {CATALOGUE_NETWORK_BLOCKED_SCENARIO} missing blockedCatalogRequests'
        ]
    value = scenario['blockedCatalogRequests']
    if not is_nonnegative_integer(value):
        return [
            f'{label} scenario {CATALOGUE_NETWORK_BLOCKED_SCENARIO} '
            'blockedCatalogRequests must be a nonnegative integer'
        ]
    if value != 0:
        return [f'{label} observed {value} runtime catalogue request(s)']
    return []


def validate_bootstrap_asset_failure_fallback(
    scenarios: dict[str, dict],
    label: str,
    expected_catalog_cards: int,
) -> list[str]:
    scenario = scenarios.get(BOOTSTRAP_ASSET_FAILURE_SCENARIO)
    if scenario is None:
        return [f'{label} missing required scenario: {BOOTSTRAP_ASSET_FAILURE_SCENARIO}']
    errors: list[str] = []
    blocked = scenario.get('blockedBootstrapRequests')
    if not is_nonnegative_integer(blocked):
        errors.append(
            f'{label} scenario {BOOTSTRAP_ASSET_FAILURE_SCENARIO} '
            'blockedBootstrapRequests must be a nonnegative integer'
        )
    elif blocked != 1:
        errors.append(f'{label} expected exactly one blocked bootstrap request, got {blocked}')
    cards = scenario.get('fallbackCatalogCards')
    if not is_nonnegative_integer(cards):
        errors.append(
            f'{label} scenario {BOOTSTRAP_ASSET_FAILURE_SCENARIO} '
            'fallbackCatalogCards must be a nonnegative integer'
        )
    elif cards != expected_catalog_cards:
        errors.append(
            f'{label} bootstrap fallback catalog is incomplete: '
            f'expected {expected_catalog_cards}, got {cards}'
        )
    hidden = scenario.get('hiddenFallbackCatalogCards')
    if not is_nonnegative_integer(hidden):
        errors.append(
            f'{label} scenario {BOOTSTRAP_ASSET_FAILURE_SCENARIO} '
            'hiddenFallbackCatalogCards must be a nonnegative integer'
        )
    elif hidden != 0:
        errors.append(f'{label} bootstrap fallback catalog hides {hidden} card(s)')
    if scenario.get('neutralRecoveryCopy') is not True:
        errors.append(f'{label} bootstrap fallback does not prove neutral recovery copy')
    if scenario.get('skipLinkHref') != '/#static-catalog-fallback':
        errors.append(f'{label} bootstrap failure skip link does not target the recovery catalog')
    if scenario.get('targetRecoveryHash') != '#static-catalog-fallback':
        errors.append(f'{label} bootstrap failure fragment does not target the recovery catalog')
    if scenario.get('targetRecoveryVisible') is not True:
        errors.append(f'{label} bootstrap failure fragment does not immediately reveal the recovery catalog')
    if scenario.get('targetRecoveryAnimationName') != 'none':
        errors.append(f'{label} bootstrap failure fragment reveal still depends on delayed animation')
    return errors


def validate_post_render_failure_fallback(
    scenarios: dict[str, dict],
    label: str,
    expected_catalog_cards: int,
) -> list[str]:
    scenario = scenarios.get(POST_RENDER_FAILURE_SCENARIO)
    if scenario is None:
        return [f'{label} missing required scenario: {POST_RENDER_FAILURE_SCENARIO}']
    errors: list[str] = []
    cards = scenario.get('fallbackCatalogCards')
    hidden = scenario.get('hiddenFallbackCatalogCards')
    if cards != expected_catalog_cards:
        errors.append(
            f'{label} post-render failure fallback is incomplete: '
            f'expected {expected_catalog_cards}, got {cards}'
        )
    if hidden != 0:
        errors.append(f'{label} post-render failure fallback hides {hidden} card(s)')
    if scenario.get('skipLinkHref') != '/#static-catalog-fallback':
        errors.append(f'{label} post-render failure skip link does not target the recovery catalog')
    if scenario.get('skipFocusId') != 'static-catalog-fallback':
        errors.append(f'{label} post-render failure skip handler does not focus the recovery catalog')
    if scenario.get('skipActivatedRecovery') is not True:
        errors.append(f'{label} post-render failure skip handler does not reveal the recovery catalog')
    return errors


def validate_compile_samples(profile_name: str, profile: dict) -> list[str]:
    errors: list[str] = []
    compile_metrics = profile.get('bootstrap_compile', {})
    samples = compile_metrics.get('samples_ms')
    if not isinstance(samples, list) or len(samples) != 21:
        return [f'{profile_name}: bootstrap compile samples must contain exactly 21 values']
    if any(not is_number(value) or value < 0 for value in samples):
        return [f'{profile_name}: bootstrap compile samples must be nonnegative numbers']
    if samples != sorted(samples):
        errors.append(f'{profile_name}: bootstrap compile samples must be sorted')
    median = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95)]
    if compile_metrics.get('median_ms') != median:
        errors.append(f'{profile_name}: bootstrap compile median does not match raw samples')
    if compile_metrics.get('p95_ms') != p95:
        errors.append(f'{profile_name}: bootstrap compile p95 does not match raw samples')
    return errors


def validate_actual_smoke(actual: dict, expected: dict) -> list[str]:
    errors: list[str] = []
    expected_ids, expected_scenarios, expected_errors = scenario_map(expected)
    actual_ids, actual_scenarios, actual_errors = scenario_map(actual)
    errors.extend(expected_errors)
    errors.extend(actual_errors)
    if actual.get('verdict') != 'PASS':
        errors.append('fresh public browser smoke result is not PASS')
    if actual_ids != expected_ids:
        errors.append('fresh public browser smoke scenario order or membership differs from committed evidence')
    for identifier, scenario in actual_scenarios.items():
        if scenario.get('verdict') != 'PASS':
            errors.append(f'fresh public browser smoke scenario is not PASS: {identifier}')
    errors.extend(validate_blocked_catalog_requests(actual_scenarios, 'fresh public browser smoke'))
    expected_cards = expected_scenarios.get(BOOTSTRAP_ASSET_FAILURE_SCENARIO, {}).get('fallbackCatalogCards')
    if not is_nonnegative_integer(expected_cards):
        errors.append('committed browser smoke has no valid bootstrap fallback catalog count')
    else:
        errors.extend(validate_bootstrap_asset_failure_fallback(actual_scenarios, 'fresh public browser smoke', expected_cards))
        errors.extend(validate_post_render_failure_fallback(actual_scenarios, 'fresh public browser smoke', expected_cards))
    return errors


def first_party_surface_sha256(root: Path, requests: list[str]) -> str:
    digest = hashlib.sha256()
    for request_path in sorted(requests):
        if not isinstance(request_path, str) or not request_path.startswith('/'):
            raise ValueError(f'invalid first-party request path: {request_path!r}')
        if request_path == '/__cw_probe/<nonce>/manifest':
            relative = '404.html'
        else:
            relative = 'index.html' if request_path == '/' else request_path.lstrip('/')
        target = (root / relative).resolve()
        if target != root.resolve() and root.resolve() not in target.parents:
            raise ValueError(f'first-party request escapes repository root: {request_path}')
        digest.update(request_path.encode('utf-8'))
        digest.update(b'\0')
        digest.update(target.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def validate(root: Path = ROOT, warnings: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    warning_messages = warnings if warnings is not None else []
    contract_path = root / CONTRACT_PATH.relative_to(ROOT)
    evidence_path = root / EVIDENCE_PATH.relative_to(ROOT)
    options_path = root / OPTIONS_PATH.relative_to(ROOT)
    smoke_evidence_path = root / SMOKE_EVIDENCE_PATH.relative_to(ROOT)
    app_path = root / 'assets/commonworld-app.js'
    smoke_script_path = root / SMOKE_SCRIPT_PATH.relative_to(ROOT)
    smoke_runner_path = root / SMOKE_RUNNER_PATH.relative_to(ROOT)
    smoke_plan_path = root / SMOKE_PLAN_PATH.relative_to(ROOT)
    release_manifest_path = root / RELEASE_MANIFEST_PATH.relative_to(ROOT)
    for path in (contract_path, evidence_path, smoke_evidence_path, options_path, app_path, smoke_script_path, smoke_runner_path, smoke_plan_path, release_manifest_path):
        if not path.is_file():
            errors.append(f'missing catalogue delivery artifact: {path.relative_to(root)}')
    if errors:
        return errors

    contract = load_json(contract_path)
    evidence = load_json(evidence_path)
    smoke_evidence = load_json(smoke_evidence_path)
    release_manifest = load_json(release_manifest_path)
    current_release_id = release_manifest.get('release_id')
    if not isinstance(current_release_id, str) or not current_release_id:
        errors.append('current release manifest has no release_id')
    static = measure(root)
    budgets = contract.get('budgets', {})

    if contract.get('selected_design', {}).get('id') != 'compact-build-bound-bootstrap-with-public-project-json':
        errors.append('catalogue delivery selected design is not canonical')
    if contract.get('canonical_truth', {}).get('records') != 'catalog/projects/*.json':
        errors.append('canonical CommonProject source boundary changed')

    deterministic_checks = {
        'startup project JSON requests': (static['runtime_verification_fetch']['project_request_count'], budgets.get('max_startup_project_json_requests')),
        'duplicate identity payload count': (static['runtime_verification_fetch']['duplicate_identity_payload_count'], budgets.get('max_duplicate_identity_payload_count')),
        'catalogue initial gzip bytes': (static['catalog_initial_delivery']['gzip_bytes'], budgets.get('max_catalog_initial_gzip_bytes')),
        'bootstrap raw bytes per record': (static['bootstrap']['raw_bytes_per_record'], budgets.get('max_bootstrap_raw_bytes_per_record')),
        'HTML start tags': (static['html']['start_tag_count'], budgets.get('max_html_start_tags')),
        'landing recovery entries': (static['html']['catalog_card_instances'], budgets.get('max_landing_recovery_entries')),
    }
    for label, (actual, maximum) in deterministic_checks.items():
        if not is_number(maximum):
            errors.append(f'missing numeric budget for {label}')
        elif actual > maximum:
            errors.append(f'{label} exceeds budget: {actual} > {maximum}')

    actual_bootstrap_gzip = static['bootstrap']['gzip_bytes']
    warning_bootstrap_gzip = budgets.get('warn_bootstrap_gzip_bytes')
    maximum_bootstrap_gzip = budgets.get('max_bootstrap_gzip_bytes')
    if not is_nonnegative_integer(warning_bootstrap_gzip):
        errors.append('missing nonnegative integer budget for bootstrap gzip warning')
    if not is_nonnegative_integer(maximum_bootstrap_gzip):
        errors.append('missing nonnegative integer budget for bootstrap gzip maximum')
    if is_nonnegative_integer(warning_bootstrap_gzip) and is_nonnegative_integer(maximum_bootstrap_gzip):
        if warning_bootstrap_gzip > maximum_bootstrap_gzip:
            errors.append(
                'bootstrap gzip warning exceeds maximum: '
                f'warn={warning_bootstrap_gzip}, max={maximum_bootstrap_gzip}'
            )
        elif actual_bootstrap_gzip > maximum_bootstrap_gzip:
            errors.append(
                'bootstrap gzip bytes exceeds budget: '
                f'actual={actual_bootstrap_gzip}, warn={warning_bootstrap_gzip}, '
                f'max={maximum_bootstrap_gzip}'
            )
        elif actual_bootstrap_gzip >= warning_bootstrap_gzip:
            warning_messages.append(
                'bootstrap gzip bytes entered warning range: '
                f'actual={actual_bootstrap_gzip}, warn={warning_bootstrap_gzip}, '
                f'max={maximum_bootstrap_gzip}'
            )

    app = app_path.read_text(encoding='utf-8')
    for forbidden in ('async function loadRecords(', './catalog/catalog.json', 'manifest.project_files.map', '/catalog/projects/', "fetchJson('./catalog/"):
        if forbidden in app:
            errors.append(f'runtime must not refetch the canonical catalogue at startup: {forbidden}')
    if "dataset.catalogDelivery = 'build-bound-bootstrap'" not in app:
        errors.append('runtime does not declare build-bound compact catalogue delivery')

    baseline = evidence.get('baseline', {})
    optimized = evidence.get('optimized', {})
    if optimized.get('static') != static:
        errors.append('committed optimized static evidence does not match current generated surfaces')
    budget_binding = evidence.get('budget_binding', {})
    expected_budget_binding = {
        'bootstrap_gzip_bytes': actual_bootstrap_gzip,
        'warn_bootstrap_gzip_bytes': warning_bootstrap_gzip,
        'max_bootstrap_gzip_bytes': maximum_bootstrap_gzip,
    }
    if budget_binding != expected_budget_binding:
        errors.append(
            'committed bootstrap budget evidence is stale: '
            f'actual={actual_bootstrap_gzip}, warn={warning_bootstrap_gzip}, '
            f'max={maximum_bootstrap_gzip}, evidence={budget_binding}'
        )
    baseline_static = baseline.get('static', {})
    baseline_runtime = baseline_static.get('runtime_verification_fetch', {})
    baseline_catalog_initial = baseline_static.get('catalog_initial_delivery', {})
    baseline_bootstrap = baseline_static.get('bootstrap', {})
    baseline_projects = baseline_static.get('canonical_projects', {})
    baseline_manifest = baseline_static.get('manifest', {})
    optimized_static = optimized.get('static', {})
    optimized_runtime = optimized_static.get('runtime_verification_fetch', {})
    optimized_catalog_initial = optimized_static.get('catalog_initial_delivery', {})

    if baseline_static.get('entry_count') != static['entry_count']:
        errors.append('baseline static evidence does not use the current catalogue identity set')
    if baseline_projects.get('file_count') != static['entry_count']:
        errors.append('baseline static evidence does not cover every current canonical project file')
    if baseline_runtime.get('enabled') is not True:
        errors.append('baseline static evidence must model the legacy startup refetch')
    if baseline_runtime.get('project_request_count') != static['entry_count']:
        errors.append('baseline does not record one duplicate request per identity')
    if baseline_runtime.get('duplicate_identity_payload_count') != static['entry_count']:
        errors.append('baseline does not record one duplicate identity payload per identity')

    expected_baseline_runtime_raw = baseline_projects.get('raw_bytes', 0) + baseline_manifest.get('raw_bytes', 0)
    expected_baseline_runtime_gzip = baseline_projects.get('gzip_bytes_individual_files', 0) + baseline_manifest.get('gzip_bytes', 0)
    if baseline_runtime.get('raw_bytes') != expected_baseline_runtime_raw:
        errors.append('baseline runtime refetch raw bytes are inconsistent with current canonical files')
    if baseline_runtime.get('gzip_bytes') != expected_baseline_runtime_gzip:
        errors.append('baseline runtime refetch gzip bytes are inconsistent with current canonical files')
    if baseline_catalog_initial.get('raw_bytes') != baseline_bootstrap.get('raw_bytes', 0) + expected_baseline_runtime_raw:
        errors.append('baseline catalogue initial raw bytes are internally inconsistent')
    if baseline_catalog_initial.get('gzip_bytes') != baseline_bootstrap.get('gzip_bytes', 0) + expected_baseline_runtime_gzip:
        errors.append('baseline catalogue initial gzip bytes are internally inconsistent')

    delta = evidence.get('delta', {})
    expected_delta = {
        'startup_project_json_requests': optimized_runtime.get('project_request_count', 0) - baseline_runtime.get('project_request_count', 0),
        'duplicate_identity_payload_count': optimized_runtime.get('duplicate_identity_payload_count', 0) - baseline_runtime.get('duplicate_identity_payload_count', 0),
        'catalog_initial_raw_bytes': optimized_catalog_initial.get('raw_bytes', 0) - baseline_catalog_initial.get('raw_bytes', 0),
        'catalog_initial_gzip_bytes': optimized_catalog_initial.get('gzip_bytes', 0) - baseline_catalog_initial.get('gzip_bytes', 0),
    }
    for key, expected_value in expected_delta.items():
        if delta.get(key) != expected_value:
            errors.append(f'evidence delta is stale for {key}: expected {expected_value}, got {delta.get(key)}')

    baseline_raw = baseline_catalog_initial.get('raw_bytes')
    baseline_gzip = baseline_catalog_initial.get('gzip_bytes')
    if is_number(baseline_raw) and baseline_raw > 0:
        expected_raw_reduction = round((-expected_delta['catalog_initial_raw_bytes'] / baseline_raw) * 100, 1)
        if delta.get('catalog_initial_raw_reduction_percent') != expected_raw_reduction:
            errors.append('catalogue initial raw reduction percentage is inconsistent with measured bytes')
    if is_number(baseline_gzip) and baseline_gzip > 0:
        expected_gzip_reduction = round((-expected_delta['catalog_initial_gzip_bytes'] / baseline_gzip) * 100, 1)
        if delta.get('catalog_initial_gzip_reduction_percent') != expected_gzip_reduction:
            errors.append('catalogue initial gzip reduction percentage is inconsistent with measured bytes')

    baseline_browser_profiles = {
        profile.get('profile'): profile
        for profile in baseline.get('browser', {}).get('profiles', [])
        if isinstance(profile, dict)
    }
    optimized_browser_profiles = {
        profile.get('profile'): profile
        for profile in optimized.get('browser', {}).get('profiles', [])
        if isinstance(profile, dict)
    }
    expected_request_delta = {
        name: optimized_browser_profiles[name].get('first_party_request_count', 0) - profile.get('first_party_request_count', 0)
        for name, profile in baseline_browser_profiles.items()
        if name in optimized_browser_profiles
    }
    if delta.get('first_party_request_count_by_profile') != expected_request_delta:
        errors.append('browser request-count delta does not match recorded baseline and optimized observations')
    expected_dom_delta = {
        name: optimized_browser_profiles[name].get('dom_node_count', 0) - profile.get('dom_node_count', 0)
        for name, profile in baseline_browser_profiles.items()
        if name in optimized_browser_profiles
    }
    if delta.get('browser_dom_nodes_by_profile') != expected_dom_delta:
        errors.append('browser DOM-node delta does not match recorded baseline and optimized observations')

    if smoke_evidence.get('verdict') != 'PASS':
        errors.append('public browser smoke evidence is not PASS')
    smoke_ids, smoke_scenarios, smoke_structure_errors = scenario_map(smoke_evidence)
    errors.extend(smoke_structure_errors)
    binding = smoke_evidence.get('binding', {})
    if binding.get('smoke_script_sha256') != file_sha256(smoke_script_path):
        errors.append('public browser smoke evidence is stale for the smoke script')
    if binding.get('smoke_runner_sha256') != file_sha256(smoke_runner_path):
        errors.append('public browser smoke evidence is stale for the smoke runner')
    if binding.get('smoke_plan_sha256') != file_sha256(smoke_plan_path):
        errors.append('public browser smoke evidence is stale for the canonical smoke plan')
    if binding.get('scenario_ids') != smoke_ids:
        errors.append('public browser smoke evidence scenario binding is stale')
    optimized_profiles = optimized.get('browser', {}).get('profiles', [])
    surface_hashes = {
        profile.get('first_party_surface_sha256')
        for profile in optimized_profiles
        if isinstance(profile, dict) and isinstance(profile.get('first_party_surface_sha256'), str)
    }
    current_surface_sha256 = next(iter(surface_hashes)) if len(surface_hashes) == 1 else None
    if len(surface_hashes) != 1 or binding.get('first_party_surface_sha256') not in surface_hashes:
        errors.append('public browser smoke evidence is stale for the first-party surface')
    for required_scenario in ('startup-and-ring-orbits', CATALOGUE_NETWORK_BLOCKED_SCENARIO, BOOTSTRAP_ASSET_FAILURE_SCENARIO, POST_RENDER_FAILURE_SCENARIO, 'provider-failure', 'method-mobile', 'method-desktop'):
        if smoke_scenarios.get(required_scenario, {}).get('verdict') != 'PASS':
            errors.append(f'public browser smoke missing PASS scenario: {required_scenario}')
    errors.extend(validate_blocked_catalog_requests(smoke_scenarios, 'public browser smoke'))
    expected_recovery_entries = min(static['entry_count'], budgets.get('max_landing_recovery_entries', -1))
    errors.extend(validate_bootstrap_asset_failure_fallback(smoke_scenarios, 'public browser smoke', expected_recovery_entries))
    errors.extend(validate_post_render_failure_fallback(smoke_scenarios, 'public browser smoke', expected_recovery_entries))

    browser = optimized.get('browser', {})
    if browser.get('cpu_throttle_rate') != 4:
        errors.append('optimized browser evidence must use fourfold CPU throttling')
    profiles = {profile.get('profile'): profile for profile in browser.get('profiles', [])}
    if set(profiles) != {'mobile-low-power', 'desktop-low-power'}:
        errors.append('optimized browser evidence must cover mobile and desktop low-power profiles')
    for name, profile in profiles.items():
        checks = {
            'project JSON requests': (profile.get('project_json_request_count'), budgets.get('max_startup_project_json_requests')),
            'DOM nodes': (profile.get('dom_node_count'), budgets.get('max_browser_dom_nodes')),
            'runtime ready milliseconds': (profile.get('runtime_ready_ms'), budgets.get('max_runtime_ready_ms_at_4x_cpu')),
            'script duration milliseconds': (profile.get('script_duration_ms'), budgets.get('max_script_duration_ms_at_4x_cpu')),
            'task duration milliseconds': (profile.get('task_duration_ms'), budgets.get('max_task_duration_ms_at_4x_cpu')),
            'bootstrap compile p95 milliseconds': (profile.get('bootstrap_compile', {}).get('p95_ms'), budgets.get('max_bootstrap_compile_p95_ms_at_4x_cpu')),
        }
        for label, (actual, maximum) in checks.items():
            if not is_number(actual) or not is_number(maximum):
                errors.append(f'{name}: missing numeric {label} evidence or budget')
            elif actual > maximum:
                errors.append(f'{name}: {label} exceeds budget: {actual} > {maximum}')
        errors.extend(validate_compile_samples(name, profile))
        if profile.get('runtime_ready') is not True or profile.get('runtime_failed') is not False:
            errors.append(f'{name}: runtime did not reach a healthy ready state')
        requests = profile.get('first_party_requests')
        if not isinstance(requests, list) or not requests:
            errors.append(f'{name}: first-party surface request inventory missing')
        else:
            try:
                current_surface_sha256 = first_party_surface_sha256(root, requests)
            except (OSError, ValueError) as error:
                errors.append(f'{name}: cannot verify first-party surface: {error}')
            else:
                if profile.get('first_party_surface_sha256') != current_surface_sha256:
                    errors.append(f'{name}: browser evidence is stale for the current first-party surface')
            request_release_ids = release_ids_from_requests(requests)
            if current_release_id and request_release_ids != {current_release_id}:
                errors.append(
                    f'{name}: browser evidence release binding is stale: '
                    f'expected {current_release_id}, got {sorted(request_release_ids)}'
                )

    validation = evidence.get('validation', {})
    public_summary = validation.get('public_browser_smoke', {})
    expected_public_summary = {
        'verdict': 'PASS',
        'committed_evidence_sha256': file_sha256(smoke_evidence_path),
        'first_party_surface_sha256': binding.get('first_party_surface_sha256'),
        'scenario_count': len(smoke_ids),
        'release_id': current_release_id,
        'scope': f'local Chromium on deterministic release {current_release_id}',
    }
    for key, expected_value in expected_public_summary.items():
        if public_summary.get(key) != expected_value:
            errors.append(f'current public browser smoke summary is stale for {key}')

    measurement_summary = validation.get('catalog_delivery_browser_measurement', {})
    expected_attempt_hashes = [
        attempt.get('measurement_sha256')
        for attempt in browser.get('attempts', [])
        if isinstance(attempt, dict)
    ]
    expected_measurement_summary = {
        'verdict': 'PASS' if browser.get('gate_verdict') == 'pass' else str(browser.get('gate_verdict', '')).upper(),
        'decision': browser.get('decision'),
        'attempt_count': browser.get('attempt_count'),
        'attempt_measurement_sha256s': expected_attempt_hashes,
        'profiles': [profile.get('profile') for profile in browser.get('profiles', [])],
        'cpu_throttle_rate': browser.get('cpu_throttle_rate'),
        'first_party_surface_sha256': browser.get('first_party_surface_sha256'),
        'release_id': current_release_id,
    }
    for key, expected_value in expected_measurement_summary.items():
        if measurement_summary.get(key) != expected_value:
            errors.append(f'current browser measurement summary is stale for {key}')
    measurement_note = measurement_summary.get('repeatability_note')
    if not isinstance(measurement_note, str) or f'release-{current_release_id}' not in measurement_note:
        errors.append('current browser measurement repeatability note is stale')

    static_summary = validation.get('catalog_delivery_static_measurement', {})
    if static_summary.get('verdict') != 'PASS':
        errors.append('current static measurement summary is not PASS')
    if static_summary.get('result_sha256') != canonical_sha256(optimized_static):
        errors.append('current static measurement summary hash is stale')
    if static_summary.get('release_id') != current_release_id:
        errors.append('current static measurement summary release is stale')
    static_note = static_summary.get('note')
    if not isinstance(static_note, str) or f'release {current_release_id}' not in static_note:
        errors.append('current static measurement summary note is stale')

    expected_current_surface_binding = {
        'release_id': current_release_id,
        'first_party_surface_sha256': browser.get('first_party_surface_sha256'),
        'public_browser_smoke_evidence_sha256': file_sha256(smoke_evidence_path),
        'browser_measurement_decision_sha256': canonical_sha256(browser),
        'static_measurement_sha256': canonical_sha256(optimized_static),
    }
    if evidence.get('current_surface_binding') != expected_current_surface_binding:
        errors.append('current surface binding is stale')

    current_surface_note = evidence.get('current_surface_note')
    if not isinstance(current_surface_note, str) or f'deterministic release {current_release_id}' not in current_surface_note:
        errors.append('current surface note is stale')

    attempt_profiles: list[dict[str, dict]] = []
    for attempt in browser.get('attempts', []):
        measurement = attempt.get('measurement', {}) if isinstance(attempt, dict) else {}
        attempt_profiles.append({
            profile.get('profile'): profile
            for profile in measurement.get('profiles', [])
            if isinstance(profile, dict) and isinstance(profile.get('profile'), str)
        })
    expected_repeatability_profiles: dict[str, dict] = {}
    for name in ('mobile-low-power', 'desktop-low-power'):
        if not attempt_profiles or any(name not in attempt for attempt in attempt_profiles):
            continue
        expected_repeatability_profiles[name] = {}
        for field in ('runtime_ready_ms', 'script_duration_ms', 'task_duration_ms'):
            values = [attempt[name].get(field) for attempt in attempt_profiles]
            if all(is_number(value) for value in values):
                expected_repeatability_profiles[name][field] = {
                    'min': min(values),
                    'max': max(values),
                    'values': values,
                }
    repeatability = evidence.get('browser_repeatability', {})
    if repeatability.get('run_count') != browser.get('attempt_count'):
        errors.append('browser repeatability run count is stale')
    if repeatability.get('cpu_throttle_rate') != browser.get('cpu_throttle_rate'):
        errors.append('browser repeatability CPU throttle binding is stale')
    if repeatability.get('profiles') != expected_repeatability_profiles:
        errors.append('browser repeatability metrics are stale')
    repeatability_interpretation = repeatability.get('interpretation')
    if (
        not isinstance(repeatability_interpretation, str)
        or f'release-{current_release_id}' not in repeatability_interpretation
    ):
        errors.append('browser repeatability interpretation is stale')

    options = options_path.read_text(encoding='utf-8')
    for token in (
        'Generierter vollständiger Bootstrap',
        'HTML-Hydration',
        'Segmentiertes statisches JSON',
        'Bedarfsgeladene schreibgeschützte statische Lieferung',
        'Barrierefreiheit und No-JS',
        'SEO',
        'Datenschutz',
        'Caching',
        'GitHub Pages',
        'Katalogzahl',
    ):
        if token not in options:
            errors.append(f'catalogue delivery option comparison missing: {token}')
    if (
        static['html']['static_fallback_catalogs'] != 1
        or static['html']['noscript_elements'] != 0
        or static['html']['catalog_card_instances'] != min(static['entry_count'], budgets.get('max_landing_recovery_entries', -1))
        or static['html']['interactive_catalog_cards'] != 0
    ):
        errors.append('generated static fallback catalogue must be bounded exactly once in ordinary DOM, without a duplicate noscript catalogue or static interactive cards')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-result', type=Path)
    args = parser.parse_args()
    warnings: list[str] = []
    errors = validate(warnings=warnings)
    if args.smoke_result:
        if not args.smoke_result.is_file():
            errors.append(f'fresh public browser smoke result missing: {args.smoke_result}')
        else:
            errors.extend(validate_actual_smoke(load_json(args.smoke_result), load_json(SMOKE_EVIDENCE_PATH)))
    for warning in warnings:
        print(f'WARNING: {warning}')
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    metrics = measure()
    suffix = ', fresh browser smoke bound' if args.smoke_result else ''
    print(
        'catalogue delivery budget valid: '
        f"{metrics['entry_count']} records, "
        f"{metrics['catalog_initial_delivery']['gzip_bytes']} catalogue gzip bytes, "
        f"{metrics['bootstrap']['gzip_bytes']} bootstrap gzip bytes, "
        f"{metrics['runtime_verification_fetch']['project_request_count']} startup project requests"
        f"{suffix}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
