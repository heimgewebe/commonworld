const PAGE_BUILD_PATTERN = /^[0-9a-f]{16}$/u;
const RELEASE_ID_PATTERN = /^[0-9a-f]{20}$/u;
const PAGE_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9.-]{0,79}$/u;
const MANIFEST_KIND = 'commonworld.release_manifest';
const MANIFEST_PREFIX = '<!-- commonworld-release-manifest:';
const MANIFEST_SUFFIX = ' -->';
const LEGACY_RELEASE_PARAMETER = 'cw_release';
const LEGACY_PROBE_PARAMETER = 'cw_probe';
const PROBE_TIMEOUT_MS = 3_000;
export const RELEASE_NAVIGATION_EVENT = 'commonworld:release-navigation';
export const RELEASE_CHECK_REQUEST_EVENT = 'commonworld:release-check-request';

function metaContent(documentImpl, name) {
  const value = documentImpl?.querySelector?.(`meta[name="${name}"]`)?.content;
  return typeof value === 'string' ? value : '';
}

function canonicalPath(page) {
  if (page === 'index.html') return '/';
  return `/${page}`;
}

function snapshotPath(releaseId, page) {
  return `/releases/${releaseId}/${page}`;
}

function announceReleaseNavigation(documentImpl, detail) {
  if (typeof documentImpl?.dispatchEvent !== 'function') return true;
  const EventImpl = documentImpl.defaultView?.CustomEvent ?? globalThis.CustomEvent;
  if (typeof EventImpl !== 'function') return true;
  return documentImpl.dispatchEvent(new EventImpl(RELEASE_NAVIGATION_EVENT, { detail, cancelable: true }));
}

export function validatePageBuildManifest(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('release manifest must be an object');
  const keys = Object.keys(value).sort();
  if (keys.join(',') !== 'kind,pages,release_id,schema_version') throw new Error('release manifest fields mismatch');
  if (value.kind !== MANIFEST_KIND || value.schema_version !== 2) throw new Error('unsupported release manifest');
  if (!RELEASE_ID_PATTERN.test(value.release_id)) throw new Error('invalid release manifest identity');
  if (!value.pages || typeof value.pages !== 'object' || Array.isArray(value.pages)) throw new Error('release manifest pages must be an object');
  const pages = {};
  for (const [page, build] of Object.entries(value.pages)) {
    if (!PAGE_NAME_PATTERN.test(page) || !PAGE_BUILD_PATTERN.test(build)) throw new Error('invalid release manifest page');
    pages[page] = build;
  }
  if (Object.keys(pages).length === 0) throw new Error('release manifest must not be empty');
  return Object.freeze({
    kind: MANIFEST_KIND,
    pages: Object.freeze(pages),
    release_id: value.release_id,
    schema_version: 2,
  });
}

export function parseReleaseManifestDocument(markup) {
  if (typeof markup !== 'string') throw new TypeError('release probe document must be text');
  const start = markup.indexOf(MANIFEST_PREFIX);
  const end = start < 0 ? -1 : markup.indexOf(MANIFEST_SUFFIX, start + MANIFEST_PREFIX.length);
  if (start < 0 || end < 0 || markup.indexOf(MANIFEST_PREFIX, start + 1) >= 0) throw new Error('release probe marker mismatch');
  const payload = markup.slice(start + MANIFEST_PREFIX.length, end);
  return validatePageBuildManifest(JSON.parse(payload));
}

export function releaseNavigationUrl(currentHref, releaseId, page) {
  if (!RELEASE_ID_PATTERN.test(releaseId)) throw new TypeError('latest release identity is invalid');
  if (!PAGE_NAME_PATTERN.test(page)) throw new TypeError('public page identity is invalid');
  const target = new URL(currentHref);
  target.pathname = snapshotPath(releaseId, page);
  target.searchParams.delete(LEGACY_RELEASE_PARAMETER);
  target.searchParams.delete(LEGACY_PROBE_PARAMETER);
  return target.href;
}

export function cleanReleaseNavigationUrl(currentHref, page) {
  if (!PAGE_NAME_PATTERN.test(page)) throw new TypeError('public page identity is invalid');
  const target = new URL(currentHref);
  if (/^\/releases\/[0-9a-f]{20}\/[A-Za-z0-9][A-Za-z0-9.-]{0,79}$/u.test(target.pathname)) target.pathname = canonicalPath(page);
  target.searchParams.delete(LEGACY_RELEASE_PARAMETER);
  target.searchParams.delete(LEGACY_PROBE_PARAMETER);
  return target.href;
}

function probeToken(now, nonce) {
  const token = `${now()}-${nonce()}`.replace(/[^A-Za-z0-9_-]/gu, '');
  if (token.length < 3 || token.length > 160) throw new Error('invalid release probe token');
  return token;
}

async function fetchReleaseProbe({
  locationImpl,
  fetchImpl,
  now,
  nonce,
  timeoutMs,
  AbortControllerImpl,
  setTimeoutImpl,
  clearTimeoutImpl,
}) {
  const current = new URL(locationImpl.href);
  const url = new URL(`/__cw_probe/${probeToken(now, nonce)}/manifest`, current.origin);
  const controller = typeof AbortControllerImpl === 'function' ? new AbortControllerImpl() : null;
  const timeout = controller ? setTimeoutImpl(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetchImpl(url.href, {
      headers: { Accept: 'text/html' },
      cache: 'no-store',
      credentials: 'same-origin',
      ...(controller ? { signal: controller.signal } : {}),
    });
    if (response.status !== 404 && response.status !== 200) return Object.freeze({ state: 'probe-failed', status: response.status });
    return Object.freeze({ state: 'probe-ready', manifest: parseReleaseManifestDocument(await response.text()), url: url.href });
  } catch (error) {
    if (controller?.signal.aborted) return Object.freeze({ state: 'probe-timeout' });
    return Object.freeze({ state: 'probe-failed', error: error instanceof Error ? error.name : 'unknown' });
  } finally {
    if (timeout !== null) clearTimeoutImpl(timeout);
  }
}

