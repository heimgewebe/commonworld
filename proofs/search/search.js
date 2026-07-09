import { loadJson } from "../shared/aspects.js";

const SEARCH_INPUT_URL = new URL("../../examples/commonworld/search-index-input.sample.json", import.meta.url);
const QUERY_FIXTURES_URL = new URL("../../examples/commonworld/search-query-fixtures.sample.json", import.meta.url);
const ALLOWED_ENTRY_KEYS = [
  "id",
  "title",
  "summary",
  "aspects",
  "curation_state",
  "location_label",
  "location_mode",
  "project_path",
  "profile_handoff_state",
];
const QUERY_FIXTURE_KIND = "commonworld.static_search_query_fixtures";
const QUERY_FIXTURE_STATUS = "static-fixture-only";
const QUERY_FIXTURE_TASK = "COMMONWORLD-ATLAS-V1-T018";
const FORBIDDEN_ENTRY_KEYS = new Set([
  "coordinates",
  "lat",
  "lon",
  "provenance",
  "review_notes",
  "private_review_notes",
  "handoff",
  "links",
  "writes",
  "submissions",
]);

function requiredElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error("Search proof is missing " + selector);
  }
  return element;
}

const queryInput = requiredElement("[data-search-query]");
const curationFilter = requiredElement("[data-curation-filter]");
const locationFilter = requiredElement("[data-location-filter]");
const resetButton = requiredElement("[data-reset-search]");
const resultCount = requiredElement("[data-result-count]");
const rankingNote = requiredElement("[data-ranking-note]");
const queryFixtureState = requiredElement("[data-query-fixture-state]");
const queryFixtureList = requiredElement("[data-query-fixtures]");
const resultGrid = requiredElement("[data-result-grid]");
const loadState = requiredElement("[data-load-state]");
const resultTemplate = requiredElement("[data-result-template]");
let entries = [];
let queryFixtures = [];

function normalise(value) {
  return String(value || "").toLocaleLowerCase("en");
}

function searchableFields(entry) {
  return [
    { field: "title", label: "Title", value: entry.title, weight: 40 },
    { field: "summary", label: "Summary", value: entry.summary, weight: 20 },
    { field: "aspect", label: "Aspect", value: (entry.aspects || []).flatMap((aspect) => [aspect.id, aspect.label]).join(" "), weight: 24 },
    { field: "location", label: "Location", value: [entry.location_label, entry.location_mode].join(" "), weight: 12 },
    { field: "curation", label: "Curation", value: entry.curation_state, weight: 8 },
    { field: "source", label: "Source path", value: entry.project_path, weight: 4 },
    { field: "handoff", label: "Handoff state", value: entry.profile_handoff_state, weight: 2 },
  ];
}

function explainMatch(entry, query) {
  const cleanQuery = normalise(query.trim());
  if (cleanQuery === "") {
    return {
      matches: true,
      score: 0,
      reasons: [{ field: "all", label: "All entries", weight: 0 }],
    };
  }
  const terms = cleanQuery.split(/\s+/).filter(Boolean);
  const reasons = [];
  let score = 0;
  for (const field of searchableFields(entry)) {
    const haystack = normalise(field.value);
    const matchedTerms = terms.filter((term) => haystack.includes(term));
    if (matchedTerms.length === 0) continue;
    const termFactor = matchedTerms.length / terms.length;
    const exactBoost = haystack === cleanQuery ? 1.5 : 1;
    const contribution = Math.round(field.weight * termFactor * exactBoost);
    reasons.push({
      field: field.field,
      label: field.label,
      weight: contribution,
      terms: matchedTerms,
    });
    score += contribution;
  }
  return { matches: reasons.length > 0, score, reasons };
}

function validateEntry(entry, index) {
  const keys = Object.keys(entry);
  if (keys.join("|") !== ALLOWED_ENTRY_KEYS.join("|")) {
    throw new Error(`Search input entry ${index} does not match the allowed T014 field order.`);
  }
  for (const key of keys) {
    if (FORBIDDEN_ENTRY_KEYS.has(key)) {
      throw new Error(`Search input entry ${index} includes forbidden field ${key}.`);
    }
  }
  if (!Array.isArray(entry.aspects) || entry.aspects.length === 0) {
    throw new Error(`Search input entry ${index} needs at least one aspect.`);
  }
  for (const aspect of entry.aspects) {
    if (Object.keys(aspect).join("|") !== "id|label") {
      throw new Error(`Search input entry ${index} aspects may only expose id and label.`);
    }
  }
}

