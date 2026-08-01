import { COMMONWORLD_EN_LOCALE } from './commonworld-en-locale.mjs?v=5326744e6ec9';
import {
  CANDIDATE_LOCALES,
  DEFAULT_LOCALE,
  FALLBACK_LOCALE,
  KNOWN_UI_LOCALES,
  LOCALE_REGISTRY,
  RELEASED_LOCALES,
  canonicalLocaleTag,
  localeEntry,
  localeSurfaceHref,
  matchRegistryLocale,
  normalizeKnownLocale,
  normalizeReleasedLocale,
} from './commonworld-locale-registry.mjs?v=322c888feae3';

export {
  CANDIDATE_LOCALES,
  DEFAULT_LOCALE,
  FALLBACK_LOCALE,
  KNOWN_UI_LOCALES,
  LOCALE_REGISTRY,
  RELEASED_LOCALES,
  canonicalLocaleTag,
  localeEntry,
  matchRegistryLocale,
  normalizeReleasedLocale,
};
export const SUPPORTED_LOCALES = RELEASED_LOCALES;

const runtimeDocumentLocale = canonicalLocaleTag(globalThis.document?.documentElement?.lang);
const nodeRuntime = typeof process !== 'undefined' && Boolean(process?.versions?.node);
let WAVE1_LOCALE_PACKS = Object.freeze({});
if (nodeRuntime || (runtimeDocumentLocale && CANDIDATE_LOCALES.includes(runtimeDocumentLocale))) {
  ({ WAVE1_LOCALE_PACKS } = await import('./commonworld-wave1-locales.mjs?v=00ad225e0849'));
}

export function normalizeLocale(value, fallback = DEFAULT_LOCALE) {
  return normalizeKnownLocale(value, fallback);
}

export function catalogContentLocale(value = DEFAULT_LOCALE) {
  return normalizeLocale(value) === 'de' ? 'de' : 'en';
}

export function documentLocale(documentRef = globalThis.document) {
  return normalizeLocale(documentRef?.documentElement?.lang ?? DEFAULT_LOCALE);
}

export function documentDirection(locale = DEFAULT_LOCALE) {
  return localeEntry(normalizeLocale(locale))?.direction ?? 'ltr';
}

