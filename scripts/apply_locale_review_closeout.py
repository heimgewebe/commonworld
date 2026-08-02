#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, *, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} occurrences, found {actual}: {old[:120]!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


def insert_before(path: str, marker: str, addition: str) -> None:
    replace_exact(path, marker, addition + marker)


# 1. Proposal privacy: detect locale-independent DMS tuples while avoiding the
# English verb "coordinates" as a standalone false positive.
replace_exact(
    "assets/commonworld-proposal.js",
    'const SENSITIVE_CONTEXT_PATTERN = /(?:^|[^\\p{L}\\p{N}])(?:latitude|longitude|coordinates?|coordonnées?|coordenadas?|gps|الإحداثيات|احداثيات|خط\\s+العرض|خط\\s+الطول)(?=$|[^\\p{L}\\p{N}])/iu;\n',
    'const SENSITIVE_CONTEXT_PATTERN = /(?:^|[^\\p{L}\\p{N}])(?:latitude|longitude|gps(?:\\s+coordinates?)?|coordonnées?|coordenadas?|الإحداثيات|احداثيات|خط\\s+العرض|خط\\s+الطول)(?=$|[^\\p{L}\\p{N}])/iu;\n',
)
replace_exact(
    "assets/commonworld-proposal.js",
    'const DMS_COORDINATE_PATTERN = /\\p{Nd}{1,3}\\s*°\\s*\\p{Nd}{1,2}\\s*[′\']\\s*\\p{Nd}{1,2}(?:[.,\\u066B]\\p{Nd}+)?\\s*(?:[″"]|[′\']{2})\\s*[NS](?:\\s*[,،;]\\s*|\\s+)\\p{Nd}{1,3}\\s*°\\s*\\p{Nd}{1,2}\\s*[′\']\\s*\\p{Nd}{1,2}(?:[.,\\u066B]\\p{Nd}+)?\\s*(?:[″"]|[′\']{2})\\s*[EW]/iu;\n',
    '''const DMS_COMPONENT = String.raw`\\p{Nd}{1,3}\\s*°\\s*\\p{Nd}{1,2}\\s*[′'’]\\s*\\p{Nd}{1,2}(?:[.,\\u066B]\\p{Nd}+)?\\s*(?:[″"“”]|[′'’]{2})`;
const DMS_LATITUDE_DIRECTION = String.raw`(?:N|S|north|south|nord|sud|norte|sur|sul|شمال|جنوب)`;
const DMS_LONGITUDE_DIRECTION = String.raw`(?:E|W|O|east|west|est|ouest|este|oeste|leste|شرق|غرب)`;
const DMS_PAIR_SEPARATOR = String.raw`(?:\\s*[,،;]\\s*|\\s+)`;
const DMS_COORDINATE_PATTERN = new RegExp(
  String.raw`${DMS_COMPONENT}(?:\\s*${DMS_LATITUDE_DIRECTION})?${DMS_PAIR_SEPARATOR}${DMS_COMPONENT}(?:\\s*${DMS_LONGITUDE_DIRECTION})?`,
  'iu',
);
''',
)
replace_exact(
    "scripts/validate_proposal_path.py",
    'SENSITIVE_CONTEXT_PATTERN = re.compile(r"(?:^|[^\\w])(?:latitude|longitude|coordinates?|coordonnées?|coordenadas?|gps|الإحداثيات|احداثيات|خط\\s+العرض|خط\\s+الطول)(?=$|[^\\w])", re.I)\n',
    'SENSITIVE_CONTEXT_PATTERN = re.compile(r"(?:^|[^\\w])(?:latitude|longitude|gps(?:\\s+coordinates?)?|coordonnées?|coordenadas?|الإحداثيات|احداثيات|خط\\s+العرض|خط\\s+الطول)(?=$|[^\\w])", re.I)\n',
)
replace_exact(
    "scripts/validate_proposal_path.py",
    'DMS_COORDINATE_PATTERN = re.compile(rf"{UNICODE_DECIMAL_DIGIT}{{1,3}}\\s*°\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}\\s*[′\']\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}(?:[.,\\u066B]{UNICODE_DECIMAL_DIGIT}+)?\\s*(?:[″\\"]|[′\']{{2}})\\s*[NS](?:\\s*[,،;]\\s*|\\s+){UNICODE_DECIMAL_DIGIT}{{1,3}}\\s*°\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}\\s*[′\']\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}(?:[.,\\u066B]{UNICODE_DECIMAL_DIGIT}+)?\\s*(?:[″\\"]|[′\']{{2}})\\s*[EW]", re.I)\n',
    '''DMS_COMPONENT = rf"{UNICODE_DECIMAL_DIGIT}{{1,3}}\\s*°\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}\\s*[′'’]\\s*{UNICODE_DECIMAL_DIGIT}{{1,2}}(?:[.,\\u066B]{UNICODE_DECIMAL_DIGIT}+)?\\s*(?:[″\\\"“”]|[′'’]{{2}})"
DMS_LATITUDE_DIRECTION = r"(?:N|S|north|south|nord|sud|norte|sur|sul|شمال|جنوب)"
DMS_LONGITUDE_DIRECTION = r"(?:E|W|O|east|west|est|ouest|este|oeste|leste|شرق|غرب)"
DMS_PAIR_SEPARATOR = r"(?:\\s*[,،;]\\s*|\\s+)"
DMS_COORDINATE_PATTERN = re.compile(
    rf"{DMS_COMPONENT}(?:\\s*{DMS_LATITUDE_DIRECTION})?{DMS_PAIR_SEPARATOR}{DMS_COMPONENT}(?:\\s*{DMS_LONGITUDE_DIRECTION})?",
    re.I,
)
''',
)

