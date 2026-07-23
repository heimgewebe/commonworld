import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { BOOTSTRAP_RECORDS } from '../../assets/commonworld-bootstrap-catalog.mjs';
import {
  actionLabel,
  localizeCatalogRecords,
  normalizeLocale,
  taxonomyLabel,
  text,
  themeLabel,
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

test('Theme labels are localized in both public locales instead of leaking raw keys', () => {
  assert.equal(themeLabel('open-data', 'en'), 'Open data');
  assert.equal(themeLabel('open-data', 'de'), 'Offene Daten');
  assert.equal(themeLabel('community-finance', 'de'), 'Gemeinschaftsfinanzierung');
  assert.equal(themeLabel('cultural-heritage', 'en'), 'Cultural heritage');
  assert.equal(themeLabel('research', 'de'), 'Forschung');
  assert.equal(themeLabel('archives', 'en'), 'Archives');
});


test('every static app t() call has an English UI entry', () => {
  const source = readFileSync(new URL('../../assets/commonworld-app.js', import.meta.url), 'utf8');
  const keys = [...source.matchAll(/\bt\('([^']+)'/gu)].map((match) => match[1]);
  assert.ok(keys.length > 0);
  for (const key of new Set(keys)) assert.notEqual(text('en', key, 'fallback'), `[missing:${key}]`, key);
});

test('missing English UI keys fail closed instead of leaking German fallback text', () => {
  assert.equal(text('en', '__missing_test_key__', 'Deutscher Fallback'), '[missing:__missing_test_key__]');
});

test('geographic translations stay bound to location ids when canonical order changes', () => {
  const canonical = BOOTSTRAP_RECORDS.find((record) => record.id === 'fucvam');
  assert.ok(canonical);
  const baseline = localizeCatalogRecords([canonical], 'en').records[0];
  const expected = new Map(baseline.presence.geographic.map((location) => [location.id, location.label]));
  const reordered = {
    ...canonical,
    presence: { ...canonical.presence, geographic: [...canonical.presence.geographic].reverse() },
  };
  const localized = localizeCatalogRecords([reordered], 'en').records[0];
  for (const location of localized.presence.geographic) assert.equal(location.label, expected.get(location.id));
});

test('English localization preserves meaningful canonical source labels', () => {
  const canonical = BOOTSTRAP_RECORDS.find((record) => record.id === 'debian');
  assert.ok(canonical);
  const localized = localizeCatalogRecords([canonical], 'en').records[0];
  assert.match(localized.provenance.sources[0].label, /^About Debian · /u);
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
