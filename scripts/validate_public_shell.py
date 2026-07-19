#!/usr/bin/env python3
"""Validate the public globe-first Commonworld shell."""

from __future__ import annotations

import re
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

    errors.extend(_validate_ipad_landscape_wiring(root, html))
    return errors


def _validate_ipad_landscape_wiring(root: Path, html: str) -> list[str]:
    errors: list[str] = []
    ipad_css_path = root / 'assets/ipad-layout.css'
    render_source_path = root / 'scripts/render_public_shell.py'
    if not ipad_css_path.is_file():
        return ['missing assets/ipad-layout.css']
    ipad_css = ipad_css_path.read_text(encoding='utf-8')
    render_source = render_source_path.read_text(encoding='utf-8') if render_source_path.is_file() else ''

    index_link = '<link rel="stylesheet" href="./index.css" />'
    ipad_link = '<link rel="stylesheet" href="./assets/ipad-layout.css" />'
    if index_link not in html or ipad_link not in html:
        errors.append('index.html must load index.css and assets/ipad-layout.css')
    elif html.index(index_link) >= html.index(ipad_link):
        errors.append('index.html must load assets/ipad-layout.css after index.css')
    if ipad_link not in render_source:
        errors.append('render_public_shell.py must emit the assets/ipad-layout.css stylesheet link')

    presence_match = re.search(
        r'<fieldset class="filter-presence-group"><legend>[^<]*</legend>'
        r'<div class="filter-presence-options">(.*?)</div></fieldset>',
        html,
    )
    if presence_match is None:
        errors.append('presence fieldset must wrap its options in .filter-presence-options')
    else:
        wrapped = presence_match.group(1)
        if 'id="filter-presence-geographic"' not in wrapped or 'id="filter-presence-digital"' not in wrapped:
            errors.append('presence options wrapper must contain both presence checkboxes')
    if 'class="filter-presence-options"' not in render_source:
        errors.append('render_public_shell.py must emit the .filter-presence-options wrapper')

    if '.intent-filter-grid > .filter-presence-group' not in ipad_css or '.filter-presence-options' not in ipad_css:
        errors.append('assets/ipad-layout.css must style the presence group and its options')
    options_block_match = re.search(r'\.filter-presence-options > label\s*\{([^}]*)\}', ipad_css)
    if options_block_match is None or not re.search(r'min-height:\s*var\(--minimum-touch-target', options_block_match.group(1)):
        errors.append('assets/ipad-layout.css presence options must define a compact, touch-safe label style')

    breakpoint_match = re.search(
        r'@media([^{]*)\{(.*)\}\s*$',
        ipad_css,
        re.DOTALL,
    )
    if breakpoint_match is None:
        errors.append('assets/ipad-layout.css must define exactly one trailing breakpoint')
        return errors
        
    media_query = breakpoint_match.group(1)
    if 'orientation: landscape' not in media_query or 'min-width: 48rem' not in media_query or 'max-width: 90rem' not in media_query or 'max-height: 65rem' not in media_query:
        errors.append('assets/ipad-layout.css media query must explicitly cover up to 1366x1024 through max-width:90rem and max-height:65rem, excluding very large viewports')
    media_block = breakpoint_match.group(2)

    discovery_match = re.search(r'\.layer-discovery\s*\{([^}]*)\}', media_block)
    if discovery_match is None:
        errors.append('tablet landscape breakpoint must override .layer-discovery geometry')
    else:
        block = discovery_match.group(1)
        if 'left: 50%' not in block or 'translateX(-50%)' not in block:
            errors.append('tablet landscape breakpoint must center .layer-discovery horizontally')
        if 'right: max' in block:
            errors.append('tablet landscape breakpoint must not reintroduce right-anchored .layer-discovery geometry')

    if '.layer-track-deck' not in media_block:
        errors.append('tablet landscape breakpoint must reduce .layer-track-deck padding')
    focused_lane_match = re.search(
        r'\.globe-stage\[data-focused-path\] \.digital-lane\.is-focused\s*\{([^}]*)\}',
        media_block,
    )
    if focused_lane_match is None:
        errors.append('tablet landscape breakpoint must reduce the focused lane min-height')
    else:
        block = focused_lane_match.group(1)
        if 'min-height' not in block:
            errors.append('tablet landscape breakpoint focused lane rule must define min-height')
        if 'min(44vh, 24rem)' in block:
            errors.append('tablet landscape breakpoint must not reuse the oversized default focused lane height')

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
