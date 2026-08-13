import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CANDIDATE_LOCALES,
  KNOWN_UI_LOCALES,
  RELEASED_LOCALES,
  WAVE1_LOCALES,
  canonicalLocaleTag,
  localeFromSurfaceFile,
  localeScriptForMatching,
  localeSurfaceHref,
  matchRegistryLocale,
  normalizeReleasedLocale,
} from '../../assets/commonworld-locale-registry.mjs';
import { documentDirection, text, wave1LocalePackReady } from '../../assets/commonworld-i18n.mjs';

await wave1LocalePackReady;

test('registry preserves canonical BCP 47 casing and release states', () => {
  assert.equal(canonicalLocaleTag('PT-br'), 'pt-BR');
  assert.equal(canonicalLocaleTag('AR-arab-eg'), 'ar-Arab-EG');
  assert.equal(canonicalLocaleTag('zh-hans'), 'zh-Hans');
  assert.deepEqual(RELEASED_LOCALES, ['en', 'de', 'es', 'fr', 'pt-BR', 'ar', 'zh-Hans', 'hi']);
  assert.deepEqual(CANDIDATE_LOCALES, []);
  assert.deepEqual(WAVE1_LOCALES, ['es', 'fr', 'pt-BR', 'ar', 'zh-Hans', 'hi']);
  assert.deepEqual(KNOWN_UI_LOCALES.slice(0, 8), ['en', 'de', 'es', 'fr', 'pt-BR', 'ar', 'zh-Hans', 'hi']);
  assert.equal(localeScriptForMatching('zh-Hans'), 'Hans');
  assert.equal(localeScriptForMatching('zh-CN'), 'Hans');
  assert.equal(localeScriptForMatching('zh-SG'), 'Hans');
  assert.equal(localeScriptForMatching('zh-Hant'), 'Hant');
  assert.equal(localeScriptForMatching('zh-TW'), 'Hant');
  assert.equal(localeScriptForMatching('zh-HK'), 'Hant');
  assert.equal(localeScriptForMatching('zh-MO'), 'Hant');
  assert.equal(localeScriptForMatching('pt-BR'), null);
});

test('released Wave-1 matching is script-aware and an empty candidate class fails safely', () => {
  assert.equal(matchRegistryLocale(['AR-arab-EG'], { statuses: ['released'] }), 'ar');
  assert.equal(matchRegistryLocale(['PT-br'], { statuses: ['released'] }), 'pt-BR');
  assert.equal(matchRegistryLocale(['pt-PT'], { statuses: ['released'] }), 'pt-BR');
  assert.equal(matchRegistryLocale(['pt'], { statuses: ['released'] }), 'pt-BR');
  assert.equal(matchRegistryLocale(['fr-CA'], { statuses: ['released'] }), 'fr');
  assert.equal(matchRegistryLocale(['zh-CN'], { statuses: ['released'] }), 'zh-Hans');
  assert.equal(matchRegistryLocale(['zh-SG'], { statuses: ['released'] }), 'zh-Hans');
  assert.equal(matchRegistryLocale(['zh-Hant', 'fr-CA'], { statuses: ['released'] }), 'fr');
  assert.equal(matchRegistryLocale(['zh-TW', 'fr-CA'], { statuses: ['released'] }), 'fr');
  assert.equal(matchRegistryLocale(['zh-HK', 'fr-CA'], { statuses: ['released'] }), 'fr');
  assert.equal(matchRegistryLocale(['zh-MO', 'fr-CA'], { statuses: ['released'] }), 'fr');
  assert.equal(matchRegistryLocale(['hi-IN'], { statuses: ['released'] }), 'hi');
  assert.equal(matchRegistryLocale(['hi'], { statuses: ['released'] }), 'hi');
  assert.equal(matchRegistryLocale(['fr-CA'], { statuses: ['candidate'] }), 'en');
  assert.equal(normalizeReleasedLocale('es'), 'es');
});

test('registry drives locale surface names without lowercasing region subtags', () => {
  assert.equal(localeSurfaceHref('PT-br', 'proposal'), './propose.pt-BR.html');
  assert.equal(localeSurfaceHref('ar', 'method'), './method.ar.html');
  assert.equal(localeFromSurfaceFile('method.pt-BR.html'), 'pt-BR');
  assert.equal(localeSurfaceHref('hi', 'proposal'), './propose.hi.html');
  assert.equal(localeFromSurfaceFile('method.hi.html'), 'hi');
});

test('Wave-1 runtime strings are complete and Arabic declares RTL', () => {
  assert.equal(text('es', 'show_more', '', { count: 3 }).includes('3'), true);
  assert.equal(text('fr', 'open_project', '', { title: 'OpenStreetMap' }).includes('OpenStreetMap'), true);
  assert.equal(text('pt-BR', 'shown_of_commons', '', { shown: 4, total: 8 }).includes('4'), true);
  assert.equal(text('ar', 'show_more_in_bundle', '', { count: 2, label: 'Open Data' }).includes('Open Data'), true);
  assert.equal(documentDirection('ar'), 'rtl');
  assert.equal(text('zh-Hans', 'type_energy', ''), '能源');
  assert.equal(documentDirection('fr'), 'ltr');
  assert.equal(documentDirection('zh-Hans'), 'ltr');
  assert.equal(text('hi', 'type_energy', ''), 'ऊर्जा');
  assert.equal(documentDirection('hi'), 'ltr');
});
