import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SELECTABLE_UI_LOCALES,
  UI_LOCALE_CHOICES,
  matchSupportedLocale,
  normalizeLocalePreference,
  resolveLocalePreference,
} from '../../assets/commonworld-locale.mjs';

test('manual language choices include reviewed and preview locales', () => {
  assert.deepEqual(
    [...SELECTABLE_UI_LOCALES],
    ['en', 'de', 'es', 'fr', 'pt-BR', 'ar'],
  );
  assert.deepEqual(
    [...UI_LOCALE_CHOICES],
    ['auto', 'en', 'de', 'es', 'fr', 'pt-BR', 'ar'],
  );
  assert.equal(normalizeLocalePreference('fr-FR'), 'fr');
  assert.equal(normalizeLocalePreference('pt-br'), 'pt-BR');
  assert.equal(normalizeLocalePreference('zh-Hans'), null);
});

test('automatic language matching remains limited to released locales', () => {
  assert.equal(matchSupportedLocale(['fr-FR', 'de-DE']), 'de');
  assert.equal(matchSupportedLocale(['ar', 'en-GB']), 'en');
});

test('manual and direct preview locale navigation keeps the preview choice', () => {
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
