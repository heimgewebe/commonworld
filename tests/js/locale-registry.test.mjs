import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CANDIDATE_LOCALES,
  KNOWN_UI_LOCALES,
  RELEASED_LOCALES,
  canonicalLocaleTag,
  localeFromSurfaceFile,
  localeSurfaceHref,
  matchRegistryLocale,
  normalizeReleasedLocale,
} from '../../assets/commonworld-locale-registry.mjs';
import { documentDirection, text } from '../../assets/commonworld-i18n.mjs';

test('registry preserves canonical BCP 47 casing and release states', () => {
  assert.equal(canonicalLocaleTag('PT-br'), 'pt-BR');
  assert.equal(canonicalLocaleTag('AR-arab-eg'), 'ar-Arab-EG');
  assert.deepEqual(RELEASED_LOCALES, ['en', 'de']);
  assert.deepEqual(CANDIDATE_LOCALES, ['es', 'fr', 'pt-BR', 'ar']);
  assert.deepEqual(KNOWN_UI_LOCALES.slice(0, 6), ['en', 'de', 'es', 'fr', 'pt-BR', 'ar']);
});

test('candidate matching is script-aware but cannot activate a candidate as released', () => {
  assert.equal(matchRegistryLocale(['AR-arab-EG'], { statuses: ['candidate'] }), 'ar');
  assert.equal(matchRegistryLocale(['PT-br'], { statuses: ['candidate'] }), 'pt-BR');
  assert.equal(matchRegistryLocale(['fr-CA'], { statuses: ['candidate'] }), 'fr');
  assert.equal(normalizeReleasedLocale('es'), 'en');
});

test('registry drives locale surface names without lowercasing region subtags', () => {
  assert.equal(localeSurfaceHref('PT-br', 'proposal'), './propose.pt-BR.html');
  assert.equal(localeSurfaceHref('ar', 'method'), './method.ar.html');
  assert.equal(localeFromSurfaceFile('method.pt-BR.html'), 'pt-BR');
});

test('candidate runtime strings are complete and Arabic declares RTL', () => {
  assert.equal(text('es', 'show_more', '', { count: 3 }).includes('3'), true);
  assert.equal(text('fr', 'open_project', '', { title: 'OpenStreetMap' }).includes('OpenStreetMap'), true);
  assert.equal(text('pt-BR', 'shown_of_commons', '', { shown: 4, total: 8 }).includes('4'), true);
  assert.equal(text('ar', 'show_more_in_bundle', '', { count: 2, label: 'Open Data' }).includes('Open Data'), true);
  assert.equal(documentDirection('ar'), 'rtl');
  assert.equal(documentDirection('fr'), 'ltr');
});
