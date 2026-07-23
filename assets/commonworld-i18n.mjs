import { COMMONWORLD_EN_LOCALE } from './commonworld-en-locale.mjs';

export const SUPPORTED_LOCALES = Object.freeze(['en', 'de']);
export const DEFAULT_LOCALE = 'en';
export const FALLBACK_LOCALE = 'de';

export function normalizeLocale(value) {
  const primary = String(value ?? '').trim().toLowerCase().split('-')[0];
  return SUPPORTED_LOCALES.includes(primary) ? primary : DEFAULT_LOCALE;
}

export function documentLocale(documentRef = globalThis.document) {
  return normalizeLocale(documentRef?.documentElement?.lang ?? DEFAULT_LOCALE);
}

const UI_EN = Object.freeze({
  map_degraded: 'The basemap is temporarily unavailable; the globe state and text view remain available.',
  globe_ready: 'Globe ready. Drag to rotate; pinch or use keys to zoom.',
  globe_loading: 'Loading globe. The text view remains available.',
  catalog_empty: 'The catalog contains no entries.',
  invalid_or_duplicate_id: 'Invalid or duplicate CommonProject ID.',
  no_visible_entries: 'no visible entries',
  open_project: 'Open {title}',
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
  type_other: 'Other'
});

function format(template, variables = {}) {
  return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (_, key) => String(variables[key] ?? `{${key}}`));
}

export function text(locale, key, germanFallback, variables = {}) {
  const normalized = normalizeLocale(locale);
  const template = normalized === 'en' ? (UI_EN[key] ?? germanFallback) : germanFallback;
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
  return text(locale, ACTION_LABEL_KEYS[normalized], fallback);
}

const THEME_LABELS_EN = Object.freeze({
  knowledge: 'Knowledge',
  'open-data': 'Open data',
  research: 'Research',
  documentation: 'Documentation',
  'free-software': 'Free software',
  'open-source': 'Open source',
  infrastructure: 'Infrastructure',
  platform: 'Platform',
  'open-media': 'Open media',
  culture: 'Culture',
  archives: 'Archives',
  'creative-commons': 'Creative Commons',
  education: 'Education',
  'open-educational-resources': 'Open educational resources',
  learning: 'Learning',
  communication: 'Communication',
  'community-network': 'Community network',
  federation: 'Federation',
  protocol: 'Protocol',
  housing: 'Housing',
  'community-land': 'Community land',
  'shared-space': 'Shared space',
  agriculture: 'Agriculture',
  seeds: 'Seeds',
  food: 'Food',
  water: 'Water',
  irrigation: 'Irrigation',
  energy: 'Energy',
  'renewable-energy': 'Renewable energy',
  health: 'Health',
  'open-knowledge': 'Open knowledge',
  'software-infrastructure': 'Software infrastructure',
  'open-hardware': 'Open hardware',
  'distributed-manufacturing': 'Distributed manufacturing',
  'commons-governance': 'Commons governance',
  'cooperative-economy': 'Cooperative economy',
  'community-ownership': 'Community ownership',
  cooperative: 'Cooperative',
  'civic-tech': 'Civic tech',
  network: 'Network',
  'rural-infrastructure': 'Rural infrastructure',
  'digital-equity': 'Digital equity',
  'digital-literacy': 'Digital literacy',
  'environmental-education': 'Environmental education',
  agrobiodiversity: 'Agrobiodiversity',
  'indigenous-knowledge': 'Indigenous knowledge',
  'citizen-science': 'Citizen science',
  music: 'Music',
  'public-domain': 'Public domain',
  'circular-economy': 'Circular economy',
  'tool-sharing': 'Tool sharing',
  repair: 'Repair',
  skills: 'Skills',
  'energy-democracy': 'Energy democracy',
  environment: 'Environment',
  neighbourhood: 'Neighbourhood',
  'mutual-aid': 'Mutual aid',
  'volunteer-community': 'Volunteer community'
});

export function themeLabel(theme, locale = DEFAULT_LOCALE) {
  const value = String(theme ?? '');
  return normalizeLocale(locale) === 'en' ? (THEME_LABELS_EN[value] ?? value.replaceAll('-', ' ')) : value;
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
  const publicLocationLabels = locations.flatMap((location, index) => (
    location?.mode !== 'hidden' && Boolean(location?.geometry)
      ? [translation.geographic_labels?.[index] ?? location?.label]
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
  if (normalizeLocale(locale) !== 'en') return link;
  const type = String(link?.type ?? '');
  return { ...link, label: actionLabel(type, 'en') || link?.label };
}

function localizeSource(source, locale, index) {
  if (normalizeLocale(locale) !== 'en') return source;
  const host = hostLabel(source?.url ?? '');
  return { ...source, label: `${text('en', 'source', 'Quelle')} ${index + 1} · ${host}` };
}

export function localizeCatalogRecords(records, locale = DEFAULT_LOCALE) {
  const normalized = normalizeLocale(locale);
  const sourceRecords = Array.isArray(records) ? records : [];
  const translations = COMMONWORLD_EN_LOCALE.projects ?? {};
  if (normalized !== 'en') {
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
      ? record.presence.geographic.map((location, index) => ({
          ...location,
          label: translation.geographic_labels?.[index] ?? location.label
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
          ? record.provenance.sources.map((source, index) => localizeSource(source, normalized, index))
          : record.provenance.sources
      } : record.provenance
    };
  });
  return Object.freeze({ records: localized, searchAliasesById });
}

export function taxonomyLabel(nodeId, locale = DEFAULT_LOCALE, germanFallback = '') {
  if (normalizeLocale(locale) === 'en') return COMMONWORLD_EN_LOCALE.taxonomy_labels?.[nodeId] ?? germanFallback;
  return germanFallback;
}

export function localeSwitchHref(locale, surface = 'index') {
  const target = normalizeLocale(locale);
  const names = {
    index: target === 'en' ? './' : './de.html',
    method: target === 'en' ? './method.html' : './method.de.html',
    propose: target === 'en' ? './propose.html' : './propose.de.html'
  };
  return names[surface] ?? names.index;
}