const UI_EN = Object.freeze({
  map_degraded: 'The basemap is temporarily unavailable; the globe state and text view remain available.',
  globe_ready: 'Globe ready. Drag to rotate; pinch or use keys to zoom.',
  globe_loading: 'Loading globe. The text view remains available.',
  catalog_empty: 'The catalog contains no entries.',
  invalid_or_duplicate_id: 'Invalid or duplicate CommonProject ID.',
  no_visible_entries: 'no visible entries',
  visible_ring_commons: 'Visible Commons in the digital rings: {titles}.',
  visible_ring_commons_empty: 'No Commons are currently visible in the digital rings.',
  open_project: 'Open {title}',
  show_project_details: 'Show details for {title}',
  project_preview: 'Preview of {title}',
  project_selected: '{title} selected',
  selection_retained_during_filtering: 'This selection remains open while search or filters change the rest of the view.',
  catalog_detail_loading: 'Catalog details are being verified for this generation.',
  catalog_detail_retrying: 'Catalog details are being verified again.',
  catalog_detail_ready: 'Catalog details for this generation passed integrity verification.',
  catalog_detail_mismatch: 'The verified catalog details differ from the embedded record. The embedded details remain active.',
  catalog_detail_degraded: 'Verified catalog details are currently unavailable. The embedded details remain available.',
  catalog_detail_retry: 'Verify again',
  horizontal_scroll: 'Scroll {label} horizontally',
  shown_of_commons: '{shown} of {total} Commons shown',
  show_more: 'Show {count} more',
  show_more_in_bundle: 'Show {count} more Commons in {label}',
  overview: 'Overview',
  catalog_coverage_unassessed: 'catalog coverage not assessed',
  digital_sphere: 'Digital Commons Sphere',
  sphere: 'Sphere',
  presence_geographic: 'On site',
  presence_digital: 'Digital',
  all_countries: 'All countries',
  country: 'Country',
  published_location: 'Published location',
  show_on_globe: 'Show on globe',
  show_on_globe_aria: 'Show {label} on the globe',
  show_commons: 'Show Commons',
  show_commons_in: 'Show Commons in {label}',
  search_nearby: 'Search nearby',
  search_nearby_aria: 'Search for Commons near {label}',
  geolocation_unsupported: 'Location access is not supported by this browser.',
  geolocation_loading: 'Determining location …',
  geolocation_used: 'Location used · radius {km} km',
  geolocation_denied: 'Location permission was not granted.',
  geolocation_failed: 'Location could not be determined.',
  one_public_location: '1 public location',
  public_locations: '{count} public locations',
  location_independent_digital: 'Location-independent digital presence',
  no_public_geometry: 'No public geometry',
  presence_both: 'On site + digital',
  presence_not_published: 'Presence not published',
  preview_of_commons: '{shown} of {total} Commons previewed',
  all_hits_text: 'Show all {count} results in the text view',
  open: 'Open',
  no_spatial_commons: 'No spatially evidenced public Commons in this selection. Catalog coverage is not assessed.',
  spatial_summary: '{count} spatially evidenced public Commons: {distribution}. Catalog coverage is not assessed; this does not indicate density. Small groups or small filtered remainders of approximate locations are withheld without count or type.',
  more_commons: 'Show {count} more Commons',
  more_commons_aria: 'Show {count} more of {total} Commons',
  digital_presence_published: 'Digital presence published',
  digital_presence_none: 'No digital presence published.',
  relation_chapter_of: 'Part of {title}',
  relation_none: 'No evidenced relationship published.',
  curation_review: 'Editorially reviewed on {reviewed}; next review {next}.',
  unknown: 'unknown',
  open_date: 'open',
  no_matching_commons: 'No Commons match this search or filter selection.',
  current_selection: '{count} Commons in the current selection. {summary}',
  choose_location: 'Choose a published location or use your location.',
  country_filter: 'Country: {label}',
  nearby_radius: 'Radius: {km} km',
  remove_filter: 'Remove {label}',
  sort_hint_default: 'Recommended: The filtered result order is retained.',
  sort_hint_relevance: 'Recommended: Search results are ordered by relevance.',
  sort_hint_distance: 'Recommended: Nearby Commons come first, followed by the newest catalog date.',
  sort_hint_country: 'Recommended: Results in the selected country retain the filtered result order.',
  sort_hint_catalogued: 'New to the catalog: newest catalog date first.',
  sort_hint_reviewed: 'Recently reviewed: newest review date first.',
  sort_hint_title: 'Name A–Z: alphabetical by title.',
  catalog_bootstrap_failed: 'Commonworld could not read the build-bound catalog either.',
  source: 'Source',
  official_website: 'Official website',
  action_visit: 'Visit',
  action_use: 'Use',
  action_borrow: 'Borrow',
  action_learn: 'Learn',
  action_contribute: 'Contribute',
  action_volunteer: 'Volunteer',
  action_donate: 'Donate',
  action_contact: 'Contact',
  action_replicate: 'Replicate',
  action_homepage: 'Official website',
  type_knowledge: 'Knowledge and Data',
  type_software: 'Software and Infrastructure',
  type_culture: 'Culture and Media',
  type_food_seeds: 'Seeds and Food',
  type_water: 'Water and Irrigation',
  type_energy: 'Energy',
  type_housing_land: 'Land and Housing',
  type_health_care: 'Care and Health',
  type_tools_repair: 'Tools, Repair and Making',
  type_community_network: 'Community Network',
  type_other: 'Other',
  activity_unknown_runtime: 'Current operating status has not been verified recently. Sources reviewed on {observed}; priority re-review {next}.',
  location: 'Location',
  location_hidden: 'location hidden',
  location_approximate: 'approximate, at least {uncertainty} uncertainty',
  public_area: 'public area',
  exact_public_point: 'exact public point',
  hidden_location_one: '1 hidden location',
  hidden_locations: '{count} hidden locations',
  earth: 'Earth',
  macroregion: 'Macroregion',
  region: 'Region',
  local_context: 'Local context',
  spatial_evidenced_commons: '{count} spatially evidenced Commons',
  regional_contexts: 'regional contexts',
  public_areas_approximate_locations: 'public areas and approximate locations',
  public_points_areas_relationships: 'public points, areas and relationships'
});

function format(template, variables = {}) {
  return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (_, key) => String(variables[key] ?? `{${key}}`));
}

const warnedMissingUiKeys = new Set();

function missingUi(locale, key) {
  const marker = `${locale}:${key}`;
  if (!warnedMissingUiKeys.has(marker)) {
    warnedMissingUiKeys.add(marker);
    console.warn(`[i18n] missing ${locale} UI key: ${key}`);
  }
  return locale === 'en' ? `[missing:${key}]` : `[missing:${locale}:${key}]`;
}

