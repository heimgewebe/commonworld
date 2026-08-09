#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

header = "    new = '''@media (hover: none) and (pointer: coarse) {\n"
header_replacement = """    new = '''@keyframes sphere-ring-orbit-reduced {
  from, to { transform: rotate(var(--ring-orbit-start-angle, 0deg)); }
}

@media (hover: none) and (pointer: coarse) {
"""
if header not in source:
    raise SystemExit('coarse touch CSS replacement header missing')
source = source.replace(header, header_replacement, 1)

old_reduced = "    --ring-orbit-direction: 0;\n"
new_reduced = (
    "    animation-name: sphere-ring-orbit-reduced !important;\n"
    "    animation-duration: var(--ring-orbit-duration, 240s) !important;\n"
    "    animation-iteration-count: infinite !important;\n"
)
if old_reduced not in source:
    raise SystemExit('reduced-motion orbit insertion point missing')
source = source.replace(old_reduced, new_reduced, 1)

old_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, labelOrbitDirection, ringAnimationName, ringOrbitDirection }) => labelAnimationName === 'sphere-ring-orbit' && labelOrbitDirection === '0' && ringAnimationName === 'sphere-ring-orbit' && ringOrbitDirection === '0').length >= 2, scenarioId + ': live reduced-motion change did not zero wide touch ring motion ' + JSON.stringify(reducedTouchAfter));"""
new_assert = """  assert(reducedTouchAfter.filter(({ labelAnimationName, ringAnimationName }) => labelAnimationName === 'sphere-ring-orbit-reduced' && ringAnimationName === 'sphere-ring-orbit-reduced').length >= 2, scenarioId + ': live reduced-motion change did not switch wide touch rings to the static CSS orbit ' + JSON.stringify(reducedTouchAfter));"""
if old_assert not in source:
    raise SystemExit('reduced-motion smoke assertion missing')
source = source.replace(old_assert, new_assert, 1)

path.write_text(source, encoding='utf-8')
