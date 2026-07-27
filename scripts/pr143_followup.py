#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, found {count}')
    return text.replace(old, new, 1)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def remove_simple_css_blocks(css: str, markers: tuple[str, ...]) -> str:
    stack: list[tuple[int, str]] = []
    spans: list[tuple[int, int]] = []
    last_boundary = 0
    for index, char in enumerate(css):
        if char == '{':
            selector_start = last_boundary
            selector = css[selector_start:index].strip()
            stack.append((selector_start, selector))
            last_boundary = index + 1
        elif char == '}':
            if not stack:
                raise SystemExit('CSS parser saw an unmatched closing brace')
            selector_start, selector = stack.pop()
            if not selector.startswith('@') and any(marker in selector for marker in markers):
                end = index + 1
                while end < len(css) and css[end] in ' \t':
                    end += 1
                if end < len(css) and css[end] == '\n':
                    end += 1
                spans.append((selector_start, end))
            last_boundary = index + 1
    if stack:
        raise SystemExit('CSS parser saw an unmatched opening brace')
    for start, end in sorted(spans, reverse=True):
        css = css[:start] + css[end:]
    return css


def patch_app() -> None:
    path = 'assets/commonworld-app.js'
    app = read(path)
    app = replace_once(app, '  deriveDigitalProjectPath,\n', '', 'remove app-only derived path import')
    app = replace_once(
        app,
        """function selectDigitalProject(record, { trigger = document.activeElement } = {}) {
  const derived = deriveDigitalProjectPath(record);
  if (runtime.state.view === 'layers' && derived?.path?.length) {
    if (serializeDigitalPath(currentDigitalPath()) !== derived.pathKey) {
      setDigitalPath(derived.path, { historyMode: null, focusHierarchy: false });
    }
    selectProject(record.id, { trigger });
    return;
  }
  selectProject(record.id, { trigger });
}

""",
        '',
        'remove path-rewriting digital selection wrapper',
    )
    app = replace_once(
        app,
        "  segment.addEventListener('click', () => selectDigitalProject(record, { trigger: segment }));",
        "  segment.addEventListener('click', () => selectProject(record.id, { trigger: segment }));",
        'route ribbons directly to shared focus',
    )
    app = replace_once(
        app,
        """function usesInlineLayerProjectDetail(record, view = visibleDigitalView()) {
  if (!record || runtime.state.view !== 'layers') return false;
  return runtime.state.project !== record.id
    && isIdentityLevelView(view)
    && recordVisibleInCurrentSelection(record);
}

""",
        '',
        'remove obsolete inline-detail ownership helper',
    )
    app = replace_once(
        app,
        '  layerPreviewProject: null,\n  lastLayerProjectStatus: null,\n',
        '',
        'remove obsolete inline-detail runtime state',
    )
    app = replace_once(
        app,
        """function renderLayerProjectDetail() {
  runtime.layerPreviewProject = null;
  runtime.lastLayerProjectStatus = null;
  elements.layerProjects.replaceChildren();
""",
        """function renderLayerProjectDetail() {
  elements.layerProjects.replaceChildren();
""",
        'simplify retired layer detail renderer',
    )
    app = replace_once(
        app,
        """function reconcileProjectSelection(records = visibleRecords()) {
  const ids = records === runtime.visibleRecordsCache?.records
    ? visibleRecordIds()
    : new Set(records.map(({ id }) => id));
  if (runtime.layerPreviewProject && !ids.has(runtime.layerPreviewProject)) {
    runtime.layerPreviewProject = null;
    runtime.lastLayerProjectStatus = null;
  }
}

""",
        '',
        'remove obsolete inline-detail reconciliation',
    )
    app = replace_once(app, '  reconcileProjectSelection();\n', '', 'remove obsolete reconciliation call')
    app = replace_once(app, '  const retainedDuringFiltering = filteringActive && !usesInlineLayerProjectDetail(record);', '  const retainedDuringFiltering = filteringActive;', 'shared focus filtering status')
    app = replace_once(app, '  runtime.layerPreviewProject = null;\n  renderLayerProjectDetail();', '  renderLayerProjectDetail();', 'remove obsolete close state')
    for forbidden in ('selectDigitalProject', 'runtime.layerPreviewProject', 'runtime.lastLayerProjectStatus', 'usesInlineLayerProjectDetail', 'reconcileProjectSelection'):
        if forbidden in app:
            raise SystemExit(f'app still contains obsolete token: {forbidden}')
    write(path, app)


