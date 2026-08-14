import { WAVE1_LOCALES, normalizeKnownLocale } from './commonworld-locale-registry.mjs?v=8e456cc3c543';

const ACTIVE_LOCALE = normalizeKnownLocale(
  typeof document !== 'undefined' ? document.documentElement?.lang : 'de',
  'de',
);
const WAVE1_LOCALE_PACK_TIMEOUT_MS = 2_500;
let wave1RuntimeMessages = null;
let wave1RuntimeFallbackToEnglish = false;
if (WAVE1_LOCALES.includes(ACTIVE_LOCALE)) {
  let timeoutId = null;
  try {
    const importPromise = import('./commonworld-wave1-locales.mjs?v=645465a97119');
    const { WAVE1_LOCALE_PACKS } = await Promise.race([
      importPromise,
      new Promise((_, reject) => {
        timeoutId = globalThis.setTimeout(
          () => reject(new Error('proposal locale pack load timed out')),
          WAVE1_LOCALE_PACK_TIMEOUT_MS,
        );
      }),
    ]);
    wave1RuntimeMessages = WAVE1_LOCALE_PACKS?.[ACTIVE_LOCALE]?.proposal_runtime ?? null;
    if (!wave1RuntimeMessages) throw new Error(`missing proposal runtime locale pack: ${ACTIVE_LOCALE}`);
  } catch (error) {
    wave1RuntimeFallbackToEnglish = true;
    const detail = error instanceof Error ? error.message : String(error);
    console.warn(`[i18n] Proposal locale pack unavailable; continuing with English runtime messages. ${detail}`);
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
  }
}

const WAVE1_TEMPLATE_MESSAGES = Object.freeze([
  [/^at most (?<max>\d+) characters\.$/u, 'at most {max} characters.'],
  [/^Suggestion: unknown field (?<key>.+)\.$/u, 'Suggestion: unknown field {key}.'],
  [/^Project: unknown field (?<key>.+)\.$/u, 'Project: unknown field {key}.'],
  [/^Commons basis draft: unknown field (?<key>.+)\.$/u, 'Commons basis draft: unknown field {key}.'],
  [/^Commons basis draft: unknown dimension (?<key>.+)\.$/u, 'Commons basis draft: unknown dimension {key}.'],
]);

function wave1Message(source) {
  if (wave1RuntimeFallbackToEnglish) return source;
  const direct = wave1RuntimeMessages?.[source];
  if (typeof direct === 'string') return direct;
  for (const [pattern, templateKey] of WAVE1_TEMPLATE_MESSAGES) {
    const match = pattern.exec(source);
    const translatedTemplate = wave1RuntimeMessages?.[templateKey];
    if (!match || typeof translatedTemplate !== 'string') continue;
    return translatedTemplate.replace(/\{([A-Za-z_$][\w$]*)\}/gu, (placeholder, name) => match.groups?.[name] ?? placeholder);
  }
  return `[missing:proposal_runtime:${ACTIVE_LOCALE}:${source}]`;
}

const tr = (de, en) => ACTIVE_LOCALE === 'de' ? de : (ACTIVE_LOCALE === 'en' ? en : wave1Message(en));