fixture_path = ROOT / "tests/fixtures/proposals/sensitive-location-cases.json"
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
blocked_additions = [
    {"id": "ar-dms-native-directions", "value": "٤٨° ٨′ ٠″ شمال، ١١° ٣٤′ ٠″ شرق"},
    {"id": "fa-dms-native-digits", "value": "۴۸° ۸′ ۰″ شمال، ۱۱° ۳۴′ ۰″ شرق"},
    {"id": "fr-dms-words", "value": "48° 8′ 0″ Nord, 11° 34′ 0″ Est"},
    {"id": "es-dms-west-o", "value": "48° 8′ 0″ N, 11° 34′ 0″ O"},
    {"id": "pt-dms-words", "value": "48° 8′ 0″ Norte, 11° 34′ 0″ Leste"},
    {"id": "directionless-dms", "value": "48° 8′ 0″, 11° 34′ 0″"},
]
allowed_additions = [
    {"id": "coordinate-verb", "value": "The network coordinates community repair groups across three regions."},
]
for section, additions in (("blocked", blocked_additions), ("allowed", allowed_additions)):
    existing = {entry["id"] for entry in fixture[section]}
    fixture[section].extend(entry for entry in additions if entry["id"] not in existing)
fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Localize the actual public issue body, not only the visible form.
replace_exact(
    "assets/commonworld-proposal.js",
    '    `**Name:** ${markdown(project.name)}`,\n',
    '    `**${tr("Name", "Name")}:** ${markdown(project.name)}`,\n',
)
replace_exact(
    "assets/commonworld-proposal.js",
    "    `**${tr(\"Präsenz\", \"Presence\")}:** ${project.presence_geographic && project.presence_digital ? tr('Vor Ort und Digital', 'On site and Digital') : (project.presence_geographic ? tr('Geografisch (Vor Ort)', 'Geographic (On site)') : 'Digital')}`,\n",
    "    `**${tr(\"Präsenz\", \"Presence\")}:** ${project.presence_geographic && project.presence_digital ? tr('Vor Ort und Digital', 'On site and Digital') : (project.presence_geographic ? tr('Geografisch (Vor Ort)', 'Geographic (On site)') : tr('Digital', 'Digital'))}`,\n",
)

