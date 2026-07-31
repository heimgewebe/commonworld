import {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  documentLocale,
  localeSwitchHref,
  normalizeLocale,
} from './commonworld-i18n.mjs?v=196667f2d9af';

export const UI_LOCALE_STORAGE_KEY = 'commonworld.ui-locale';
export const UI_LOCALE_QUERY_PARAMETER = 'ui_lang';
export const UI_LOCALE_CHOICES = Object.freeze(['auto', ...SUPPORTED_LOCALES]);

const SURFACE_FILES = Object.freeze({
  '': Object.freeze({ surface: 'index', locale: 'en', neutral: true }),
  'index.html': Object.freeze({ surface: 'index', locale: 'en', neutral: true }),
  'de.html': Object.freeze({ surface: 'index', locale: 'de', neutral: false }),
  'method.html': Object.freeze({ surface: 'method', locale: 'en', neutral: false }),
  'method.de.html': Object.freeze({ surface: 'method', locale: 'de', neutral: false }),
  'propose.html': Object.freeze({ surface: 'propose', locale: 'en', neutral: false }),
  'propose.de.html': Object.freeze({ surface: 'propose', locale: 'de', neutral: false }),
});

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
  const normalized = String(value ?? '').trim().toLowerCase();
  return UI_LOCALE_CHOICES.includes(normalized) ? normalized : null;
}

export function supportedLocale(value) {
  const primary = String(value ?? '').trim().toLowerCase().split('-')[0];
  return SUPPORTED_LOCALES.includes(primary) ? primary : null;
}

export function matchSupportedLocale(values, fallback = DEFAULT_LOCALE) {
  const candidates = Array.isArray(values) ? values : [];
  for (const candidate of candidates) {
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
    choice = current;
    locale = current;
    source = 'explicit-surface';
  }

  return Object.freeze({
    choice,
    locale: normalizeLocale(locale),
    source,
    shouldRedirect: normalizeLocale(locale) !== current,
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
  const target = new URL(localeSwitchHref(targetLocale, surface), documentBase ?? currentHref);
  target.search = current.search;
  target.searchParams.set(UI_LOCALE_QUERY_PARAMETER, normalizeLocalePreference(choice) ?? targetLocale);
  target.hash = current.hash;
  return target.href;
}

function effectiveLanguageLabel(locale, interfaceLocale) {
  if (normalizeLocale(interfaceLocale) === 'de') {
    return `Aktive Sprache: ${locale === 'de' ? 'Deutsch' : 'Englisch'}`;
  }
  return `Effective language: ${locale === 'de' ? 'German' : 'English'}`;
}

function reflectLocaleControl(documentRef, choice, locale) {
  const normalizedChoice = normalizeLocalePreference(choice) ?? locale;
  for (const link of documentRef.querySelectorAll('[data-locale-choice]')) {
    if (link.dataset.localeChoice === normalizedChoice) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  for (const control of documentRef.querySelectorAll('.language-switch')) {
    control.dataset.effectiveLocale = locale;
  }
  for (const status of documentRef.querySelectorAll('[data-locale-effective]')) {
    status.textContent = effectiveLanguageLabel(locale, documentLocale(documentRef));
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
