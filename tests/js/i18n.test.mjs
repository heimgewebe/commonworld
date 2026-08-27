import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { BOOTSTRAP_RECORDS } from '../../assets/commonworld-bootstrap-catalog.mjs';
import {
  actionLabel,
  catalogContentLocale,
  RELEASED_LOCALES,
  WAVE1_LOCALES,
  hasThemeLabel,
  loadWave1LocalePacks,
  localizeCatalogRecords,
  normalizeLocale,
  shouldLoadWave1LocalePack,
  taxonomyLabel,
  text,
  themeLabel,
  wave1LocalePackReady,
} from '../../assets/commonworld-i18n.mjs';
import { prepareIntentSearchIndex } from '../../assets/commonworld-core.mjs';

await wave1LocalePackReady;

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

test('Wave-1 translation packages remain loadable after candidate promotion', () => {
  assert.equal(shouldLoadWave1LocalePack('es', false), true);
  assert.equal(shouldLoadWave1LocalePack('fr', false), true);
  assert.equal(shouldLoadWave1LocalePack('pt-BR', false), true);
  assert.equal(shouldLoadWave1LocalePack('ar', false), true);
  assert.equal(shouldLoadWave1LocalePack('zh-Hans', false), true);
  assert.equal(shouldLoadWave1LocalePack('de', false), false);
  assert.equal(shouldLoadWave1LocalePack('de', true), true);
});

test('Wave-1 locale pack loading has a bounded timeout', async () => {
  const startedAt = performance.now();
  await assert.rejects(
    loadWave1LocalePacks({ importer: () => new Promise(() => {}), timeoutMs: 20 }),
    /load timed out/u,
  );
  assert.ok(performance.now() - startedAt < 1_000);
});

test('released Wave-1 locales use their complete catalog presentation packs', () => {
  const english = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'en').records;
  const englishById = new Map(english.map((record) => [record.id, record]));
  for (const locale of WAVE1_LOCALES) {
    assert.equal(catalogContentLocale(locale), locale);
    const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, locale).records;
    assert.equal(localized.length, english.length);
    for (const projectId of ['mundraub', 'common-voice']) {
      const record = localized.find((entry) => entry.id === projectId);
      const englishRecord = englishById.get(projectId);
      assert.ok(record && englishRecord);
      assert.equal(record._content_locale, locale, `${locale}:${projectId}:content-locale`);
      assert.equal(record._title_locale, englishRecord._title_locale, `${locale}:${projectId}:title-locale`);
      assert.equal(record.title, englishRecord.title, `${locale}:${projectId}:proper-name`);
      assert.notEqual(record.summary, englishRecord.summary, `${locale}:${projectId}:summary`);
      if (record.presence.digital?.available === true) {
        assert.notEqual(record.presence.digital.label, englishRecord.presence.digital.label, `${locale}:${projectId}:digital`);
      }
      if (locale === 'ar') assert.match(record.summary, /[\u0600-\u06ff]/u);
    }
    for (const record of localized) {
      assert.equal(record._content_locale, locale, `${locale}:${record.id}`);
      for (const link of record.links ?? []) {
        if (['homepage', 'visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate'].includes(link.type)) {
          assert.equal(link.label, actionLabel(link.type, locale), `${locale}:${record.id}:${link.type}`);
        }
      }
    }
  }
});

test('canonical identity titles without an explicit English overlay remain language-unknown', () => {
  for (const locale of ['en', ...WAVE1_LOCALES]) {
    const record = localizeCatalogRecords(BOOTSTRAP_RECORDS, locale).records.find((entry) => entry.id === 'akiba-mashinani-trust');
    assert.ok(record);
    assert.equal(record._title_locale, null, locale);
  }
});

test('exact Commons counts stay localized on every candidate surface', () => {
  assert.equal(text('es', 'commons_count', '{count} Commons', { count: 4 }), '4 Commons');
  assert.equal(text('fr', 'commons_count', '{count} Commons', { count: 4 }), '4 Communs');
  assert.equal(text('pt-BR', 'commons_count', '{count} Commons', { count: 4 }), '4 Comuns');
  assert.equal(text('ar', 'commons_count', '{count} Commons', { count: 4 }), '4 من المشاعات');
});

test('registry normalizes released and candidate locales', () => {
  assert.equal(normalizeLocale('de-DE'), 'de');
  assert.equal(normalizeLocale('fr'), 'fr');
  assert.equal(normalizeLocale('zh-CN'), 'zh-Hans');
  const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'de');
  assert.notEqual(localized.records, BOOTSTRAP_RECORDS);
  assert.equal(localized.searchAliasesById.size, BOOTSTRAP_RECORDS.length);
  for (const record of localized.records) {
    assert.equal(record._content_locale, 'de');
    assert.equal(record._title_locale, null);
    for (const link of record.links ?? []) {
      const expected = ['homepage', 'visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate'].includes(link.type) ? 'de' : null;
      assert.equal(link._label_locale, expected, `${record.id}:${link.type}`);
    }
    for (const source of record.provenance?.sources ?? []) {
      assert.equal(source._label_locale, 'de');
      assert.match(source.label, /^Quelle \d+ · /u);
    }
  }
});

