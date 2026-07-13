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
    'data-presentation-choice="globe"',
    'data-presentation-choice="text"',
    'id="globe-surface"',
    'class="globe-stage"',
    'class="globe-map"',
    'class="digital-sphere"',
    'id="sphere-edge-control"',
    'id="layer-panel"',
    'id="layer-stack-visual"',
    'id="text-view"',
    'id="catalog"',
    'id="project-focus"',
    'href="./catalog/catalog.json"',
    'href="./contracts/commonworld/project.schema.json"',
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
    '.layer-panel',
    '.layer-stack-visual',
    '.layer-stack-item',
    '.settings-panel',
    '.text-view',
    '.noscript-catalog',
    '.project-focus',
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
    if not html_path.is_file():
        return ['missing public index.html']
    if not css_path.is_file():
        return ['missing public index.css']

    html = html_path.read_text(encoding='utf-8')
    css = css_path.read_text(encoding='utf-8')
    lowered = html.casefold()
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
