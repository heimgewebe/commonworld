const SEED_MANIFEST_URL = new URL("../../examples/commonworld/seed-projects.json", import.meta.url);
const MAP_SOURCE_URL = new URL("./map-source.json", import.meta.url);

const ASPECT_COLORS = {
  "aspect.data": "var(--aspect-data)",
  "aspect.community": "var(--aspect-community)",
  "aspect.infrastructure": "var(--aspect-infrastructure)",
  "aspect.repair": "var(--aspect-repair)",
  "aspect.education": "var(--aspect-education)",
  "aspect.mutual-aid": "var(--aspect-mutual-aid)",
};

const ICON_GLYPHS = {
  "icon.map": "⌖",
  "icon.people": "◌",
  "icon.layers": "▣",
  "icon.tool": "⚒",
  "icon.book-open": "◇",
  "icon.hands": "∞",
};

const loadState = requiredElement("[data-load-state]");
const detailSurface = requiredElement("[data-detail-surface]");
const closeButton = requiredElement("[data-close-detail]");
let activeMarkerButton = null;
let mapSourceCssPromise = null;
let mapSourceScriptPromise = null;

function requiredElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error("Map proof is missing " + selector);
  }
  return element;
}

function sortAspects(aspects) {
  return [...aspects].sort((left, right) => {
    const byWeight = right.weight - left.weight;
    if (byWeight !== 0) return byWeight;
    const byLabel = left.label.localeCompare(right.label, "en", { sensitivity: "base" });
    if (byLabel !== 0) return byLabel;
    return left.id.localeCompare(right.id, "en", { sensitivity: "base" });
  });
}

function buildSegments(project) {
  const ordered = sortAspects(project.aspects);
  let cursor = 0;
  return ordered.map((aspect, index) => {
    const start = cursor;
    const end = index === ordered.length - 1 ? 1 : cursor + aspect.weight;
    cursor = end;
    return { aspect, start, end, span: end - start };
  });
}

function aspectColor(aspect) {
  return ASPECT_COLORS[aspect.color_token] || "var(--line)";
}

function iconFor(aspect) {
  return ICON_GLYPHS[aspect.icon_token] || aspect.icon_token;
}

