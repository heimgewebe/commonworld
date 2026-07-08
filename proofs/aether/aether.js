const SEED_MANIFEST_URL = new URL("../mixed-node/seed-projects.json", import.meta.url);

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
    throw new Error("Aether proof is missing " + selector);
  }
  return element;
}

const branchList = requiredElement("[data-aether-list]");
const branchCount = requiredElement("[data-aether-count]");
const loadState = requiredElement("[data-load-state]");
const activeBranch = requiredElement("[data-active-branch]");
const activeKicker = requiredElement("[data-active-kicker]");
const activeTitle = requiredElement("[data-active-title]");
const activeSummary = requiredElement("[data-active-summary]");
const activeSphere = requiredElement("[data-active-sphere]");
const activeLocation = requiredElement("[data-active-location]");
const activeCuration = requiredElement("[data-active-curation]");
const activeHandoff = requiredElement("[data-active-handoff]");
const activeAspects = requiredElement("[data-active-aspects]");
const activeSources = requiredElement("[data-active-sources]");
let activeBranchButton = null;
let branchButtons = [];

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}: ${response.status}`);
  }
  return response.json();
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

function filterAetherProjects(projects) {
  return projects.filter((project) => project.projections?.aether);
}

function sortAetherProjects(projects) {
  return [...projects].sort((left, right) => left.title.localeCompare(right.title, "en", { sensitivity: "base" }));
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

function iconFor(aspect) {
  return ICON_GLYPHS[aspect.icon_token] || aspect.icon_token;
}

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function setActiveButton(nextButton) {
  for (const button of branchButtons) {
    const isActive = button === nextButton;
    button.setAttribute("aria-current", isActive ? "true" : "false");
    button.setAttribute("aria-expanded", isActive ? "true" : "false");
  }
}

function handoffLabel(project) {
  if (project.handoff?.enabled === false) return "Locked until weltgewebe project identity exists";
  return "No handoff declared";
}

function renderBranchButton(project) {
  const button = document.createElement("button");
  button.className = "aether-card";
  button.type = "button";
  button.setAttribute("aria-controls", "aether-active-branch");
  button.setAttribute("aria-expanded", "false");

  const title = document.createElement("strong");
  title.textContent = project.title;
  const meta = document.createElement("span");
  const projection = project.projections?.aether;
  const signal = projection?.ortssignal ? " · Ortssignal" : "";
  meta.textContent = `${projection?.stream || "aether"}${signal} · ${project.sphere || "unknown"} / ${project.location?.mode || "hidden"} · ${curationBadgeLabel(project)}`;

  button.append(title, meta);
  button.addEventListener("click", () => setActiveBranch(project, button));
  return button;
}

function renderAspectCard(aspect) {
  const card = document.createElement("article");
  card.className = "aspect-card";
  card.style.setProperty("--aspect-color", `var(--${aspect.color_token.replaceAll(".", "-")})`);

  const heading = document.createElement("h3");
  heading.textContent = `${iconFor(aspect)} ${aspect.label}`;

  const weight = document.createElement("span");
  weight.className = "weight";
  weight.textContent = `${formatPercent(aspect.weight)} profile weight`;
  heading.append(weight);

  const confidence = document.createElement("span");
  confidence.className = "confidence";
  confidence.textContent = `${formatPercent(aspect.confidence)} confidence`;
  heading.append(confidence);

  const description = document.createElement("p");
  description.textContent = aspect.description;

  const evidence = document.createElement("p");
  evidence.className = "evidence-pill";
  evidence.textContent = `${aspect.evidence.length} evidence item${aspect.evidence.length === 1 ? "" : "s"}`;

  card.append(heading, description, evidence);
  return card;
}

function renderSources(project) {
  return (project.provenance?.sources || []).map((source) => {
    const item = document.createElement("li");
    item.textContent = `${source.label} · ${source.type.replaceAll("-", " ")}`;
    return item;
  });
}

function setActiveBranch(project, sourceButton) {
  activeBranchButton = sourceButton;
  setActiveButton(sourceButton);
  activeKicker.textContent = `${project.id} · ${project.location?.label || "Digital Commons"}`;
  activeTitle.textContent = project.title;
  activeSummary.textContent = project.summary;
  activeSphere.textContent = project.sphere || "unknown";
  activeLocation.textContent = `${project.location?.mode || "hidden"} / ${project.location?.precision || "none"}`;
  activeCuration.textContent = curationStateLabel(project);
  activeHandoff.innerHTML = "";
  const lock = document.createElement("span");
  lock.className = "handoff-lock";
  lock.textContent = handoffLabel(project);
  activeHandoff.append(lock);
  activeAspects.replaceChildren(...(project.aspects || []).map(renderAspectCard));
  activeSources.replaceChildren(...renderSources(project));
  activeBranch.focus();
}

async function initAether() {
  const projects = sortAetherProjects(filterAetherProjects(await loadSeedProjects()));
  if (projects.length === 0) {
    throw new Error("No digital Commons projects available for the Aether proof.");
  }
  branchButtons = projects.map(renderBranchButton);
  branchList.replaceChildren(...branchButtons);
  branchCount.textContent = `${projects.length} focus branch${projects.length === 1 ? "" : "es"}`;
  loadState.textContent = `${projects.length} Aether branch${projects.length === 1 ? "" : "es"} loaded from explicit aether projections without forced map placement.`;
  setActiveBranch(projects[0], branchButtons[0]);
}

initAether().catch((error) => {
  loadState.textContent = error.message;
  loadState.dataset.error = "true";
});
