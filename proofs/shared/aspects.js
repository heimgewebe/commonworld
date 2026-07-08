// Shared CommonProject aspect and seed helpers for the static commonworld proofs.
//
// The mixed-node, map and aether proofs all render the same aspect ring geometry,
// percentage labels, curation badges and seed-manifest loading. This module is the
// single implementation so those surfaces cannot drift apart again.

export const SEED_MANIFEST_URL = new URL(
  "../../examples/commonworld/seed-projects.json",
  import.meta.url,
);

export const ASPECT_COLORS = {
  "aspect.data": "var(--aspect-data)",
  "aspect.community": "var(--aspect-community)",
  "aspect.infrastructure": "var(--aspect-infrastructure)",
  "aspect.repair": "var(--aspect-repair)",
  "aspect.education": "var(--aspect-education)",
  "aspect.mutual-aid": "var(--aspect-mutual-aid)",
};

export const ICON_GLYPHS = {
  "icon.map": "⌖",
  "icon.people": "◌",
  "icon.layers": "▣",
  "icon.tool": "⚒",
  "icon.book-open": "◇",
  "icon.hands": "∞",
};

export function aspectColor(aspect) {
  return ASPECT_COLORS[aspect.color_token] || "var(--line)";
}

export function iconFor(aspect) {
  return ICON_GLYPHS[aspect.icon_token] || aspect.icon_token;
}

export function sortAspects(aspects) {
  return [...aspects].sort((left, right) => {
    const byWeight = right.weight - left.weight;
    if (byWeight !== 0) return byWeight;
    const byLabel = left.label.localeCompare(right.label, "en", { sensitivity: "base" });
    if (byLabel !== 0) return byLabel;
    return left.id.localeCompare(right.id, "en", { sensitivity: "base" });
  });
}

export function buildSegments(project) {
  const ordered = sortAspects(project.aspects);
  let cursor = 0;
  return ordered.map((aspect, index) => {
    const start = cursor;
    const end = index === ordered.length - 1 ? 1 : cursor + aspect.weight;
    cursor = end;
    return { aspect, start, end, span: end - start };
  });
}

export function gradientFor(project) {
  const parts = buildSegments(project).map(
    ({ aspect, start, end }) => `${aspectColor(aspect)} ${start}turn ${end}turn`,
  );
  return `conic-gradient(${parts.join(", ")})`;
}

export function formatPercent(value) {
  const percent = value * 100;
  if (percent > 0 && percent < 1) return "<1%";
  if (percent < 10 && !Number.isInteger(percent)) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

export function formatConfidence(value) {
  return `${formatPercent(value)} confidence`;
}

export function curationStateLabel(project) {
  const state = project.curation?.state || "unreviewed";
  if (state === "fixture") return "Synthetic fixture";
  return state;
}

export function curationBadgeLabel(project) {
  const state = curationStateLabel(project);
  if (state === "Synthetic fixture") return state;
  return `Curation: ${state}`;
}

export async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}: ${response.status}`);
  }
  return response.json();
}

export async function loadSeedProjects() {
  const manifest = await loadJson(SEED_MANIFEST_URL);
  if (!Array.isArray(manifest.project_paths)) {
    throw new Error("Seed manifest must contain project_paths.");
  }
  return Promise.all(
    manifest.project_paths.map((projectPath) => loadJson(new URL(projectPath, SEED_MANIFEST_URL))),
  );
}