test('English presentation labels cover actions and digital taxonomy', () => {
  assert.equal(actionLabel('borrow', 'en'), 'Borrow');
  assert.equal(actionLabel('borrow', 'de'), 'Ausleihen');
  assert.equal(taxonomyLabel('free_software', 'en', 'Freie Software und Infrastruktur'), 'Free Software and Infrastructure');
});

test('every catalog theme has an explicit label in every rendered UI locale', () => {
  const catalogThemes = new Set(BOOTSTRAP_RECORDS.flatMap((record) => record.themes ?? []));
  for (const locale of RELEASED_LOCALES) {
    for (const theme of catalogThemes) {
      assert.equal(hasThemeLabel(theme, locale), true, `${locale}:${theme}`);
      assert.ok(!themeLabel(theme, locale).startsWith('[missing:'), `${locale}:${theme}`);
    }
  }
});

test('broad care labels stay distinct from care-work labels in every released locale', () => {
  for (const locale of RELEASED_LOCALES) {
    assert.equal(hasThemeLabel('care', locale), true, `${locale}:care`);
    assert.equal(hasThemeLabel('care-work', locale), true, `${locale}:care-work`);
    assert.notEqual(themeLabel('care', locale), themeLabel('care-work', locale), locale);
  }
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

test('compact bootstrap source links receive localized host-based labels', () => {
  const canonical = BOOTSTRAP_RECORDS.find((record) => record.id === 'debian');
  assert.ok(canonical);
  assert.deepEqual(Object.keys(canonical.provenance.sources[0]).sort(), ['url']);
  const english = localizeCatalogRecords([canonical], 'en').records[0];
  assert.match(english.provenance.sources[0].label, /^Source 1 · debian\.org$/u);
  assert.equal(english.provenance.sources[0]._label_locale, 'en');
  for (const locale of WAVE1_LOCALES) {
    const localized = localizeCatalogRecords([canonical], locale).records[0];
    assert.equal(localized.provenance.sources[0]._label_locale, locale, locale);
    assert.ok(localized.provenance.sources[0].label.includes(' · debian.org'), locale);
    assert.ok(!localized.provenance.sources[0].label.startsWith('https://'), locale);
  }
});

test('compact bootstrap action links derive localized labels without shipping canonical copies', () => {
  const canonical = BOOTSTRAP_RECORDS.find((record) => record.id === 'debian');
  assert.ok(canonical);
  const homepage = canonical.links.find((link) => link.type === 'homepage');
  assert.ok(homepage);
  assert.equal(homepage.label, undefined);
  for (const locale of RELEASED_LOCALES) {
    const localized = localizeCatalogRecords([canonical], locale).records[0];
    const localizedHomepage = localized.links.find((link) => link.type === 'homepage');
    assert.equal(localizedHomepage.label, actionLabel('homepage', locale), locale);
    assert.equal(localizedHomepage._label_locale, normalizeLocale(locale), locale);
  }
});

test('full canonical source labels remain meaningful original-source text', () => {
  const bootstrap = BOOTSTRAP_RECORDS.find((record) => record.id === 'debian');
  assert.ok(bootstrap);
  const canonical = structuredClone(bootstrap);
  canonical.provenance.sources[0].label = 'About Debian';
  const localized = localizeCatalogRecords([canonical], 'en').records[0];
  assert.equal(localized.provenance.sources[0].label, 'About Debian · debian.org');
  assert.equal(localized.provenance.sources[0]._label_locale, null);
});

test('English catalog search remains bilingual through canonical German aliases', () => {
  const { records, searchAliasesById } = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'en');
  const index = prepareIntentSearchIndex(records, { searchAliasesById });

  assert.equal(index.search({ query: 'free operating system', all: true })[0]?.id, 'debian');
  assert.equal(index.search({ query: 'freies betriebssystem', all: true })[0]?.id, 'debian');
  assert.ok(index.search({ query: 'borrow', all: true }).some(({ id }) => id === 'brisbane-tool-library' || id === 'edinburgh-tool-library'));
  assert.equal(index.search({ query: 'private heimrouter', all: true }).length, 0);
});



test('Wave-1 localized search retains English and canonical German discovery aliases', () => {
  for (const locale of WAVE1_LOCALES) {
    const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, locale);
    const index = prepareIntentSearchIndex(localized.records, { searchAliasesById: localized.searchAliasesById });
    assert.equal(index.search({ query: 'free operating system', all: true })[0]?.id, 'debian', `${locale}:english`);
    assert.equal(index.search({ query: 'freies betriebssystem', all: true })[0]?.id, 'debian', `${locale}:german`);
  }
});

test('German catalog search also accepts English translation aliases without hidden-location leakage', () => {
  const localized = localizeCatalogRecords(BOOTSTRAP_RECORDS, 'de');
  const index = prepareIntentSearchIndex(localized.records, { searchAliasesById: localized.searchAliasesById });
  assert.equal(index.search({ query: 'free operating system', all: true })[0]?.id, 'debian');
  assert.ok([...localized.searchAliasesById.values()].every((value) => !value.toLowerCase().includes('private home router')));
});
