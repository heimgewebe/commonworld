import test from 'node:test';
import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import {
  INTENT_SEARCH_CACHE_LIMIT,
  normalizeSearchText,
  prepareIntentSearchIndex,
  recordMatchesIntentFilters,
  searchTokens,
} from '../../assets/commonworld-core.mjs';

const records = [
  {
    id: 'freifunk-hamburg',
    title: 'Freifunk Hamburg',
    summary: 'Gemeinschaftlich getragenes digitales Netz in Hamburg.',
    kind: 'hybrid',
    themes: ['communication', 'community-network', 'infrastructure'],
    actions: ['use', 'learn', 'contribute', 'volunteer', 'contact'],
    languages: { codes: ['de'], source_ids: ['homepage'] },
    access: { type: 'public' },
    presence: {
      geographic: [
        { id: 'community', mode: 'approximate', label: 'Community Hamburg' },
        { id: 'private', mode: 'hidden', label: 'Private Heimrouter' },
      ],
      digital: { available: true, reach: 'regional', label: 'Hamburger Community-Netz' },
    },
    activity: { status: 'active' },
    curation: { state: 'listed', next_review_at: '2026-10-15' },
    links: [{ type: 'use', label: 'Öffentliche Netzkarte', url: 'https://example.test/map' }],
  },
  {
    id: 'le-nid',
    title: 'Le Nid',
    summary: 'Gemeinschaftlich getragener Wohnraum.',
    kind: 'geographic',
    themes: ['housing', 'community-land', 'shared-space'],
    actions: ['visit', 'learn', 'contact', 'replicate'],
    presence: {
      geographic: [{ id: 'entrance', mode: 'exact', label: 'Rue Verheyden 121, Anderlecht' }],
      digital: { available: false },
    },
    activity: { status: 'active' },
    curation: { state: 'listed', next_review_at: '2026-10-15' },
    links: [{ type: 'visit', label: 'Besuchsinformation', url: 'https://example.test/visit' }],
  },
  {
    id: 'debian',
    title: 'Debian',
    summary: 'Freies Betriebssystem.',
    kind: 'digital',
    themes: ['free-software', 'infrastructure'],
    actions: ['use', 'learn', 'contribute', 'donate'],
    presence: { geographic: [], digital: { available: true, reach: 'global', label: 'Weltweite Projektinfrastruktur' } },
    activity: { status: 'active' },
    curation: { state: 'listed', next_review_at: '2026-01-01' },
    links: [{ type: 'homepage', label: 'Offizielle Seite', url: 'https://example.test' }],
  },
];

test('German search normalization folds umlauts, sharp s and punctuation deterministically', () => {
  assert.equal(normalizeSearchText('  Föderierte Größe & Spaß! '), 'foderierte grosse und spass');
  assert.deepEqual(searchTokens('Vor Ort / online'), ['vor', 'ort', 'online']);
});

test('derived intent index finds German actions, themes and public places without hidden-location leakage', () => {
  const index = prepareIntentSearchIndex(records);
  assert.deepEqual(index.search({ query: 'ich möchte mitmachen' }).map(({ id }) => id), ['debian', 'freifunk-hamburg']);
  assert.deepEqual(index.search({ query: 'freie software' }).map(({ id }) => id), ['debian']);
  assert.deepEqual(index.search({ query: 'Anderlecht' }).map(({ id }) => id), ['le-nid']);
  assert.deepEqual(index.search({ query: 'private heimrouter' }).map(({ id }) => id), []);
  assert.deepEqual(index.search({ query: 'wiki' }).map(({ id }) => id), []);
  assert.deepEqual(index.search({ query: 'quantenbanane-xyz' }).map(({ id }) => id), []);
});

test('multiple meaningful query terms intersect and title matches rank deterministically', () => {
  const index = prepareIntentSearchIndex(records);
  assert.deepEqual(index.search({ query: 'mitmachen hamburg' }).map(({ id }) => id), ['freifunk-hamburg']);
  assert.equal(index.search({ query: 'freifunk' })[0].id, 'freifunk-hamburg');
  assert.deepEqual(index.search({ query: 'besuchen lernen' }).map(({ id }) => id), ['le-nid']);
});