function validateSearchInput(payload) {
  if (payload.kind !== "commonworld.static_search_index_input") {
    throw new Error("Search proof can only load the static search index input sample.");
  }
  if (payload.status !== "static-sample-only") {
    throw new Error("Search proof input must remain static-sample-only.");
  }
  if (payload.boundary?.implementation !== "no search service") {
    throw new Error("Search proof boundary must not create a search service.");
  }
  if (!Array.isArray(payload.entries)) {
    throw new Error("Search proof input must expose an entries array.");
  }
  if (payload.entry_count !== payload.entries.length) {
    throw new Error("Search proof input entry_count is stale.");
  }
  payload.entries.forEach(validateEntry);
  return payload.entries;
}

function validateQueryFixturePayload(payload) {
  if (payload.kind !== QUERY_FIXTURE_KIND) {
    throw new Error("Search proof query fixtures must use the static query fixture kind.");
  }
  if (payload.status !== QUERY_FIXTURE_STATUS) {
    throw new Error("Search proof query fixtures must remain static-fixture-only.");
  }
  if (payload.task !== QUERY_FIXTURE_TASK) {
    throw new Error("Search proof query fixtures must declare T018.");
  }
  if (payload.source_input !== "examples/commonworld/search-index-input.sample.json") {
    throw new Error("Search proof query fixtures must point at the static search input sample.");
  }
  if (payload.boundary?.implementation !== "no search service") {
    throw new Error("Search proof query fixtures must not create a search service.");
  }
  if (payload.boundary?.runtime_dependency !== "none" || payload.boundary?.writes !== false || payload.boundary?.submissions !== false) {
    throw new Error("Search proof query fixtures must keep the no-runtime boundary.");
  }
  if (payload.boundary?.authority !== "not a ranking authority or curation decision") {
    throw new Error("Search proof query fixtures must not become ranking authority.");
  }
  if (!Array.isArray(payload.fixtures)) {
    throw new Error("Search proof query fixtures must expose a fixtures array.");
  }
  return payload.fixtures.map(validateQueryFixture);
}

function validateQueryFixture(fixture, index) {
  if (!fixture || typeof fixture !== "object") {
    throw new Error(`Search proof query fixture ${index} must be an object.`);
  }
  if (typeof fixture.id !== "string" || fixture.id === "") {
    throw new Error(`Search proof query fixture ${index} needs an id.`);
  }
  if (typeof fixture.query !== "string" || fixture.query.trim() === "") {
    throw new Error(`Search proof query fixture ${fixture.id} needs a query.`);
  }
  const filters = fixture.filters || {};
  const curation = filters.curation || "all";
  const location = filters.location || "all";
  if (typeof curation !== "string" || typeof location !== "string") {
    throw new Error(`Search proof query fixture ${fixture.id} filters must be strings.`);
  }
  if (!Array.isArray(fixture.expected_top_ids) || fixture.expected_top_ids.length === 0) {
    throw new Error(`Search proof query fixture ${fixture.id} needs expected top ids.`);
  }
  return {
    id: fixture.id,
    query: fixture.query,
    filters: { curation, location },
    expectedTopIds: fixture.expected_top_ids,
    minResultCount: fixture.min_result_count,
    minTopScore: fixture.min_top_score,
  };
}

function uniqueValues(field) {
  return [...new Set(entries.map((entry) => entry[field]))].sort((left, right) =>
    left.localeCompare(right, "en", { sensitivity: "base" }),
  );
}

function optionFor(value) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  return option;
}

function populateFilters() {
  curationFilter.append(...uniqueValues("curation_state").map(optionFor));
  locationFilter.append(...uniqueValues("location_mode").map(optionFor));
}

function rankedEntry(entry) {
  const curation = curationFilter.value;
  const location = locationFilter.value;
  if (curation !== "all" && entry.curation_state !== curation) return null;
  if (location !== "all" && entry.location_mode !== location) return null;
  const explanation = explainMatch(entry, queryInput.value);
  if (!explanation.matches) return null;
  return { entry, ...explanation };
}

function rankResults(left, right) {
  const byScore = right.score - left.score;
  if (byScore !== 0) return byScore;
  return left.entry.title.localeCompare(right.entry.title, "en", { sensitivity: "base" });
}

function renderAspectPill(aspect) {
  const pill = document.createElement("span");
  pill.className = "aspect-pill";
  pill.textContent = `${aspect.label} · ${aspect.id}`;
  return pill;
}

