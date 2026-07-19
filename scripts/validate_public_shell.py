#!/usr/bin/env python3
"""Validate the public globe-first Commonworld shell."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    from html.parser import HTMLParser

    class LinkParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.links: list[str] = []
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == 'link':
                attr_dict = dict(attrs)
                if attr_dict.get('rel') == 'stylesheet' and attr_dict.get('href'):
                    self.links.append(attr_dict['href'])

    class PresenceParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.in_fieldset = False
            self.fieldset_count = 0
            self.options_count = 0
            self.in_options = False
            self.has_geographic = False
            self.has_digital = False
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_dict = dict(attrs)
            classes = attr_dict.get('class', '').split()
            if tag == 'fieldset' and 'filter-presence-group' in classes:
                self.in_fieldset = True
                self.fieldset_count += 1
            elif tag == 'div' and 'filter-presence-options' in classes and self.in_fieldset:
                self.in_options = True
                self.options_count += 1
            elif tag == 'input' and attr_dict.get('type') == 'checkbox' and self.in_options:
                if attr_dict.get('id') == 'filter-presence-geographic':
                    self.has_geographic = True
                if attr_dict.get('id') == 'filter-presence-digital':
                    self.has_digital = True
        def handle_endtag(self, tag: str) -> None:
            if tag == 'fieldset':
                self.in_fieldset = False
            elif tag == 'div' and self.in_options:
                self.in_options = False

    def find_css_block(css: str, prefix: str) -> tuple[str, str] | None:
        in_string = None
        in_comment = False
        i = 0
        length = len(css)
        while i < length:
            if in_comment:
                if css[i:i+2] == '*/':
                    in_comment = False
                    i += 2
                else:
                    i += 1
                continue
            if in_string:
                if css[i] == '\\':
                    i += 2
                elif css[i] == in_string:
                    in_string = None
                    i += 1
                else:
                    i += 1
                continue
            if css[i:i+2] == '/*':
                in_comment = True
                i += 2
                continue
            if css[i] in ("'", '"'):
                in_string = css[i]
                i += 1
                continue
            if css[i:].startswith(prefix):
                start_idx = i
                brace_idx = -1
                while i < length:
                    if in_comment:
                        if css[i:i+2] == '*/':
                            in_comment = False
                            i += 2
                        else:
                            i += 1
                        continue
                    if in_string:
                        if css[i] == '\\':
                            i += 2
                        elif css[i] == in_string:
                            in_string = None
                            i += 1
                        else:
                            i += 1
                        continue
                    if css[i:i+2] == '/*':
                        in_comment = True
                        i += 2
                        continue
                    if css[i] in ("'", '"'):
                        in_string = css[i]
                        i += 1
                        continue
                    if css[i] == '{':
                        brace_idx = i
                        break
                    i += 1
                if brace_idx == -1:
                    return None
                selector_str = css[start_idx:brace_idx].strip()
                block_start = brace_idx + 1
                brace_count = 1
                i = block_start
                while i < length:
                    if in_comment:
                        if css[i:i+2] == '*/':
                            in_comment = False
                            i += 2
                        else:
                            i += 1
                        continue
                    if in_string:
                        if css[i] == '\\':
                            i += 2
                        elif css[i] == in_string:
                            in_string = None
                            i += 1
                        else:
                            i += 1
                        continue
                    if css[i:i+2] == '/*':
                        in_comment = True
                        i += 2
                        continue
                    if css[i] in ("'", '"'):
                        in_string = css[i]
                        i += 1
                        continue
                    if css[i] == '{':
                        brace_count += 1
                    elif css[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            return (selector_str, css[block_start:i])
                    i += 1
                return None
            i += 1
        return None

    index_link = './index.css'
    ipad_link = './assets/ipad-layout.css'
    
    link_parser = LinkParser()
    link_parser.feed(html)
    
    if index_link not in link_parser.links or ipad_link not in link_parser.links:
        errors.append('index.html must load index.css and assets/ipad-layout.css')
    elif link_parser.links.index(index_link) >= link_parser.links.index(ipad_link):
        errors.append('index.html must load assets/ipad-layout.css after index.css')
        
    if '<link rel="stylesheet" href="./assets/ipad-layout.css" />' not in render_source:
        errors.append('render_public_shell.py must emit the assets/ipad-layout.css stylesheet link')

    presence_parser = PresenceParser()
    presence_parser.feed(html)
    
    if presence_parser.fieldset_count == 0 or presence_parser.options_count == 0:
        errors.append('presence fieldset must wrap its options in .filter-presence-options')
    else:
        if not presence_parser.has_geographic or not presence_parser.has_digital:
            errors.append('presence options wrapper must contain both presence checkboxes')
            
    if 'class="filter-presence-options"' not in render_source:
        errors.append('render_public_shell.py must emit the .filter-presence-options wrapper')

    if '.intent-filter-grid > .filter-presence-group' not in ipad_css or '.filter-presence-options' not in ipad_css:
        errors.append('assets/ipad-layout.css must style the presence group and its options')
        
    options_block_match = find_css_block(ipad_css, '.filter-presence-options > label')
    if options_block_match is None or not re.search(r'min-height:\s*var\(--minimum-touch-target', options_block_match[1]):
        errors.append('assets/ipad-layout.css presence options must define a compact, touch-safe label style')

    breakpoint_match = find_css_block(ipad_css, '@media')
    if breakpoint_match is None:
        errors.append('assets/ipad-layout.css must define exactly one trailing breakpoint')
        return errors
        
    media_query = breakpoint_match[0]
    if 'orientation: landscape' not in media_query or 'min-width: 48rem' not in media_query or 'max-width: 90rem' not in media_query or 'max-height: 65rem' not in media_query:
        errors.append('assets/ipad-layout.css media query must explicitly cover up to 1366x1024 through max-width:90rem and max-height:65rem, excluding very large viewports')
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
