import {
  CANDIDATE_LOCALES,
  DEFAULT_LOCALE,
  LOCALE_REGISTRY,
  RELEASED_LOCALES,
  canonicalLocaleTag,
  documentLocale,
  localeSwitchHref,
  normalizeLocale,
} from './commonworld-i18n.mjs?v=32e02556e8f5';

export const UI_LOCALE_STORAGE_KEY = 'commonworld.ui-locale';
export const UI_LOCALE_QUERY_PARAMETER = 'ui_lang';
export const UI_LOCALE_CHOICES = Object.freeze(['auto', ...RELEASED_LOCALES]);

const SURFACE_FILES = Object.freeze((() => {
  const values = {
    '': Object.freeze({ surface: 'index', locale: DEFAULT_LOCALE, neutral: true }),
  };
  for (const [locale, entry] of Object.entries(LOCALE_REGISTRY)) {
    for (const [surfaceName, fileName] of Object.entries(entry.surface_files ?? {})) {
      const surface = surfaceName === 'proposal' ? 'propose' : surfaceName;
      values[fileName] = Object.freeze({
        surface,
        locale,
        neutral: fileName === 'index.html',
      });
    }
  }
  return values;
})());

function pathnameFile(pathname) {
  const value = String(pathname ?? '');
  if (value.endsWith('/')) return '';
  const normalized = value.replace(/\/+$/u, '');
  return normalized.split('/').pop() ?? '';
}

