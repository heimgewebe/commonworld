#!/usr/bin/env python3
"""Validate the public globe-first Commonworld shell."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

try:
    from scripts.static_surface_parser import (
        find_css_block,
        find_media_block,
        find_media_blocks,
        parse_presence_group,
        parse_stylesheet_links,
    )
except ModuleNotFoundError as exc:  # direct script execution puts the scripts dir on sys.path
    # Only fall back when the 'scripts' package itself is unreachable; a missing
    # dependency inside static_surface_parser must stay visible.
    if exc.name not in {"scripts", "scripts.static_surface_parser"}:
        raise
    from static_surface_parser import (
        find_css_block,
        find_media_block,
        find_media_blocks,
        parse_presence_group,
        parse_stylesheet_links,
    )

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_HTML = (
    '<html lang="en">',
    '<body data-presentation="globe">',
    '<title>commonworld — Discover Commons</title>',
    'class="topbar"',
    'id="commons-search"',
    'id="filter-commons-type"',
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
    'id="layer-project-status"',
    'id="focus-selection-status"',
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
    'No API runtime, no write path and no standalone CLI.',
    '<script src="./assets/vendor/maplibre-gl.js" defer></script>',
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
    german_html_path = root / 'de.html'
    german_method_path = root / 'method.de.html'
    bootstrap_path = root / 'assets/commonworld-bootstrap-catalog.mjs'
    if not html_path.is_file():
        return ['missing public index.html']
    if not css_path.is_file():
        return ['missing public index.css']
    if not method_path.is_file():
        return ['missing public method.html']
    require_locale_alternates = root.resolve() == ROOT.resolve()
    if require_locale_alternates and not german_html_path.is_file():
        return ['missing public de.html']
    if require_locale_alternates and not german_method_path.is_file():
        return ['missing public method.de.html']
    if not bootstrap_path.is_file():
        return ['missing build-bound bootstrap catalog module']

    html = html_path.read_text(encoding='utf-8')
    css = css_path.read_text(encoding='utf-8')
    method = method_path.read_text(encoding='utf-8')
    german_html = german_html_path.read_text(encoding='utf-8') if german_html_path.is_file() else ''
    german_method = german_method_path.read_text(encoding='utf-8') if german_method_path.is_file() else ''
    bootstrap = bootstrap_path.read_text(encoding='utf-8')
    lowered = html.casefold()
    if 'id="catalog-bootstrap"' in html:
        errors.append('public shell must not embed catalog JSON in the DOM')
    if 'export const BOOTSTRAP_RECORDS = [' not in bootstrap:
        errors.append('build-bound bootstrap catalog module missing exported records')
    for token in REQUIRED_HTML:
        if token not in html:
            errors.append(f'public shell missing required token: {token}')
    app_version = hashlib.sha256((root / 'assets/commonworld-app.js').read_bytes()).hexdigest()[:12]
    css_version = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    if f'<script type="module" src="./assets/commonworld-app.js?v={app_version}"></script>' not in html:
        errors.append('public shell must load commonworld-app.js with its deterministic content hash')
    expected_css_link = f'./index.css?v={css_version}'
    if expected_css_link not in parse_stylesheet_links(html):
        errors.append('public shell must load index.css with its deterministic content hash')
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
        'Method, coverage and privacy',
        'not a complete global statistic',
        'no accounts, first-party telemetry, cookies or write API',
        'AGPL-3.0-only',
        'CC0-1.0',
        'without warranty',
        'https://github.com/heimgewebe/commonworld',
        './contracts/commonworld/current-state.contract.json',
    ):
        if token not in method:
            errors.append(f'public method surface missing required token: {token}')
    if require_locale_alternates:
        for token in ('<html lang="de">', 'Commons entdecken', 'Methode, Abdeckung und Datenschutz'):
            if token not in german_html and token not in german_method:
                errors.append(f'German alternative surfaces missing required token: {token}')
        if 'href="./de.html"' not in html or 'href="./"' not in german_html:
            errors.append('public locale switch must connect English and German index surfaces')
    if "<script" in method.casefold():
        errors.append('public method surface must remain script-free')

    errors.extend(_validate_accessibility_modes(css))
    errors.extend(_validate_ipad_landscape_wiring(root, html))
    return errors


def _validate_accessibility_modes(css: str) -> list[str]:
    errors: list[str] = []
    forced = find_media_block(css, ('forced-colors: active',))
    if forced is None:
        errors.append('public shell CSS must define a forced-colors: active contract')
    else:
        block = forced[1]
        for token in ('CanvasText', 'ButtonText', 'Highlight', ':focus-visible', '[aria-pressed=\"true\"]', 'input:checked'):
            if token not in block:
                errors.append(f'public forced-colors contract missing token: {token}')

    reduced_motion = find_media_blocks(css, ('prefers-reduced-motion: reduce',))
    if not reduced_motion:
        errors.append('public shell CSS must define a prefers-reduced-motion: reduce contract')
    elif not any('transition: none !important' in block for _, block in reduced_motion):
        errors.append('public reduced-motion contract must disable transitions')

    contrast = find_media_block(css, ('prefers-contrast: more',))
    if contrast is None:
        errors.append('public shell CSS must define a prefers-contrast: more contract')
    else:
        block = contrast[1]
        for token in (':focus-visible', 'outline: 4px', 'border-width: 2px', '[aria-checked=\"true\"]'):
            if token not in block:
                errors.append(f'public increased-contrast contract missing token: {token}')
    return errors


def _validate_ipad_landscape_wiring(root: Path, html: str) -> list[str]:
    errors: list[str] = []
    ipad_css_path = root / 'assets/ipad-layout.css'
    render_source_path = root / 'scripts/render_public_shell.py'
    if not ipad_css_path.is_file():
        return ['missing assets/ipad-layout.css']
    ipad_css = ipad_css_path.read_text(encoding='utf-8')
    index_css = (root / 'index.css').read_text(encoding='utf-8')
    render_source = render_source_path.read_text(encoding='utf-8') if render_source_path.is_file() else ''
    if 'class="filter-commons-type"' not in render_source or 'data-intent-filter="commons_type"' not in render_source:
        errors.append('render_public_shell.py must emit the Commons-Art filter with its compact layout hook')
    if 'class="filter-commons-type"' not in html or '.filter-commons-type' not in index_css:
        errors.append('public shell and index.css must preserve the Commons-Art filter layout hook')

    index_links = [link for link in parse_stylesheet_links(html) if link.startswith('./index.css?v=')]
    ipad_version = hashlib.sha256(ipad_css_path.read_bytes()).hexdigest()[:12]
    ipad_link = f'./assets/ipad-layout.css?v={ipad_version}'

    links = parse_stylesheet_links(html)
    if len(index_links) != 1 or ipad_link not in links:
        errors.append('index.html must load content-versioned index.css and assets/ipad-layout.css')
    elif links.index(index_links[0]) >= links.index(ipad_link):
        errors.append('index.html must load assets/ipad-layout.css after index.css')

    render_token = "href=\"./assets/ipad-layout.css?v={asset_version('assets/ipad-layout.css', root)}\""
    if render_token not in render_source:
        errors.append('render_public_shell.py must emit the content-versioned assets/ipad-layout.css stylesheet link')

    presence = parse_presence_group(html)
    if presence.fieldset_count != 1:
        errors.append('index.html must define exactly one presence fieldset')
    if presence.options_wrapper_count != 1:
        errors.append('presence fieldset must wrap its options in exactly one .filter-presence-options')
    if not presence.has_legend:
        errors.append('presence fieldset must expose a legend')
    if not presence.has_both_checkboxes:
        errors.append('presence options wrapper must contain both presence checkboxes')

    render_presence = parse_presence_group(render_source)
    if render_presence.options_wrapper_count != 1 or not render_presence.has_both_checkboxes:
        errors.append('render_public_shell.py must emit the .filter-presence-options wrapper with both presence checkboxes')

    if '.filter-group-controls > .filter-presence-group' not in index_css or '.filter-presence-options' not in index_css:
        errors.append('index.css must own the shared presence group and option styles')

    options_block_match = find_css_block(index_css, '.filter-presence-options > label')
    if options_block_match is None or not re.search(r'min-height:\s*var\(--minimum-touch-target', options_block_match[1]):
        errors.append('index.css presence options must define a compact, touch-safe label style')
    if '.filter-group-controls > .filter-presence-group > .filter-presence-options > label' in ipad_css:
        errors.append('assets/ipad-layout.css must not duplicate the shared presence option component style')

    target_media_tokens = (
        'orientation: landscape',
        'min-width: 48rem',
        'max-width: 90rem',
        'max-height: 65rem',
    )
    breakpoint_match = find_media_block(ipad_css, target_media_tokens)
    if breakpoint_match is None:
        errors.append('assets/ipad-layout.css must define the tablet landscape breakpoint media query (orientation: landscape, min-width: 48rem, max-width: 90rem, max-height: 65rem) covering up to 1366x1024 while excluding very large viewports')
        return errors
    media_block = breakpoint_match[1]

    discovery_match = find_css_block(media_block, '.layer-discovery')
    if discovery_match is None:
        errors.append('tablet landscape breakpoint must override .layer-discovery geometry')
    else:
        block = discovery_match[1]
        if 'left: 50%' not in block or 'translateX(-50%)' not in block:
            errors.append('tablet landscape breakpoint must center .layer-discovery horizontally')
        if 'right: max' in block:
            errors.append('tablet landscape breakpoint must not reintroduce right-anchored .layer-discovery geometry')

    if '.layer-track-deck' not in media_block:
        errors.append('tablet landscape breakpoint must reduce .layer-track-deck padding')
        
    focused_lane_match = find_css_block(media_block, '.globe-stage[data-focused-path] .digital-lane.is-focused')
    if focused_lane_match is None:
        errors.append('tablet landscape breakpoint must reduce the focused lane min-height')
    else:
        block = focused_lane_match[1]
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