# 3. Mark candidate bodies explicitly and allocate the banner outside the
# full-height application stage.
replace_exact(
    "scripts/commonworld_i18n.py",
    '''    markup = markup.replace('<body>', '<body>\\n  ' + banner, 1) if '<body>' in markup else re.sub(
        r'<body([^>]*)>', lambda match: match.group(0) + '\\n  ' + banner, markup, count=1
    )
    return markup
''',
    '''    def decorate_body(match: re.Match[str]) -> str:
        attributes = match.group(1)
        return f'<body{attributes} data-locale-candidate="{normalized}">\\n  {banner}'

    markup, body_count = re.subn(r'<body([^>]*)>', decorate_body, markup, count=1)
    if body_count != 1:
        raise ValueError(f"candidate locale {normalized} surface lacks one body element")
    return markup
''',
)
replace_exact(
    "index.css",
    '''/* Locale candidates and bidirectional layout */
.locale-candidate-banner {
  position: relative;
  z-index: 20;
  margin: 0;
  padding: 0.65rem max(1rem, env(safe-area-inset-right)) 0.65rem max(1rem, env(safe-area-inset-left));
  border-block-end: 1px solid var(--line);
  background: var(--panel);
  color: var(--muted);
  font-size: 0.9rem;
  text-align: start;
}
''',
    '''/* Locale candidates and bidirectional layout */
body[data-locale-candidate][data-presentation] {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100dvh;
  min-height: 100dvh;
}

body[data-locale-candidate][data-presentation] .app-shell {
  position: relative;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

body[data-locale-candidate][data-presentation] .topbar {
  position: absolute;
}

body[data-locale-candidate][data-presentation] .globe-surface,
body[data-locale-candidate][data-presentation] .globe-stage {
  min-height: 0;
  height: 100%;
}

body[data-locale-candidate][data-presentation] .text-view {
  min-height: 0;
  max-height: 100%;
  overflow: auto;
}

.locale-candidate-banner {
  position: relative;
  z-index: 60;
  margin: 0;
  padding: 0.65rem max(1rem, env(safe-area-inset-right)) 0.65rem max(1rem, env(safe-area-inset-left));
  border-block-end: 1px solid var(--line);
  background: var(--surface-solid);
  color: var(--muted);
  font-size: 0.9rem;
  text-align: start;
}
''',
)

