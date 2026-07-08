import {
  aspectColor,
  buildSegments,
  curationBadgeLabel,
  curationStateLabel,
  formatConfidence,
  formatPercent,
  gradientFor,
  iconFor,
  loadJson,
  loadSeedProjects,
} from "../shared/aspects.js";

const MAP_SOURCE_URL = new URL("./map-source.json", import.meta.url);

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

function isMapRenderable(project) {
  const coordinates = project.location?.coordinates;
  const mode = project.location?.mode;
  return (
    (mode === "exact" || mode === "approximate") &&
    Number.isFinite(coordinates?.lat) &&
    Number.isFinite(coordinates?.lon)
  );
}

function privacyLabel(project) {
  if (project.location.mode === "approximate") return "Approximate location";
  if (project.location.mode === "exact") return "Exact location";
  return "Hidden location";
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
  confidence.textContent = formatConfidence(aspect.confidence);
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

    const renderedLabel = renderableProjects.length === 1 ? "node" : "nodes";
    const skippedLabel = skippedProjects.length === 1 ? "project" : "projects";
    loadState.textContent = `Map ready. ${renderableProjects.length} location-safe ${renderedLabel} rendered. ${skippedProjects.length} non-map ${skippedLabel} skipped.`;
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