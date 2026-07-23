import test from 'node:test';
import assert from 'node:assert/strict';

import { BOOTSTRAP_RECORDS } from '../../assets/commonworld-bootstrap-catalog.mjs';
import {
  actionLabel,
  localizeCatalogRecords,
  normalizeLocale,
  taxonomyLabel,
} from '../../assets/commonworld-i18n.mjs';
import { prepareIntentSearchIndex } from '../../assets/commonworld-core.mjs';

test('English locale overlay preserves canonical identity and factual fields', () => {
  const { records, searchAliasesById } = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'en');
  assert.equal(records.length, BOOTSTRAP_RECORDS.length);
  assert.equal(searchAliasesById.size, BOOTSTRAP_RECORDS.length);

  for (let index = 0; index < records.length; index += 1) {
    const localized = records[index];
    const canonical = BOOTSTRAP_RECORDS[index];
    assert.equal(localized.id, canonical.id);
    assert.deepEqual(localized.curation, canonical.curation);
    assert.deepEqual(localized.activity, canonical.activity);
    assert.deepEqual(
      localized.presence.geographic.map(({ geometry, mode, uncertainty_meters_min }) => ({ geometry, mode, uncertainty_meters_min })),
      canonical.presence.geographic.map(({ geometry, mode, uncertainty_meters_min }) => ({ geometry, mode, uncertainty_meters_min })),
    );
    assert.deepEqual(localized.links.map(({ type, url }) => ({ type, url })), canonical.links.map(({ type, url }) => ({ type, url })));
    assert.deepEqual(localized.provenance.sources.map(({ url }) => ({ url })), canonical.provenance.sources.map(({ url }) => ({ url })));
    assert.notEqual(localized.summary.trim(), '');
  }
});

test('German remains the explicit fallback locale', () => {
  assert.equal(normalizeLocale('de-DE'), 'de');
  assert.equal(normalizeLocale('fr'), 'en');
  const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'de');
  assert.equal(localized.records, BOOTSTRAP_RECORDS);
  assert.equal(localized.searchAliasesById.size, BOOTSTRAP_RECORDS.length);
});

test('English presentation labels cover actions and digital taxonomy', () => {
  assert.equal(actionLabel('borrow', 'en'), 'Borrow');
  assert.equal(actionLabel('borrow', 'de'), 'Ausleihen');
  assert.equal(taxonomyLabel('free_software', 'Freie Software und Infrastruktur', 'en'), 'Free Software and Infrastructure');
});

test('English catalog search remains bilingual through canonical German aliases', () => {
  const { records, searchAliasesById } = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'en');
  const index = prepareIntentSearchIndex(records, { searchAliasesById });

  assert.equal(index.search({ query: 'free operating system', all: true })[0]?.id, 'debian');
  assert.equal(index.search({ query: 'freies betriebssystem', all: true })[0]?.id, 'debian');
  assert.ok(index.search({ query: 'borrow', all: true }).some(({ id }) => id === 'brisbane-tool-library' || id === 'edinburgh-tool-library'));
  assert.equal(index.search({ query: 'private heimrouter', all: true }).length, 0);
});

test('German catalog search also accepts English translation aliases without hidden-location leakage', () => {
  const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'de');
  const index = prepareIntentSearchIndex(localized.records, { searchAliasesById: localized.searchAliasesById });
  assert.equal(index.search({ query: 'free operating system', all: true })[0]?.id, 'debian');
  assert.ok([...localized.searchAliasesById.values()].every((value) => !value.toLowerCase().includes('private home router')));
});