def patch_css() -> None:
    path = 'index.css'
    css = read(path)
    css = remove_simple_css_blocks(css, ('.layer-project-detail', '.project-detail-', '.layer-panel .layer-projects'))
    mobile_focus = """@media (max-width: 48rem) {
  .focus-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

"""
    anchor = '.digital-lane-content .identity-show-more {'
    if mobile_focus not in css:
        if anchor not in css:
            raise SystemExit('focus-grid insertion anchor missing')
        css = css.replace(anchor, mobile_focus + anchor, 1)
    css = re.sub(r'\n{3,}', '\n\n', css)
    for forbidden in ('.layer-project-detail', '.project-detail-', '.layer-panel .layer-projects'):
        if forbidden in css:
            raise SystemExit(f'CSS still contains orphaned detail selector: {forbidden}')
    write(path, css)


def patch_i18n() -> None:
    path = 'assets/commonworld-i18n.mjs'
    text = read(path)
    block = """  back_to_bundle: 'Back to {label}',
  back_to_bundle_aria: 'Close details and return to {label}',
  direct_actions: 'Direct actions',
  detail_profile: 'Profile',
  detail_presence: 'Presence',
  detail_network: 'Network and links',
  detail_evidence: 'Evidence',
  themes: 'Themes',
  ways_to_engage: 'Ways to engage',
  locations: 'Locations',
  digital_presence: 'Digital presence',
  relationships: 'Relationships',
  official_links: 'Official links',
  sources: 'Sources',
  curation: 'Curation',
  not_published: 'Not published',
"""
    text = replace_once(text, block, '', 'remove orphaned inline-detail translations')
    write(path, text)


def patch_tests() -> None:
    path = 'tests/test_public_shell.py'
    text = read(path)
    text = replace_once(text, '        self.assertIn("function selectDigitalProject", app)\n        self.assertIn("deriveDigitalProjectPath(record)", app)\n', '        self.assertNotIn("function selectDigitalProject", app)\n        self.assertNotIn("deriveDigitalProjectPath(record)", app)\n', 'update route assertions')
    text = replace_once(text, '        self.assertIn("selectProject(record.id, { trigger });", app)\n', '        self.assertIn("segment.addEventListener(\'click\', () => selectProject(record.id, { trigger: segment }));", app)\n', 'assert direct ribbon routing')
    text = replace_once(text, '        self.assertIn("reconcileProjectSelection();", app)\n', '        self.assertNotIn("reconcileProjectSelection", app)\n', 'remove reconciliation assertion')
    text = replace_once(text, '        self.assertIn("runtime.layerPreviewProject = null", app)\n', '        self.assertNotIn("runtime.layerPreviewProject", app)\n', 'remove preview state assertion')
    write(path, text)


def patch_validator() -> None:
    path = 'scripts/validate_public_maplibre_vertical_slice.py'
    text = read(path)
    old = """        "function selectDigitalProject",
        "deriveDigitalProjectPath(record)",
        "renderLayerProjectDetail(view);",
        "!usesInlineLayerProjectDetail(record)",
"""
    new = """        "segment.addEventListener('click', () => selectProject(record.id, { trigger: segment }));",
        "renderLayerProjectDetail(view);",
        "elements.layerProjects.hidden = true;",
        "const retainedDuringFiltering = filteringActive;",
"""
    text = replace_once(text, old, new, 'update vertical-slice route contract')
    write(path, text)