test('intent filters preserve identity and treat absent language or access as unknown', () => {
  const index = prepareIntentSearchIndex(records);
  assert.deepEqual(index.search({ filters: { presence: 'hybrid' } }).map(({ id }) => id), ['freifunk-hamburg']);
  assert.deepEqual(index.search({ filters: { action: 'donate' } }).map(({ id }) => id), ['debian']);
  assert.deepEqual(index.search({ filters: { language: 'de' } }).map(({ id }) => id), ['freifunk-hamburg']);
  assert.deepEqual(index.search({ filters: { language: 'unknown' } }).map(({ id }) => id), ['debian', 'le-nid']);
  assert.deepEqual(index.search({ filters: { access: 'public' } }).map(({ id }) => id), ['freifunk-hamburg']);
  assert.deepEqual(index.search({ filters: { freshness: 'stale' }, today: '2026-07-15' }).map(({ id }) => id), ['debian']);
  assert(recordMatchesIntentFilters(records[1], { presence: 'geographic', curation: 'listed' }, '2026-07-15'));
});

test('query cache is bounded and identical searches reuse immutable results', () => {
  const index = prepareIntentSearchIndex(records, { cacheLimit: 3 });
  const first = index.search({ query: 'lernen' });
  assert.equal(index.search({ query: 'lernen' }), first);
  for (const query of ['hamburg', 'debian', 'wohnen', 'spenden']) index.search({ query });
  assert.equal(index.cacheSize(), 3);
  assert(Object.isFrozen(first));
  assert(Object.isFrozen(first[0]));
});

test('one-time index handles fifty thousand identities without per-query catalogue scans', () => {
  const synthetic = Array.from({ length: 50_000 }, (_, position) => ({
    id: 'common-' + String(position).padStart(5, '0'),
    title: 'Commons ' + position,
    summary: position === 49_999 ? 'Ein seltener Leuchtturmbegriff.' : 'Gemeinschaftliche Infrastruktur.',
    kind: 'digital',
    themes: ['infrastructure'],
    actions: ['use'],
    presence: { geographic: [], digital: { available: true, reach: 'global', label: 'Digitale Präsenz' } },
    activity: { status: 'active' },
    curation: { state: 'listed', next_review_at: '2027-01-01' },
    links: [],
  }));
  const started = performance.now();
  const index = prepareIntentSearchIndex(synthetic);
  const buildMs = performance.now() - started;
  const queryStarted = performance.now();
  const result = index.search({ query: 'leuchtturmbegriff' });
  const queryMs = performance.now() - queryStarted;
  assert.equal(index.indexedRecordCount, 50_000);
  assert.deepEqual(result.map(({ id }) => id), ['common-49999']);
  assert(buildMs < 8_000, 'index build unexpectedly slow: ' + buildMs.toFixed(1) + ' ms');
  assert(queryMs < 250, 'indexed query unexpectedly slow: ' + queryMs.toFixed(1) + ' ms');
});

test('borrow remains a first-class German intent and action filter value', () => {
  const lending = [{
    id: 'leihladen',
    title: 'Leihladen',
    summary: 'Gemeinschaftlich Dinge ausleihen.',
    kind: 'geographic',
    themes: ['shared-space'],
    actions: ['borrow'],
    presence: { geographic: [], digital: { available: false } },
    activity: { status: 'active' },
    curation: { state: 'listed', next_review_at: '2027-01-01' },
    links: [],
  }];
  const index = prepareIntentSearchIndex(lending);
  assert.deepEqual(index.search({ query: 'ausleihen' }).map(({ id }) => id), ['leihladen']);
  assert.deepEqual(index.search({ filters: { action: 'borrow' } }).map(({ id }) => id), ['leihladen']);
});

assert.equal(INTENT_SEARCH_CACHE_LIMIT, 128);