function safeStorage(storage) {
  if (storage !== undefined) return storage;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function normalizeLocalePreference(value) {
  const raw = String(value ?? '').trim();
  if (raw.toLowerCase() === 'auto') return 'auto';
  const canonical = canonicalLocaleTag(raw);
  return canonical && RELEASED_LOCALES.includes(canonical) ? canonical : null;
}

export function matchSupportedLocaleTag(value, supportedLocales = RELEASED_LOCALES) {
  const canonical = canonicalLocaleTag(value);
  if (!canonical) return null;
  const allowed = Array.isArray(supportedLocales) ? supportedLocales : RELEASED_LOCALES;
  const exact = allowed.find((tag) => tag.toLowerCase() === canonical.toLowerCase());
  if (exact) return exact;
  const parts = canonical.split('-');
  if (parts.length >= 2 && parts[1].length === 4) {
    const languageScript = parts.slice(0, 2).join('-').toLowerCase();
    const scriptMatch = allowed.find((tag) => tag.toLowerCase() === languageScript);
    if (scriptMatch) return scriptMatch;
  }
  const primary = parts[0].toLowerCase();
  return allowed.find((tag) => tag.split('-')[0].toLowerCase() === primary) ?? null;
}

export function supportedLocale(value) {
  return matchSupportedLocaleTag(value);
}

export function matchSupportedLocale(values, fallback = DEFAULT_LOCALE) {
  for (const candidate of Array.isArray(values) ? values : []) {
    const matched = supportedLocale(candidate);
    if (matched) return matched;
  }
  return supportedLocale(fallback) ?? DEFAULT_LOCALE;
}

export function readStoredLocalePreference(storage = undefined) {
  const target = safeStorage(storage);
  if (!target) return null;
  try {
    return normalizeLocalePreference(target.getItem(UI_LOCALE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function writeStoredLocalePreference(choice, storage = undefined) {
  const normalized = normalizeLocalePreference(choice);
  const target = safeStorage(storage);
  if (!normalized || !target) return false;
  try {
    target.setItem(UI_LOCALE_STORAGE_KEY, normalized);
    return true;
  } catch {
    return false;
  }
}

export function localeSurfaceFromPathname(pathname) {
  return SURFACE_FILES[pathnameFile(pathname)]?.surface ?? 'index';
}

export function localeFromPathname(pathname, fallback = DEFAULT_LOCALE) {
  return SURFACE_FILES[pathnameFile(pathname)]?.locale ?? normalizeLocale(fallback);
}

export function isNeutralLocaleEntry(pathname) {
  return SURFACE_FILES[pathnameFile(pathname)]?.neutral === true;
}

export function resolveLocalePreference({
  pathname = '/',
  currentLocale = DEFAULT_LOCALE,
  queryChoice = null,
  storedChoice = null,
  languages = [],
} = {}) {
  const current = normalizeLocale(currentLocale);
  const explicit = normalizeLocalePreference(queryChoice);
  const stored = normalizeLocalePreference(storedChoice);
  let choice;
  let locale;
  let source;

  if (explicit) {
    choice = explicit;
    locale = explicit === 'auto' ? matchSupportedLocale(languages) : explicit;
    source = 'query';
  } else if (isNeutralLocaleEntry(pathname) && current === DEFAULT_LOCALE) {
    choice = stored ?? 'auto';
    locale = choice === 'auto' ? matchSupportedLocale(languages) : choice;
    source = stored ? 'storage' : 'browser';
  } else {
    choice = RELEASED_LOCALES.includes(current) ? current : null;
    locale = current;
    source = 'explicit-surface';
  }

  const resolved = normalizeLocale(locale);
  return Object.freeze({
    choice,
    locale: resolved,
    source,
    shouldRedirect: resolved !== current,
  });
}

export function localeNavigationUrl({
  currentHref,
  documentBase,
  surface,
  targetLocale,
  choice,
}) {
  const current = new URL(currentHref);
  const normalizedTarget = supportedLocale(targetLocale) ?? DEFAULT_LOCALE;
  const target = new URL(localeSwitchHref(normalizedTarget, surface), documentBase ?? currentHref);
  target.search = current.search;
  target.searchParams.set(
    UI_LOCALE_QUERY_PARAMETER,
    normalizeLocalePreference(choice) ?? normalizedTarget,
  );
  target.hash = current.hash;
  return target.href;
}

function effectiveLanguageLabel(locale, interfaceLocale) {
  const entry = LOCALE_REGISTRY[locale] ?? LOCALE_REGISTRY[DEFAULT_LOCALE];
  if (normalizeLocale(interfaceLocale) === 'de') {
    return `Aktive Sprache: ${entry.native_name}`;
  }
  return `Effective language: ${entry.english_name}`;
}

function reflectLocaleControl(documentRef, choice, locale) {
  const normalizedChoice = normalizeLocalePreference(choice);
  const interfaceLocale = documentLocale(documentRef);
  for (const link of documentRef.querySelectorAll('[data-locale-choice]')) {
    if (normalizedChoice && link.dataset.localeChoice === normalizedChoice) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  for (const control of documentRef.querySelectorAll('.language-switch')) {
    control.dataset.effectiveLocale = locale;
  }
  for (const status of documentRef.querySelectorAll('[data-locale-effective]')) {
    if (!CANDIDATE_LOCALES.includes(interfaceLocale)) {
      status.textContent = effectiveLanguageLabel(locale, interfaceLocale);
    }
  }
}

export function initializeLocalePreference({
  windowRef = globalThis.window,
  documentRef = globalThis.document,
} = {}) {
  if (!windowRef?.location || !documentRef?.documentElement) return null;

  const currentUrl = new URL(windowRef.location.href);
  const currentLocale = documentLocale(documentRef);
  const queryChoice = normalizeLocalePreference(currentUrl.searchParams.get(UI_LOCALE_QUERY_PARAMETER));
  const storedChoice = readStoredLocalePreference();
  if (queryChoice) writeStoredLocalePreference(queryChoice);

  const resolution = resolveLocalePreference({
    pathname: currentUrl.pathname,
    currentLocale,
    queryChoice,
    storedChoice,
    languages: windowRef.navigator?.languages ?? [],
  });
  const surface = documentRef.querySelector('.language-switch')?.dataset.localeSurface
    ?? localeSurfaceFromPathname(currentUrl.pathname);

  if (resolution.shouldRedirect) {
    const target = localeNavigationUrl({
      currentHref: currentUrl.href,
      documentBase: documentRef.baseURI,
      surface,
      targetLocale: resolution.locale,
      choice: resolution.choice,
    });
    if (target !== currentUrl.href) {
      windowRef.location.replace(target);
      return Object.freeze({ ...resolution, redirected: true, target });
    }
  }

  reflectLocaleControl(documentRef, resolution.choice, resolution.locale);
  for (const link of documentRef.querySelectorAll('[data-locale-choice]')) {
    link.addEventListener('click', (event) => {
      const choice = normalizeLocalePreference(link.dataset.localeChoice);
      if (!choice) return;
      event.preventDefault();
      writeStoredLocalePreference(choice);
      const targetLocale = choice === 'auto'
        ? matchSupportedLocale(windowRef.navigator?.languages ?? [])
        : choice;
      const target = localeNavigationUrl({
        currentHref: windowRef.location.href,
        documentBase: documentRef.baseURI,
        surface: link.dataset.localeSurface ?? surface,
        targetLocale,
        choice,
      });
      windowRef.location.assign(target);
    });
  }

  return Object.freeze({ ...resolution, redirected: false, target: currentUrl.href });
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  initializeLocalePreference();
}
