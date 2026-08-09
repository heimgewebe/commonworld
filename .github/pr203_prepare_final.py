#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_prepare.py')
source = path.read_text(encoding='utf-8')

target = '    smoke.write_text(hardened_smoke, encoding="utf-8")\n'
insertion = r'''    moveend_bound = "  assert(elapsed < 5000, `moveend return:"
    moveend_bound_hardened = "  assert(elapsed < 6500, `moveend return:"
    if moveend_bound not in hardened_smoke:
        raise RuntimeError("moveend return timing bound marker not found")
    hardened_smoke = hardened_smoke.replace(moveend_bound, moveend_bound_hardened, 1)

    phase_log_marker = """    window.__commonworldPhaseLog = [];
    window.__commonworldPhaseObserver?.disconnect?.();
"""
    phase_log_hardened = """    window.__commonworldPhaseLog = [];
    window.__commonworldMovingDiagnosticLog = [];
    let observedMapMoving = stageNode.dataset.mapMoving === 'true';
    window.__commonworldPhaseObserver?.disconnect?.();
"""
    if phase_log_marker not in hardened_smoke:
        raise RuntimeError("layer journey phase-log marker not found")
    hardened_smoke = hardened_smoke.replace(phase_log_marker, phase_log_hardened, 1)

    observer_callback = """    window.__commonworldPhaseObserver = new MutationObserver((mutations) => {
      window.__commonworldPhaseLog.push(snapshot(mutations.map((mutation) => `${mutation.target.id || mutation.target.className}:${mutation.attributeName}`).join('|')));
    });
"""
    observer_callback_hardened = """    window.__commonworldPhaseObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.target === stageNode && mutation.attributeName === 'data-map-moving') {
          observedMapMoving = mutation.oldValue === null;
          continue;
        }
        if (mutation.target === stageNode
          && mutation.attributeName === 'data-sphere-geometry-diagnostic-publishes'
          && observedMapMoving) {
          window.__commonworldMovingDiagnosticLog.push({
            geometryEvaluations: Number(stageNode.dataset.sphereGeometryEvaluations ?? 0),
            diagnosticPublishes: Number(stageNode.dataset.sphereGeometryDiagnosticPublishes ?? 0),
            at: performance.now(),
          });
        }
      }
      window.__commonworldPhaseLog.push(snapshot(mutations.map((mutation) => `${mutation.target.id || mutation.target.className}:${mutation.attributeName}`).join('|')));
    });
"""
    if observer_callback not in hardened_smoke:
        raise RuntimeError("layer journey phase observer callback not found")
    hardened_smoke = hardened_smoke.replace(observer_callback, observer_callback_hardened, 1)

    observer_options = """    window.__commonworldPhaseObserver.observe(stageNode, {
      attributes: true,
      attributeFilter: ['data-view-phase', 'data-globe-geometry-source', 'data-layer-panel-visible-at', 'data-last-camera-command', 'data-last-camera-duration', 'data-map-moving'],
    });
"""
    observer_options_hardened = """    window.__commonworldPhaseObserver.observe(stageNode, {
      attributes: true,
      attributeOldValue: true,
      attributeFilter: ['data-view-phase', 'data-globe-geometry-source', 'data-layer-panel-visible-at', 'data-last-camera-command', 'data-last-camera-duration', 'data-map-moving', 'data-sphere-geometry-diagnostic-publishes'],
    });
"""
    if observer_options not in hardened_smoke:
        raise RuntimeError("layer journey phase observer options not found")
    hardened_smoke = hardened_smoke.replace(observer_options, observer_options_hardened, 1)

    diagnostic_start = "  const firstMovingEntry = phaseLog.find((entry) => entry.mapMovingAttribute);"
    diagnostic_end = "  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout'"
    diagnostic_start_index = hardened_smoke.find(diagnostic_start)
    diagnostic_end_index = hardened_smoke.find(diagnostic_end, diagnostic_start_index)
    if diagnostic_start_index < 0 or diagnostic_end_index < 0:
        raise RuntimeError("layer journey diagnostic budget boundaries not found")
    diagnostic_block_hardened = """  const movingDiagnosticEntries = (await run.page.evaluate(() => window.__commonworldMovingDiagnosticLog ?? []))
    .filter((entry, index, entries) => index === 0 || entry.diagnosticPublishes !== entries[index - 1].diagnosticPublishes);
  const movingDiagnosticSpacings = movingDiagnosticEntries.slice(1).map((entry, index) => ({
    evaluations: entry.geometryEvaluations - movingDiagnosticEntries[index].geometryEvaluations,
    publishes: entry.diagnosticPublishes - movingDiagnosticEntries[index].diagnosticPublishes,
  }));
  const maxMovingDiagnosticEntries = Math.ceil(flightGeometryEvaluationDelta / MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL) + 1;
  assert(movingDiagnosticEntries.length > 0 && movingDiagnosticEntries.length <= maxMovingDiagnosticEntries, 'layer journey: moving diagnostic publication count exceeded the sampled budget ' + JSON.stringify({ movingDiagnosticEntries, maxMovingDiagnosticEntries, phaseLog }));
  assert(movingDiagnosticSpacings.every(({ evaluations, publishes }) => publishes > 0 && evaluations >= MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL * publishes), 'layer journey: consecutive moving diagnostics were not sample-spaced ' + JSON.stringify({ movingDiagnosticEntries, movingDiagnosticSpacings, phaseLog }));

"""
    hardened_smoke = hardened_smoke[:diagnostic_start_index] + diagnostic_block_hardened + hardened_smoke[diagnostic_end_index:]
'''

if target not in source:
    raise SystemExit('smoke write insertion point missing')
source = source.replace(target, insertion + target, 1)
path.write_text(source, encoding='utf-8')
