import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SELECTABLE_UI_LOCALES,
  UI_LOCALE_CHOICES,
  matchSupportedLocale,
  normalizeLocalePreference,
  readStoredLocalePreference,
  resolveLocalePreference,
  writeStoredLocalePreference,
} from '../../assets/commonworld-locale.mjs';
import { RELEASED_LOCALES } from '../../assets/commonworld-locale-registry.mjs';

test('manual language choices include reviewed and preview locales', () => {
  assert.deepEqual(
    [...SELECTABLE_UI_LOCALES],
    [...RELEASED_LOCALES],
  );
  assert.deepEqual(
    [...UI_LOCALE_CHOICES],
    ['auto', ...RELEASED_LOCALES],
  );
  assert.equal(normalizeLocalePreference('fr-FR'), 'fr');
  assert.equal(normalizeLocalePreference('pt-br'), 'pt-BR');
  assert.equal(normalizeLocalePreference('zh-Hans'), 'zh-Hans');
  assert.equal(normalizeLocalePreference('zh-Hant'), null);
});

test('automatic language matching includes every released Wave-1 locale', () => {
  assert.equal(matchSupportedLocale(['fr-FR', 'de-DE']), 'fr');
  assert.equal(matchSupportedLocale(['ar', 'en-GB']), 'ar');
  assert.equal(matchSupportedLocale(['zh-CN', 'fr-FR']), 'zh-Hans');
  assert.equal(matchSupportedLocale(['zh-Hant', 'fr-FR']), 'fr');
  assert.equal(matchSupportedLocale(['zh-TW', 'fr-FR']), 'fr');
});

test('Wave-1 locale choices survive the same bounded storage path as baseline choices', () => {
  const values = new Map();
  const storage = {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
  };
  assert.equal(writeStoredLocalePreference('fr', storage), true);
  assert.equal(readStoredLocalePreference(storage), 'fr');
  assert.equal(writeStoredLocalePreference('zh-Hans', storage), true);
  assert.equal(readStoredLocalePreference(storage), 'zh-Hans');
});

test('manual and direct Wave-1 locale navigation keeps the released choice', () => {
  const manual = resolveLocalePreference({
    pathname: '/index.html',
    currentLocale: 'en',
    queryChoice: 'fr',
    languages: ['de-DE'],
  });
  assert.equal(manual.choice, 'fr');
  assert.equal(manual.locale, 'fr');
  assert.equal(manual.source, 'query');
  assert.equal(manual.shouldRedirect, true);

  const direct = resolveLocalePreference({
    pathname: '/fr.html',
    currentLocale: 'fr',
  });
  assert.equal(direct.choice, 'fr');
  assert.equal(direct.locale, 'fr');
  assert.equal(direct.source, 'explicit-surface');
  assert.equal(direct.shouldRedirect, false);
});
