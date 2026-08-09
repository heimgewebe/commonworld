#!/usr/bin/env python3
from pathlib import Path

smoke = Path('scripts/smoke_public_browser.mjs')
source = smoke.read_text(encoding='utf-8')

probe_marker = """    window.__commonworldCameraCommands = [];
    window.__commonworldPhaseLog = [];
    window.__commonworldPhaseObserver?.disconnect?.();
"""
probe_replacement = """    window.__commonworldCameraCommands = [];
    window.__commonworldMovingGeometrySamples = [];
    const movingGeometryProbeMap = window.__commonworldTestMap;
    const captureMovingGeometrySample = (event) => {
      window.__commonworldMovingGeometrySamples.push({
        event,
        mapMoving: stageNode.dataset.mapMoving === 'true',
        geometryEvaluations: Number(stageNode.dataset.sphereGeometryEvaluations ?? 0),
        diagnosticPublishes: Number(stageNode.dataset.sphereGeometryDiagnosticPublishes ?? 0),
        at: performance.now(),
      });
    };
    const onMovingGeometryMoveStart = () => captureMovingGeometrySample('movestart');
    const onMovingGeometryRender = () => {
      if (stageNode.dataset.mapMoving === 'true') captureMovingGeometrySample('render');
    };
    const onMovingGeometryMoveEnd = () => captureMovingGeometrySample('moveend');
    movingGeometryProbeMap?.on('movestart', onMovingGeometryMoveStart);
    movingGeometryProbeMap?.on('render', onMovingGeometryRender);
    movingGeometryProbeMap?.on('moveend', onMovingGeometryMoveEnd);
    window.__commonworldDetachMovingGeometryProbe = () => {
      movingGeometryProbeMap?.off('movestart', onMovingGeometryMoveStart);
      movingGeometryProbeMap?.off('render', onMovingGeometryRender);
      movingGeometryProbeMap?.off('moveend', onMovingGeometryMoveEnd);
    };
    window.__commonworldPhaseLog = [];
    window.__commonworldPhaseObserver?.disconnect?.();
"""
if probe_marker not in source:
    raise SystemExit('layer journey moving geometry probe marker not found')
source = source.replace(probe_marker, probe_replacement, 1)

diagnostic_start = "  const firstMovingEntry = phaseLog.find((entry) => entry.mapMovingAttribute);"
diagnostic_end = "  assert((await stage.getAttribute('data-globe-geometry-source')) === 'side-view-layout'"
start = source.find(diagnostic_start)
end = source.find(diagnostic_end, start)
if start < 0 or end < 0:
    raise SystemExit('layer journey diagnostic budget boundaries not found')

diagnostic_replacement = """  const movingGeometrySamples = await run.page.evaluate(() => {
    const samples = [...(window.__commonworldMovingGeometrySamples ?? [])];
    window.__commonworldDetachMovingGeometryProbe?.();
    delete window.__commonworldDetachMovingGeometryProbe;
    return samples;
  });
  const moveStartGeometrySample = movingGeometrySamples.find((sample) => sample.event === 'movestart');
  const movingRenderSamples = movingGeometrySamples.filter((sample) => sample.event === 'render' && sample.mapMoving);
  const movingEvaluationSamples = movingRenderSamples.filter((sample, index, samples) => {
    const previous = samples[index - 1];
    return !previous
      || sample.geometryEvaluations !== previous.geometryEvaluations
      || sample.diagnosticPublishes !== previous.diagnosticPublishes;
  });
  assert(moveStartGeometrySample?.mapMoving === true, 'layer journey: direct MapLibre probe missed the moving start state ' + JSON.stringify(movingGeometrySamples));
  assert(movingEvaluationSamples.length > 0, 'layer journey: direct MapLibre probe observed no moving geometry evaluations ' + JSON.stringify(movingGeometrySamples));
  let previousDiagnosticPublishes = moveStartGeometrySample.diagnosticPublishes;
  const movingDiagnosticEvents = [];
  for (const sample of movingEvaluationSamples) {
    const publishes = sample.diagnosticPublishes - previousDiagnosticPublishes;
    if (publishes > 0) {
      movingDiagnosticEvents.push({ ...sample, publishes });
      previousDiagnosticPublishes = sample.diagnosticPublishes;
    }
  }
  const movingDiagnosticSpacings = movingDiagnosticEvents.slice(1).map((entry, index) => ({
    evaluations: entry.geometryEvaluations - movingDiagnosticEvents[index].geometryEvaluations,
    publishes: entry.publishes,
  }));
  const maxMovingDiagnosticEvents = Math.ceil(movingEvaluationSamples.length / MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL) + 1;
  assert(movingDiagnosticEvents.length > 0 && movingDiagnosticEvents.length <= maxMovingDiagnosticEvents, 'layer journey: moving diagnostic publication count exceeded the sampled budget ' + JSON.stringify({ movingDiagnosticEvents, maxMovingDiagnosticEvents, movingGeometrySamples, phaseLog }));
  assert(movingDiagnosticEvents.every(({ publishes }) => publishes === 1), 'layer journey: a moving render published diagnostics more than once ' + JSON.stringify({ movingDiagnosticEvents, movingGeometrySamples }));
  assert(movingDiagnosticSpacings.every(({ evaluations, publishes }) => publishes === 1 && evaluations >= MAP_GEOMETRY_DIAGNOSTIC_SAMPLE_INTERVAL), 'layer journey: consecutive moving diagnostics were not sample-spaced ' + JSON.stringify({ movingDiagnosticEvents, movingDiagnosticSpacings, movingGeometrySamples, phaseLog }));
"""
source = source[:start] + diagnostic_replacement + source[end:]

smoke.write_text(source, encoding='utf-8')