# 4. Carry per-link label language through localization and apply it in the
# dynamic focus renderer. The CSS isolation prevents RTL punctuation/host drift.
replace_exact(
    "assets/commonworld-i18n.mjs",
    '''function localizeLink(link, locale) {
  const normalized = normalizeLocale(locale);
  if (normalized === 'de') return link;
  const type = String(link?.type ?? '');
  return ACTION_LABEL_KEYS[type] ? { ...link, label: actionLabel(type, normalized) } : link;
}

function localizeSource(source, contentLocale, index) {
  if (contentLocale !== 'en') return source;
  const host = hostLabel(source?.url ?? '');
  const canonicalLabel = String(source?.label ?? '').trim();
  return { ...source, label: canonicalLabel ? `${canonicalLabel} · ${host}` : `${text('en', 'source', 'Quelle')} ${index + 1} · ${host}` };
}
''',
    '''function localizeLink(link, locale, contentLocale) {
  const normalized = normalizeLocale(locale);
  if (normalized === 'de') return link;
  const type = String(link?.type ?? '');
  if (ACTION_LABEL_KEYS[type]) {
    return { ...link, label: actionLabel(type, normalized), _label_locale: normalized };
  }
  return contentLocale ? { ...link, _label_locale: contentLocale } : link;
}

function localizeSource(source, contentLocale, index) {
  if (contentLocale !== 'en') return source;
  const host = hostLabel(source?.url ?? '');
  const canonicalLabel = String(source?.label ?? '').trim();
  return {
    ...source,
    label: canonicalLabel ? `${canonicalLabel} · ${host}` : `${text('en', 'source', 'Quelle')} ${index + 1} · ${host}`,
    _label_locale: 'en',
  };
}
''',
)
replace_exact(
    "assets/commonworld-i18n.mjs",
    "      links: Array.isArray(record.links) ? record.links.map((link) => localizeLink(link, normalized)) : record.links,\n",
    "      links: Array.isArray(record.links) ? record.links.map((link) => localizeLink(link, normalized, contentLocale)) : record.links,\n",
)
replace_exact(
    "assets/commonworld-app.js",
    '''function replaceLinks(container, links) {
  container.replaceChildren();
  for (const link of links) {
    const url = safeExternalHttpsUrl(link?.url);
    if (!url || !url.startsWith('https://')) continue;
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.rel = 'external noreferrer';
    anchor.textContent = link.label || url;
    item.append(anchor);
    container.append(item);
  }
}
''',
    '''function replaceLinks(container, links) {
  container.replaceChildren();
  for (const link of links) {
    const url = safeExternalHttpsUrl(link?.url);
    if (!url || !url.startsWith('https://')) continue;
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.rel = 'external noreferrer';
    anchor.textContent = link.label || url;
    const labelLocale = typeof link?._label_locale === 'string' && link._label_locale.trim()
      ? link._label_locale
      : null;
    applyContentLanguage(anchor, labelLocale);
    if (labelLocale) anchor.dataset.contentLanguage = labelLocale;
    item.append(anchor);
    container.append(item);
  }
}
''',
)
insert_before(
    "index.css",
    "html[dir=\"rtl\"] body {\n",
    '''#focus-links a[data-content-language],
#focus-sources a[data-content-language] {
  unicode-bidi: isolate;
}

''',
)

# 5. Make the released-locale matcher future-safe for region-tag releases.
replace_exact(
    "assets/commonworld-locale.mjs",
    '''export function supportedLocale(value) {
  const canonical = canonicalLocaleTag(value);
  if (!canonical) return null;
  const exact = RELEASED_LOCALES.find((tag) => tag.toLowerCase() === canonical.toLowerCase());
  if (exact) return exact;
  const parts = canonical.split('-');
  if (parts.length >= 2 && parts[1].length === 4) {
    const languageScript = parts.slice(0, 2).join('-').toLowerCase();
    const scriptMatch = RELEASED_LOCALES.find((tag) => tag.toLowerCase() === languageScript);
    if (scriptMatch) return scriptMatch;
  }
  const primary = parts[0].toLowerCase();
  return RELEASED_LOCALES.find((tag) => tag.toLowerCase() === primary) ?? null;
}
''',
    '''export function matchSupportedLocaleTag(value, supportedLocales = RELEASED_LOCALES) {
  const canonical = canonicalLocaleTag(value);
  if (!canonical) return null;
  const allowed = Array.isArray(supportedLocales) ? supportedLocales : RELEASED_LOCALES;
  const exact = allowed.find((tag) => tag.toLowerCase() === canonical.toLowerCase());
  if (exact) return exact;
  const parts = canonical.split('-');
  if (parts.length >= 2 && parts[1].length === 4) {
    const languageScript = parts.slice(0, 2).join('-').toLowerCase();
    const scriptMatch = allowed.find((tag) => tag.toLowerCase() === languageScript);
    if (scriptMatch) return scriptMatch;
  }
  const primary = parts[0].toLowerCase();
  return allowed.find((tag) => tag.split('-')[0].toLowerCase() === primary) ?? null;
}

export function supportedLocale(value) {
  return matchSupportedLocaleTag(value);
}
''',
)
(ROOT / "tests/js/locale-preference.test.mjs").write_text(
    '''import test from 'node:test';
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
''',
    encoding="utf-8",
)