def patch_smoke() -> None:
    path = 'scripts/smoke_public_browser.mjs'
    text = read(path)
    old = """  const parentWikipedia = run.page.locator('.digital-ribbon-item[data-commonproject-id="wikipedia"]');
  assert(await parentWikipedia.isVisible(), 'layer journey: Wikipedia is not visible in the parent bundle lane');
  await parentWikipedia.click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture/open_knowledge_data');
  assert(await run.page.locator('#project-focus').isVisible(), 'layer journey: parent-lane selection did not open the shared focus panel');
  assert((await run.page.locator('#focus-title').textContent()) === 'Wikipedia', 'layer journey: shared focus panel describes the wrong parent-lane project');
  assert(await run.page.locator('#layer-projects').isHidden(), 'layer journey: selected project duplicated the canonical shared focus with inline details');
  await run.page.keyboard.press('Escape');
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('project') === null);
  assert(await run.page.locator('#project-focus').isHidden(), 'layer journey: closing the shared focus did not hide it');
  assert(await run.page.locator('#layer-projects').isHidden(), 'layer journey: closing shared focus exposed a competing inline detail');
  assert(new URL(run.page.url()).searchParams.get('project') === null, 'layer journey: closing shared focus retained project history');
  await run.page.locator('#layer-breadcrumb .digital-breadcrumb-item[data-digital-path="sphere/knowledge_learning_culture"]').click();
  await run.page.waitForFunction(() => document.querySelector('.globe-stage')?.dataset.digitalPath === 'sphere/knowledge_learning_culture');
"""
    new = """  const parentWikipedia = run.page.locator('.digital-ribbon-item[data-commonproject-id="wikipedia"]');
  assert(await parentWikipedia.isVisible(), 'layer journey: Wikipedia is not visible in the parent bundle lane');
  const parentLanePath = 'sphere/knowledge_learning_culture';
  await parentWikipedia.click();
  await run.page.waitForFunction((pathKey) => document.querySelector('.globe-stage')?.dataset.digitalPath === pathKey, parentLanePath);
  assert(new URL(run.page.url()).searchParams.get('digital_path') === parentLanePath, 'layer journey: parent-lane selection rewrote the originating bundle');
  assert(await run.page.locator('#project-focus').isVisible(), 'layer journey: parent-lane selection did not open the shared focus panel');
  assert((await run.page.locator('#focus-title').textContent()) === 'Wikipedia', 'layer journey: shared focus panel describes the wrong parent-lane project');
  assert(await run.page.locator('#layer-projects').isHidden(), 'layer journey: selected project duplicated the canonical shared focus with inline details');
  await run.page.keyboard.press('Escape');
  await run.page.waitForFunction(() => new URL(location.href).searchParams.get('project') === null);
  assert(await run.page.locator('#project-focus').isHidden(), 'layer journey: closing the shared focus did not hide it');
  assert(await run.page.locator('#layer-projects').isHidden(), 'layer journey: closing shared focus exposed a competing inline detail');
  assert(new URL(run.page.url()).searchParams.get('digital_path') === parentLanePath, 'layer journey: closing shared focus did not preserve the originating bundle');
"""
    text = replace_once(text, old, new, 'parent-lane focus path regression')
    old = """  const selectedDigitalPath = new URL(focusRun.page.url()).searchParams.get('digital_path');
  assert(Boolean(selectedDigitalPath), `atomic focus: ${focusProjectId} did not navigate to its concrete digital path`);
"""
    new = """  const selectedDigitalPath = new URL(focusRun.page.url()).searchParams.get('digital_path');
  assert(selectedDigitalPath === null, `atomic focus: ${focusProjectId} rewrote the originating root lane (${selectedDigitalPath})`);
  assert((await focusRun.page.locator('.globe-stage').getAttribute('data-digital-path')) === 'sphere', `atomic focus: ${focusProjectId} changed the visible root lane`);
"""
    text = replace_once(text, old, new, 'root-lane focus path regression')
    old = """  assert(await focusRun.page.locator('#project-focus').isHidden(), 'atomic focus: Escape did not close the shared focus');
  assert(await focusRun.page.locator('#layer-projects').isHidden(), 'atomic focus: Escape exposed a competing inline detail');
"""
    new = old + "  assert(new URL(focusRun.page.url()).searchParams.get('digital_path') === null, 'atomic focus: Escape did not preserve the originating root lane');\n"
    text = replace_once(text, old, new, 'escape path preservation assertion')
    if '.project-detail-' in text or '.layer-project-detail' in text:
        raise SystemExit('browser smoke still references removed inline-detail classes')
    write(path, text)


def patch_review() -> None:
    path = 'docs/evidence/digital-detail-unification-review-v1.md'
    text = read(path)
    addition = """
- The final exact-head Codex review found two additional P1 issues: opening shared focus from a parent lane rewrote the lane path, and the removed inline renderer left a dormant stylesheet and translations. Ribbon selection now preserves its originating lane; the obsolete CSS, runtime state and translation keys are removed; browser history covers parent- and root-lane close/back behavior.
"""
    if 'opening shared focus from a parent lane rewrote the lane path' not in text:
        text = text.rstrip() + '\n' + addition
    write(path, text)


def patch() -> None:
    patch_app()
    patch_css()
    patch_i18n()
    patch_tests()
    patch_validator()
    patch_smoke()
    patch_review()


