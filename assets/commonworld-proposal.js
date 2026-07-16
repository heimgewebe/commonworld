const MAX = Object.freeze({ name: 140, description: 800, region: 120, note: 500, url: 300 });
const ISSUE_BASE = "https://github.com/heimgewebe/commonworld/issues/new";
const ACTION_TYPES = new Set(["visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"]);
const COMMONS_TYPES = new Set(["knowledge", "software", "culture", "food-seeds", "water", "energy", "housing-land", "health-care", "tools-repair", "community-network", "other"]);
const PRESENCE_TYPES = new Set(["geographic", "digital", "hybrid"]);
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
  if (typeof value !== "string" || value.trim().length < min) errors.push(`${field}: zu kurz oder fehlt.`);
  if (typeof value === "string" && value.length > max) errors.push(`${field}: höchstens ${max} Zeichen.`);
  if (typeof value === "string" && ACTIVE_CONTENT_PATTERN.test(value)) errors.push(`${field}: aktiver HTML- oder Script-Inhalt ist nicht erlaubt.`);
  if (typeof value === "string" && containsContactData(value)) errors.push(`${field}: keine E-Mail-Adresse oder Telefonnummer in öffentlichen Vorschlägen.`);
}

export function validateProposal(proposal, knownTitles = [], knownHosts = []) {
  const errors = [];
  if (!proposal || typeof proposal !== "object" || Array.isArray(proposal)) return ["Vorschlag: ungültiges Datenformat."];
  const allowedTop = new Set(["schema_version", "kind", "proposal_id", "submitted_at", "status", "project", "consent"]);
  for (const key of Object.keys(proposal)) if (!allowedTop.has(key)) errors.push(`Vorschlag: unbekanntes Feld ${key}.`);
  if (proposal.schema_version !== 1 || proposal.kind !== "commonworld_commons_proposal" || proposal.status !== "submitted") errors.push("Vorschlag: Vertragskennung oder Startstatus ungültig.");
  if (!/^cw-[0-9]{8}t[0-9]{6}z-[a-z0-9-]{3,48}$/u.test(String(proposal.proposal_id || ""))) errors.push("Vorschlag: Kennung ungültig.");
  if (Number.isNaN(Date.parse(String(proposal.submitted_at || "")))) errors.push("Vorschlag: Zeitangabe ungültig.");

  const project = proposal.project;
  if (!project || typeof project !== "object" || Array.isArray(project)) return [...errors, "Projekt: Angaben fehlen."];
  const allowedProject = new Set(["name", "description", "official_website", "commons_type", "presence_kind", "region", "actions", "sources", "sensitive_location_risk", "location_precision", "editorial_note"]);
  for (const key of Object.keys(project)) if (!allowedProject.has(key)) errors.push(`Projekt: unbekanntes Feld ${key}.`);
  validateText(errors, "Name", project.name, 2, MAX.name);
  validateText(errors, "Beschreibung", project.description, 40, MAX.description);
  validateText(errors, "Region", project.region, 2, MAX.region);
  if (containsSensitiveLocation(project.region)) errors.push("Region: nur Land, Großregion oder Stadt nennen; keine Adresse oder Koordinate.");
  if (project.editorial_note) validateText(errors, "Redaktioneller Hinweis", project.editorial_note, 0, MAX.note);
  if (!isSafeHttpsUrl(project.official_website)) errors.push("Offizielle Website: nur eine gültige HTTPS-Adresse ist erlaubt.");
  if (!COMMONS_TYPES.has(project.commons_type)) errors.push("Commons-Art: unbekannter Wert.");
  if (!PRESENCE_TYPES.has(project.presence_kind)) errors.push("Präsenz: unbekannter Wert.");
  if (project.location_precision !== "country_or_region_only") errors.push("Ortsgenauigkeit: nur Land oder grobe Region ist zulässig.");
  if (typeof project.sensitive_location_risk !== "boolean") errors.push("Sensibilitätsangabe: erforderlich.");

  if (!Array.isArray(project.actions) || project.actions.length < 1 || project.actions.length > 3) {
    errors.push("Handlungswege: ein bis drei belegte Wege sind erforderlich.");
  } else {
    const seen = new Set();
    for (const action of project.actions) {
      if (!action || typeof action !== "object" || !ACTION_TYPES.has(action.type) || !isSafeHttpsUrl(action.url)) errors.push("Handlungswege: Typ und HTTPS-Adresse prüfen.");
      const key = `${action?.type || ""}|${action?.url || ""}`;
      if (seen.has(key)) errors.push("Handlungswege: Dublette entfernen.");
      seen.add(key);
    }
  }
  if (!Array.isArray(project.sources) || project.sources.length < 1 || project.sources.length > 5) {
    errors.push("Quellen: mindestens eine und höchstens fünf primärnahe HTTPS-Quellen angeben.");
  } else {
    const unique = new Set(project.sources);
    if (unique.size !== project.sources.length) errors.push("Quellen: Dubletten entfernen.");
    if (project.sources.some((url) => !isSafeHttpsUrl(url))) errors.push("Quellen: nur gültige HTTPS-Adressen sind erlaubt.");
  }

  const title = normalizeTitle(project.name);
  if (knownTitles.map(normalizeTitle).includes(title)) errors.push("Dublette: dieser Name ist bereits im öffentlichen Katalog vorhanden.");
  if (isSafeHttpsUrl(project.official_website)) {
    const host = new URL(project.official_website).hostname.replace(/^www\./u, "").toLocaleLowerCase("en");
    if (knownHosts.map((value) => String(value).replace(/^www\./u, "").toLocaleLowerCase("en")).includes(host)) errors.push("Dublette: diese offizielle Domain ist bereits im Katalog vorhanden.");
  }
  const consent = proposal.consent;
  if (!consent || consent.public_issue_acknowledged !== true || consent.processing_agreed !== true || consent.no_sensitive_data_confirmed !== true) errors.push("Einwilligung: alle drei Bestätigungen sind erforderlich.");
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
      presence_kind: fields.presence_kind,
      region: fields.region.trim(),
      actions,
      sources,
      sensitive_location_risk: Boolean(fields.sensitive_location_risk),
      location_precision: "country_or_region_only",
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
    "## Öffentlicher Commons-Vorschlag",
    "",
    "> Dieser Vorschlag ist ein redaktioneller Kandidat. Er wird nicht automatisch veröffentlicht.",
    "",
    `**Vorschlags-ID:** \`${proposal.proposal_id}\``,
    `**Name:** ${markdown(project.name)}`,
    `**Commons-Art:** ${markdown(project.commons_type)}`,
    `**Präsenz:** ${markdown(project.presence_kind)}`,
    `**Grobe Region:** ${markdown(project.region)}`,
    `**Offizielle Website:** ${project.official_website}`,
    `**Möglicherweise sensible Orte:** ${project.sensitive_location_risk ? "ja – redaktionell besonders prüfen" : "nein angegeben"}`,
    "",
    "### Kurzbeschreibung",
    markdown(project.description),
    "",
    "### Vorgeschlagene Handlungswege",
    actionLines,
    "",
    "### Primärnahe Quellen",
    sourceLines,
    ...(project.editorial_note ? ["", "### Redaktioneller Hinweis", markdown(project.editorial_note)] : []),
    "",
    "### Bestätigungen",
    "- [x] Mir ist bewusst, dass dieses Issue öffentlich ist.",
    "- [x] Ich willige in die redaktionelle Verarbeitung dieser Angaben ein.",
    "- [x] Der Vorschlag enthält keine privaten Adressen, Koordinaten oder Kontaktdaten.",
    "",
    "<!-- commonworld-proposal-v1; status=submitted; no-auto-publish -->",
  ].join("\n");
}

