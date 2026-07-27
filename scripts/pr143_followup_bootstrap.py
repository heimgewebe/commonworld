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
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')
