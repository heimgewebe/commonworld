#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

old_reduced = "    --ring-orbit-direction: 0;\n"
new_reduced = (
    "    animation: none;\n"
    "    transform: rotate(var(--ring-orbit-start-angle, 0deg));\n"
)
if old_reduced not in source:
    raise SystemExit('reduced-motion orbit insertion point missing')
source = source.replace(old_reduced, new_reduced, 1)

old_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, labelOrbitDirection, ringAnimationName, ringOrbitDirection }) => labelAnimationName === 'sphere-ring-orbit' && labelOrbitDirection === '0' && ringAnimationName === 'sphere-ring-orbit' && ringOrbitDirection === '0').length >= 2, scenarioId + ': live reduced-motion change did not zero wide touch ring motion ' + JSON.stringify(reducedTouchAfter));"""
new_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, ringAnimationName }) => labelAnimationName === 'none' && ringAnimationName === 'none').length >= 2, scenarioId + ': live reduced-motion change did not stop wide touch CSS orbits ' + JSON.stringify(reducedTouchAfter));"""
if old_assert not in source:
    raise SystemExit('reduced-motion smoke assertion missing')
source = source.replace(old_assert, new_assert, 1)

anchor = '''    css.write_text(s.replace(old, new, 1), encoding="utf-8")

    smoke = ROOT / "scripts/smoke_public_browser.mjs"
'''
replacement = '''    css.write_text(s.replace(old, new, 1), encoding="utf-8")

    app = ROOT / "assets/commonworld-app.js"
    app_source = app.read_text(encoding="utf-8")
    boot_marker = "async function boot() {\\n"
    recovery = """function installReducedMotionRingRecovery() {
  const restartCoarseTouchOrbits = (event) => {
    if (event.matches) return;
    if (!window.matchMedia('(hover: none) and (pointer: coarse)').matches) return;
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (reducedMotion.matches) return;
        const orbitNodes = [...elements.sphereRings.querySelectorAll('.sphere-ring-plane > use, .sphere-ring-plane > .sphere-ring-text')];
        orbitNodes.forEach((node) => node.style.setProperty('animation', 'none', 'important'));
        elements.sphereRings.getBoundingClientRect();
        window.requestAnimationFrame(() => {
          if (reducedMotion.matches) return;
          orbitNodes.forEach((node) => node.style.removeProperty('animation'));
        });
      });
    });
  };
  if (typeof reducedMotion.addEventListener === 'function') {
    reducedMotion.addEventListener('change', restartCoarseTouchOrbits);
  } else {
    reducedMotion.addListener?.(restartCoarseTouchOrbits);
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