export function text(locale, key, germanFallback, variables = {}) {
  const normalized = normalizeLocale(locale);
  let template;
  if (normalized === 'de') template = germanFallback;
  else if (normalized === 'en') template = UI_EN[key];
  else template = WAVE1_LOCALE_PACKS[normalized]?.ui?.[key];
  if (typeof template !== 'string' || !template.trim()) return missingUi(normalized, key);
  return format(template, variables);
}

const ACTION_LABEL_KEYS = Object.freeze({
  homepage: 'action_homepage',
  visit: 'action_visit',
  use: 'action_use',
  borrow: 'action_borrow',
  learn: 'action_learn',
  contribute: 'action_contribute',
  volunteer: 'action_volunteer',
  donate: 'action_donate',
  contact: 'action_contact',
  replicate: 'action_replicate'
});

const ACTION_LABELS_DE = Object.freeze({
  homepage: 'Offizielle Seite',
  visit: 'Besuchen',
  use: 'Nutzen',
  borrow: 'Ausleihen',
  learn: 'Lernen',
  contribute: 'Mitmachen',
  volunteer: 'Ehrenamtlich helfen',
  donate: 'Spenden',
  contact: 'Kontaktieren',
  replicate: 'Übertragen'
});

export function actionLabel(action, locale = DEFAULT_LOCALE) {
  const normalized = String(action ?? '');
  const fallback = ACTION_LABELS_DE[normalized] ?? normalized;
  const key = ACTION_LABEL_KEYS[normalized];
  return key ? text(locale, key, fallback) : fallback;
}

const THEME_LABELS_DE = Object.freeze({
  agriculture: 'Landwirtschaft',
  archives: 'Archive',
  agrobiodiversity: 'Agrobiodiversität',
  'basic-services': 'Grundversorgung',
  biodiversity: 'Biodiversität',
  'circular-economy': 'Kreislaufwirtschaft',
  'citizen-science': 'Bürgerwissenschaft',
  'civic-tech': 'Civic Tech',
  'climate-resilience': 'Klimaresilienz',
  'commons-governance': 'Commons-Governance',
  communication: 'Kommunikation',
  'community-finance': 'Gemeinschaftsfinanzierung',
  'community-land': 'Gemeinschaftsland',
  'community-network': 'Gemeinschaftsnetz',
  'community-ownership': 'Gemeinschaftseigentum',
  conservation: 'Naturschutz',
  cooperative: 'Genossenschaft',
  'cooperative-economy': 'Genossenschaftliche Wirtschaft',
  'creative-commons': 'Creative Commons',
  culture: 'Kultur',
  'cultural-heritage': 'Kulturerbe',
  'customary-law': 'Gewohnheitsrecht',
  'digital-equity': 'Digitale Teilhabe',
  'digital-literacy': 'Digitale Kompetenz',
  'distributed-manufacturing': 'Verteilte Fertigung',
  documentation: 'Dokumentation',
  education: 'Bildung',
  energy: 'Energie',
  'energy-democracy': 'Energiedemokratie',
  environment: 'Umwelt',
  'environmental-education': 'Umweltbildung',
  'environmental-justice': 'Umweltgerechtigkeit',
  federation: 'Föderation',
  fisheries: 'Fischerei',
  food: 'Ernährung',
  forest: 'Wald',
  'free-software': 'Freie Software',
  health: 'Gesundheit',
  housing: 'Wohnen',
  'indigenous-knowledge': 'Indigenes Wissen',
  infrastructure: 'Infrastruktur',
  irrigation: 'Bewässerung',
  knowledge: 'Wissen',
  learning: 'Lernen',
  mangroves: 'Mangroven',
  'marine-conservation': 'Meeresschutz',
  music: 'Musik',
  'mutual-aid': 'Gegenseitige Hilfe',
  neighbourhood: 'Nachbarschaft',
  network: 'Netzwerk',
  'open-data': 'Offene Daten',
  'open-educational-resources': 'Offene Bildungsressourcen',
  'open-hardware': 'Offene Hardware',
  'open-knowledge': 'Offenes Wissen',
  'open-media': 'Offene Medien',
  'open-source': 'Open Source',
  platform: 'Plattform',
  protocol: 'Protokoll',
  'public-domain': 'Gemeinfreiheit',
  'renewable-energy': 'Erneuerbare Energie',
  research: 'Forschung',
  repair: 'Reparatur',
  restoration: 'Renaturierung',
  'rural-infrastructure': 'Ländliche Infrastruktur',
  'savings-groups': 'Spargruppen',
  seeds: 'Saatgut',
  'shared-space': 'Geteilter Raum',
  skills: 'Fähigkeiten',
  'software-infrastructure': 'Software-Infrastruktur',
  'tool-sharing': 'Werkzeugteilen',
  'urban-gardening': 'Urbanes Gärtnern',
  'volunteer-community': 'Ehrenamtliche Gemeinschaft',
  'appropriate-technology': 'Angepasste Technologie',
  'care-work': 'Sorgearbeit',
  'community-maintenance': 'Gemeinschaftliche Instandhaltung',
  'customary-governance': 'Traditionelle Selbstverwaltung',
  'forest-conservation': 'Waldschutz',
  'land-commons': 'Land-Commons',
  'local-currency': 'Lokalwährung',
  watershed: 'Wassereinzugsgebiet',
  water: 'Wasser'
});

