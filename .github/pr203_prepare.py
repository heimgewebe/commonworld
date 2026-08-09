#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

old = "    --ring-orbit-direction: 0;\n"
new = (
    "    animation-duration: var(--ring-orbit-duration, 240s) !important;\n"
    "    animation-iteration-count: infinite !important;\n"
    "    --ring-orbit-direction: 0;\n"
)
if old not in source:
    raise SystemExit('reduced-motion orbit insertion point missing')
source = source.replace(old, new, 1)

anchor = '''    css.write_text(s.replace(old, new, 1), encoding="utf-8")

    smoke = ROOT / "scripts/smoke_public_browser.mjs"
'''
replacement = '''    css.write_text(s.replace(old, new, 1), encoding="utf-8")

    app = ROOT / "assets/commonworld-app.js"
    app_source = app.read_text(encoding="utf-8")
    boot_marker = "async function boot() {\\n"
    recovery = """function installReducedMotionRingRecovery() {
  const restartCoarseTouchRings = (event) => {
    if (event.matches) return;
    if (!window.matchMedia('(hover: none) and (pointer: coarse)').matches) return;
    renderSphereRibbons(runtime.records);
  };
  if (typeof reducedMotion.addEventListener === 'function') {
    reducedMotion.addEventListener('change', restartCoarseTouchRings);
  } else {
    reducedMotion.addListener?.(restartCoarseTouchRings);
  }
}

"""
    if boot_marker not in app_source:
        raise RuntimeError("boot marker for reduced-motion ring recovery not found")
    app_source = app_source.replace(boot_marker, recovery + boot_marker, 1)
    wire_marker = "    wireControls();\\n"
    if wire_marker not in app_source:
        raise RuntimeError("wireControls marker for reduced-motion ring recovery not found")
    app_source = app_source.replace(wire_marker, wire_marker + "    installReducedMotionRingRecovery();\\n", 1)
    app.write_text(app_source, encoding="utf-8")

    smoke = ROOT / "scripts/smoke_public_browser.mjs"
'''
if anchor not in source:
    raise SystemExit('app recovery insertion point missing')
source = source.replace(anchor, replacement, 1)
path.write_text(source, encoding='utf-8')
