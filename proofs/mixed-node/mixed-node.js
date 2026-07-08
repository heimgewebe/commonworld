import {
  aspectColor,
  buildSegments,
  curationBadgeLabel,
  formatConfidence,
  formatPercent,
  gradientFor,
  iconFor,
  loadSeedProjects,
} from "../shared/aspects.js";

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