export async function checkForCurrentPage({
  documentImpl = globalThis.document,
  locationImpl = globalThis.location,
  historyImpl = globalThis.history,
  fetchImpl = globalThis.fetch,
  now = () => Date.now(),
  nonce = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2),
  timeoutMs = PROBE_TIMEOUT_MS,
  AbortControllerImpl = globalThis.AbortController,
  setTimeoutImpl = globalThis.setTimeout,
  clearTimeoutImpl = globalThis.clearTimeout,
  beforeNavigate = null,
} = {}) {
  if (!documentImpl || !locationImpl || typeof fetchImpl !== 'function') return Object.freeze({ state: 'unsupported' });
  const page = metaContent(documentImpl, 'commonworld-page');
  const currentBuild = metaContent(documentImpl, 'commonworld-page-build');
  const currentRelease = metaContent(documentImpl, 'commonworld-release');
  if (!PAGE_NAME_PATTERN.test(page) || !PAGE_BUILD_PATTERN.test(currentBuild) || !RELEASE_ID_PATTERN.test(currentRelease)) return Object.freeze({ state: 'unbound' });

  const probe = await fetchReleaseProbe({ locationImpl, fetchImpl, now, nonce, timeoutMs, AbortControllerImpl, setTimeoutImpl, clearTimeoutImpl });
  if (probe.state !== 'probe-ready') return probe;
  const { manifest } = probe;
  const latestBuild = manifest.pages[page];
  if (!latestBuild) return Object.freeze({ state: 'page-unknown', page });

  const currentUrl = new URL(locationImpl.href);
  if (latestBuild === currentBuild && manifest.release_id === currentRelease) {
    const cleaned = cleanReleaseNavigationUrl(currentUrl.href, page);
    if (cleaned !== currentUrl.href) historyImpl?.replaceState?.(historyImpl.state ?? null, '', cleaned);
    return Object.freeze({ state: 'current', page, build: currentBuild, releaseId: currentRelease, probeUrl: probe.url });
  }

  const target = releaseNavigationUrl(currentUrl.href, manifest.release_id, page);
  if (currentUrl.pathname === new URL(target).pathname) {
    return Object.freeze({ state: 'awaiting-propagation', page, currentBuild, currentRelease, latestBuild, latestRelease: manifest.release_id });
  }
  const navigation = Object.freeze({ page, currentBuild, currentRelease, latestBuild, latestRelease: manifest.release_id, target });
  const navigationAllowed = typeof beforeNavigate === 'function'
    ? beforeNavigate(navigation) !== false
    : announceReleaseNavigation(documentImpl, navigation);
  if (!navigationAllowed) return Object.freeze({ state: 'navigation-blocked', ...navigation });
  locationImpl.replace(target);
  return Object.freeze({ state: 'reloading', ...navigation });
}

export function startCurrentPageChecks({
  checkImpl = checkForCurrentPage,
  documentImpl = globalThis.document,
  windowImpl = globalThis.window,
  setIntervalImpl = globalThis.setInterval,
  clearIntervalImpl = globalThis.clearInterval,
  intervalMs = 5 * 60 * 1_000,
} = {}) {
  if (!documentImpl || !windowImpl || typeof checkImpl !== 'function') return () => {};

  let inFlight = false;
  const run = () => {
    if (inFlight) return;
    inFlight = true;
    void Promise.resolve()
      .then(() => checkImpl())
      .catch(() => {})
      .finally(() => { inFlight = false; });
  };
  const runWhenVisible = () => {
    if (documentImpl.visibilityState && documentImpl.visibilityState !== 'visible') return;
    run();
  };

  documentImpl.addEventListener?.('visibilitychange', runWhenVisible);
  documentImpl.addEventListener?.(RELEASE_CHECK_REQUEST_EVENT, runWhenVisible);
  windowImpl.addEventListener?.('pageshow', runWhenVisible);
  windowImpl.addEventListener?.('focus', runWhenVisible);
  const intervalId = typeof setIntervalImpl === 'function' && Number.isFinite(intervalMs) && intervalMs >= 30_000
    ? setIntervalImpl(runWhenVisible, intervalMs)
    : null;
  runWhenVisible();

  return () => {
    documentImpl.removeEventListener?.('visibilitychange', runWhenVisible);
    documentImpl.removeEventListener?.(RELEASE_CHECK_REQUEST_EVENT, runWhenVisible);
    windowImpl.removeEventListener?.('pageshow', runWhenVisible);
    windowImpl.removeEventListener?.('focus', runWhenVisible);
    if (intervalId !== null && typeof clearIntervalImpl === 'function') clearIntervalImpl(intervalId);
  };
}

if (typeof document !== 'undefined' && typeof location !== 'undefined' && /^https?:$/u.test(location.protocol)) {
  startCurrentPageChecks();
}
