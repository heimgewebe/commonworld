import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const appSource = await readFile(new URL('../../assets/commonworld-app.js', import.meta.url), 'utf8');
const cameraSourceStart = appSource.indexOf('function smoothCameraEasing(');
const cameraSourceEnd = appSource.indexOf('\nfunction sphereVisualOpacity(', cameraSourceStart);
assert(cameraSourceStart >= 0 && cameraSourceEnd > cameraSourceStart, 'camera-flight source boundary is missing');
const cameraSource = appSource.slice(cameraSourceStart, cameraSourceEnd);

class FakeMap {
  constructor({ stuck = false, silentFinish = false, finishDelay = 20 } = {}) {
    this.listeners = new Map();
    this.moving = false;
    this.stuck = stuck;
    this.silentFinish = silentFinish;
    this.finishDelay = finishDelay;
    this.finishTimer = null;
    this.lastJump = null;
  }

  on(type, listener) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
    return this;
  }

  off(type, listener) {
    this.listeners.get(type)?.delete(listener);
    return this;
  }

  emit(type) {
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener();
  }

  isMoving() {
    return this.moving;
  }

  easeTo() {
    if (this.moving) {
      clearTimeout(this.finishTimer);
      this.finishTimer = null;
      this.moving = false;
      this.emit('moveend');
    }
    this.moving = true;
    if (!this.stuck) {
      this.finishTimer = setTimeout(() => {
        this.finishTimer = null;
        this.moving = false;
        if (!this.silentFinish) this.emit('moveend');
      }, this.finishDelay);
    }
    return this;
  }

  jumpTo(options) {
    this.moving = false;
    this.lastJump = structuredClone(options);
    this.emit('moveend');
    return this;
  }

  stop() {
    clearTimeout(this.finishTimer);
    this.finishTimer = null;
    this.moving = false;
    this.emit('moveend');
    return this;
  }

  listenerCount(type) {
    return this.listeners.get(type)?.size ?? 0;
  }
}

function cameraHarness(map, { clampFallback = false } = {}) {
  const runtime = {
    map,
    cameraFlightGeneration: 0,
    cameraFlightCleanup: null,
    viewTransitionCleanup: null,
    layerReturnFocusTimer: null,
  };
  const elements = { stage: { dataset: {} } };
  const windowObject = {
    setTimeout(callback, delay) {
      return setTimeout(callback, clampFallback && delay >= 2000 ? 10 : delay);
    },
    clearTimeout,
  };
  const factory = new Function(
    'runtime',
    'elements',
    'reducedMotion',
    'window',
    `${cameraSource}\nreturn { startCameraFlight };`,
  );
  return {
    ...factory(runtime, elements, { matches: false }, windowObject),
    runtime,
    elements,
  };
}

const camera = (lng) => ({ lng, lat: 51, zoom: 2, bearing: 12, pitch: 34 });

test('replacement flight ignores the prior ease synchronous moveend and settles after its own camera', async () => {
  const map = new FakeMap();
  const { startCameraFlight, runtime, elements } = cameraHarness(map);
  const settlements = [];

  startCameraFlight(camera(10), { duration: 80, onSettled: () => settlements.push('first') });
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'pending');
  assert.equal(map.listenerCount('moveend'), 1);

  startCameraFlight(camera(20), { duration: 80, onSettled: () => settlements.push('second') });
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'pending');
  assert.equal(map.isMoving(), true);
  assert.deepEqual(settlements, [], 'the prior ease moveend settled the replacement flight');
  assert.equal(map.listenerCount('moveend'), 1, 'the replaced listener was not cleaned up');

  await new Promise((resolve) => setTimeout(resolve, 35));
  assert.deepEqual(settlements, ['second']);
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'moveend');
  assert.equal(map.isMoving(), false);
  assert.equal(map.listenerCount('moveend'), 0);
  assert.equal(runtime.cameraFlightCleanup, null);
});

test('missing moveend that becomes idle before fallback settles without a corrective jump', async () => {
  const map = new FakeMap({ silentFinish: true, finishDelay: 5 });
  const { startCameraFlight, runtime, elements } = cameraHarness(map, { clampFallback: true });
  let settled = 0;

  startCameraFlight(camera(25), { duration: 80, onSettled: () => { settled += 1; } });
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert.equal(settled, 1);
  assert.equal(map.isMoving(), false);
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'fallback-idle');
  assert.equal(map.lastJump, null);
  assert.equal(map.listenerCount('moveend'), 0);
  assert.equal(runtime.cameraFlightCleanup, null);
});

test('stuck flight fallback stops, reconciles the exact target, and removes its listener', async () => {
  const map = new FakeMap({ stuck: true });
  const { startCameraFlight, runtime, elements } = cameraHarness(map, { clampFallback: true });
  let settled = 0;
  const target = { ...camera(30), offset: [-180, 0] };

  startCameraFlight(target, { duration: 80, onSettled: () => { settled += 1; } });
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'pending');
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert.equal(settled, 1);
  assert.equal(map.isMoving(), false);
  assert.equal(elements.stage.dataset.cameraFlightSettlement, 'fallback-stop');
  assert.equal(elements.stage.dataset.lastCameraCommand, 'jumpTo');
  assert.equal(elements.stage.dataset.lastCameraDuration, '0');
  assert.deepEqual(map.lastJump, {
    center: [30, 51],
    zoom: 2,
    bearing: 12,
    pitch: 34,
    padding: { top: 0, right: 0, bottom: 0, left: 0 },
    offset: [-180, 0],
  });
  assert.equal(map.listenerCount('moveend'), 0);
  assert.equal(runtime.cameraFlightCleanup, null);
});