def select_browser(paths: list[Path], output: Path) -> None:
    runs = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
    if len(runs) < 5:
        raise SystemExit('at least five browser measurements are required')
    profile_names = {'mobile-low-power', 'desktop-low-power'}
    surfaces: set[str] = set()
    by_name: dict[str, list[dict]] = {name: [] for name in profile_names}
    for run in runs:
        if run.get('cpu_throttle_rate') != 4:
            raise SystemExit('browser measurement lacks fourfold CPU throttling')
        profiles = {item.get('profile'): item for item in run.get('profiles', [])}
        if set(profiles) != profile_names:
            raise SystemExit('browser measurement profiles are incomplete')
        for name, profile in profiles.items():
            by_name[name].append(profile)
            surfaces.add(profile.get('first_party_surface_sha256'))
    if len(surfaces) != 1 or None in surfaces:
        raise SystemExit(f'browser measurements disagree on first-party surface: {surfaces}')

    limits = {
        'runtime_ready_ms': 1800,
        'script_duration_ms': 1600,
        'task_duration_ms': 3000,
    }
    selected_profiles: list[dict] = []
    selection: dict[str, dict] = {}
    for name in sorted(profile_names):
        candidates = by_name[name]
        candidates.sort(key=lambda item: sum(float(item[key]) / limit for key, limit in limits.items()))
        chosen = candidates[len(candidates) // 2]
        for key, limit in limits.items():
            if not isinstance(chosen.get(key), (int, float)) or chosen[key] > limit:
                raise SystemExit(f'median repeated browser measurement exceeds {key}: {chosen.get(key)} > {limit} for {name}')
        if chosen.get('bootstrap_compile', {}).get('p95_ms', 99) > 5:
            raise SystemExit(f'median repeated browser compile p95 exceeds budget for {name}')
        selected_profiles.append(chosen)
        selection[name] = {
            'repetitions': len(candidates),
            'selected_rank': len(candidates) // 2 + 1,
            'ordered_scores': [round(sum(float(item[key]) / limit for key, limit in limits.items()), 6) for item in candidates],
        }
    payload = {
        'schema_version': 1,
        'kind': 'commonworld_catalog_delivery_browser_metrics',
        'measured_at': max(run.get('measured_at', '') for run in runs),
        'cpu_throttle_rate': 4,
        'measurement_protocol': {
            'kind': 'five-repetition-profile-median',
            'selection': selection,
            'note': 'Each profile is the median composite observation across five exact-surface runs; no fastest-run selection.',
        },
        'profiles': selected_profiles,
    }
    write_json(output, payload)


def bind(static_path: Path, browser_path: Path, smoke_path: Path) -> None:
    benchmark_path = ROOT / 'docs/evidence/catalog-delivery-benchmark-v1.json'
    smoke_evidence_path = ROOT / 'docs/evidence/catalog-delivery-public-browser-smoke-v1.json'
    review_path = ROOT / 'docs/evidence/digital-detail-unification-review-v1.md'
    benchmark = json.loads(benchmark_path.read_text(encoding='utf-8'))
    smoke_evidence = json.loads(smoke_evidence_path.read_text(encoding='utf-8'))
    static = json.loads(static_path.read_text(encoding='utf-8'))
    browser = json.loads(browser_path.read_text(encoding='utf-8'))
    smoke = json.loads(smoke_path.read_text(encoding='utf-8'))
    contract = json.loads((ROOT / 'contracts/commonworld/catalog-delivery-budget.contract.json').read_text(encoding='utf-8'))
    budgets = contract['budgets']
    scenarios = smoke.get('scenarios', [])
    if smoke.get('verdict') != 'PASS' or len(scenarios) != 31 or any(item.get('verdict') != 'PASS' for item in scenarios):
        raise SystemExit('fresh public browser smoke is not PASS with exactly 31 passing scenarios')
    profiles = browser.get('profiles', [])
    if browser.get('cpu_throttle_rate') != 4 or {item.get('profile') for item in profiles} != {'mobile-low-power', 'desktop-low-power'}:
        raise SystemExit('fresh browser performance evidence is incomplete')
    result_hashes = {'static': sha256(static_path), 'browser': sha256(browser_path), 'smoke': sha256(smoke_path)}
    job_id = f"github-actions-{os.environ['GITHUB_RUN_ID']}-attempt-{os.environ['GITHUB_RUN_ATTEMPT']}"

    baseline_static = benchmark['baseline']['static']
    baseline_profiles = {item['profile']: item for item in benchmark['baseline']['browser']['profiles']}
    fresh_profiles = {item['profile']: item for item in profiles}
    benchmark['optimized']['static'] = static
    benchmark['optimized']['browser'] = browser
    benchmark['budget_binding'] = {
        'bootstrap_gzip_bytes': static['bootstrap']['gzip_bytes'],
        'warn_bootstrap_gzip_bytes': budgets['warn_bootstrap_gzip_bytes'],
        'max_bootstrap_gzip_bytes': budgets['max_bootstrap_gzip_bytes'],
    }
    base_delivery = baseline_static['catalog_initial_delivery']
    fresh_delivery = static['catalog_initial_delivery']
    raw_delta = fresh_delivery['raw_bytes'] - base_delivery['raw_bytes']
    gzip_delta = fresh_delivery['gzip_bytes'] - base_delivery['gzip_bytes']
    benchmark['delta'] = {
        'startup_project_json_requests': static['runtime_verification_fetch']['project_request_count'] - baseline_static['runtime_verification_fetch']['project_request_count'],
        'duplicate_identity_payload_count': static['runtime_verification_fetch']['duplicate_identity_payload_count'] - baseline_static['runtime_verification_fetch']['duplicate_identity_payload_count'],
        'catalog_initial_raw_bytes': raw_delta,
        'catalog_initial_gzip_bytes': gzip_delta,
        'catalog_initial_raw_reduction_percent': round((-raw_delta / base_delivery['raw_bytes']) * 100, 1),
        'catalog_initial_gzip_reduction_percent': round((-gzip_delta / base_delivery['gzip_bytes']) * 100, 1),
        'first_party_request_count_by_profile': {name: fresh_profiles[name]['first_party_request_count'] - base['first_party_request_count'] for name, base in baseline_profiles.items()},
        'browser_dom_nodes_by_profile': {name: fresh_profiles[name]['dom_node_count'] - base['dom_node_count'] for name, base in baseline_profiles.items()},
    }
    scenario_ids = [item['id'] for item in scenarios]
    blocked = next(item for item in scenarios if item['id'] == 'catalogue-network-blocked')
    benchmark['validation']['public_browser_smoke'] = {
        'verdict': 'PASS', 'scenario_count': len(scenario_ids), 'scenario_ids': scenario_ids,
        'catalogue_network_blocked_requests': blocked['blockedCatalogRequests'], 'job_id': job_id,
        'result_sha256': result_hashes['smoke'],
    }
    benchmark['validation']['catalog_delivery_browser_measurement'] = {
        'verdict': 'PASS', 'profiles': [item['profile'] for item in profiles], 'cpu_throttle_rate': 4,
        'measurement_protocol': browser.get('measurement_protocol'), 'result_sha256': result_hashes['browser'], 'job_id': job_id,
    }
    surface_hashes = {item['first_party_surface_sha256'] for item in profiles}
    if len(surface_hashes) != 1:
        raise SystemExit('browser profiles disagree on first-party surface')
    surface_hash = next(iter(surface_hashes))
    benchmark.setdefault('measurement_method', {})['browser_performance_provenance'] = (
        'GitHub Actions no-store Chromium measurement on the exact final PR surface; fourfold CPU throttling; '
        'five repetitions per profile with the median composite observation committed; first-party surface SHA-256 '
        f'{surface_hash}.'
    )
    smoke_evidence['execution'] = {'job_id': job_id, 'result_sha256': result_hashes['smoke']}
    smoke_evidence['binding']['smoke_script_sha256'] = sha256(ROOT / 'scripts/smoke_public_browser.mjs')
    smoke_evidence['binding']['smoke_runner_sha256'] = sha256(ROOT / 'scripts/run_browser_smoke.py')
    smoke_evidence['binding']['smoke_plan_sha256'] = sha256(ROOT / 'scripts/browser_smoke_plan.py')
    smoke_evidence['binding']['first_party_surface_sha256'] = surface_hash
    smoke_evidence['binding']['scenario_ids'] = scenario_ids
    smoke_evidence['verdict'] = 'PASS'
    smoke_evidence['scenarios'] = scenarios
    write_json(benchmark_path, benchmark)
    write_json(smoke_evidence_path, smoke_evidence)

    review = review_path.read_text(encoding='utf-8')
    review = re.sub(r'public browser-smoke result SHA-256: `[0-9a-f]+`', f"public browser-smoke result SHA-256: `{result_hashes['smoke']}`", review)
    review = re.sub(r'browser measurement result SHA-256: `[0-9a-f]+`', f"browser measurement result SHA-256: `{result_hashes['browser']}`", review)
    review_path.write_text(review, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('patch')
    select = sub.add_parser('select-browser')
    select.add_argument('--output', type=Path, required=True)
    select.add_argument('inputs', type=Path, nargs='+')
    bind_parser = sub.add_parser('bind')
    bind_parser.add_argument('--static', type=Path, required=True)
    bind_parser.add_argument('--browser', type=Path, required=True)
    bind_parser.add_argument('--smoke', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'patch':
        patch()
    elif args.command == 'select-browser':
        select_browser(args.inputs, args.output)
    else:
        bind(args.static, args.browser, args.smoke)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
