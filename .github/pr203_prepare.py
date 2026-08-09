#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

# Let Commonworld's existing global reduced-motion rule collapse the CSS orbit to one
# effectively instantaneous iteration. Do not mutate the keyframe effect or custom
# direction while reduced motion is active.
old_reduced = "    --ring-orbit-direction: 0;\n"
if old_reduced not in source:
    raise SystemExit('reduced-motion orbit insertion point missing')
source = source.replace(old_reduced, "    /* global reduced-motion reset makes the orbit static */\n", 1)

# Expose enough native CSSAnimation state in failures to distinguish compositor
# staleness from a finished/idle timeline.
state_anchor = """      labelAnimationName: labelStyle?.animationName ?? 'none',
      labelAnimationPlayState: labelStyle?.animationPlayState ?? 'running',
      labelOrbitDirection: labelStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
      ringAnimationName: ringStyle?.animationName ?? 'none',
      ringAnimationPlayState: ringStyle?.animationPlayState ?? 'running',
      ringOrbitDirection: ringStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
"""
state_replacement = """      labelAnimationName: labelStyle?.animationName ?? 'none',
      labelAnimationPlayState: labelStyle?.animationPlayState ?? 'running',
      labelAnimationDuration: labelStyle?.animationDuration ?? '',
      labelAnimationIterations: labelStyle?.animationIterationCount ?? '',
      labelOrbitDirection: labelStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
      labelAnimations: label ? label.getAnimations().map((animation) => ({ name: animation.animationName ?? animation.constructor.name, currentTime: animation.currentTime, playState: animation.playState, pending: animation.pending, playbackRate: animation.playbackRate })) : [],
      ringAnimationName: ringStyle?.animationName ?? 'none',
      ringAnimationPlayState: ringStyle?.animationPlayState ?? 'running',
      ringAnimationDuration: ringStyle?.animationDuration ?? '',
      ringAnimationIterations: ringStyle?.animationIterationCount ?? '',
      ringOrbitDirection: ringStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
      ringAnimations: ring ? ring.getAnimations().map((animation) => ({ name: animation.animationName ?? animation.constructor.name, currentTime: animation.currentTime, playState: animation.playState, pending: animation.pending, playbackRate: animation.playbackRate })) : [],
"""
if state_anchor not in source:
    raise SystemExit('touch ring state instrumentation point missing')
source = source.replace(state_anchor, state_replacement, 1)

old_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, labelOrbitDirection, ringAnimationName, ringOrbitDirection }) => labelAnimationName === 'sphere-ring-orbit' && labelOrbitDirection === '0' && ringAnimationName === 'sphere-ring-orbit' && ringOrbitDirection === '0').length >= 2, scenarioId + ': live reduced-motion change did not zero wide touch ring motion ' + JSON.stringify(reducedTouchAfter));"""
new_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, labelAnimationDuration, labelAnimationIterations, ringAnimationName, ringAnimationDuration, ringAnimationIterations }) => labelAnimationName === 'sphere-ring-orbit' && Number.parseFloat(labelAnimationDuration) <= 0.001 && labelAnimationIterations === '1' && ringAnimationName === 'sphere-ring-orbit' && Number.parseFloat(ringAnimationDuration) <= 0.001 && ringAnimationIterations === '1').length >= 2, scenarioId + ': live reduced-motion change did not apply the global static orbit policy ' + JSON.stringify(reducedTouchAfter));"""
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
        orbitNodes.forEach((node) => {
          node.getAnimations().forEach((animation) => {
            if (animation.animationName !== 'sphere-ring-orbit') return;
            animation.cancel();
            animation.play();
          });
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