const MAX = Object.freeze({ name: 140, description: 800, region: 120, note: 500, basis: 800, url: 300 });
const COMMONS_DIMENSIONS = Object.freeze(["shared_good", "community", "rules_and_governance", "stewardship", "legitimacy"]);
const BASIS_CLASSIFICATIONS = new Set(["confirmed", "open", "not_applicable"]);
const ISSUE_BASE = "https://github.com/heimgewebe/commonworld/issues/new";
const RELEASE_NAVIGATION_EVENT = "commonworld:release-navigation";
const RELEASE_DRAFT_KEY = "commonworldProposalReleaseDraftV1";
const RELEASE_DRAFT_MAX_AGE_MS = 5 * 60_000;
const BASIS_DRAFT_SECTION_START = "<!-- commonworld-commons-basis-draft:start -->";
const BASIS_DRAFT_SECTION_END = "<!-- commonworld-commons-basis-draft:end -->";
const SOURCE_REFERENCE_MAP_MARKER = "<!-- commonworld-source-reference-map:v1; source-N=project.sources[N-1] -->";
const ACTION_TYPES = new Set(["visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"]);
const COMMONS_TYPES = new Set(["knowledge", "software", "culture", "food-seeds", "water", "energy", "housing-land", "health-care", "tools-repair", "community-network", "other"]);
const SENSITIVE_CONTEXT_PATTERN = /(?:^|[^\p{L}\p{N}])(?:latitude|longitude|gps(?:\s+coordinates?)?|coordonnées?|coordenadas?|الإحداثيات|احداثيات|خط\s+العرض|خط\s+الطول)(?=$|[^\p{L}\p{N}])/iu;
const DECIMAL_POINT_COORDINATE_PATTERN = /(?:^|[^\p{Nd}])[-+]?\p{Nd}{1,3}[.\u066B]\p{Nd}{3,}\s*[,،;/ ]\s*[-+]?\p{Nd}{1,3}[.\u066B]\p{Nd}{3,}(?:[^\p{Nd}]|$)/u;
const DECIMAL_COMMA_COORDINATE_PATTERN = /(?:^|[^\p{Nd}])[-+]?\p{Nd}{1,3},\p{Nd}{3,}\s*[;/،]\s*[-+]?\p{Nd}{1,3},\p{Nd}{3,}(?:[^\p{Nd}]|$)/u;
const DMS_COMPONENT = String.raw`\p{Nd}{1,3}\s*°\s*\p{Nd}{1,2}\s*[′'’]\s*\p{Nd}{1,2}(?:[.,\u066B]\p{Nd}+)?\s*(?:[″"“”]|[′'’]{2})`;
const DMS_LATITUDE_DIRECTION = String.raw`(?:N|S|north|south|nord|sud|norte|sur|sul|شمال|جنوب)`;
const DMS_LONGITUDE_DIRECTION = String.raw`(?:E|W|O|east|west|est|ouest|este|oeste|leste|شرق|غرب)`;
const DMS_PAIR_SEPARATOR = String.raw`(?:\s*[,،;]\s*|\s+)`;
const DMS_COORDINATE_PATTERN = new RegExp(
  String.raw`${DMS_COMPONENT}(?:\s*${DMS_LATITUDE_DIRECTION})?${DMS_PAIR_SEPARATOR}${DMS_COMPONENT}(?:\s*${DMS_LONGITUDE_DIRECTION})?`,
  'iu',
);
const WORD = String.raw`[\p{L}\p{M}][\p{L}\p{M}'’.-]*`;
const HOUSE_NUMBER = String.raw`\p{Nd}{1,5}[A-Za-z]?(?:[-/]\p{Nd}{1,5}[A-Za-z]?)?`;
const HOUSE_NUMBER_MARKER = String.raw`(?:n(?:[º°o]\.?|\.[º°o])|núm\.?|num\.?|número|numero)`;
const HOUSE_NUMBER_JOIN = String.raw`(?:\s+(?:${HOUSE_NUMBER_MARKER}\s*)?|\s*,\s*(?:${HOUSE_NUMBER_MARKER}\s*)?)`;
const ATTACHED_STREET_SUFFIX = String.raw`(?:straße|strasse|weg|gasse|allee|platz)`;
const STREET_WORD = String.raw`(?:street|road|avenue|boulevard|lane|drive|way|straße|strasse|rue|chemin|place|bd\.?|calle|c/|c\.|avenida|plaza|paseo|carretera|camino|via|viale|corso|rua|r\.|avenida|av\.|avda\.|travessa|trav\.|praça|praca|pça\.|estrada|estr\.|alameda|rodovia|ulica|prospekt|شارع|طريق|جادة|زقاق|ميدان|st\.?|rd\.?|ave\.?|blvd\.?|ln\.?|dr\.?)`;
const ADDRESS_PATTERNS = Object.freeze([
  new RegExp(String.raw`(?:^|[^\p{L}\p{N}])(?:${WORD}\s+){0,5}${WORD}${ATTACHED_STREET_SUFFIX}\s+${HOUSE_NUMBER}(?=$|[^\p{L}\p{N}])`, 'iu'),
  new RegExp(String.raw`(?:^|[^\p{L}\p{N}])(?:${WORD}\s+){1,5}${STREET_WORD}\s+${HOUSE_NUMBER}(?=$|[^\p{L}\p{N}])`, 'iu'),
  new RegExp(String.raw`(?:^|[^\p{L}\p{N}])${STREET_WORD}\s+(?:${WORD}\s+){0,4}${WORD}${HOUSE_NUMBER_JOIN}${HOUSE_NUMBER}(?=$|[^\p{L}\p{N}])`, 'iu'),
  new RegExp(String.raw`(?:^|[^\p{L}\p{N}])${HOUSE_NUMBER}\s+(?:${WORD}\s+){0,5}${STREET_WORD}(?=$|[^\p{L}\p{N}])`, 'iu'),
  new RegExp(String.raw`(?:^|[^\p{L}\p{N}])${HOUSE_NUMBER}\s+${STREET_WORD}\s+(?:${WORD}\s+){0,4}${WORD}(?=$|[^\p{L}\p{N}])`, 'iu'),
]);
const CONTACT_PATTERN = /(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|(?:\+?\p{Nd}[\p{Nd}\s()/.\-]{7,}\p{Nd}))/iu;
const ACTIVE_CONTENT_PATTERN = /(?:<\s*script\b|javascript\s*:|data\s*:\s*text\/html|on(?:error|load|click)\s*=)/iu;

export function normalizeTitle(value) {
  return String(value || "").normalize("NFKC").trim().replace(/\s+/gu, " ").toLocaleLowerCase("de");
}

