import test from 'node:test';
import assert from 'node:assert/strict';

import {
  checkForCurrentPage,
  cleanReleaseNavigationUrl,
  releaseNavigationUrl,
  validatePageBuildManifest,
} from '../../assets/commonworld-release-check.js';

const currentBuild = '1'.repeat(16);
const latestBuild = '2'.repeat(16);

function documentStub(page = 'index.html', build = currentBuild) {
  const values = new Map([
    ['commonworld-page', page],
    ['commonworld-page-build', build],
  ]);
  return {
    baseURI: 'https://commonworld.net/',
    querySelector(selector) {
      const match = selector.match(/^meta\[name="([^"]+)"\]$/u);
      return match && values.has(match[1]) ? { content: values.get(match[1]) } : null;
    },
  };
}

function fetchStub(build = latestBuild) {
  return async (url, options) => {
    assert.match(url, /commonworld-page-builds\.json\?cw_probe=123$/u);
    assert.equal(options.cache, 'no-store');
    assert.equal(options.credentials, 'same-origin');
    return {
      ok: true,
      status: 200,
      async json() {
        return { kind: 'commonworld.page_build_manifest', pages: { 'index.html': build }, schema_version: 1 };
      },
    };
  };
}

test('manifest validation rejects loose or malformed fields', () => {
  assert.deepEqual(validatePageBuildManifest({ kind: 'commonworld.page_build_manifest', pages: { 'index.html': currentBuild }, schema_version: 1 }).pages, { 'index.html': currentBuild });
  assert.throws(() => validatePageBuildManifest({ kind: 'commonworld.page_build_manifest', pages: {}, schema_version: 1 }), /must not be empty/u);
  assert.throws(() => validatePageBuildManifest({ kind: 'commonworld.page_build_manifest', pages: { '../index': currentBuild }, schema_version: 1 }), /invalid/u);
});

test('release navigation preserves product state and replaces only cache parameters', () => {
  const target = new URL(releaseNavigationUrl('https://commonworld.net/?project=debian&cw_probe=old#focus', latestBuild));
  assert.equal(target.searchParams.get('project'), 'debian');
  assert.equal(target.searchParams.get('cw_release'), latestBuild);
  assert.equal(target.searchParams.has('cw_probe'), false);
  assert.equal(target.hash, '#focus');
  assert.equal(cleanReleaseNavigationUrl(target.href), 'https://commonworld.net/?project=debian#focus');
});

test('stale page performs one release-bound replacement', async () => {
  let replaced = '';
  let announced = null;
  const result = await checkForCurrentPage({
    documentImpl: documentStub(),
    locationImpl: { href: 'https://commonworld.net/?project=debian', replace(value) { replaced = value; } },
    historyImpl: {},
    fetchImpl: fetchStub(),
    now: () => 123,
    beforeNavigate(value) { announced = value; },
  });
  assert.equal(result.state, 'reloading');
  assert.equal(new URL(replaced).searchParams.get('project'), 'debian');
  assert.equal(new URL(replaced).searchParams.get('cw_release'), latestBuild);
  assert.equal(announced.target, replaced);
  assert.equal(announced.page, 'index.html');
});

test('release navigation stays on the current page when draft preservation vetoes it', async () => {
  let replaced = false;
  const result = await checkForCurrentPage({
    documentImpl: documentStub('propose.html'),
    locationImpl: { href: 'https://commonworld.net/propose.html', replace() { replaced = true; } },
    historyImpl: {},
    fetchImpl: async () => ({
      ok: true,
      status: 200,
      async json() { return { kind: 'commonworld.page_build_manifest', pages: { 'propose.html': latestBuild }, schema_version: 1 }; },
    }),
    now: () => 123,
    beforeNavigate() { return false; },
  });
  assert.equal(result.state, 'navigation-blocked');
  assert.equal(replaced, false);
});

test('matching release target stops a propagation reload loop', async () => {
  let replaced = false;
  const result = await checkForCurrentPage({
    documentImpl: documentStub(),
    locationImpl: { href: `https://commonworld.net/?cw_release=${latestBuild}`, replace() { replaced = true; } },
    historyImpl: {},
    fetchImpl: fetchStub(),
    now: () => 123,
  });
  assert.equal(result.state, 'awaiting-propagation');
  assert.equal(replaced, false);
});

test('current page cleans the release-only query marker without navigation', async () => {
  let cleaned = '';
  const result = await checkForCurrentPage({
    documentImpl: documentStub('index.html', latestBuild),
    locationImpl: { href: `https://commonworld.net/?project=debian&cw_release=${latestBuild}`, replace() { throw new Error('must not navigate'); } },
    historyImpl: { state: { preserved: true }, replaceState(_state, _title, value) { cleaned = value; } },
    fetchImpl: fetchStub(),
    now: () => 123,
  });
  assert.equal(result.state, 'current');
  assert.equal(cleaned, 'https://commonworld.net/?project=debian');
});
