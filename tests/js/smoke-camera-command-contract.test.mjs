import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const smokeSource = await readFile(new URL('../../scripts/smoke_public_browser.mjs', import.meta.url), 'utf8');
const contractSourceStart = smokeSource.indexOf('function validRecordedCameraTarget(');
const contractSourceEnd = smokeSource.indexOf('\nasync function hierarchyFocusDiagnostic(', contractSourceStart);
assert(contractSourceStart >= 0 && contractSourceEnd > contractSourceStart, 'smoke camera contract source boundary is missing');
const contractSource = smokeSource.slice(contractSourceStart, contractSourceEnd);
const { hasBoundedLayerOpeningCameraCommands } = new Function(
  `${contractSource}\nreturn { hasBoundedLayerOpeningCameraCommands };`,
)();

const duration = 420;
const target = () => ({
  center: [12.3, 45.6],
  zoom: 2.75,
  bearing: 12,
  pitch: 34,
  padding: { top: 0, right: 0, bottom: 0, left: 0 },
  offset: [-180, 0],
});
const ease = (overrides = {}) => ({ command: 'easeTo', duration, target: target(), ...overrides });
const jump = (overrides = {}) => ({ command: 'jumpTo', duration: 0, target: target(), ...overrides });
const accepted = (commands, settlement = 'moveend', mapIdle = true) => (
  hasBoundedLayerOpeningCameraCommands({ commands, settlement, mapIdle }, duration)
);

test('accepts one settled ordinary opening camera command', () => {
  assert.equal(accepted([ease()]), true);
});

test('accepts only the exact idle fallback-stop reconciliation pair', () => {
  assert.equal(accepted([ease(), jump()], 'fallback-stop'), true);
});

test('rejects malformed fallback commands and settlement states', () => {
  assert.equal(accepted([ease(), jump()], 'moveend'), false);
  assert.equal(accepted([ease(), jump()], 'fallback-stop', false), false);
  assert.equal(accepted([ease()], 'fallback-stop'), false);
  assert.equal(accepted([ease(), jump({ command: 'easeTo' })], 'fallback-stop'), false);
  assert.equal(accepted([ease(), jump({ duration: 1 })], 'fallback-stop'), false);
  assert.equal(accepted([ease(), jump({ target: { ...target(), zoom: 3 } })], 'fallback-stop'), false);
});

test('rejects malformed ordinary and multiple camera command patterns', () => {
  assert.equal(accepted([ease({ command: 'jumpTo' })]), false);
  assert.equal(accepted([ease({ duration: 419 })]), false);
  assert.equal(accepted([ease({ target: { ...target(), center: [12.3] } })]), false);
  assert.equal(accepted([ease()], 'already-idle'), false);
  assert.equal(accepted([ease(), jump(), jump()], 'fallback-stop'), false);
  assert.equal(accepted([]), false);
});