# 6. Extend the candidate browser contract: actual issue-body localization,
# focus-link language boundaries and non-overlapping banner geometry.
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''      let proposalRuntimeError = '';
      let proposalDigitalLabel = '';
      if (pageName.startsWith('propose.')) {
''',
    '''      let proposalRuntimeError = '';
      let proposalDigitalLabel = '';
      let proposalIssueBody = '';
      if (pageName.startsWith('propose.')) {
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''        assert(!proposalRuntimeError.includes('[missing:proposal_runtime:'), `${pageName}: proposal runtime fallback marker rendered`);
      }
''',
    '''        assert(!proposalRuntimeError.includes('[missing:proposal_runtime:'), `${pageName}: proposal runtime fallback marker rendered`);
        proposalIssueBody = await page.evaluate(async () => {
          const moduleScript = [...document.scripts].find((script) => script.src.includes('/assets/commonworld-proposal.js'));
          if (!moduleScript?.src) throw new Error('candidate proposal module script is missing');
          const proposalModule = await import(moduleScript.src);
          const proposal = proposalModule.proposalFromFields({
            name: 'Candidate Issue Body Commons',
            description: 'A community-managed resource with open rules, primary-near sources and a real public participation path.',
            official_website: 'https://example.net/commons',
            commons_type: 'other',
            presence_geographic: false,
            presence_digital: true,
            region: '',
            actions: [{ type: 'learn', url: 'https://example.net/commons/about' }, { type: '', url: '' }, { type: '', url: '' }],
            sources: 'https://example.net/commons/governance',
            sensitive_location_risk: false,
            editorial_note: '',
            public_issue_acknowledged: true,
            processing_agreed: true,
            no_sensitive_data_confirmed: true,
          }, new Date('2026-08-02T00:00:00Z'));
          return proposalModule.buildIssueBody(proposal);
        });
        const expectedName = CANDIDATE_SOURCE.locales[candidate.locale].proposal_runtime.Name;
        assert(proposalIssueBody.includes(`**${expectedName}:**`), `${pageName}: localized Name label missing from issue body: ${proposalIssueBody}`);
        assert(proposalIssueBody.includes(proposalDigitalLabel), `${pageName}: localized Digital value missing from issue body: ${proposalIssueBody}`);
        assert(!proposalIssueBody.includes('**Name:**'), `${pageName}: hardcoded English Name leaked into issue body`);
      }
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''          const focusDigitalDir = focusDigital?.getAttribute('dir') ?? '';
          const semanticLevelNode = document.querySelector('#semantic-level');
''',
    '''          const focusDigitalDir = focusDigital?.getAttribute('dir') ?? '';
          const focusLinkNodes = [...document.querySelectorAll('#focus-links a')];
          const focusSourceNodes = [...document.querySelectorAll('#focus-sources a')];
          const focusLinkLangs = focusLinkNodes.map((node) => node.getAttribute('lang') ?? '');
          const focusLinkDirs = focusLinkNodes.map((node) => node.getAttribute('dir') ?? '');
          const focusLinkBidi = focusLinkNodes.map((node) => getComputedStyle(node).unicodeBidi);
          const focusSourceLangs = focusSourceNodes.map((node) => node.getAttribute('lang') ?? '');
          const focusSourceDirs = focusSourceNodes.map((node) => node.getAttribute('dir') ?? '');
          const focusSourceBidi = focusSourceNodes.map((node) => getComputedStyle(node).unicodeBidi);
          const semanticLevelNode = document.querySelector('#semantic-level');
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''            focusDigitalText,
            focusDigitalLang,
            focusDigitalDir,
            semanticLevelText,
