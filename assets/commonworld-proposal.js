const ACTIVE_LOCALE = typeof document !== 'undefined' && document.documentElement?.lang === 'en' ? 'en' : 'de';
const tr = (de, en) => ACTIVE_LOCALE === 'en' ? en : de;

const MAX = Object.freeze({ name: 140, description: 800, region: 120, note: 500, url: 300 });
const ISSUE_BASE = "https://github.com/heimgewebe/commonworld/issues/new";
const ACTION_TYPES = new Set(["visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"]);
const COMMONS_TYPES = new Set(["knowledge", "software", "culture", "food-seeds", "water", "energy", "housing-land", "health-care", "tools-repair", "community-network", "other"]);
const SENSITIVE_PATTERN = /(?:\b(?:latitude|longitude|coordinates?|gps|street|straße|strasse|avenue|road|router|roof|dach|wohnung|apartment|household|haushalt)\b|[-+]?\d{1,3}\.\d{3,}\s*[,;/ ]\s*[-+]?\d{1,3}\.\d{3,})/iu;
const CONTACT_PATTERN = /(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|(?:\+?\d[\d\s()/.-]{7,}\d))/iu;
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
  return SENSITIVE_PATTERN.test(String(value || ""));
}

export function containsContactData(value) {
  return CONTACT_PATTERN.test(String(value || ""));
}

function validateText(errors, field, value, min, max) {
  if (typeof value !== "string" || value.trim().length < min) errors.push(`${field}: ${tr("zu kurz oder fehlt.", "too short or missing.")}`);
  if (typeof value === "string" && value.length > max) errors.push(`${field}: ${tr(`höchstens ${max} Zeichen.`, `at most ${max} characters.`)}`);
  if (typeof value === "string" && ACTIVE_CONTENT_PATTERN.test(value)) errors.push(`${field}: ${tr("aktiver HTML- oder Script-Inhalt ist nicht erlaubt.", "active HTML or script content is not allowed.")}`);
  if (typeof value === "string" && containsContactData(value)) errors.push(`${field}: ${tr("keine E-Mail-Adresse oder Telefonnummer in öffentlichen Vorschlägen.", "no email address or phone number in public suggestions.")}`);
}

export function validateProposal(proposal, knownTitles = [], knownHosts = []) {
  const errors = [];
  if (!proposal || typeof proposal !== "object" || Array.isArray(proposal)) return [tr("Vorschlag: ungültiges Datenformat.", "Suggestion: invalid data format.")];
  const allowedTop = new Set(["schema_version", "kind", "proposal_id", "submitted_at", "status", "project", "consent"]);
  for (const key of Object.keys(proposal)) if (!allowedTop.has(key)) errors.push(tr(`Vorschlag: unbekanntes Feld ${key}.`, `Suggestion: unknown field ${key}.`));
  if (proposal.schema_version !== 1 || proposal.kind !== "commonworld_commons_proposal" || proposal.status !== "submitted") errors.push(tr("Vorschlag: Vertragskennung oder Startstatus ungültig.", "Suggestion: contract identity or initial status is invalid."));
  if (!/^cw-[0-9]{8}t[0-9]{6}z-[a-z0-9-]{3,48}$/u.test(String(proposal.proposal_id || ""))) errors.push(tr("Vorschlag: Kennung ungültig.", "Suggestion: identifier is invalid."));
  if (Number.isNaN(Date.parse(String(proposal.submitted_at || "")))) errors.push(tr("Vorschlag: Zeitangabe ungültig.", "Suggestion: timestamp is invalid."));

  const project = proposal.project;
  if (!project || typeof project !== "object" || Array.isArray(project)) return [...errors, tr("Projekt: Angaben fehlen.", "Project: information is missing.")];
  const allowedProject = new Set(["name", "description", "official_website", "commons_type", "presence_geographic", "presence_digital", "region", "actions", "sources", "sensitive_location_risk", "location_precision", "editorial_note"]);
  for (const key of Object.keys(project)) if (!allowedProject.has(key)) errors.push(tr(`Projekt: unbekanntes Feld ${key}.`, `Project: unknown field ${key}.`));
  validateText(errors, "Name", project.name, 2, MAX.name);
  validateText(errors, tr("Beschreibung", "Description"), project.description, 40, MAX.description);
  if (project.presence_geographic === true) {
    validateText(errors, "Region", project.region, 2, MAX.region);
    if (containsSensitiveLocation(project.region)) errors.push(tr("Region: nur Land, Großregion oder Stadt nennen; keine Adresse oder Koordinate.", "Region: provide only a country, broad region or city; no address or coordinates."));
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

export function proposalFromFields(fields, now = new Date()) {
  const actions = fields.actions.filter((entry) => entry.type || entry.url).map((entry) => ({ type: entry.type, url: entry.url.trim() }));
  const sources = fields.sources.split(/\r?\n/gu).map((value) => value.trim()).filter(Boolean);
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

export function buildIssueBody(proposal) {
  const project = proposal.project;
  const actionLines = project.actions.map((entry) => `- ${markdown(entry.type)}: ${entry.url}`).join("\n");
  const sourceLines = project.sources.map((url) => `- ${url}`).join("\n");
  return [
    tr("## Öffentlicher Commons-Vorschlag", "## Public Commons suggestion"),
    "",
    tr("> Dieser Vorschlag ist ein redaktioneller Kandidat. Er wird nicht automatisch veröffentlicht.", "> This suggestion is an editorial candidate. It is not published automatically."),
    "",
    `**${tr("Vorschlags-ID", "Suggestion ID")}:** \`${proposal.proposal_id}\``,
    `**Name:** ${markdown(project.name)}`,
    `**${tr("Commons-Art", "Commons type")}:** ${markdown(project.commons_type)}`,
    `**${tr("Präsenz", "Presence")}:** ${project.presence_geographic && project.presence_digital ? tr('Vor Ort und Digital', 'On site and Digital') : (project.presence_geographic ? tr('Geografisch (Vor Ort)', 'Geographic (On site)') : 'Digital')}`,
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
    sourceLines,
    ...(project.editorial_note ? ["", tr("### Redaktioneller Hinweis", "### Editorial note"), markdown(project.editorial_note)] : []),
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
    public_issue_acknowledged: form.elements.public_issue_acknowledged.checked,
    processing_agreed: form.elements.processing_agreed.checked,
    no_sensitive_data_confirmed: form.elements.no_sensitive_data_confirmed.checked,
  };
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
  syncGeographicFields();

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