export function buildIssueUrl(proposal) {
  const params = new URLSearchParams({
    title: `[Commons-Vorschlag] ${proposal.project.name}`,
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
    presence_kind: form.elements.presence_kind.value,
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
  const heading = document.createElement("strong"); heading.textContent = "Bitte korrigieren:"; node.append(heading);
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

  function validateCurrent() {
    if (!catalog) return { proposal: null, errors: ["Der öffentliche Katalogindex konnte nicht sicher geladen werden. Bitte die Seite neu laden."] };
    if (form.elements.website_confirm.value) return { proposal: null, errors: ["Automatische Einreichung blockiert."] };
    const proposal = proposalFromFields(readFields(form));
    return { proposal, errors: validateProposal(proposal, catalog.titles, catalog.hosts) };
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault(); errorsNode.hidden = true; statusNode.textContent = ""; fallback.hidden = true;
    const { proposal, errors } = validateCurrent();
    if (errors.length) { renderErrors(errors, errorsNode); return; }
    const last = readLastPreparedAt();
    if (Date.now() - last < 60_000) { renderErrors(["Mehrfachvorbereitung begrenzt: bitte eine Minute warten oder den vorhandenen GitHub-Tab verwenden."], errorsNode); return; }
    lastProposal = proposal;
    const issueUrl = buildIssueUrl(proposal);
    direct.href = issueUrl;
    storeLastPreparedAt(Date.now());
    if (navigator.onLine === false) {
      statusNode.textContent = "Keine Netzverbindung erkannt. Lade den validierten JSON-Vorschlag herunter und reiche ihn später über GitHub ein.";
      fallback.hidden = false;
      return;
    }
    let opened = null;
    try { opened = window.open(issueUrl, "_blank"); } catch { opened = null; }
    if (opened) {
      try { opened.opener = null; } catch { /* Cross-origin window; noopener best effort after popup detection. */ }
    }
    if (!opened) {
      statusNode.textContent = "Der GitHub-Tab wurde blockiert. Nutze den direkten Link oder den JSON-Download.";
      fallback.hidden = false;
      return;
    }
    statusNode.textContent = "GitHub wurde geöffnet. Erst das Absenden des öffentlichen Issues überträgt den Vorschlag; eine Veröffentlichung im Katalog erfolgt dadurch nicht.";
    fallback.hidden = false;
  });

  download.addEventListener("click", () => {
    const result = lastProposal ? { proposal: lastProposal, errors: [] } : validateCurrent();
    if (result.errors.length) { renderErrors(result.errors, errorsNode); return; }
    downloadJson(result.proposal);
    statusNode.textContent = "Validierte JSON-Datei lokal erstellt. Commonworld hat den Inhalt nicht gespeichert.";
  });
}

if (typeof document !== "undefined") init();