const THEME_LABELS_EN = Object.freeze({
  agriculture: 'Agriculture',
  archives: 'Archives',
  agrobiodiversity: 'Agrobiodiversity',
  'basic-services': 'Basic services',
  biodiversity: 'Biodiversity',
  'circular-economy': 'Circular economy',
  'citizen-science': 'Citizen science',
  'civic-tech': 'Civic tech',
  'climate-resilience': 'Climate resilience',
  'commons-governance': 'Commons governance',
  communication: 'Communication',
  'community-finance': 'Community finance',
  'community-land': 'Community land',
  'community-network': 'Community network',
  'community-ownership': 'Community ownership',
  conservation: 'Conservation',
  cooperative: 'Cooperative',
  'cooperative-economy': 'Cooperative economy',
  'creative-commons': 'Creative Commons',
  culture: 'Culture',
  'cultural-heritage': 'Cultural heritage',
  'customary-law': 'Customary law',
  'digital-equity': 'Digital equity',
  'digital-literacy': 'Digital literacy',
  'distributed-manufacturing': 'Distributed manufacturing',
  documentation: 'Documentation',
  education: 'Education',
  energy: 'Energy',
  'energy-democracy': 'Energy democracy',
  environment: 'Environment',
  'environmental-education': 'Environmental education',
  'environmental-justice': 'Environmental justice',
  federation: 'Federation',
  fisheries: 'Fisheries',
  food: 'Food',
  forest: 'Forest',
  'free-software': 'Free software',
  health: 'Health',
  housing: 'Housing',
  'indigenous-knowledge': 'Indigenous knowledge',
  infrastructure: 'Infrastructure',
  irrigation: 'Irrigation',
  knowledge: 'Knowledge',
  learning: 'Learning',
  mangroves: 'Mangroves',
  'marine-conservation': 'Marine conservation',
  music: 'Music',
  'mutual-aid': 'Mutual aid',
  neighbourhood: 'Neighbourhood',
  network: 'Network',
  'open-data': 'Open data',
  'open-educational-resources': 'Open educational resources',
  'open-hardware': 'Open hardware',
  'open-knowledge': 'Open knowledge',
  'open-media': 'Open media',
  'open-source': 'Open source',
  platform: 'Platform',
  protocol: 'Protocol',
  'public-domain': 'Public domain',
  'renewable-energy': 'Renewable energy',
  research: 'Research',
  repair: 'Repair',
  restoration: 'Restoration',
  'rural-infrastructure': 'Rural infrastructure',
  'savings-groups': 'Savings groups',
  seeds: 'Seeds',
  'shared-space': 'Shared space',
  skills: 'Skills',
  'software-infrastructure': 'Software infrastructure',
  'tool-sharing': 'Tool sharing',
  'urban-gardening': 'Urban gardening',
  'volunteer-community': 'Volunteer community',
  'appropriate-technology': 'Appropriate technology',
  'care-work': 'Care work',
  'community-maintenance': 'Community maintenance',
  'customary-governance': 'Customary governance',
  'forest-conservation': 'Forest conservation',
  'land-commons': 'Land commons',
  'local-currency': 'Local currency',
  watershed: 'Watershed',
  water: 'Water'
});

export function hasThemeLabel(theme, locale = DEFAULT_LOCALE) {
  const value = String(theme ?? '');
  const normalized = normalizeLocale(locale);
  const labels = normalized === 'en'
    ? THEME_LABELS_EN
    : normalized === 'de'
      ? THEME_LABELS_DE
      : WAVE1_LOCALE_PACKS[normalized]?.themes;
  return Boolean(labels && typeof labels[value] === 'string');
}

