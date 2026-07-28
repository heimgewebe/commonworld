import test from 'node:test';
import assert from 'node:assert/strict';

import {
  checkForCurrentPage,
  cleanReleaseNavigationUrl,
  parseReleaseManifestDocument,
  releaseNavigationUrl,
  validatePageBuildManifest,
} from '../../assets/commonworld-release-check.js';

const currentBuild = '1'.repeat(16);
const latestBuild = '2'.repeat(16);
const currentRelease = 'a'.repeat(20);
const latestRelease = 'b'.repeat(20);

function manifest(build = latestBuild, releaseId = latestRelease, page = 'index.html') {
  return { kind: 'commonworld.release_manifest', pages: { [page]: build }, release_id: releaseId, schema_version: 2 };
}

function probeDocument(value = manifest()) {
  return `<!doctype html>\n<html><body>not found<!-- commonworld-release-manifest:${JSON.stringify(value)} --></body></html>`;
}

function documentStub(page = 'index.html', build = currentBuild, releaseId = currentRelease) {
  const values = new Map([
    ['commonworld-page', page],
    ['commonworld-page-build', build],
    ['commonworld-release', releaseId],
  ]);
  return {
    baseURI: `https://commonworld.net/releases/${releaseId}/`,
    querySelector(selector) {
      const match = selector.match(/^meta\[name="([^"]+)"\]$/u);
      return match && values.has(match[1]) ? { content: values.get(match[1]) } : null;
    },
  };
}

function fetchStub(value = manifest()) {
  return async (url, options) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, '/__cw_probe/123-nonce/manifest');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers.Accept, 'text/html');
    return {
      status: 404,
      async text() { return probeDocument(value); },
    };
  };
}

const deterministicProbe = Object.freeze({ now: () => 123, nonce: () => 'nonce' });

test('release manifest validation and 404 marker parsing reject loose input', () => {
  assert.deepEqual(validatePageBuildManifest(manifest()).pages, { 'index.html': latestBuild });
  assert.equal(parseReleaseManifestDocument(probeDocument()).release_id, latestRelease);
  assert.throws(() => validatePageBuildManifest({ ...manifest(), extra: true }), /fields mismatch/u);
  assert.throws(() => validatePageBuildManifest({ ...manifest(), release_id: 'loose' }), /identity/u);
  assert.throws(() => validatePageBuildManifest({ ...manifest(), pages: {} }), /must not be empty/u);
  assert.throws(() => parseReleaseManifestDocument('no marker'), /marker/u);
  assert.throws(() => parseReleaseManifestDocument(`${probeDocument()}${probeDocument()}`), /marker/u);
});

test('path-keyed release navigation preserves product query and fragment', () => {
  const target = new URL(releaseNavigationUrl('https://commonworld.net/?project=debian&cw_probe=old#focus', latestRelease, 'index.html'));
  assert.equal(target.pathname, `/releases/${latestRelease}/index.html`);
  assert.equal(target.searchParams.get('project'), 'debian');
  assert.equal(target.searchParams.has('cw_release'), false);
  assert.equal(target.searchParams.has('cw_probe'), false);
  assert.equal(target.hash, '#focus');
  assert.equal(cleanReleaseNavigationUrl(target.href, 'index.html'), 'https://commonworld.net/?project=debian#focus');
  assert.equal(cleanReleaseNavigationUrl(`https://commonworld.net/releases/${latestRelease}/method.de.html?x=1`, 'method.de.html'), 'https://commonworld.net/method.de.html?x=1');
});

test('stale page performs one path-bound replacement after announcing navigation', async () => {
  let replaced = '';
  let announced = null;
  const result = await checkForCurrentPage({
    documentImpl: documentStub(),
    locationImpl: { href: 'https://commonworld.net/?project=debian', replace(value) { replaced = value; } },
    historyImpl: {},
    fetchImpl: fetchStub(),
    beforeNavigate(value) { announced = value; },
    ...deterministicProbe,
  });
  assert.equal(result.state, 'reloading');
  assert.equal(new URL(replaced).pathname, `/releases/${latestRelease}/index.html`);
  assert.equal(new URL(replaced).searchParams.get('project'), 'debian');
  assert.equal(announced.target, replaced);
  assert.equal(announced.latestRelease, latestRelease);
});

test('asset-only release change reloads even when page bytes are unchanged', async () => {
  let replaced = '';
  const result = await checkForCurrentPage({
    documentImpl: documentStub('index.html', currentBuild, currentRelease),
    locationImpl: { href: 'https://commonworld.net/', replace(value) { replaced = value; } },
    historyImpl: {},
    fetchImpl: fetchStub(manifest(currentBuild, latestRelease)),
    ...deterministicProbe,
  });
  assert.equal(result.state, 'reloading');
  assert.equal(new URL(replaced).pathname, `/releases/${latestRelease}/index.html`);
});

test('matching path target stops a propagation reload loop', async () => {
  let replaced = false;
  const result = await checkForCurrentPage({
    documentImpl: documentStub(),
    locationImpl: { href: `https://commonworld.net/releases/${latestRelease}/index.html`, replace() { replaced = true; } },
    historyImpl: {},
    fetchImpl: fetchStub(),
    ...deterministicProbe,
  });
  assert.equal(result.state, 'awaiting-propagation');
  assert.equal(replaced, false);
});

test('current release snapshot cleans its address to the canonical page', async () => {
  let cleaned = '';
  const result = await checkForCurrentPage({
    documentImpl: documentStub('index.html', latestBuild, latestRelease),
    locationImpl: { href: `https://commonworld.net/releases/${latestRelease}/index.html?project=debian#focus`, replace() { throw new Error('must not navigate'); } },
    historyImpl: { state: { preserved: true }, replaceState(_state, _title, value) { cleaned = value; } },
    fetchImpl: fetchStub(),
    ...deterministicProbe,
  });
  assert.equal(result.state, 'current');
  assert.equal(cleaned, 'https://commonworld.net/?project=debian#focus');
});

test('draft guard can cancel release navigation before replacement', async () => {
  let replaced = false;
  let offered = null;
  const result = await checkForCurrentPage({
    documentImpl: documentStub('propose.html', currentBuild, currentRelease),
    locationImpl: { href: 'https://commonworld.net/propose.html', replace() { replaced = true; } },
    historyImpl: {},
    fetchImpl: fetchStub(manifest(latestBuild, latestRelease, 'propose.html')),
    beforeNavigate(navigation) { offered = navigation; return false; },
    ...deterministicProbe,
  });
  assert.equal(result.state, 'navigation-blocked');
  assert.equal(replaced, false);
  assert.equal(offered.latestRelease, latestRelease);
  assert.equal(new URL(offered.target).pathname, `/releases/${latestRelease}/propose.html`);
});

test('bounded probe timeout cannot navigate after a delayed response', async () => {
  let replaced = false;
  const result = await checkForCurrentPage({
    documentImpl: documentStub(),
    locationImpl: { href: 'https://commonworld.net/', replace() { replaced = true; } },
    historyImpl: {},
    fetchImpl: async (_url, options) => {
      assert.equal(options.signal.aborted, true);
      throw new DOMException('aborted', 'AbortError');
    },
    setTimeoutImpl(callback) { callback(); return 1; },
    clearTimeoutImpl() {},
    ...deterministicProbe,
  });
  assert.equal(result.state, 'probe-timeout');
  assert.equal(replaced, false);
});
