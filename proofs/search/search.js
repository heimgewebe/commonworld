import { loadJson } from "../shared/aspects.js";

const SEARCH_INPUT_URL = new URL("../../examples/commonworld/search-index-input.sample.json", import.meta.url);
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
const resultGrid = requiredElement("[data-result-grid]");
const loadState = requiredElement("[data-load-state]");
const resultTemplate = requiredElement("[data-result-template]");
let entries = [];

function normalise(value) {
  return String(value || "").toLocaleLowerCase("en");
}

function entrySearchText(entry) {
  return normalise(
    [
      entry.id,
      entry.title,
      entry.summary,
      entry.curation_state,
      entry.location_label,
      entry.location_mode,
      entry.project_path,
      entry.profile_handoff_state,
      ...(entry.aspects || []).flatMap((aspect) => [aspect.id, aspect.label]),
    ].join(" "),
  );
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

function entryMatches(entry) {
  const query = normalise(queryInput.value.trim());
  const curation = curationFilter.value;
  const location = locationFilter.value;
  if (curation !== "all" && entry.curation_state !== curation) return false;
  if (location !== "all" && entry.location_mode !== location) return false;
  return query === "" || entrySearchText(entry).includes(query);
}

function renderAspectPill(aspect) {
  const pill = document.createElement("span");
  pill.className = "aspect-pill";
  pill.textContent = `${aspect.label} · ${aspect.id}`;
  return pill;
}

function renderCard(entry) {
  const fragment = resultTemplate.content.cloneNode(true);
  fragment.querySelector("[data-card-kicker]").textContent = `${entry.id} · ${entry.location_mode}`;
  fragment.querySelector("[data-card-title]").textContent = entry.title;
  fragment.querySelector("[data-card-summary]").textContent = entry.summary;
  fragment.querySelector("[data-card-aspects]").replaceChildren(...entry.aspects.map(renderAspectPill));
  fragment.querySelector("[data-card-curation]").textContent = entry.curation_state;
  fragment.querySelector("[data-card-location]").textContent = `${entry.location_label} / ${entry.location_mode}`;
  fragment.querySelector("[data-card-handoff]").textContent = entry.profile_handoff_state;
  fragment.querySelector("[data-card-path]").textContent = entry.project_path;
  return fragment;
}

function renderResults() {
  const matches = entries.filter(entryMatches);
  resultCount.textContent = `${matches.length} of ${entries.length} static search input ${entries.length === 1 ? "entry" : "entries"}`;
  if (matches.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No static search input entries match these read-only filters.";
    resultGrid.replaceChildren(empty);
    return;
  }
  resultGrid.replaceChildren(...matches.map(renderCard));
}

async function initSearchProof() {
  const payload = await loadJson(SEARCH_INPUT_URL);
  entries = validateSearchInput(payload).sort((left, right) =>
    left.title.localeCompare(right.title, "en", { sensitivity: "base" }),
  );
  populateFilters();
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
