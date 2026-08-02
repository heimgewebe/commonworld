import test from 'node:test';
import assert from 'node:assert/strict';

import { matchSupportedLocaleTag, supportedLocale } from '../../assets/commonworld-locale.mjs';

test('current released locale matching remains exact and primary-language aware', () => {
  assert.equal(supportedLocale('de-DE'), 'de');
  assert.equal(supportedLocale('en-GB'), 'en');
  assert.equal(supportedLocale('fr-CA'), null);
});

test('a future region-tag release accepts primary and sibling-region preferences', () => {
  const futureReleased = ['en', 'de', 'pt-BR'];
  assert.equal(matchSupportedLocaleTag('PT-br', futureReleased), 'pt-BR');
  assert.equal(matchSupportedLocaleTag('pt', futureReleased), 'pt-BR');
  assert.equal(matchSupportedLocaleTag('pt-PT', futureReleased), 'pt-BR');
});
