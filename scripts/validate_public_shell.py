#!/usr/bin/env python3
"""Validate the public globe-first Commonworld shell."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_HTML = (
    '<html lang="de">',
    '<body data-presentation="globe">',
    '<title>commonworld — Commons entdecken</title>',
    'class="topbar"',
    'id="commons-search"',
    'id="settings-toggle"',
    'id="settings-panel"',
    'id="globe-results"',
    'role="region"',
    'data-presentation-choice="globe"',
    'data-presentation-choice="text"',
    'id="globe-surface"',
    'class="globe-stage"',
    'class="globe-map"',
    'class="digital-sphere"',
    'id="sphere-edge-control"',
    'id="layer-panel"',
    'id="layer-breadcrumb"',
    'id="layer-current"',
    'id="layer-stack-visual"',
    'id="text-view"',
    'id="text-layer-breadcrumb"',
    'id="text-layer-current"',
    'id="catalog"',
    'id="project-focus"',
    'href="./catalog/catalog.json"',
    'href="./contracts/commonworld/project.schema.json"',
    'href="./method.html"',
    'href="./contracts/commonworld/current-state.contract.json"',
    'type="application/json"',
    'Keine API-Laufzeit, kein Schreibweg und keine eigenständige CLI.',
    '<script src="./assets/vendor/maplibre-gl.js" defer></script>',
    '<script type="module" src="./assets/commonworld-app.js"></script>',
    '<meta http-equiv="Content-Security-Policy"',
)

FORBIDDEN_HTML = (
    '<section class="intro"',
    '<section class="status"',
    'Die gemeinsame Welt wird sichtbar.',
    'Der erste interaktive Globus ist gebaut.',
    'proof hub',
    'fixture',
    'aether',
    'atlas shift',
    'game feel',
    'gamification',
    '<form',
    '/proofs/',
    '/api/',
    'unpkg.com',
    'cdn.jsdelivr.net',
    'cdnjs.cloudflare.com',
    'three.js',
    "'unsafe-inline'",
    "'unsafe-eval'",
)

REQUIRED_CSS = (
    '.topbar',
    '.globe-surface',
    '.globe-stage',
    '.globe-map',
    '.digital-sphere',
    '--sphere-x',
    '--sphere-y',
    '--sphere-size',
    '.sphere-edge-control',
    '.digital-breadcrumb',
    '.digital-current',
    '.layer-panel',
    '.layer-stack-visual',
    '.layer-stack-item',
    '.settings-panel',
    '.text-view',
    '.noscript-catalog',
    '.project-focus',
    '.globe-results',
    '.method-page',
    '.maplibregl-ctrl-group button',
    '.catalog-grid',
    '.catalog-card',
    ':focus-visible',
    '@media (max-width: 48rem)',
    '@media (prefers-reduced-motion: reduce)',
)


def validate_public_shell(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    html_path = root / 'index.html'
    css_path = root / 'index.css'
    method_path = root / 'method.html'
    bootstrap_path = root / 'assets/commonworld-bootstrap-catalog.mjs'
    if not html_path.is_file():
        return ['missing public index.html']
    if not css_path.is_file():
        return ['missing public index.css']
    if not method_path.is_file():
        return ['missing public method.html']
    if not bootstrap_path.is_file():
        return ['missing build-bound bootstrap catalog module']

    html = html_path.read_text(encoding='utf-8')
    css = css_path.read_text(encoding='utf-8')
    method = method_path.read_text(encoding='utf-8')
    bootstrap = bootstrap_path.read_text(encoding='utf-8')
    lowered = html.casefold()
    if 'id="catalog-bootstrap"' in html:
        errors.append('public shell must not embed catalog JSON in the DOM')
    if 'export const BOOTSTRAP_RECORDS = [' not in bootstrap:
        errors.append('build-bound bootstrap catalog module missing exported records')
    for token in REQUIRED_HTML:
        if token not in html:
            errors.append(f'public shell missing required token: {token}')
    for token in FORBIDDEN_HTML:
        if token.casefold() in lowered:
            errors.append(f'public shell contains obsolete or unsafe token: {token}')
    for token in REQUIRED_CSS:
        if token not in css:
            errors.append(f'public shell CSS missing required token: {token}')
    if html.count('id="settings-toggle"') != 1:
        errors.append('public shell must expose exactly one settings gear')
    globe_position = html.find('id="globe-surface"')
    text_position = html.find('id="text-view"')
    if globe_position < 0 or text_position < 0 or globe_position >= text_position:
        errors.append('globe surface must precede the alternate text surface')
    for token in (
        'Methode, Abdeckung und Datenschutz',
        'keine vollständige Weltstatistik',
        'keine Konten, eigene Telemetrie, Cookies oder schreibende API',
        'AGPL-3.0-only',
        'CC0-1.0',
        'ohne Gewährleistung',
        'https://github.com/heimgewebe/commonworld',
        './contracts/commonworld/current-state.contract.json',
    ):
        if token not in method:
            errors.append(f'public method surface missing required token: {token}')
    if "<script" in method.casefold():
        errors.append('public method surface must remain script-free')
    return errors


def main() -> int:
    errors = validate_public_shell(ROOT)
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print('commonworld globe-first public shell validation ok')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