export function isSafeHttpsUrl(value) {
  if (typeof value !== "string" || value.length < 8 || value.length > MAX.url || ACTIVE_CONTENT_PATTERN.test(value)) return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && Boolean(parsed.hostname) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export function containsSensitiveLocation(value) {
  const normalized = String(value || "").normalize("NFKC");
  return SENSITIVE_CONTEXT_PATTERN.test(normalized)
    || DECIMAL_POINT_COORDINATE_PATTERN.test(normalized)
    || DECIMAL_COMMA_COORDINATE_PATTERN.test(normalized)
    || DMS_COORDINATE_PATTERN.test(normalized)
    || ADDRESS_PATTERNS.some((pattern) => pattern.test(normalized));
}

export function containsContactData(value) {
  return CONTACT_PATTERN.test(String(value || "").normalize("NFKC"));
}

function validateText(errors, field, value, min, max) {
  if (typeof value !== "string" || value.trim().length < min) errors.push(`${field}: ${tr("zu kurz oder fehlt.", "too short or missing.")}`);
  if (typeof value === "string" && value.length > max) errors.push(`${field}: ${tr(`höchstens ${max} Zeichen.`, `at most ${max} characters.`)}`);
  if (typeof value === "string" && ACTIVE_CONTENT_PATTERN.test(value)) errors.push(`${field}: ${tr("aktiver HTML- oder Script-Inhalt ist nicht erlaubt.", "active HTML or script content is not allowed.")}`);
  if (typeof value === "string" && containsContactData(value)) errors.push(`${field}: ${tr("keine E-Mail-Adresse oder Telefonnummer in öffentlichen Vorschlägen.", "no email address or phone number in public suggestions.")}`);
  if (typeof value === "string" && containsSensitiveLocation(value)) errors.push(`${field}: ${tr("keine private Adresse oder Koordinate in öffentlichen Vorschlägen.", "no private address or coordinates in public suggestions.")}`);
}

function dimensionLabel(key) {
  const labels = {
    shared_good: tr("Gemeinsames Gut", "Shared good"),
    community: tr("Gemeinschaft", "Community"),
    rules_and_governance: tr("Regeln und Governance", "Rules and governance"),
    stewardship: tr("Fürsorge und Verantwortung", "Stewardship"),
    legitimacy: tr("Kontextuelle Legitimität", "Contextual legitimacy"),
  };
  return labels[key] || key;
}

function validateCommonsBasisDraft(errors, draft, sources) {
  if (!draft || typeof draft !== "object" || Array.isArray(draft)) {
    errors.push(tr("Commons-Basisentwurf: Angaben ungültig.", "Commons basis draft: information is invalid."));
    return;
  }
  const allowedDraft = new Set(["status", "dimensions"]);
  for (const key of Object.keys(draft)) if (!allowedDraft.has(key)) errors.push(tr(`Commons-Basisentwurf: unbekanntes Feld ${key}.`, `Commons basis draft: unknown field ${key}.`));
  if (draft.status !== "needs_review") errors.push(tr("Commons-Basisentwurf: Status muss needs_review bleiben.", "Commons basis draft: status must remain needs_review."));
  const dimensions = draft.dimensions;
  if (!dimensions || typeof dimensions !== "object" || Array.isArray(dimensions)) {
    errors.push(tr("Commons-Basisentwurf: Dimensionen ungültig.", "Commons basis draft: dimensions are invalid."));
    return;
  }
  const entries = Object.entries(dimensions);
  if (entries.length < 1) errors.push(tr("Commons-Basisentwurf: bei vorhandenem Entwurf ist mindestens eine Dimension erforderlich.", "Commons basis draft: at least one dimension is required when the draft is present."));
  const sourceIds = new Set((Array.isArray(sources) ? sources : []).map((_, index) => `source-${index + 1}`));
  for (const [key, dimension] of entries) {
    if (!COMMONS_DIMENSIONS.includes(key)) {
      errors.push(tr(`Commons-Basisentwurf: unbekannte Dimension ${key}.`, `Commons basis draft: unknown dimension ${key}.`));
      continue;
    }
    const label = dimensionLabel(key);
    if (!dimension || typeof dimension !== "object" || Array.isArray(dimension)) {
      errors.push(`${label}: ${tr("Dimensionsangaben ungültig.", "dimension data is invalid.")}`);
      continue;
    }
    const allowedDimension = new Set(["classification", "text", "refs"]);
    if (Object.keys(dimension).some((name) => !allowedDimension.has(name))) errors.push(`${label}: ${tr("Dimensionsangaben ungültig.", "dimension data is invalid.")}`);
    const classificationIsValid = BASIS_CLASSIFICATIONS.has(dimension.classification);
    if (!classificationIsValid) {
      const hasPartialInput = (typeof dimension.text === "string" && dimension.text.trim().length > 0)
        || (Array.isArray(dimension.refs) && dimension.refs.length > 0);
      const classificationMessage = hasPartialInput && ACTIVE_LOCALE === 'de'
        ? "Belegt, Unklar oder Nicht zutreffend wählen, weil Text oder Quellenverweise eingetragen wurden."
        : (hasPartialInput && ACTIVE_LOCALE === 'en'
          ? "choose Confirmed, Unknown, or Not applicable because text or source references were entered."
          : tr("Belegt, Unklar oder Nicht zutreffend wählen.", "choose Confirmed, Unknown, or Not applicable."));
      errors.push(`${label}: ${classificationMessage}`);
    }
    validateText(errors, label, dimension.text, 0, MAX.basis);
    if (dimension.classification === "confirmed" && (typeof dimension.text !== "string" || dimension.text.trim().length < 20)) errors.push(`${label}: ${tr("belegte Dimensionen benötigen mindestens 20 Zeichen.", "confirmed dimensions need at least 20 characters.")}`);
    if (!Array.isArray(dimension.refs) || dimension.refs.length > 5 || dimension.refs.some((ref) => typeof ref !== "string" || !sourceIds.has(ref))) errors.push(`${label}: ${tr("Quellenverweise müssen zu den aufgeführten Quellen passen.", "source references must match the listed sources.")}`);
    if (Array.isArray(dimension.refs) && new Set(dimension.refs).size !== dimension.refs.length) errors.push(`${label}: ${tr("doppelte Quellenverweise entfernen.", "remove duplicate source references.")}`);
    if (dimension.classification === "confirmed" && (!Array.isArray(dimension.refs) || dimension.refs.length < 1)) errors.push(`${label}: ${tr("belegte Dimensionen benötigen mindestens einen Quellenverweis.", "confirmed dimensions need at least one source reference.")}`);
  }
}

export function validateProposal(proposal, knownTitles = [], knownHosts = []) {
  const errors = [];
  if (!proposal || typeof proposal !== "object" || Array.isArray(proposal)) return [tr("Vorschlag: ungültiges Datenformat.", "Suggestion: invalid data format.")];
  const allowedTop = new Set(["schema_version", "kind", "proposal_id", "submitted_at", "status", "project", "commons_basis_draft", "consent"]);
  for (const key of Object.keys(proposal)) if (!allowedTop.has(key)) errors.push(tr(`Vorschlag: unbekanntes Feld ${key}.`, `Suggestion: unknown field ${key}.`));
  if (proposal.schema_version !== 1 || proposal.kind !== "commonworld_commons_proposal" || proposal.status !== "submitted") errors.push(tr("Vorschlag: Vertragskennung oder Startstatus ungültig.", "Suggestion: contract identity or initial status is invalid."));
  if (!/^cw-[0-9]{8}t[0-9]{6}z-[a-z0-9-]{3,48}$/u.test(String(proposal.proposal_id || ""))) errors.push(tr("Vorschlag: Kennung ungültig.", "Suggestion: identifier is invalid."));
  if (Number.isNaN(Date.parse(String(proposal.submitted_at || "")))) errors.push(tr("Vorschlag: Zeitangabe ungültig.", "Suggestion: timestamp is invalid."));

  const project = proposal.project;
  if (!project || typeof project !== "object" || Array.isArray(project)) return [...errors, tr("Projekt: Angaben fehlen.", "Project: information is missing.")];
  const allowedProject = new Set(["name", "description", "official_website", "commons_type", "presence_geographic", "presence_digital", "region", "actions", "sources", "sensitive_location_risk", "location_precision", "editorial_note"]);
  for (const key of Object.keys(project)) if (!allowedProject.has(key)) errors.push(tr(`Projekt: unbekanntes Feld ${key}.`, `Project: unknown field ${key}.`));
  validateText(errors, tr("Name", "Name"), project.name, 2, MAX.name);
  validateText(errors, tr("Beschreibung", "Description"), project.description, 40, MAX.description);
  if (project.presence_geographic === true) {
    validateText(errors, tr("Region", "Region"), project.region, 2, MAX.region);
    if (project.location_precision !== "country_or_region_only") errors.push(tr("Ortsgenauigkeit: nur Land oder grobe Region ist zulässig.", "Location precision: only a country or broad region is allowed."));
  } else {
    if (Object.prototype.hasOwnProperty.call(project, "region")) errors.push(tr("Region: bei rein digitaler Präsenz nicht angeben.", "Region: do not provide one for digital-only presence."));
    if (Object.prototype.hasOwnProperty.call(project, "location_precision")) errors.push(tr("Ortsgenauigkeit: bei rein digitaler Präsenz nicht angeben.", "Location precision: do not provide it for digital-only presence."));
  }
  if (project.editorial_note) validateText(errors, tr("Redaktioneller Hinweis", "Editorial note"), project.editorial_note, 0, MAX.note);
  if (!isSafeHttpsUrl(project.official_website)) errors.push(tr("Offizielle Website: nur eine gültige HTTPS-Adresse ist erlaubt.", "Official website: only a valid HTTPS address is allowed."));
  if (!COMMONS_TYPES.has(project.commons_type)) errors.push(tr("Commons-Art: unbekannter Wert.", "Commons type: unknown value."));
  if (typeof project.presence_geographic !== "boolean" || typeof project.presence_digital !== "boolean") errors.push(tr("Präsenz: Boolean-Werte erforderlich.", "Presence: Boolean values are required."));
  if (!project.presence_geographic && !project.presence_digital) errors.push(tr("Präsenz: mindestens eine Option (Vor Ort oder Digital) muss gewählt werden.", "Presence: choose at least one option (On site or Digital)."));
  if (typeof project.sensitive_location_risk !== "boolean") errors.push(tr("Sensibilitätsangabe: erforderlich.", "Sensitive-location indication: required."));

  if (!Array.isArray(project.actions) || project.actions.length < 1 || project.actions.length > 3) {
    errors.push(tr("Handlungswege: ein bis drei belegte Wege sind erforderlich.", "Ways to engage: one to three evidenced paths are required."));
  } else {
    const seen = new Set();
    for (const action of project.actions) {
      if (!action || typeof action !== "object" || !ACTION_TYPES.has(action.type) || !isSafeHttpsUrl(action.url)) errors.push(tr("Handlungswege: Typ und HTTPS-Adresse prüfen.", "Ways to engage: check the type and HTTPS address."));
      const key = `${action?.type || ""}|${action?.url || ""}`;
      if (seen.has(key)) errors.push(tr("Handlungswege: Dublette entfernen.", "Ways to engage: remove the duplicate."));
      seen.add(key);
    }
  }
  if (!Array.isArray(project.sources) || project.sources.length < 1 || project.sources.length > 5) {
    errors.push(tr("Quellen: mindestens eine und höchstens fünf primärnahe HTTPS-Quellen angeben.", "Sources: provide at least one and at most five primary-near HTTPS sources."));
  } else {
    const unique = new Set(project.sources);
    if (unique.size !== project.sources.length) errors.push(tr("Quellen: Dubletten entfernen.", "Sources: remove duplicates."));
    if (project.sources.some((url) => !isSafeHttpsUrl(url))) errors.push(tr("Quellen: nur gültige HTTPS-Adressen sind erlaubt.", "Sources: only valid HTTPS addresses are allowed."));
  }

  if (Object.prototype.hasOwnProperty.call(proposal, "commons_basis_draft")) validateCommonsBasisDraft(errors, proposal.commons_basis_draft, project.sources);

  const title = normalizeTitle(project.name);
  if (knownTitles.map(normalizeTitle).includes(title)) errors.push(tr("Dublette: dieser Name ist bereits im öffentlichen Katalog vorhanden.", "Duplicate: this name is already present in the public catalog."));
  if (isSafeHttpsUrl(project.official_website)) {
    const host = new URL(project.official_website).hostname.replace(/^www\./u, "").toLocaleLowerCase("en");
    if (knownHosts.map((value) => String(value).replace(/^www\./u, "").toLocaleLowerCase("en")).includes(host)) errors.push(tr("Dublette: diese offizielle Domain ist bereits im Katalog vorhanden.", "Duplicate: this official domain is already present in the catalog."));
  }
  const consent = proposal.consent;
  if (!consent || consent.public_issue_acknowledged !== true || consent.processing_agreed !== true || consent.no_sensitive_data_confirmed !== true) errors.push(tr("Einwilligung: alle drei Bestätigungen sind erforderlich.", "Consent: all three confirmations are required."));
  return errors;
}

function slug(value) {
  return normalizeTitle(value).replace(/[^a-z0-9äöüß]+/gu, "-").replace(/[ä]/gu, "ae").replace(/[ö]/gu, "oe").replace(/[ü]/gu, "ue").replace(/[ß]/gu, "ss").replace(/^-+|-+$/gu, "").slice(0, 48) || "commons";
}

function isoCompact(date) {
  return date.toISOString().replace(/[-:]/gu, "").replace(/\.\d{3}Z$/u, "Z").toLocaleLowerCase("en");
}

function commonsBasisDraftFromFields(fields) {
  const dimensions = {};
  const source = fields.commons_basis && typeof fields.commons_basis === "object" ? fields.commons_basis : {};
  for (const key of COMMONS_DIMENSIONS) {
    const entry = source[key];
    if (!entry || typeof entry !== "object") continue;
    const classification = String(entry.classification || "");
    const text = String(entry.text || "").trim();
    const refs = Array.isArray(entry.refs) ? entry.refs.map(String) : [];
    if (!classification && !text && refs.length === 0) continue;
    dimensions[key] = { classification, text, refs };
  }
  return Object.keys(dimensions).length ? { status: "needs_review", dimensions } : null;
}

export function proposalFromFields(fields, now = new Date()) {
  const actions = fields.actions.filter((entry) => entry.type || entry.url).map((entry) => ({ type: entry.type, url: entry.url.trim() }));
  const sources = fields.sources.split(/\r?\n/gu).map((value) => value.trim()).filter(Boolean);
  const commonsBasisDraft = commonsBasisDraftFromFields(fields);
  return {
    schema_version: 1,
    kind: "commonworld_commons_proposal",
    proposal_id: `cw-${isoCompact(now)}-${slug(fields.name)}`,
    submitted_at: now.toISOString(),
    status: "submitted",
    project: {
      name: fields.name.trim(),
      description: fields.description.trim(),
      official_website: fields.official_website.trim(),
      commons_type: fields.commons_type,
      presence_geographic: Boolean(fields.presence_geographic),
      presence_digital: Boolean(fields.presence_digital),
      ...(fields.presence_geographic ? {
        region: fields.region.trim(),
        location_precision: "country_or_region_only",
      } : {}),
      actions,
      sources,
      sensitive_location_risk: fields.presence_geographic ? Boolean(fields.sensitive_location_risk) : false,
      ...(fields.editorial_note.trim() ? { editorial_note: fields.editorial_note.trim() } : {}),
    },
    ...(commonsBasisDraft ? { commons_basis_draft: commonsBasisDraft } : {}),
    consent: {
      public_issue_acknowledged: Boolean(fields.public_issue_acknowledged),
      processing_agreed: Boolean(fields.processing_agreed),
      no_sensitive_data_confirmed: Boolean(fields.no_sensitive_data_confirmed),
    },
  };
}

function markdown(value) {
  return String(value).replace(/[\\`*_{}\[\]()#+\-.!|>]/gu, "\\$&").replace(/[<>]/gu, "");
}

function assertPublicHandoffSafe(proposal) {
  const errors = validateProposal(proposal);
  if (errors.length) throw new TypeError(`public issue handoff rejected: ${errors.join(" | ")}`);
}

export function buildIssueBody(proposal) {
  assertPublicHandoffSafe(proposal);
  const project = proposal.project;
  const actionLines = project.actions.map((entry) => `- ${markdown(entry.type)}: ${entry.url}`).join("\n");
  const sourceLines = project.sources.map((url, index) => `- source-${index + 1}: ${url}`).join("\n");
  const basisLines = proposal.commons_basis_draft ? [
    "",
    BASIS_DRAFT_SECTION_START,
    tr("### Optionaler Commons-Basisentwurf", "### Optional Commons basis draft"),
    tr("> Nur redaktionelles Arbeitsmaterial. Keine Punktzahl und keine automatische Aufnahmeentscheidung.", "> Editorial working material only. No score and no automatic admission decision."),
    ...JSON.stringify(proposal.commons_basis_draft, null, 2).split("\n").map((line) => `    ${line}`),
    BASIS_DRAFT_SECTION_END,
  ] : [];
  return [
    tr("## Öffentlicher Commons-Vorschlag", "## Public Commons suggestion"),
    "",
    tr("> Dieser Vorschlag ist ein redaktioneller Kandidat. Er wird nicht automatisch veröffentlicht.", "> This suggestion is an editorial candidate. It is not published automatically."),
    "",
    `**${tr("Vorschlags-ID", "Suggestion ID")}:** \`${proposal.proposal_id}\``,
    `**${tr("Name", "Name")}:** ${markdown(project.name)}`,
    `**${tr("Commons-Art", "Commons type")}:** ${markdown(project.commons_type)}`,
    `**${tr("Präsenz", "Presence")}:** ${project.presence_geographic && project.presence_digital ? tr('Vor Ort und Digital', 'On site and Digital') : (project.presence_geographic ? tr('Geografisch (Vor Ort)', 'Geographic (On site)') : tr('Digital', 'Digital'))}`,
    `**${tr("Grobe Region", "Broad region")}:** ${project.presence_geographic ? markdown(project.region) : tr("nicht zutreffend (nur digital)", "not applicable (digital only)")}`,
    `**${tr("Offizielle Website", "Official website")}:** ${project.official_website}`,
    `**${tr("Möglicherweise sensible Orte", "Potentially sensitive locations")}:** ${project.sensitive_location_risk ? tr("ja – redaktionell besonders prüfen", "yes — apply especially strict editorial review") : tr("nein angegeben", "none indicated")}`,
    "",
    tr("### Kurzbeschreibung", "### Short description"),
    markdown(project.description),
    "",
    tr("### Vorgeschlagene Handlungswege", "### Suggested ways to engage"),
    actionLines,
    "",
    tr("### Primärnahe Quellen", "### Primary-near sources"),
    SOURCE_REFERENCE_MAP_MARKER,
    sourceLines,
    ...(project.editorial_note ? ["", tr("### Redaktioneller Hinweis", "### Editorial note"), markdown(project.editorial_note)] : []),
    ...basisLines,
    "",
    tr("### Bestätigungen", "### Confirmations"),
    tr("- [x] Mir ist bewusst, dass dieses Issue öffentlich ist.", "- [x] I understand that this issue is public."),
    tr("- [x] Ich willige in die redaktionelle Verarbeitung dieser Angaben ein.", "- [x] I consent to editorial processing of this information."),
    tr("- [x] Der Vorschlag enthält keine privaten Adressen, Koordinaten oder Kontaktdaten.", "- [x] The suggestion contains no private addresses, coordinates or contact data."),
    "",
    "<!-- commonworld-proposal-v1; status=submitted; no-auto-publish -->",
  ].join("\n");
}

export function buildIssueUrl(proposal) {
  const params = new URLSearchParams({
    title: `[${tr("Commons-Vorschlag", "Commons suggestion")}] ${proposal.project.name}`,
    body: buildIssueBody(proposal),
    labels: "catalog-candidate,editorial-review",
  });
  return `${ISSUE_BASE}?${params.toString()}`;
}

function downloadJson(proposal) {
  const blob = new Blob([`${JSON.stringify(proposal, null, 2)}\n`], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = `${proposal.proposal_id}.json`;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 1_000);
}

function getCatalogIndex() {
  const node = document.getElementById("proposal-catalog-index");
  try {
    const value = JSON.parse(node?.textContent || "null");
    if (!value || !Array.isArray(value.titles) || !Array.isArray(value.hosts)) return null;
    return value;
  } catch {
    return null;
  }
}

function readLastPreparedAt() {
  try { return Number(sessionStorage.getItem("commonworldProposalLastPreparedAt") || 0); }
  catch { return 0; }
}

function storeLastPreparedAt(value) {
  try { sessionStorage.setItem("commonworldProposalLastPreparedAt", String(value)); }
  catch { /* Storage may be disabled; GitHub remains the authoritative spam boundary. */ }
}

function readBasisFields(form) {
  const basis = {};
  for (const key of COMMONS_DIMENSIONS) {
    basis[key] = {
      classification: form.elements[`basis_${key}_classification`]?.value || "",
      text: form.elements[`basis_${key}_text`]?.value || "",
      refs: [1, 2, 3, 4, 5].filter((index) => form.elements[`basis_${key}_ref_${index}`]?.checked).map((index) => `source-${index}`),
    };
  }
  return basis;
}

function readFields(form) {
  const actions = [1, 2, 3].map((index) => ({ type: form.elements[`action_type_${index}`].value, url: form.elements[`action_url_${index}`].value }));
  return {
    name: form.elements.name.value,
    description: form.elements.description.value,
    official_website: form.elements.official_website.value,
    commons_type: form.elements.commons_type.value,
    presence_geographic: form.elements.presence_geographic.checked,
    presence_digital: form.elements.presence_digital.checked,
    region: form.elements.region.value,
    actions,
    sources: form.elements.sources.value,
    sensitive_location_risk: form.elements.sensitive_location_risk.checked,
    editorial_note: form.elements.editorial_note.value,
    commons_basis: readBasisFields(form),
    public_issue_acknowledged: form.elements.public_issue_acknowledged.checked,
    processing_agreed: form.elements.processing_agreed.checked,
    no_sensitive_data_confirmed: form.elements.no_sensitive_data_confirmed.checked,
  };
}

function writeFields(form, fields) {
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) return false;
  const strings = ["name", "description", "official_website", "commons_type", "region", "sources", "editorial_note"];
  const booleans = ["presence_geographic", "presence_digital", "sensitive_location_risk", "public_issue_acknowledged", "processing_agreed", "no_sensitive_data_confirmed"];
  if (strings.some((name) => typeof fields[name] !== "string" || !form.elements[name])) return false;
  if (booleans.some((name) => typeof fields[name] !== "boolean" || !form.elements[name])) return false;
  if (!Array.isArray(fields.actions) || fields.actions.length !== 3) return false;
  if (fields.actions.some((action, offset) => !action || typeof action.type !== "string" || typeof action.url !== "string" || !form.elements[`action_type_${offset + 1}`] || !form.elements[`action_url_${offset + 1}`])) return false;
  const basisControlsPresent = Boolean(form.elements.basis_shared_good_classification);
  const basis = fields.commons_basis && typeof fields.commons_basis === "object" && !Array.isArray(fields.commons_basis) ? fields.commons_basis : {};
  if (basisControlsPresent) {
    for (const key of COMMONS_DIMENSIONS) {
      const entry = basis[key] || { classification: "", text: "", refs: [] };
      if (!entry || typeof entry.classification !== "string" || typeof entry.text !== "string" || !Array.isArray(entry.refs) || entry.refs.some((ref) => !/^source-[1-5]$/u.test(String(ref)))) return false;
    }
  } else if (Object.values(basis).some((entry) => entry?.classification || entry?.text || entry?.refs?.length)) return false;
  for (const name of strings) form.elements[name].value = fields[name];
  for (const name of booleans) form.elements[name].checked = fields[name];
  for (const [offset, action] of fields.actions.entries()) {
    const index = offset + 1;
    form.elements[`action_type_${index}`].value = action.type;
    form.elements[`action_url_${index}`].value = action.url;
  }
  if (basisControlsPresent) {
    for (const key of COMMONS_DIMENSIONS) {
      const entry = basis[key] || { classification: "", text: "", refs: [] };
      form.elements[`basis_${key}_classification`].value = entry.classification;
      form.elements[`basis_${key}_text`].value = entry.text;
      for (const index of [1, 2, 3, 4, 5]) form.elements[`basis_${key}_ref_${index}`].checked = entry.refs.includes(`source-${index}`);
    }
  }
  return true;
}

export function storeProposalReleaseDraft(form, storage = globalThis.sessionStorage, now = () => Date.now()) {
  try {
    storage.setItem(RELEASE_DRAFT_KEY, JSON.stringify({
      schema_version: 1,
      locale: ACTIVE_LOCALE,
      saved_at: now(),
      fields: readFields(form),
    }));
    return true;
  } catch {
    return false;
  }
}

export function restoreProposalReleaseDraft(form, storage = globalThis.sessionStorage, now = () => Date.now()) {
  let serialized = null;
  try {
    serialized = storage.getItem(RELEASE_DRAFT_KEY);
    storage.removeItem(RELEASE_DRAFT_KEY);
  } catch {
    return false;
  }
  if (!serialized) return false;
  try {
    const draft = JSON.parse(serialized);
    if (typeof draft.saved_at !== "number") return false;
    const age = now() - draft.saved_at;
    if (draft.schema_version !== 1 || draft.locale !== ACTIVE_LOCALE || !Number.isFinite(age) || age < 0 || age > RELEASE_DRAFT_MAX_AGE_MS) return false;
    return writeFields(form, draft.fields);
  } catch {
    return false;
  }
}

function renderErrors(errors, node) {
  node.replaceChildren();
  if (!errors.length) return;
  const heading = document.createElement("strong"); heading.textContent = tr("Bitte korrigieren:", "Please correct:"); node.append(heading);
  const list = document.createElement("ul");
  for (const error of errors) { const item = document.createElement("li"); item.textContent = error; list.append(item); }
  node.append(list); node.hidden = false; node.focus();
}

function init() {
  const form = document.getElementById("commons-proposal-form");
  if (!form) return;
  const errorsNode = document.getElementById("proposal-errors");
  const statusNode = document.getElementById("proposal-status");
  const fallback = document.getElementById("proposal-fallback");
  const direct = document.getElementById("proposal-direct-link");
  const download = document.getElementById("proposal-download");
  const catalog = getCatalogIndex();
  let lastProposal = null;
  const geographicToggle = form.elements.presence_geographic;
  const region = form.elements.region;
  const sensitiveLocation = form.elements.sensitive_location_risk;
  const sourcesField = form.elements.sources;
  const restoredReleaseDraft = restoreProposalReleaseDraft(form);
  let formDirty = restoredReleaseDraft;

  function syncBasisSourceRefs() {
    const sourceCount = String(sourcesField.value || "").split(/\r?\n/gu).map((value) => value.trim()).filter(Boolean).slice(0, 5).length;
    for (const key of COMMONS_DIMENSIONS) {
      for (const index of [1, 2, 3, 4, 5]) {
        const input = form.elements[`basis_${key}_ref_${index}`];
        if (!input) continue;
        const disabled = index > sourceCount;
        input.disabled = disabled;
        input.closest("label")?.toggleAttribute("data-disabled", disabled);
        if (disabled) input.checked = false;
      }
    }
  }

  function syncGeographicFields() {
    const enabled = geographicToggle.checked;
    region.required = enabled;
    region.disabled = !enabled;
    sensitiveLocation.disabled = !enabled;
    document.getElementById("proposal-region-field")?.toggleAttribute("data-disabled", !enabled);
    document.getElementById("proposal-sensitive-location-field")?.toggleAttribute("data-disabled", !enabled);
    if (!enabled) sensitiveLocation.checked = false;
  }

  geographicToggle.addEventListener("change", syncGeographicFields);
  sourcesField.addEventListener("input", syncBasisSourceRefs);
  form.addEventListener("input", () => { formDirty = true; });
  form.addEventListener("change", () => { formDirty = true; });
  form.addEventListener("reset", () => {
    formDirty = false;
    window.setTimeout(() => { syncGeographicFields(); syncBasisSourceRefs(); }, 0);
  });
  document.addEventListener(RELEASE_NAVIGATION_EVENT, (event) => {
    if (!formDirty || storeProposalReleaseDraft(form)) return;
    event.preventDefault();
    statusNode.textContent = tr(
      "Der automatische Versionswechsel wurde pausiert, weil der Entwurf in diesem Tab nicht sicher zwischengespeichert werden konnte. Das Formular bleibt geöffnet.",
      "The automatic release change was paused because the draft could not be stored safely in this tab. The form remains open.",
    );
  });
  syncGeographicFields();
  syncBasisSourceRefs();
  if (restoredReleaseDraft) statusNode.textContent = tr("Begonnene Eingaben wurden nach dem Versionswechsel dieses Tabs wiederhergestellt.", "Draft input was restored after this tab changed release version.");

  function validateCurrent() {
    if (!catalog) return { proposal: null, errors: [tr("Der öffentliche Katalogindex konnte nicht sicher geladen werden. Bitte die Seite neu laden.", "The public catalog index could not be loaded safely. Please reload the page.")] };
    if (form.elements.website_confirm.value) return { proposal: null, errors: [tr("Automatische Einreichung blockiert.", "Automated submission blocked.")] };
    const proposal = proposalFromFields(readFields(form));
    return { proposal, errors: validateProposal(proposal, catalog.titles, catalog.hosts) };
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault(); errorsNode.hidden = true; statusNode.textContent = ""; fallback.hidden = true;
    const { proposal, errors } = validateCurrent();
    if (errors.length) { renderErrors(errors, errorsNode); return; }
    const last = readLastPreparedAt();
    if (Date.now() - last < 60_000) { renderErrors([tr("Mehrfachvorbereitung begrenzt: bitte eine Minute warten oder den vorhandenen GitHub-Tab verwenden.", "Repeated preparation is rate-limited: wait one minute or use the existing GitHub tab.")], errorsNode); return; }
    lastProposal = proposal;
    const issueUrl = buildIssueUrl(proposal);
    direct.href = issueUrl;
    storeLastPreparedAt(Date.now());
    if (navigator.onLine === false) {
      statusNode.textContent = tr("Keine Netzverbindung erkannt. Lade den validierten JSON-Vorschlag herunter und reiche ihn später über GitHub ein.", "No network connection detected. Download the validated JSON suggestion and submit it through GitHub later.");
      fallback.hidden = false;
      return;
    }
    let opened = null;
    try { opened = window.open(issueUrl, "_blank"); } catch { opened = null; }
    if (opened) {
      try { opened.opener = null; } catch { /* Cross-origin window; noopener best effort after popup detection. */ }
    }
    if (!opened) {
      statusNode.textContent = tr("Der GitHub-Tab wurde blockiert. Nutze den direkten Link oder den JSON-Download.", "The GitHub tab was blocked. Use the direct link or the JSON download.");
      fallback.hidden = false;
      return;
    }
    statusNode.textContent = tr("GitHub wurde geöffnet. Erst das Absenden des öffentlichen Issues überträgt den Vorschlag; eine Veröffentlichung im Katalog erfolgt dadurch nicht.", "GitHub was opened. The suggestion is transferred only when you submit the public issue; this does not publish it in the catalog.");
    fallback.hidden = false;
  });

  download.addEventListener("click", () => {
    const result = lastProposal ? { proposal: lastProposal, errors: [] } : validateCurrent();
    if (result.errors.length) { renderErrors(result.errors, errorsNode); return; }
    downloadJson(result.proposal);
    statusNode.textContent = tr("Validierte JSON-Datei lokal erstellt. Commonworld hat den Inhalt nicht gespeichert.", "Validated JSON file created locally. Commonworld did not store its contents.");
  });
}

if (typeof document !== "undefined") init();