function formatPercent(value) {
  const percent = value * 100;
  if (percent > 0 && percent < 1) return "<1%";
  if (percent < 10 && !Number.isInteger(percent)) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function gradientFor(project) {
  return `conic-gradient(${buildSegments(project)
    .map(({ aspect, start, end }) => `${aspectColor(aspect)} ${start}turn ${end}turn`)
    .join(", ")})`;
}

function isMapRenderable(project) {
  const coordinates = project.location?.coordinates;
  return (
    project.location?.mode !== "hidden" &&
    Number.isFinite(coordinates?.lat) &&
    Number.isFinite(coordinates?.lon)
  );
}

function privacyLabel(project) {
  if (project.location.mode === "approximate") return "Approximate location";
  if (project.location.mode === "exact") return "Exact location";
  return "Hidden location";
}

function curationStateLabel(project) {
  const state = project.curation?.state || "unreviewed";
  if (state === "fixture") return "Synthetic fixture";
  return state;
}

function curationBadgeLabel(project) {
  const state = curationStateLabel(project);
  if (state === "Synthetic fixture") return state;
  return `Curation: ${state}`;
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}: ${response.status}`);
  }
  return response.json();
}

function requireString(value, message) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(message);
  }
}

function validateMapSource(mapSource) {
  if (mapSource.schema_version !== 1) {
    throw new Error("Map source must use schema_version 1.");
  }
  if (mapSource.mode !== "proof") {
    throw new Error("Static map proof must use proof map source mode.");
  }
  requireString(mapSource.library?.script_url, "Map source missing library script_url.");
  requireString(mapSource.library?.css_url, "Map source missing library css_url.");
  if (!mapSource.library.script_url.endsWith("/dist/maplibre-gl.js")) {
    throw new Error("Map source must use the allowed MapLibre browser bundle.");
  }
  if (!mapSource.library.css_url.endsWith("/dist/maplibre-gl.css")) {
    throw new Error("Map source must use the allowed MapLibre CSS bundle.");
  }
  if (!mapSource.basemap?.style) {
    throw new Error("Map source missing basemap style.");
  }
  if (!Array.isArray(mapSource.initial_view?.center) || !Number.isFinite(mapSource.initial_view?.zoom)) {
    throw new Error("Map source missing initial view.");
  }
}

async function loadMapSource() {
  const mapSource = await loadJson(MAP_SOURCE_URL);
  validateMapSource(mapSource);
  return mapSource;
}

function loadStylesheet(cssUrl) {
  if (mapSourceCssPromise) return mapSourceCssPromise;
  mapSourceCssPromise = new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = cssUrl;
    link.dataset.mapSourceCss = "true";
    link.addEventListener("load", () => resolve());
    link.addEventListener("error", () => {
      link.remove();
      mapSourceCssPromise = null;
      reject(new Error(`Could not load map source stylesheet ${cssUrl}`));
    });
    document.head.append(link);
  });
  return mapSourceCssPromise;
}

function loadScript(scriptUrl) {
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  if (mapSourceScriptPromise) return mapSourceScriptPromise;
  mapSourceScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = scriptUrl;
    script.async = true;
    script.dataset.mapSourceScript = "true";
    script.addEventListener("load", () => {
      if (!window.maplibregl) {
        script.remove();
        mapSourceScriptPromise = null;
        reject(new Error("MapLibre did not load from the configured source."));
        return;
      }
      resolve(window.maplibregl);
    });
    script.addEventListener("error", () => {
      script.remove();
      mapSourceScriptPromise = null;
      reject(new Error(`Could not load map source script ${scriptUrl}`));
    });
    document.head.append(script);
  });
  return mapSourceScriptPromise;
}

async function ensureMapLibre(mapSource) {
  await loadStylesheet(mapSource.library.css_url);
  const maplibre = await loadScript(mapSource.library.script_url);
  if (!window.maplibregl) {
    throw new Error("MapLibre did not load from the configured source.");
  }
  return maplibre;
}

async function loadSeedProjects() {
  const manifest = await loadJson(SEED_MANIFEST_URL);
  if (!Array.isArray(manifest.project_paths)) {
    throw new Error("Seed manifest must contain project_paths.");
  }
  return Promise.all(
    manifest.project_paths.map((projectPath) => loadJson(new URL(projectPath, SEED_MANIFEST_URL))),
  );
}

function renderEvidence(aspect) {
  const list = document.createElement("ul");
  list.className = "evidence-list";
  for (const item of aspect.evidence) {
    const evidenceItem = document.createElement("li");
    evidenceItem.textContent = `${item.label} · ${item.type.replaceAll("-", " ")}`;
    list.append(evidenceItem);
  }
  return list;
}

function renderAspectCard(segment) {
  const { aspect, span } = segment;
  const card = document.createElement("article");
  card.className = "aspect-card";
  card.style.setProperty("--aspect-color", aspectColor(aspect));

  const heading = document.createElement("h3");
  heading.textContent = `${iconFor(aspect)} ${aspect.label}`;

  const token = document.createElement("span");
  token.className = "aspect-token";
  token.textContent = aspect.icon_token;
  heading.append(token);

  const weight = document.createElement("span");
  weight.className = "weight";
  weight.textContent = `${formatPercent(span)} profile weight`;
  heading.append(weight);

  const confidence = document.createElement("span");
  confidence.className = "confidence";
  confidence.textContent = `${formatPercent(aspect.confidence)} confidence`;
  heading.append(confidence);

  const description = document.createElement("p");
  description.textContent = aspect.description || "No aspect description supplied.";

  card.append(heading, description, renderEvidence(aspect));
  return card;
}

function setExpandedMarkerButton(nextButton) {
  for (const button of document.querySelectorAll(".map-marker .mixed-node")) {
    button.setAttribute("aria-expanded", button === nextButton ? "true" : "false");
  }
}

function openDetail(project, sourceButton) {
  activeMarkerButton = sourceButton;
  setExpandedMarkerButton(sourceButton);
  detailSurface.hidden = false;
  detailSurface.querySelector("[data-detail-kicker]").textContent = `${project.id} · ${project.location.label}`;
  detailSurface.querySelector("[data-detail-title]").textContent = project.title;
  detailSurface.querySelector("[data-detail-summary]").textContent = project.summary;
  detailSurface.querySelector("[data-detail-sphere]").textContent = project.sphere;
  detailSurface.querySelector("[data-detail-location]").textContent = `${project.location.mode} / ${project.location.precision}`;
  detailSurface.querySelector("[data-detail-privacy]").textContent = project.location.privacy_note || privacyLabel(project);
  detailSurface.querySelector("[data-detail-curation]").textContent = curationStateLabel(project);
  detailSurface.querySelector("[data-aspect-cards]").replaceChildren(...buildSegments(project).map(renderAspectCard));
  detailSurface.focus();
}

function closeDetail(options = {}) {
  const restoreFocus = options.restoreFocus !== false;
  detailSurface.hidden = true;
  setExpandedMarkerButton(null);
  if (restoreFocus && activeMarkerButton) {
    activeMarkerButton.focus();
  }
  activeMarkerButton = null;
}

function createMapMarkerElement(project) {
  const container = document.createElement("div");
  container.className = "map-marker";

  if (project.location.mode === "approximate") {
    const halo = document.createElement("span");
    halo.className = "approximate-halo";
    halo.setAttribute("aria-hidden", "true");
    container.append(halo);
  }

  const button = document.createElement("button");
  button.className = "mixed-node";
  button.type = "button";
  button.style.setProperty("--ring", gradientFor(project));
  button.setAttribute("aria-controls", "project-detail");
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-label", `${project.title}. ${privacyLabel(project)}. ${curationBadgeLabel(project)}. Open details.`);

  const core = document.createElement("span");
  core.className = "mixed-node-core";
  const title = document.createElement("span");
  title.className = "node-title";
  title.textContent = project.title;
  core.append(title);
  button.append(core);
  button.addEventListener("click", () => openDetail(project, button));
  container.append(button);

  if (project.location.mode === "approximate" || project.location.mode === "exact") {
    const badge = document.createElement("span");
    badge.className = `privacy-badge privacy-badge--${project.location.mode}`;
    badge.textContent = project.location.mode === "exact" ? "Exact" : "Approximate";
    container.append(badge);
  }

  const curationBadge = document.createElement("span");
  curationBadge.className = "curation-badge";
  curationBadge.textContent = curationBadgeLabel(project);
  container.append(curationBadge);

  return container;
}

function createMap(mapSource, maplibre) {
  return new maplibre.Map({
    container: "map",
    style: mapSource.basemap.style,
    center: mapSource.initial_view.center,
    zoom: mapSource.initial_view.zoom,
  });
}

async function initMap() {
  try {
    const mapSource = await loadMapSource();
    loadState.textContent = mapSource.disclosure;
    const maplibre = await ensureMapLibre(mapSource);
    const map = createMap(mapSource, maplibre);
    map.addControl(new maplibre.NavigationControl(), "top-right");
    const projects = await loadSeedProjects();
    const renderableProjects = projects.filter(isMapRenderable);
    const skippedProjects = projects.filter((project) => !isMapRenderable(project));

    for (const project of renderableProjects) {
      const { lon, lat } = project.location.coordinates;
      new maplibre.Marker({ element: createMapMarkerElement(project) }).setLngLat([lon, lat]).addTo(map);
    }

    loadState.textContent = `Map ready. ${renderableProjects.length} location-safe node rendered. ${skippedProjects.length} hidden node skipped.`;
  } catch (error) {
    loadState.textContent = error.message;
    loadState.dataset.error = "true";
  }
}

closeButton.addEventListener("click", () => closeDetail());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !detailSurface.hidden) {
    closeDetail();
  }
});

initMap();