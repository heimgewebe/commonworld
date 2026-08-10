import test from 'node:test';
import assert from 'node:assert/strict';

import {
  UI_LOCALE_STORAGE_KEY,
  isNeutralLocaleEntry,
  localeFromPathname,
  localeNavigationUrl,
  localeSurfaceFromPathname,
  matchSupportedLocale,
  matchSupportedLocaleTag,
  normalizeLocalePreference,
  readStoredLocalePreference,
  resolveLocalePreference,
  supportedLocale,
  writeStoredLocalePreference,
} from '../../assets/commonworld-locale.mjs';

test('ordered browser preferences match supported BCP 47 primary subtags', () => {
  assert.equal(supportedLocale('DE-de'), 'de');
  assert.equal(supportedLocale('en-Latn-GB'), 'en');
  assert.equal(supportedLocale('zh-Hant'), null);
  assert.equal(supportedLocale('zh-CN'), 'zh-Hans');
  assert.equal(supportedLocale('zh-TW'), null);
  assert.equal(matchSupportedLocale(['fr-FR', 'de-DE', 'en-GB']), 'fr');
  assert.equal(matchSupportedLocale(['zh-Hant', 'fr-FR']), 'fr');
});

test('future region-tag release accepts primary and sibling-region preferences', () => {
  const futureReleased = ['en', 'de', 'pt-BR'];
  assert.equal(matchSupportedLocaleTag('PT-br', futureReleased), 'pt-BR');
  assert.equal(matchSupportedLocaleTag('pt', futureReleased), 'pt-BR');
  assert.equal(matchSupportedLocaleTag('pt-PT', futureReleased), 'pt-BR');
});

test('future Chinese region locales participate in script-safe matching', () => {
  assert.equal(matchSupportedLocaleTag('zh-Hant', ['en', 'zh-CN']), null);
  assert.equal(matchSupportedLocaleTag('zh-Hant', ['en', 'zh-TW']), 'zh-TW');
  assert.equal(matchSupportedLocaleTag('zh-HK', ['en', 'zh-TW']), 'zh-TW');
  assert.equal(matchSupportedLocaleTag('zh-CN', ['en', 'zh-TW']), null);
  assert.equal(matchSupportedLocaleTag('zh-SG', ['en', 'zh-Hans']), 'zh-Hans');
});

test('locale preference accepts automatic and all released manual choices', () => {
  assert.equal(normalizeLocalePreference('AUTO'), 'auto');
  assert.equal(normalizeLocalePreference('de'), 'de');
  assert.equal(normalizeLocalePreference('fr'), 'fr');
  assert.equal(normalizeLocalePreference('pt-PT'), 'pt-BR');
  assert.equal(normalizeLocalePreference('zh-Hans'), 'zh-Hans');
  assert.equal(normalizeLocalePreference('zh-Hant'), null);
  assert.equal(normalizeLocalePreference('zh-TW'), null);
});

test('storage failures and corrupt values fail safely', () => {
  const values = new Map();
  const storage = { getItem(key) { return values.get(key) ?? null; }, setItem(key, value) { values.set(key, value); } };
  assert.equal(readStoredLocalePreference(storage), null);
  assert.equal(writeStoredLocalePreference('de', storage), true);
  assert.equal(values.get(UI_LOCALE_STORAGE_KEY), 'de');
  assert.equal(readStoredLocalePreference(storage), 'de');
  values.set(UI_LOCALE_STORAGE_KEY, 'corrupt');
  assert.equal(readStoredLocalePreference(storage), null);
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.equal(readStoredLocalePreference(blocked), null);
  assert.equal(writeStoredLocalePreference('en', blocked), false);
});

test('explicit locale query wins while explicit surface resists stored override', () => {
  assert.deepEqual(resolveLocalePreference({ pathname:'/releases/abc/de.html', currentLocale:'de', queryChoice:'en', storedChoice:'de', languages:['de-DE'] }), { choice:'en', locale:'en', source:'query', shouldRedirect:true });
  assert.deepEqual(resolveLocalePreference({ pathname:'/method.html', currentLocale:'en', storedChoice:'de', languages:['de-DE'] }), { choice:'en', locale:'en', source:'explicit-surface', shouldRedirect:false });
});

test('neutral entry uses stored choice, browser preference, then English', () => {
  assert.deepEqual(resolveLocalePreference({ pathname:'/', currentLocale:'en', storedChoice:'de', languages:['en-GB'] }), { choice:'de', locale:'de', source:'storage', shouldRedirect:true });
  assert.deepEqual(resolveLocalePreference({ pathname:'/index.html', currentLocale:'en', languages:['fr-FR','de-DE'] }), { choice:'auto', locale:'fr', source:'browser', shouldRedirect:true });
  assert.deepEqual(resolveLocalePreference({ pathname:'/', currentLocale:'en', languages:['fr-FR'] }), { choice:'auto', locale:'fr', source:'browser', shouldRedirect:true });
});

test('surface detection covers canonical and immutable release paths', () => {
  assert.equal(isNeutralLocaleEntry('/'), true);
  assert.equal(isNeutralLocaleEntry('/releases/abc/'), true);
  assert.equal(isNeutralLocaleEntry('/de.html'), false);
  assert.equal(localeSurfaceFromPathname('/releases/abc/method.de.html'), 'method');
  assert.equal(localeSurfaceFromPathname('/propose.html'), 'propose');
  assert.equal(localeFromPathname('/releases/abc/de.html'), 'de');
});

test('locale navigation preserves discovery query and fragment state', () => {
  const target = new URL(localeNavigationUrl({ currentHref:'https://example.test/?project=debian&language=de#text-view', documentBase:'https://example.test/releases/release-1/', surface:'index', targetLocale:'de', choice:'de' }));
  assert.equal(target.pathname, '/releases/release-1/de.html');
  assert.equal(target.searchParams.get('project'), 'debian');
  assert.equal(target.searchParams.get('language'), 'de');
  assert.equal(target.searchParams.get('ui_lang'), 'de');
  assert.equal(target.hash, '#text-view');
});