export function themeLabel(theme, locale = DEFAULT_LOCALE) {
  const value = String(theme ?? '');
  const normalized = normalizeLocale(locale);
  const labels = normalized === 'en'
    ? THEME_LABELS_EN
    : normalized === 'de'
      ? THEME_LABELS_DE
      : WAVE1_LOCALE_PACKS[normalized]?.themes;
  if (labels && typeof labels[value] === 'string') return labels[value];
  return normalized === 'en' || normalized === 'de' ? value.replaceAll('-', ' ') : `[missing:${normalized}:theme:${value}]`;
}

function hostLabel(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '') || url;
  } catch {
    return url;
  }
}

function canonicalSearchAlias(record) {
  const locations = Array.isArray(record?.presence?.geographic)
    ? record.presence.geographic.filter((location) => location?.mode !== 'hidden' && Boolean(location?.geometry))
    : [];
  const links = Array.isArray(record?.links) ? record.links : [];
  const sources = Array.isArray(record?.provenance?.sources) ? record.provenance.sources : [];
  return [
    record?.title,
    record?.summary,
    record?.presence?.digital?.label,
    ...locations.map((location) => location?.label),
    ...links.map((link) => link?.label),
    ...sources.map((source) => source?.label)
  ].filter(Boolean).join(' ');
}

function englishTranslationSearchAlias(record, translation = {}) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  const publicLocationLabels = locations.flatMap((location) => (
    location?.mode !== 'hidden' && Boolean(location?.geometry)
      ? [translation.geographic_labels?.[location?.id] ?? location?.label]
      : []
  ));
  return [
    translation.title ?? record?.title,
    translation.summary,
    record?.presence?.digital?.available === true ? translation.digital_label : null,
    ...publicLocationLabels,
  ].filter(Boolean).join(' ');
}

function localizeLink(link, locale) {
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

export function localizeCatalogRecords(records, locale = DEFAULT_LOCALE) {
  const normalized = normalizeLocale(locale);
  const contentLocale = catalogContentLocale(normalized);
  const sourceRecords = Array.isArray(records) ? records : [];
  const translations = COMMONWORLD_EN_LOCALE.projects ?? {};
  if (contentLocale !== 'en') {
    const searchAliasesById = new Map(sourceRecords.map((record) => [
      record.id,
      englishTranslationSearchAlias(record, translations[record?.id] ?? {}),
    ]));
    return Object.freeze({ records: sourceRecords, searchAliasesById });
  }
  const searchAliasesById = new Map();
  const localized = sourceRecords.map((record) => {
    const translation = translations[record?.id] ?? {};
    searchAliasesById.set(record.id, canonicalSearchAlias(record));
    const geographic = Array.isArray(record?.presence?.geographic)
      ? record.presence.geographic.map((location) => ({
          ...location,
          label: translation.geographic_labels?.[location?.id] ?? location.label
        }))
      : [];
    const digital = record?.presence?.digital
      ? {
          ...record.presence.digital,
          label: translation.digital_label ?? record.presence.digital.label
        }
      : record?.presence?.digital;
    return {
      ...record,
      _content_locale: 'en',
      title: translation.title ?? record.title,
      summary: translation.summary ?? record.summary,
      presence: {
        ...record.presence,
        geographic,
        digital
      },
      links: Array.isArray(record.links) ? record.links.map((link) => localizeLink(link, normalized)) : record.links,
      provenance: record.provenance ? {
        ...record.provenance,
        sources: Array.isArray(record.provenance.sources)
          ? record.provenance.sources.map((source, index) => localizeSource(source, contentLocale, index))
          : record.provenance.sources
      } : record.provenance
    };
  });
  return Object.freeze({ records: localized, searchAliasesById });
}

export function taxonomyLabel(nodeId, locale = DEFAULT_LOCALE, germanFallback = '') {
  const normalized = normalizeLocale(locale);
  if (normalized === 'en') return COMMONWORLD_EN_LOCALE.taxonomy_labels?.[nodeId] ?? germanFallback;
  if (normalized === 'de') return germanFallback;
  return WAVE1_LOCALE_PACKS[normalized]?.taxonomy?.[nodeId] ?? `[missing:${normalized}:taxonomy:${nodeId}]`;
}

export function localeSwitchHref(locale, surface = 'index') {
  return localeSurfaceHref(locale, surface === 'propose' ? 'proposal' : surface);
}
