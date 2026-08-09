#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

# The existing global reduced-motion policy already collapses all animations to one
# effectively instantaneous iteration. Do not add a competing coarse-touch animation
# mechanism; verify Reduced Motion on a fresh context instead of mutating it live.
old_reduced = "    --ring-orbit-direction: 0;\n"
if old_reduced not in source:
    raise SystemExit('reduced-motion orbit insertion point missing')
source = source.replace(old_reduced, "    /* reduced motion is governed by the global animation reset */\n", 1)

live_start = "  await run.page.emulateMedia({ reducedMotion: 'reduce' });\n"
compact_start = "  const compactDesktopRun = await newPage({\n"
start = source.index(live_start)
end = source.index(compact_start, start)
fresh_reduced = '''  const reducedTouchRun = await newPage({
    mobile: true,
    touch: true,
    viewportOverride: { width: 844, height: 390 },
    reducedMotion: 'reduce',
  });
  await reducedTouchRun.page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await reducedTouchRun.page.waitForSelector('html.runtime-ready');
  await reducedTouchRun.page.waitForFunction(() => document.querySelectorAll('.sphere-ring-plane .sphere-ring-text').length > 0);
  const reducedTouchState = () => reducedTouchRun.page.evaluate(() => [...document.querySelectorAll('.sphere-ring-plane')].map((plane) => {
    const label = plane.querySelector('.sphere-ring-text');
    const ring = plane.querySelector('use');
    const labelStyle = label ? getComputedStyle(label) : null;
    const ringStyle = ring ? getComputedStyle(ring) : null;
    const labelRect = label?.getBoundingClientRect();
    const ringRect = ring?.getBoundingClientRect();
    return {
      coarse: window.matchMedia('(hover: none) and (pointer: coarse)').matches,
      reduced: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      labelAnimationName: labelStyle?.animationName ?? 'none',
      labelAnimationDuration: labelStyle?.animationDuration ?? '',
      labelAnimationIterations: labelStyle?.animationIterationCount ?? '',
      ringAnimationName: ringStyle?.animationName ?? 'none',
      ringAnimationDuration: ringStyle?.animationDuration ?? '',
      ringAnimationIterations: ringStyle?.animationIterationCount ?? '',
      labelBox: labelRect ? [labelRect.x, labelRect.y, labelRect.width, labelRect.height] : null,
      ringBox: ringRect ? [ringRect.x, ringRect.y, ringRect.width, ringRect.height] : null,
    };
  }));
  const reducedTouchBefore = await reducedTouchState();
  await reducedTouchRun.page.waitForTimeout(350);
  const reducedTouchAfter = await reducedTouchState();
  const visibleBoxesMoved = (before, after, key, threshold = 1e-3) => after.filter((entry, index) => {
    const previous = before[index];
    if (!entry[key] || !previous?.[key]) return false;
    return entry[key].some((value, boxIndex) => Math.abs(value - previous[key][boxIndex]) > threshold);
  });
  assert(reducedTouchAfter.length >= 2 && reducedTouchAfter.every(({ coarse, reduced }) => coarse && reduced), scenarioId + ': reduced-motion touch context did not exercise the intended media path ' + JSON.stringify(reducedTouchAfter));
  assert(reducedTouchAfter.filter(({ labelAnimationDuration, labelAnimationIterations, ringAnimationDuration, ringAnimationIterations }) => Number.parseFloat(labelAnimationDuration) <= 0.001 && labelAnimationIterations === '1' && Number.parseFloat(ringAnimationDuration) <= 0.001 && ringAnimationIterations === '1').length >= 2, scenarioId + ': reduced-motion touch context did not inherit the global static animation policy ' + JSON.stringify(reducedTouchAfter));
  assert(visibleBoxesMoved(reducedTouchBefore, reducedTouchAfter, 'labelBox').length === 0, scenarioId + ': reduced-motion touch labels moved ' + JSON.stringify({ before: reducedTouchBefore, after: reducedTouchAfter }));
  assert(visibleBoxesMoved(reducedTouchBefore, reducedTouchAfter, 'ringBox').length === 0, scenarioId + ': reduced-motion touch ring strokes moved ' + JSON.stringify({ before: reducedTouchBefore, after: reducedTouchAfter }));
  await reducedTouchRun.context.close();

'''
source = source[:start] + fresh_reduced + source[end:]

cleanup_anchor = '''    shutil.rmtree(TMP, ignore_errors=True)
    run("git", "config", "user.name", "Commonworld Repair Bot")
'''
cleanup_replacement = '''    shutil.rmtree(TMP, ignore_errors=True)
    for helper in (
        ROOT / ".github/pr203_prepare.py",
        ROOT / ".github/pr203_repair.py",
        ROOT / ".github/pr203_media_probe.mjs",
        ROOT / ".github/workflows/pr203-repair.yml",
        ROOT / ".github/workflows/pr203-media-probe.yml",
        ROOT / "pr203-repair.log",
    ):
        helper.unlink(missing_ok=True)
    run("git", "config", "user.name", "Commonworld Repair Bot")
'''
if cleanup_anchor not in source:
    raise SystemExit('final cleanup insertion point missing')
source = source.replace(cleanup_anchor, cleanup_replacement, 1)

path.write_text(source, encoding='utf-8')