function renderReasonPill(reason) {
  const pill = document.createElement("span");
  pill.className = "reason-pill";
  const terms = reason.terms?.length ? `: ${reason.terms.join(", ")}` : "";
  pill.textContent = `${reason.label}${terms}`;
  return pill;
}

function renderCard(result) {
  const { entry, score, reasons } = result;
  const fragment = resultTemplate.content.cloneNode(true);
  fragment.querySelector("[data-card-kicker]").textContent = `${entry.id} · ${entry.location_mode}`;
  fragment.querySelector("[data-card-title]").textContent = entry.title;
  fragment.querySelector("[data-card-summary]").textContent = entry.summary;
  fragment.querySelector("[data-card-aspects]").replaceChildren(...entry.aspects.map(renderAspectPill));
  const scorePill = document.createElement("span");
  scorePill.className = "score-pill";
  scorePill.textContent = score === 0 ? "unranked browse" : `${score} local proof points`;
  fragment.querySelector("[data-card-score]").replaceChildren(scorePill);
  const reasonList = document.createElement("span");
  reasonList.className = "reason-list";
  reasonList.replaceChildren(...reasons.map(renderReasonPill));
  fragment.querySelector("[data-card-reasons]").replaceChildren(reasonList);
  fragment.querySelector("[data-card-curation]").textContent = entry.curation_state;
  fragment.querySelector("[data-card-location]").textContent = `${entry.location_label} / ${entry.location_mode}`;
  fragment.querySelector("[data-card-handoff]").textContent = entry.profile_handoff_state;
  fragment.querySelector("[data-card-path]").textContent = entry.project_path;
  return fragment;
}

function renderResults() {
  const matches = entries.map(rankedEntry).filter(Boolean).sort(rankResults);
  const hasQuery = queryInput.value.trim() !== "";
  resultCount.textContent = `${matches.length} of ${entries.length} static search input ${entries.length === 1 ? "entry" : "entries"}`;
  rankingNote.textContent = hasQuery
    ? "Ranked locally by transparent match reasons; this is not a server ranking or authority signal."
    : "Browse mode: entries are unranked until a search term is entered.";
  if (matches.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No static search input entries match these read-only filters.";
    resultGrid.replaceChildren(empty);
    return;
  }
  resultGrid.replaceChildren(...matches.map(renderCard));
}

function applyQueryFixture(fixture) {
  queryInput.value = fixture.query;
  curationFilter.value = fixture.filters.curation;
  locationFilter.value = fixture.filters.location;
  renderResults();
  queryInput.focus();
}

function renderQueryFixture(fixture) {
  const item = document.createElement("article");
  item.className = "fixture-item";
  const button = document.createElement("button");
  button.className = "fixture-button";
  button.type = "button";
  button.dataset.queryFixtureId = fixture.id;
  button.textContent = fixture.query;
  button.addEventListener("click", () => applyQueryFixture(fixture));
  const meta = document.createElement("p");
  meta.className = "fixture-meta";
  meta.textContent = `${fixture.filters.curation} / ${fixture.filters.location} · expects ${fixture.expectedTopIds.join(", ")}`;
  item.replaceChildren(button, meta);
  return item;
}

function renderQueryFixtures() {
  queryFixtureList.replaceChildren(...queryFixtures.map(renderQueryFixture));
  queryFixtureState.textContent = `${queryFixtures.length} static T018 query fixtures loaded; buttons only set local filters.`;
}

async function initSearchProof() {
  const [inputPayload, fixturePayload] = await Promise.all([
    loadJson(SEARCH_INPUT_URL),
    loadJson(QUERY_FIXTURES_URL),
  ]);
  entries = validateSearchInput(inputPayload).sort((left, right) =>
    left.title.localeCompare(right.title, "en", { sensitivity: "base" }),
  );
  queryFixtures = validateQueryFixturePayload(fixturePayload);
  populateFilters();
  renderQueryFixtures();
  queryInput.addEventListener("input", renderResults);
  curationFilter.addEventListener("change", renderResults);
  locationFilter.addEventListener("change", renderResults);
  resetButton.addEventListener("click", () => {
    queryInput.value = "";
    curationFilter.value = "all";
    locationFilter.value = "all";
    renderResults();
    queryInput.focus();
  });
  loadState.textContent = `${entries.length} static search input entries loaded from T015; filtering stays in this browser proof.`;
  renderResults();
}

initSearchProof().catch((error) => {
  loadState.textContent = error.message;
  loadState.dataset.error = "true";
});
