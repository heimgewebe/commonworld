const PAGE_BUILD_PATTERN = /^[0-9a-f]{16}$/u;
const PAGE_NAME_PATTERN = /^[a-z0-9][a-z0-9.-]{0,79}$/u;
const MANIFEST_KIND = 'commonworld.page_build_manifest';
const MANIFEST_URL = './assets/commonworld-page-builds.json';
const RELEASE_PARAMETER = 'cw_release';
const PROBE_PARAMETER = 'cw_probe';
export const RELEASE_NAVIGATION_EVENT = 'commonworld:release-navigation';

function metaContent(documentImpl, name) {
  const value = documentImpl?.querySelector?.(`meta[name="${name}"]`)?.content;
  return typeof value === 'string' ? value : '';
}

function announceReleaseNavigation(documentImpl, detail) {
  if (typeof documentImpl?.dispatchEvent !== 'function') return true;
  const EventImpl = documentImpl.defaultView?.CustomEvent ?? globalThis.CustomEvent;
  if (typeof EventImpl !== 'function') return true;
  return documentImpl.dispatchEvent(new EventImpl(RELEASE_NAVIGATION_EVENT, { detail, cancelable: true }));
}

export function validatePageBuildManifest(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('page build manifest must be an object');
  const keys = Object.keys(value).sort();
  if (keys.join(',') !== 'kind,pages,schema_version') throw new Error('page build manifest fields mismatch');
  if (value.kind !== MANIFEST_KIND || value.schema_version !== 1) throw new Error('unsupported page build manifest');
  if (!value.pages || typeof value.pages !== 'object' || Array.isArray(value.pages)) throw new Error('page build manifest pages must be an object');
  const pages = {};
  for (const [page, build] of Object.entries(value.pages)) {
    if (!PAGE_NAME_PATTERN.test(page) || !PAGE_BUILD_PATTERN.test(build)) throw new Error('invalid page build manifest entry');
    pages[page] = build;
  }
  if (Object.keys(pages).length === 0) throw new Error('page build manifest must not be empty');
  return Object.freeze({ kind: MANIFEST_KIND, schema_version: 1, pages: Object.freeze(pages) });
}

export function releaseNavigationUrl(currentHref, latestBuild) {
  if (!PAGE_BUILD_PATTERN.test(latestBuild)) throw new TypeError('latest page build is invalid');
  const target = new URL(currentHref);
  target.searchParams.set(RELEASE_PARAMETER, latestBuild);
  target.searchParams.delete(PROBE_PARAMETER);
  return target.href;
}

export function cleanReleaseNavigationUrl(currentHref) {
  const target = new URL(currentHref);
  target.searchParams.delete(RELEASE_PARAMETER);
  target.searchParams.delete(PROBE_PARAMETER);
  return target.href;
}

export async function checkForCurrentPage({
  documentImpl = globalThis.document,
  locationImpl = globalThis.location,
  historyImpl = globalThis.history,
  fetchImpl = globalThis.fetch,
  now = () => Date.now(),
  beforeNavigate = null,
} = {}) {
  if (!documentImpl || !locationImpl || typeof fetchImpl !== 'function') return Object.freeze({ state: 'unsupported' });
  const page = metaContent(documentImpl, 'commonworld-page');
  const currentBuild = metaContent(documentImpl, 'commonworld-page-build');
  if (!PAGE_NAME_PATTERN.test(page) || !PAGE_BUILD_PATTERN.test(currentBuild)) return Object.freeze({ state: 'unbound' });

  const manifestUrl = new URL(MANIFEST_URL, documentImpl.baseURI || locationImpl.href);
  manifestUrl.searchParams.set(PROBE_PARAMETER, String(now()));
  const response = await fetchImpl(manifestUrl.href, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    credentials: 'same-origin',
  });
  if (!response.ok) return Object.freeze({ state: 'probe-failed', status: response.status });
  const manifest = validatePageBuildManifest(await response.json());
  const latestBuild = manifest.pages[page];
  if (!latestBuild) return Object.freeze({ state: 'page-unknown', page });

  const currentUrl = new URL(locationImpl.href);
  if (latestBuild === currentBuild) {
    if (currentUrl.searchParams.has(RELEASE_PARAMETER) || currentUrl.searchParams.has(PROBE_PARAMETER)) {
      historyImpl?.replaceState?.(historyImpl.state ?? null, '', cleanReleaseNavigationUrl(currentUrl.href));
    }
    return Object.freeze({ state: 'current', page, build: currentBuild });
  }
  if (currentUrl.searchParams.get(RELEASE_PARAMETER) === latestBuild) {
    return Object.freeze({ state: 'awaiting-propagation', page, currentBuild, latestBuild });
  }

  const target = releaseNavigationUrl(currentUrl.href, latestBuild);
  const navigation = Object.freeze({ page, currentBuild, latestBuild, target });
  const navigationAllowed = typeof beforeNavigate === 'function'
    ? beforeNavigate(navigation) !== false
    : announceReleaseNavigation(documentImpl, navigation);
  if (!navigationAllowed) return Object.freeze({ state: 'navigation-blocked', ...navigation });
  locationImpl.replace(target);
  return Object.freeze({ state: 'reloading', ...navigation });
}

if (typeof document !== 'undefined' && typeof location !== 'undefined' && /^https?:$/u.test(location.protocol)) {
  void checkForCurrentPage().catch(() => {});
}
