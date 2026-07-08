const SEED_MANIFEST_URL = new URL("../../examples/commonworld/seed-projects.json", import.meta.url);

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

function requiredElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error("Mixed-node proof is missing " + selector);
  }
  return element;
}

const nodeList = requiredElement("[data-node-list]");
const loadState = requiredElement("[data-load-state]");
const detailSurface = requiredElement("[data-detail-surface]");
const closeButton = requiredElement("[data-close-detail]");
let activeNodeButton = null;

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

function gradientFor(project) {
  const parts = buildSegments(project).map(({ aspect, start, end }) => {
    return `${aspectColor(aspect)} ${start}turn ${end}turn`;
  });
  return `conic-gradient(${parts.join(", ")})`;
}

function formatPercent(value) {
  const percent = value * 100;
  if (percent > 0 && percent < 1) return "<1%";
  if (percent < 10 && !Number.isInteger(percent)) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function formatConfidence(value) {
  return `${Math.round(value * 100)}% confidence`;
}

function evidenceText(evidence) {
  return evidence
    .map((item) => {
      const type = item.type.replaceAll("-", " ");
      return `${item.label} · ${type}`;
    })
    .join("; ");
}

function setExpandedButton(nextButton) {
  for (const button of nodeList.querySelectorAll(".mixed-node")) {
    button.setAttribute("aria-expanded", button === nextButton ? "true" : "false");
  }
}

function curationBadgeLabel(project) {
  const state = project.curation?.state || "unreviewed";
  if (state === "fixture") return "Synthetic fixture";
  return `Curation: ${state}`;
}

function renderNode(project) {
  const segments = buildSegments(project);
  const wrapper = document.createElement("article");
  wrapper.className = "mixed-node-card";

  const button = document.createElement("button");
  button.className = "mixed-node";
  button.type = "button";
  button.style.setProperty("--ring", gradientFor(project));
  button.setAttribute("aria-controls", "project-detail");
  button.setAttribute("aria-expanded", "false");

  const curationBadge = curationBadgeLabel(project);
  const accessibilityParts = [
    `${project.title}: ${segments
      .map(({ aspect }) => `${aspect.label}, ${formatPercent(aspect.weight)}`)
      .join(", ")}.`,
    curationBadge ? `${curationBadge}.` : "",
    "Open details.",
  ].filter(Boolean);
  button.setAttribute("aria-label", accessibilityParts.join(" "));
  button.addEventListener("click", () => openDetail(project, button));

  const core = document.createElement("span");
  core.className = "mixed-node-core";
  const title = document.createElement("span");
  title.className = "node-title";
  title.textContent = project.title;
  core.append(title);
  button.append(core);

  const aspectSummary = document.createElement("p");
  aspectSummary.className = "node-aspects";
  aspectSummary.textContent = segments
    .map(({ aspect }) => `${iconFor(aspect)} ${aspect.label} ${formatPercent(aspect.weight)}`)
    .join(" · ");

  wrapper.append(button, aspectSummary);

  if (curationBadge) {
    const badge = document.createElement("p");
    badge.className = "node-badge";
    badge.textContent = curationBadge;
    wrapper.append(badge);
  }

  return wrapper;
}

function iconFor(aspect) {
  return ICON_GLYPHS[aspect.icon_token] || aspect.icon_token;
}

function renderEvidence(aspect) {
  const list = document.createElement("ul");
  list.className = "evidence-list";

  for (const item of aspect.evidence) {
    const evidenceItem = document.createElement("li");
    evidenceItem.textContent = evidenceText([item]);
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

function openDetail(project, sourceButton) {
  activeNodeButton = sourceButton;
  setExpandedButton(sourceButton);
  detailSurface.hidden = false;
  detailSurface.querySelector("[data-detail-kicker]").textContent = `${project.id} · ${project.location.label}`;
  detailSurface.querySelector("[data-detail-title]").textContent = project.title;
  detailSurface.querySelector("[data-detail-summary]").textContent = project.summary;
  detailSurface.querySelector("[data-detail-sphere]").textContent = project.sphere;
  detailSurface.querySelector("[data-detail-location]").textContent = `${project.location.mode} / ${project.location.precision}`;
  detailSurface.querySelector("[data-detail-curation]").textContent = project.curation.state;

  const cards = detailSurface.querySelector("[data-aspect-cards]");
  cards.replaceChildren(...buildSegments(project).map(renderAspectCard));
  detailSurface.focus();
}

function closeDetail(options = {}) {
  const restoreFocus = options.restoreFocus !== false;
  detailSurface.hidden = true;
  setExpandedButton(null);
  if (restoreFocus && activeNodeButton) {
    activeNodeButton.focus();
  }
  activeNodeButton = null;
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}: ${response.status}`);
  }
  return response.json();
}

async function loadSeedProjects() {
  const manifest = await loadJson(SEED_MANIFEST_URL); if (!Array.isArray(manifest.project_paths)) { throw new Error("Seed manifest must contain project_paths."); }
  return Promise.all(
    manifest.project_paths.map((projectPath) => loadJson(new URL(projectPath, SEED_MANIFEST_URL))),
  );
}

async function init() {
  const projects = await loadSeedProjects();
  nodeList.replaceChildren(...projects.map(renderNode));
  loadState.textContent = `${projects.length} seed projects loaded from CommonProject examples.`;
}

closeButton.addEventListener("click", () => closeDetail());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !detailSurface.hidden) {
    closeDetail();
  }
});

init().catch((error) => {
  loadState.textContent = error.message;
  loadState.dataset.error = "true";
});
