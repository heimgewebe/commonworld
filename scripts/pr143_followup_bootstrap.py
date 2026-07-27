#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name('pr143_followup.py')
text = path.read_text(encoding='utf-8')
needle = """    app = replace_once(app, '  runtime.layerPreviewProject = null;\\n  renderLayerProjectDetail();', '  renderLayerProjectDetail();', 'remove obsolete close state')
    for forbidden in ('selectDigitalProject', 'runtime.layerPreviewProject', 'runtime.lastLayerProjectStatus', 'usesInlineLayerProjectDetail', 'reconcileProjectSelection'):
"""
replacement = """    app = replace_once(app, '  runtime.layerPreviewProject = null;\\n  renderLayerProjectDetail();', '  renderLayerProjectDetail();', 'remove obsolete close state')
    app = re.sub(r'^\\s*runtime\\.layerPreviewProject.*\\n', '', app, flags=re.MULTILINE)
    app = re.sub(r'^\\s*runtime\\.lastLayerProjectStatus.*\\n', '', app, flags=re.MULTILINE)
    app = re.sub(r'usesInlineLayerProjectDetail\\([^)]*\\)', 'false', app)
    app = re.sub(r'^\\s*reconcileProjectSelection\\(\\);\\n', '', app, flags=re.MULTILINE)
    for forbidden in ('selectDigitalProject', 'runtime.layerPreviewProject', 'runtime.lastLayerProjectStatus', 'usesInlineLayerProjectDetail', 'reconcileProjectSelection'):
"""
if text.count(needle) != 1:
    raise SystemExit(f'follow-up bootstrap anchor count: {text.count(needle)}')
text = text.replace(needle, replacement, 1)

start = text.index('def patch_css() -> None:')
end = text.index('\ndef patch_i18n() -> None:', start)
patch_css = '''def patch_css() -> None:
    path = 'index.css'
    css = read(path)
    start_marker = '.globe-stage[data-focused-path] .layer-panel .layer-projects:not([hidden]) {'
    end_marker = '.digital-lane-content .identity-show-more {'
    start = css.find(start_marker)
    end = css.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit('orphan detail stylesheet boundary missing')
    mobile_focus = """@media (max-width: 48rem) {
  .focus-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

"""
    css = css[:start] + mobile_focus + css[end:]
    dead_rule = re.compile(
        r'(?ms)^[ \\t]*(?:'
        r'\\.layer-project-detail(?:-title|-summary)?|'
        r'\\.project-detail-header|'
        r'\\.project-detail-grid|'
        r'\\.layer-panel \\.layer-projects\\[hidden\\]|'
        r'\\.globe-stage\\[data-focused-path\\] \\.layer-panel \\.layer-projects:not\\(\\[hidden\\]\\)'
        r')\\s*\\{[^{}]*\\}\\n?'
    )
    css = dead_rule.sub('', css)
    css = css.replace(""".layer-panel .layer-projects[hidden] {
  display: none;
}

""", '')
    css = re.sub(r'\\n{3,}', '\\n\\n', css)
    for forbidden in ('.layer-project-detail', '.project-detail-', '.layer-panel .layer-projects'):
        if forbidden in css:
            raise SystemExit(f'CSS still contains orphaned detail selector: {forbidden}')
    for required in ('@media (forced-colors: active)', '@media (prefers-reduced-motion: reduce)', '@media (prefers-contrast: more)', '.presence-option'):
        if required not in css:
            raise SystemExit(f'CSS cleanup removed required contract: {required}')
    write(path, css)

'''
text = text[:start] + patch_css + text[end + 1:]
path.write_text(text, encoding='utf-8')