''',
    '''            focusDigitalText,
            focusDigitalLang,
            focusDigitalDir,
            focusLinkLangs,
            focusLinkDirs,
            focusLinkBidi,
            focusSourceLangs,
            focusSourceDirs,
            focusSourceBidi,
            semanticLevelText,
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''      const state = await page.evaluate(() => ({
''',
    '''      const shellLayouts = [];
      if (pageName === `${candidate.locale}.html`) {
        for (const viewport of [{ width: 1024, height: 768 }, { width: 390, height: 844 }]) {
          await page.setViewportSize(viewport);
          await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          shellLayouts.push(await page.evaluate(() => {
            const banner = document.querySelector('.locale-candidate-banner');
            const topbar = document.querySelector('.topbar');
            const stage = document.querySelector('.globe-stage');
            const bannerRect = banner?.getBoundingClientRect();
            const topbarRect = topbar?.getBoundingClientRect();
            const stageRect = stage?.getBoundingClientRect();
            const visibleBottomControls = [...document.querySelectorAll('.orientation-bar, .maplibregl-ctrl-bottom-left, .maplibregl-ctrl-bottom-right')]
              .filter((node) => node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden');
            const bottomControlBottom = visibleBottomControls.reduce(
              (maximum, node) => Math.max(maximum, node.getBoundingClientRect().bottom),
              0,
            );
            const hit = bannerRect
              ? document.elementFromPoint((bannerRect.left + bannerRect.right) / 2, (bannerRect.top + bannerRect.bottom) / 2)
              : null;
            return {
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              candidateMarker: document.body.dataset.localeCandidate ?? '',
              bannerHit: Boolean(banner && hit && banner.contains(hit)),
              bannerBottom: bannerRect?.bottom ?? -1,
              topbarTop: topbarRect?.top ?? -1,
              stageBottom: stageRect?.bottom ?? -1,
              bottomControlBottom,
              documentHeight: document.documentElement.scrollHeight,
            };
          }));
        }
      }
      const state = await page.evaluate(() => ({
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''        bannerVisible: Boolean(document.querySelector('.locale-candidate-banner')?.getClientRects().length),
        bodyText: document.body.textContent ?? '',
''',
    '''        bannerVisible: Boolean(document.querySelector('.locale-candidate-banner')?.getClientRects().length),
        candidateMarker: document.body.dataset.localeCandidate ?? '',
        bodyText: document.body.textContent ?? '',
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''      assert(state.bannerVisible, `${pageName}: candidate banner is not visible`);
      assert(state.effectiveLanguage === CANDIDATE_SOURCE.locales[candidate.locale].static.effective_language, `${pageName}: effective-language status drifted: ${state.effectiveLanguage}`);
''',
    '''      assert(state.bannerVisible, `${pageName}: candidate banner is not visible`);
      assert(state.candidateMarker === candidate.locale, `${pageName}: candidate body marker drifted: ${state.candidateMarker}`);
      for (const layout of shellLayouts) {
        assert(layout.candidateMarker === candidate.locale, `${pageName}: shell candidate marker drifted at ${layout.viewportWidth}x${layout.viewportHeight}`);
        assert(layout.bannerHit, `${pageName}: candidate banner is occluded at ${layout.viewportWidth}x${layout.viewportHeight}`);
        assert(layout.topbarTop + 1 >= layout.bannerBottom, `${pageName}: topbar overlaps candidate banner at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        assert(layout.stageBottom <= layout.viewportHeight + 1 && layout.stageBottom >= layout.viewportHeight - 1, `${pageName}: stage is clipped or undersized at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        assert(layout.bottomControlBottom <= layout.viewportHeight + 1, `${pageName}: bottom controls leave the viewport at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
        assert(layout.documentHeight <= layout.viewportHeight + 1, `${pageName}: candidate shell exceeds the viewport at ${layout.viewportWidth}x${layout.viewportHeight}: ${JSON.stringify(layout)}`);
      }
      assert(state.effectiveLanguage === CANDIDATE_SOURCE.locales[candidate.locale].static.effective_language, `${pageName}: effective-language status drifted: ${state.effectiveLanguage}`);
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    '''        assert(runtimeCatalogBoundary?.focusDigitalDir === 'ltr', `${pageName}: focus digital content label lacks dir=ltr boundary`);
        assert((runtimeCatalogBoundary?.sphereNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereNameLangs.every((lang) => lang === 'en'), `${pageName}: sphere ring titles lack lang=en boundaries`);
''',
    '''        assert(runtimeCatalogBoundary?.focusDigitalDir === 'ltr', `${pageName}: focus digital content label lacks dir=ltr boundary`);
        assert((runtimeCatalogBoundary?.focusLinkLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.focusLinkLangs.every((lang) => [candidate.locale, 'en'].includes(lang)), `${pageName}: focus link labels lack explicit language boundaries: ${runtimeCatalogBoundary?.focusLinkLangs?.join(' | ')}`);
        assert(runtimeCatalogBoundary.focusLinkDirs.every((direction, index) => direction === (runtimeCatalogBoundary.focusLinkLangs[index] === 'en' ? 'ltr' : 'auto')), `${pageName}: focus link directions drifted: ${runtimeCatalogBoundary?.focusLinkDirs?.join(' | ')}`);
        assert(runtimeCatalogBoundary.focusLinkBidi.every((value) => value === 'isolate'), `${pageName}: focus link bidi isolation is missing: ${runtimeCatalogBoundary?.focusLinkBidi?.join(' | ')}`);
        assert((runtimeCatalogBoundary?.focusSourceLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.focusSourceLangs.every((lang) => lang === 'en'), `${pageName}: focus source labels lack lang=en boundaries`);
        assert(runtimeCatalogBoundary.focusSourceDirs.every((direction) => direction === 'ltr'), `${pageName}: focus source labels lack dir=ltr boundaries`);
        assert(runtimeCatalogBoundary.focusSourceBidi.every((value) => value === 'isolate'), `${pageName}: focus source bidi isolation is missing`);
        assert((runtimeCatalogBoundary?.sphereNameLangs?.length ?? 0) > 0 && runtimeCatalogBoundary.sphereNameLangs.every((lang) => lang === 'en'), `${pageName}: sphere ring titles lack lang=en boundaries`);
''',
)
replace_exact(
    "scripts/smoke_locale_candidates_browser.mjs",
    "      results.push({ page: pageName, locale: candidate.locale, direction: candidate.direction, proposalRuntimeLocalized: pageName.startsWith('propose.'), proposalDigitalLabel, verdict: 'PASS' });\n",
    "      results.push({ page: pageName, locale: candidate.locale, direction: candidate.direction, proposalRuntimeLocalized: pageName.startsWith('propose.'), proposalDigitalLabel, proposalIssueBodyLocalized: Boolean(proposalIssueBody), verdict: 'PASS' });\n",
)

# Browser-level DMS handoff regression: the public URL/download fallback must
# remain unavailable for a localized exact coordinate.
insert_before(
    "scripts/smoke_proposal_browser.mjs",
    '''{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'مشاع اختبار الهاتف',
''',
    '''{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/propose.ar.html`, { waitUntil: 'networkidle' });
  await fillCandidateValid(page, {
    name: 'مشاع اختبار درجات الموقع',
    description: 'مورد مشترك تديره جماعة محلية وفق قواعد مفتوحة ومصادر رسمية ومسار مشاركة عام موثّق.',
    region: '٤٨° ٨′ ٠″ شمال، ١١° ٣٤′ ٠″ شرق',
  });
  await page.locator('#commons-proposal-form').evaluate((form) => form.requestSubmit());
  const alert = page.getByRole('alert');
  await alert.waitFor();
  const error = (await alert.textContent()) ?? '';
  assert(error.includes('إحداثيات'), `privacy-native-arabic-dms: localized DMS coordinates were not blocked: ${error}`);
  assert(await page.locator('#proposal-direct-link').isHidden(), 'privacy-native-arabic-dms: public issue URL became available');
  assert(await page.locator('#proposal-download').isHidden(), 'privacy-native-arabic-dms: JSON download became available');
  results.push('privacy-native-arabic-dms-fail-closed');
  await context.close();
}

''',
)

print("locale review closeout patch applied")
