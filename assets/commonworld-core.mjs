export const DEFAULT_CAMERA = Object.freeze({
  lng: 8,
  lat: 24,
  zoom: 1.15,
  bearing: 0,
  pitch: 0,
});

export const MAX_MAP_ZOOM = 18;
export const DIGITAL_LAYER_TRANSITION_MS = 1080;
const DIGITAL_LAYER_MAX_ZOOM = 8;

export const LAYERS = Object.freeze([
  Object.freeze({ id: 'knowledge_data', label: 'Wissen und offene Daten', trackLabel: 'Wissen', themes: ['knowledge', 'open-data', 'research', 'documentation'] }),
  Object.freeze({ id: 'software_infrastructure', label: 'Freie Software und Infrastruktur', trackLabel: 'Software', themes: ['free-software', 'open-source', 'infrastructure', 'platform'] }),
  Object.freeze({ id: 'media_culture', label: 'Offene Medien und Kultur', trackLabel: 'Medien', themes: ['open-media', 'culture', 'archives', 'creative-commons'] }),
  Object.freeze({ id: 'learning_education', label: 'Freies Lernen und Bildung', trackLabel: 'Lernen', themes: ['education', 'open-educational-resources', 'learning'] }),
  Object.freeze({ id: 'communication_networks', label: 'Kommunikation und Netze', trackLabel: 'Netze', themes: ['communication', 'community-network', 'federation', 'protocol'] }),
  Object.freeze({ id: 'mixed_other', label: 'Gemischte und weitere digitale Commons', trackLabel: 'Weitere', themes: [] }),
]);

export const DIGITAL_TAXONOMY_VERSION = 'digital-ring-bundles-v1';
export const DIGITAL_ROOT_ID = 'sphere';
export const DIGITAL_ROOT_PATH = Object.freeze([DIGITAL_ROOT_ID]);
const DIGITAL_UNCLASSIFIED_NODE_ID = 'unclassified_future_theme';
const DIGITAL_ID_PATTERN = /^[a-z][a-z0-9_-]{0,95}$/;

const deepFreeze = (value) => {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const child of Object.values(value)) deepFreeze(child);
  return value;
};

export const DIGITAL_TAXONOMY = deepFreeze({
  schema_version: 1,
  kind: 'commonworld_digital_ring_bundle_taxonomy',
  version: DIGITAL_TAXONOMY_VERSION,
  version_rule: 'Minor versions may add explicit themes and child nodes; existing stable ids, parent paths and legacy aliases remain valid until a new major version.',
  levels: ['sphere', 'field', 'network', 'identity'],
  root_id: DIGITAL_ROOT_ID,
  unknown_theme_node_id: DIGITAL_UNCLASSIFIED_NODE_ID,
  nodes: [
    { id: DIGITAL_ROOT_ID, parent_id: null, type: 'sphere', label_de: 'Digitale Commons-Sphäre', order: 0, themes: [] },
    { id: 'knowledge_learning_culture', parent_id: DIGITAL_ROOT_ID, type: 'field', label_de: 'Wissen, Lernen und Kultur', order: 0, themes: [] },
    { id: 'software_tools_production', parent_id: DIGITAL_ROOT_ID, type: 'field', label_de: 'Software, Werkzeuge und Produktion', order: 1, themes: [] },
    { id: 'communication_networks', parent_id: DIGITAL_ROOT_ID, type: 'field', label_de: 'Kommunikation und Netze', order: 2, themes: [] },
    { id: 'provision_land_ecology', parent_id: DIGITAL_ROOT_ID, type: 'field', label_de: 'Versorgung, Land und Ökologie', order: 3, themes: [] },
    { id: 'cooperation_self_organization', parent_id: DIGITAL_ROOT_ID, type: 'field', label_de: 'Kooperation und Selbstorganisation', order: 4, themes: [] },
    { id: DIGITAL_UNCLASSIFIED_NODE_ID, parent_id: DIGITAL_ROOT_ID, type: 'diagnostic', label_de: 'Unklassifizierte neue Themen', order: 90, themes: [] },

    { id: 'open_knowledge_data', parent_id: 'knowledge_learning_culture', type: 'network', label_de: 'Offenes Wissen und Daten', order: 0, themes: ['knowledge', 'open-data', 'open-knowledge', 'documentation', 'research'] },
    { id: 'learning_education', parent_id: 'knowledge_learning_culture', type: 'network', label_de: 'Lernen und Bildung', order: 1, themes: ['education', 'learning', 'open-educational-resources', 'digital-literacy', 'environmental-education'] },
    { id: 'media_culture', parent_id: 'knowledge_learning_culture', type: 'network', label_de: 'Medien, Archive und Kultur', order: 2, themes: ['open-media', 'creative-commons', 'culture', 'archives'] },
    { id: 'knowledge_learning_bridge', parent_id: 'knowledge_learning_culture', type: 'interface', label_de: 'Wissens- und Lernbrücke', order: 3, themes: [] },

    { id: 'free_software', parent_id: 'software_tools_production', type: 'network', label_de: 'Freie Software und Infrastruktur', order: 0, themes: ['free-software', 'open-source', 'software-infrastructure', 'infrastructure'] },
    { id: 'open_hardware_production', parent_id: 'software_tools_production', type: 'network', label_de: 'Offene Hardware und Produktion', order: 1, themes: ['open-hardware', 'distributed-manufacturing'] },
    { id: 'shared_platforms_tools', parent_id: 'software_tools_production', type: 'network', label_de: 'Plattformen und geteilte Werkzeuge', order: 2, themes: ['platform', 'shared-tools', 'tool-sharing', 'repair', 'circular-economy', 'skills'] },
    { id: 'knowledge_software_bridge', parent_id: 'software_tools_production', type: 'interface', label_de: 'Daten- und Softwarebrücke', order: 3, themes: [] },

    { id: 'community_networks', parent_id: 'communication_networks', type: 'network', label_de: 'Gemeinschaftsnetze', order: 0, themes: ['communication', 'community-network', 'rural-infrastructure', 'digital-equity'] },
    { id: 'federated_protocols', parent_id: 'communication_networks', type: 'network', label_de: 'Föderation und Protokolle', order: 1, themes: ['federation', 'protocol'] },
    { id: 'network_coordination', parent_id: 'communication_networks', type: 'network', label_de: 'Vernetzte Koordination', order: 2, themes: ['network'] },

    { id: 'food_seed_agriculture', parent_id: 'provision_land_ecology', type: 'network', label_de: 'Saatgut, Ernährung und Landwirtschaft', order: 0, themes: ['seeds', 'food', 'agriculture'] },
    { id: 'water_irrigation', parent_id: 'provision_land_ecology', type: 'network', label_de: 'Wasser und Bewässerung', order: 1, themes: ['water', 'irrigation'] },
    { id: 'renewable_energy', parent_id: 'provision_land_ecology', type: 'network', label_de: 'Erneuerbare Energie', order: 2, themes: ['energy', 'renewable-energy'] },
    { id: 'health_software', parent_id: 'provision_land_ecology', type: 'interface', label_de: 'Offene Gesundheitsversorgung', order: 3, themes: ['health'] },
    { id: 'land_ecology', parent_id: 'provision_land_ecology', type: 'network', label_de: 'Land, Stadtgrün und Ökologie', order: 4, themes: ['urban-gardening', 'biodiversity', 'community-land'] },
    { id: 'food_distribution_platforms', parent_id: 'provision_land_ecology', type: 'interface', label_de: 'Ernährungsplattformen', order: 5, themes: [] },
    { id: 'energy_cooperatives', parent_id: 'provision_land_ecology', type: 'interface', label_de: 'Energiegenossenschaften', order: 6, themes: [] },
    { id: 'watershed_food_systems', parent_id: 'provision_land_ecology', type: 'interface', label_de: 'Wasser- und Ernährungssysteme', order: 7, themes: [] },

    { id: 'cooperative_governance', parent_id: 'cooperation_self_organization', type: 'network', label_de: 'Gemeinschaftliche Governance und Genossenschaften', order: 0, themes: ['commons-governance', 'community-ownership', 'cooperative-economy', 'cooperative'] },
    { id: 'civic_technology', parent_id: 'cooperation_self_organization', type: 'interface', label_de: 'Civic Tech und Selbstorganisation', order: 1, themes: ['civic-tech'] },
    { id: 'mutual_local_self_help', parent_id: 'cooperation_self_organization', type: 'network', label_de: 'Nachbarschaft und gegenseitige Hilfe', order: 2, themes: ['mutual-aid', 'neighbourhood'] },
  ],
  compound_rules: [
    { id: 'food_seed_system', all_themes: ['seeds', 'food', 'agriculture'], target_node_id: 'food_seed_agriculture', reason: 'seed, food and agriculture evidence forms one provision bundle' },
    { id: 'open_data_infrastructure', all_themes: ['open-data', 'infrastructure'], target_node_id: 'knowledge_software_bridge', reason: 'open data whose public utility is infrastructure' },
    { id: 'community_network_infrastructure', all_themes: ['communication', 'community-network'], target_node_id: 'community_networks', reason: 'digital communication commons organized as community networks' },
    { id: 'food_platform', all_themes: ['food', 'platform'], target_node_id: 'food_distribution_platforms', reason: 'food commons mediated by an open platform' },
    { id: 'energy_cooperative', all_themes: ['energy', 'cooperative-economy'], target_node_id: 'energy_cooperatives', reason: 'energy provision organized cooperatively' },
    { id: 'community_owned_energy', all_themes: ['energy', 'community-ownership'], target_node_id: 'energy_cooperatives', reason: 'energy provision held through community ownership' },
    { id: 'water_food', all_themes: ['water', 'food'], target_node_id: 'watershed_food_systems', reason: 'water governance tied to food and agriculture' },
    { id: 'open_source_hardware_production', all_themes: ['open-source', 'open-hardware', 'distributed-manufacturing'], target_node_id: 'open_hardware_production', reason: 'open source ecology combines software, hardware and distributed production' },
    { id: 'health_open_software', all_themes: ['health', 'open-source'], target_node_id: 'health_software', reason: 'health provision implemented as open software' },
    { id: 'civic_tech_open_data', all_themes: ['civic-tech', 'open-data'], target_node_id: 'civic_technology', reason: 'civic technology coordinates data, code and governance' },
  ],
  tie_rules: [
    { id: 'knowledge_learning_same_field', candidate_node_ids: ['learning_education', 'open_knowledge_data'], target_node_id: 'knowledge_learning_bridge', reason: 'equal knowledge and learning themes share the knowledge field' },
    { id: 'knowledge_software_cross_field', candidate_node_ids: ['free_software', 'open_knowledge_data'], target_node_id: 'knowledge_software_bridge', reason: 'equal data and software evidence becomes an explicit interface bundle' },
    { id: 'food_water_same_field', candidate_node_ids: ['food_seed_agriculture', 'water_irrigation'], target_node_id: 'watershed_food_systems', reason: 'equal food and water evidence shares the provision field' },
  ],
  same_field_tie_fallbacks: {
    knowledge_learning_culture: 'knowledge_learning_bridge',
    software_tools_production: 'knowledge_software_bridge',
    provision_land_ecology: 'watershed_food_systems',
  },
  legacy_layer_aliases: [
    { alias: 'knowledge_data', target_path: ['sphere', 'knowledge_learning_culture', 'open_knowledge_data'], reason: 'legacy six-layer knowledge/data links' },
    { alias: 'software_infrastructure', target_path: ['sphere', 'software_tools_production', 'free_software'], reason: 'legacy six-layer software/infrastructure links' },
    { alias: 'media_culture', target_path: ['sphere', 'knowledge_learning_culture', 'media_culture'], reason: 'legacy six-layer media/culture links' },
    { alias: 'learning_education', target_path: ['sphere', 'knowledge_learning_culture', 'learning_education'], reason: 'legacy six-layer learning links' },
    { alias: 'communication_networks', target_path: ['sphere', 'communication_networks', 'community_networks'], reason: 'legacy six-layer communication links' },
    { alias: 'mixed_other', target_path: ['sphere'], broad_alias_without_filter: true, reason: 'legacy broad fallback cannot be a durable public bundle' },
  ],
});

export const DIGITAL_RING_FIELDS = Object.freeze(
  DIGITAL_TAXONOMY.nodes
    .filter((node) => node.parent_id === DIGITAL_ROOT_ID && node.type === 'field')
    .sort((left, right) => left.order - right.order)
    .map((node) => Object.freeze({
      id: node.id,
      label: node.label_de,
      trackLabel: node.label_de.split(',')[0],
      path: Object.freeze([DIGITAL_ROOT_ID, node.id]),
    })),
);

export const ORBIT_PROFILES = Object.freeze([
  Object.freeze({ rx: 316, ry: 300, rotation: -8 }),
  Object.freeze({ rx: 310, ry: 282, rotation: 20 }),
  Object.freeze({ rx: 304, ry: 268, rotation: 43 }),
  Object.freeze({ rx: 298, ry: 288, rotation: -31 }),
  Object.freeze({ rx: 292, ry: 274, rotation: 63 }),
  Object.freeze({ rx: 286, ry: 294, rotation: -62 }),
  Object.freeze({ rx: 280, ry: 262, rotation: 78 }),
  Object.freeze({ rx: 274, ry: 284, rotation: -77 }),
]);

const finite = (value, fallback) => {
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
const rounded = (value, digits) => Number(value.toFixed(digits));

export function safeExternalHttpsUrl(value) {
  if (typeof value !== 'string' || value.trim() !== value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export function hasDigitalPresence(record) {
  return record?.presence?.digital?.available === true;
}

export function deriveLayer(record) {
  if (!hasDigitalPresence(record)) return null;
  const themes = new Set(Array.isArray(record.themes) ? record.themes : []);
  const scores = LAYERS.filter((layer) => layer.id !== 'mixed_other').map((layer) => ({
    id: layer.id,
    score: layer.themes.reduce((total, theme) => total + (themes.has(theme) ? 1 : 0), 0),
  }));
  const maximum = Math.max(0, ...scores.map(({ score }) => score));
  const winners = scores.filter(({ score }) => score === maximum && score > 0);
  return winners.length === 1 ? winners[0].id : 'mixed_other';
}

function digitalNodeMap(taxonomy = DIGITAL_TAXONOMY) {
  return new Map((taxonomy.nodes ?? []).map((node) => [node.id, node]));
}

function digitalChildrenByParent(taxonomy = DIGITAL_TAXONOMY) {
  const children = new Map();
  for (const node of taxonomy.nodes ?? []) {
    if (node.parent_id === null || node.parent_id === undefined) continue;
    if (!children.has(node.parent_id)) children.set(node.parent_id, []);
    children.get(node.parent_id).push(node);
  }
  for (const values of children.values()) {
    values.sort((left, right) => left.order - right.order || left.id.localeCompare(right.id));
  }
  return children;
}

function digitalThemeMap(taxonomy = DIGITAL_TAXONOMY) {
  const map = new Map();
  for (const node of taxonomy.nodes ?? []) {
    for (const theme of Array.isArray(node.themes) ? node.themes : []) {
      map.set(theme, node.id);
    }
  }
  return map;
}

function digitalParentPath(nodeId, taxonomy = DIGITAL_TAXONOMY) {
  const nodes = digitalNodeMap(taxonomy);
  const path = [];
  let current = nodes.get(nodeId);
  const seen = new Set();
  while (current) {
    if (seen.has(current.id)) return null;
    seen.add(current.id);
    path.unshift(current.id);
    if (current.parent_id === null || current.parent_id === undefined) break;
    current = nodes.get(current.parent_id);
  }
  return path[0] === taxonomy.root_id ? Object.freeze(path) : null;
}

export function serializeDigitalPath(path = DIGITAL_ROOT_PATH) {
  const parts = Array.isArray(path) ? path : String(path ?? '').split('/');
  const cleaned = parts.map((part) => String(part ?? '').trim()).filter(Boolean);
  return cleaned.length ? cleaned.join('/') : DIGITAL_ROOT_ID;
}

export function digitalPathFromLegacyLayer(layerId, taxonomy = DIGITAL_TAXONOMY) {
  const alias = (taxonomy.legacy_layer_aliases ?? []).find((entry) => entry.alias === layerId);
  return alias ? Object.freeze([...alias.target_path]) : null;
}

export function normalizeDigitalPath(value = '', { taxonomy = DIGITAL_TAXONOMY } = {}) {
  const root = Object.freeze([taxonomy.root_id ?? DIGITAL_ROOT_ID]);
  const fail = (reason) => Object.freeze({
    valid: false,
    reason,
    path: root,
    pathKey: serializeDigitalPath(root),
    nodeId: root[0],
  });
  const isArray = Array.isArray(value);
  const serialized = isArray ? null : String(value ?? '');
  // Only an absent/empty value denotes the root; every explicit slash must separate two canonical segments.
  if (!isArray && serialized === '') {
    return Object.freeze({ valid: true, reason: 'root', path: root, pathKey: serializeDigitalPath(root), nodeId: root[0] });
  }
  const parts = isArray ? value.map((part) => String(part ?? '')) : serialized.split('/');
  if (!parts.length || parts.some((part) => part.length === 0 || part !== part.trim())) return fail('empty-or-whitespace-segment');
  if (parts.some((part) => part === '.' || part === '..' || !DIGITAL_ID_PATTERN.test(part))) return fail('invalid-segment');
  if (parts[0] !== (taxonomy.root_id ?? DIGITAL_ROOT_ID)) return fail('wrong-root');

  const nodes = digitalNodeMap(taxonomy);
  let current = nodes.get(parts[0]);
  if (!current) return fail('missing-root');
  for (const part of parts.slice(1)) {
    const next = nodes.get(part);
    if (!next || next.parent_id !== current.id) return fail('unknown-child');
    current = next;
  }
  const path = Object.freeze([...parts]);
  return Object.freeze({
    valid: true,
    reason: 'matched',
    path,
    pathKey: serializeDigitalPath(path),
    nodeId: current.id,
  });
}

function explicitFieldIds(taxonomy = DIGITAL_TAXONOMY) {
  return (taxonomy.nodes ?? [])
    .filter((node) => node.parent_id === taxonomy.root_id && node.type === 'field')
    .sort((left, right) => left.order - right.order)
    .map((node) => node.id);
}

export function validateDigitalTaxonomy(taxonomy = DIGITAL_TAXONOMY) {
  const errors = [];
  if (taxonomy.schema_version !== 1) errors.push('digital taxonomy schema_version must be 1');
  if (taxonomy.kind !== 'commonworld_digital_ring_bundle_taxonomy') errors.push('digital taxonomy kind mismatch');
  if (taxonomy.version !== DIGITAL_TAXONOMY_VERSION) errors.push('digital taxonomy version mismatch');
  if (!Array.isArray(taxonomy.levels) || taxonomy.levels.join('>') !== 'sphere>field>network>identity') errors.push('digital taxonomy levels must be sphere > field > network > identity');
  const nodes = Array.isArray(taxonomy.nodes) ? taxonomy.nodes : [];
  if (!nodes.length) errors.push('digital taxonomy nodes must be a non-empty array');
  const nodeIds = nodes.map((node) => node?.id);
  if (new Set(nodeIds).size !== nodeIds.length) errors.push('digital taxonomy node ids must be unique');
  const nodeMap = digitalNodeMap(taxonomy);
  const roots = nodes.filter((node) => node.parent_id === null);
  if (roots.length !== 1 || roots[0]?.id !== taxonomy.root_id || roots[0]?.type !== 'sphere') errors.push('digital taxonomy must have exactly one sphere root');
  for (const node of nodes) {
    if (!DIGITAL_ID_PATTERN.test(node.id ?? '')) errors.push(`digital taxonomy node id is not stable ASCII: ${node.id}`);
    if (!['sphere', 'field', 'network', 'interface', 'diagnostic'].includes(node.type)) errors.push(`digital taxonomy node has invalid type: ${node.id}`);
    if (typeof node.label_de !== 'string' || !node.label_de.trim()) errors.push(`digital taxonomy node lacks German label: ${node.id}`);
    if (!Number.isInteger(node.order) || node.order < 0) errors.push(`digital taxonomy node lacks stable order: ${node.id}`);
    if (node.parent_id !== null && !nodeMap.has(node.parent_id)) errors.push(`digital taxonomy node has missing parent: ${node.id}`);
  }
  for (const [parentId, children] of digitalChildrenByParent(taxonomy)) {
    const orders = children.map((node) => node.order);
    if (new Set(orders).size !== orders.length) errors.push(`digital taxonomy sibling order is not unique below ${parentId}`);
  }
  for (const node of nodes) {
    const seen = new Set();
    let current = node;
    while (current?.parent_id !== null && current?.parent_id !== undefined) {
      if (seen.has(current.id)) {
        errors.push(`digital taxonomy contains a cycle at ${node.id}`);
        break;
      }
      seen.add(current.id);
      current = nodeMap.get(current.parent_id);
    }
  }
  const fieldIds = explicitFieldIds(taxonomy);
  if (fieldIds.join('|') !== 'knowledge_learning_culture|software_tools_production|communication_networks|provision_land_ecology|cooperation_self_organization') {
    errors.push('digital taxonomy must expose exactly the five canonical main fields');
  }

  const themeOwners = new Map();
  for (const node of nodes) {
    for (const theme of Array.isArray(node.themes) ? node.themes : []) {
      if (themeOwners.has(theme)) errors.push(`digital taxonomy theme has multiple owners: ${theme}`);
      themeOwners.set(theme, node.id);
    }
  }
  const compoundThemes = new Set();
  for (const rule of taxonomy.compound_rules ?? []) {
    if (!DIGITAL_ID_PATTERN.test(rule.id ?? '')) errors.push(`digital taxonomy compound rule id is invalid: ${rule.id}`);
    if (!nodeMap.has(rule.target_node_id)) errors.push(`digital taxonomy compound rule targets missing node: ${rule.id}`);
    const allThemes = Array.isArray(rule.all_themes) ? rule.all_themes : [];
    if (!allThemes.length) errors.push(`digital taxonomy compound rule has no themes: ${rule.id}`);
    for (const theme of allThemes) {
      if (!themeOwners.has(theme)) errors.push(`digital taxonomy compound rule references unknown theme: ${rule.id}:${theme}`);
      compoundThemes.add(theme);
    }
  }
  const tieKeys = new Set();
  for (const rule of taxonomy.tie_rules ?? []) {
    if (!DIGITAL_ID_PATTERN.test(rule.id ?? '')) errors.push(`digital taxonomy tie rule id is invalid: ${rule.id}`);
    if (!nodeMap.has(rule.target_node_id)) errors.push(`digital taxonomy tie rule targets missing node: ${rule.id}`);
    const candidates = Array.isArray(rule.candidate_node_ids) ? [...rule.candidate_node_ids].sort() : [];
    if (candidates.length < 2 || candidates.some((id) => !nodeMap.has(id))) errors.push(`digital taxonomy tie rule candidates are invalid: ${rule.id}`);
    const key = candidates.join('|');
    if (tieKeys.has(key)) errors.push(`digital taxonomy duplicate tie rule candidate set: ${key}`);
    tieKeys.add(key);
  }
  const aliases = Array.isArray(taxonomy.legacy_layer_aliases) ? taxonomy.legacy_layer_aliases : [];
  const aliasIds = aliases.map((alias) => alias?.alias);
  if (new Set(aliasIds).size !== aliasIds.length) errors.push('digital taxonomy legacy aliases must be unique');
  for (const alias of aliases) {
    if (!LAYERS.some(({ id }) => id === alias.alias)) errors.push(`digital taxonomy legacy alias is not an old layer id: ${alias.alias}`);
    const normalized = normalizeDigitalPath(alias.target_path, { taxonomy });
    if (!normalized.valid) errors.push(`digital taxonomy legacy alias target is invalid: ${alias.alias}`);
    if (typeof alias.reason !== 'string' || !alias.reason.trim()) errors.push(`digital taxonomy legacy alias lacks reason: ${alias.alias}`);
    if (alias.alias === 'mixed_other' && (normalized.pathKey !== taxonomy.root_id || alias.broad_alias_without_filter !== true)) {
      errors.push('digital taxonomy legacy mixed_other alias must orient to the unfiltered root');
    }
  }
  for (const layer of LAYERS) {
    if (!aliases.some((alias) => alias.alias === layer.id)) errors.push(`digital taxonomy missing legacy alias for ${layer.id}`);
  }
  if (!nodeMap.has(taxonomy.unknown_theme_node_id)) errors.push('digital taxonomy unknown-theme diagnostic node is missing');
  return Object.freeze(errors);
}

function candidateFieldId(nodeId, taxonomy = DIGITAL_TAXONOMY) {
  const nodes = digitalNodeMap(taxonomy);
  let current = nodes.get(nodeId);
  while (current && current.parent_id !== null && current.parent_id !== taxonomy.root_id) current = nodes.get(current.parent_id);
  return current?.type === 'field' ? current.id : null;
}

function addCandidate(candidates, nodeId, score, matchedThemes, source) {
  const existing = candidates.get(nodeId);
  if (!existing || existing.score < score) {
    const previousThemes = existing ? [...existing.matchedThemes] : [];
    const previousSources = existing ? [...existing.sources] : [];
    candidates.set(nodeId, { nodeId, score, matchedThemes: new Set([...previousThemes, ...matchedThemes]), sources: new Set([...previousSources, source]) });
    return;
  }
  if (source.startsWith('theme:') && [...existing.sources].every((entry) => entry.startsWith('theme:'))) {
    existing.score += score;
    for (const theme of matchedThemes) existing.matchedThemes.add(theme);
    existing.sources.add(source);
    return;
  }
  if (existing.score === score) {
    for (const theme of matchedThemes) existing.matchedThemes.add(theme);
    existing.sources.add(source);
  }
}

function freezeDerivation(result) {
  return Object.freeze({
    ...result,
    path: result.path ? Object.freeze([...result.path]) : null,
    unknownThemes: Object.freeze([...(result.unknownThemes ?? [])]),
    matchedThemes: Object.freeze([...(result.matchedThemes ?? [])]),
    candidateNodeIds: Object.freeze([...(result.candidateNodeIds ?? [])]),
  });
}

export function deriveDigitalProjectPath(record, { taxonomy = DIGITAL_TAXONOMY } = {}) {
  if (!hasDigitalPresence(record)) return null;
  const rawThemes = Array.isArray(record?.themes) ? record.themes : [];
  const themes = Object.freeze([...new Set(rawThemes.filter((theme) => typeof theme === 'string'))].sort());
  const themeMap = digitalThemeMap(taxonomy);
  const unknownThemes = themes.filter((theme) => !themeMap.has(theme));
  const candidates = new Map();

  for (const theme of themes) {
    const nodeId = themeMap.get(theme);
    if (nodeId) addCandidate(candidates, nodeId, 1, [theme], `theme:${theme}`);
  }
  const themeSet = new Set(themes);
  for (const rule of taxonomy.compound_rules ?? []) {
    const allThemes = Array.isArray(rule.all_themes) ? rule.all_themes : [];
    if (allThemes.length && allThemes.every((theme) => themeSet.has(theme))) {
      addCandidate(candidates, rule.target_node_id, allThemes.length + 1, allThemes, `compound:${rule.id}`);
    }
  }
  if (candidates.size === 0) {
    const path = digitalParentPath(taxonomy.unknown_theme_node_id, taxonomy) ?? DIGITAL_ROOT_PATH;
    return freezeDerivation({
      status: 'unclassified',
      reason: 'no-known-digital-theme',
      path,
      pathKey: serializeDigitalPath(path),
      nodeId: taxonomy.unknown_theme_node_id,
      matchedThemes: [],
      unknownThemes,
      candidateNodeIds: [],
    });
  }

  const maximum = Math.max(...[...candidates.values()].map(({ score }) => score));
  let winners = [...candidates.values()].filter(({ score }) => score === maximum);
  if (winners.length > 1) {
    const winnerIds = winners.map(({ nodeId }) => nodeId).sort();
    const exactTie = (taxonomy.tie_rules ?? []).find((rule) => {
      const candidatesForRule = [...(rule.candidate_node_ids ?? [])].sort();
      return candidatesForRule.length === winnerIds.length && candidatesForRule.every((id, index) => id === winnerIds[index]);
    });
    if (exactTie) {
      const matched = [...new Set(winners.flatMap(({ matchedThemes }) => [...matchedThemes]))].sort();
      winners = [{ nodeId: exactTie.target_node_id, score: maximum, matchedThemes: new Set(matched), sources: new Set([`tie:${exactTie.id}`]) }];
    } else {
      const fields = [...new Set(winnerIds.map((nodeId) => candidateFieldId(nodeId, taxonomy)).filter(Boolean))];
      const fallback = fields.length === 1 ? taxonomy.same_field_tie_fallbacks?.[fields[0]] : null;
      if (fallback) {
        const matched = [...new Set(winners.flatMap(({ matchedThemes }) => [...matchedThemes]))].sort();
        winners = [{ nodeId: fallback, score: maximum, matchedThemes: new Set(matched), sources: new Set([`same-field:${fields[0]}`]) }];
      }
    }
  }
  if (winners.length !== 1) {
    const path = digitalParentPath(taxonomy.unknown_theme_node_id, taxonomy) ?? DIGITAL_ROOT_PATH;
    return freezeDerivation({
      status: 'unclassified',
      reason: 'unresolved-theme-tie',
      path,
      pathKey: serializeDigitalPath(path),
      nodeId: taxonomy.unknown_theme_node_id,
      matchedThemes: [],
      unknownThemes,
      candidateNodeIds: winners.map(({ nodeId }) => nodeId).sort(),
    });
  }
  const winner = winners[0];
  const path = digitalParentPath(winner.nodeId, taxonomy) ?? DIGITAL_ROOT_PATH;
  return freezeDerivation({
    status: unknownThemes.length ? 'classified_with_unknown_theme_diagnostic' : 'classified',
    reason: [...winner.sources].sort().join('+'),
    path,
    pathKey: serializeDigitalPath(path),
    nodeId: winner.nodeId,
    matchedThemes: [...winner.matchedThemes].sort(),
    unknownThemes,
    candidateNodeIds: [winner.nodeId],
  });
}

export function digitalPathContainsRecord(path, record, { taxonomy = DIGITAL_TAXONOMY } = {}) {
  const normalized = normalizeDigitalPath(path, { taxonomy });
  if (!normalized.valid || normalized.path.length === 1) return true;
  if (!hasDigitalPresence(record)) return false;
  const derived = deriveDigitalProjectPath(record, { taxonomy });
  if (!derived?.path) return false;
  return normalized.path.every((segment, index) => derived.path[index] === segment);
}

function freezeDigitalTreeNode(node) {
  node.identityIds = Object.freeze([...node.identityIds].sort());
  node.directIdentityIds = Object.freeze([...node.directIdentityIds].sort());
  node.children = Object.freeze(node.children);
  node.identityCount = node.identityIds.length;
  node.directIdentityCount = node.directIdentityIds.length;
  node.childIdentityCount = new Set(node.children.flatMap((child) => child.identityIds)).size;
  return Object.freeze(node);
}

const digitalTreeCache = new WeakMap();
let digitalTreeConstructionCount = 0;

export function digitalPresentationTreeConstructionCount() {
  return digitalTreeConstructionCount;
}

export function buildDigitalPresentationTree(records = [], { taxonomy = DIGITAL_TAXONOMY } = {}) {
  const sourceRecords = Array.isArray(records) ? records : [];
  let treesByTaxonomy = digitalTreeCache.get(sourceRecords);
  const cached = treesByTaxonomy?.get(taxonomy);
  if (cached) return cached;
  digitalTreeConstructionCount += 1;
  const nodeMap = digitalNodeMap(taxonomy);
  const pathById = new Map();
  for (const node of taxonomy.nodes ?? []) {
    pathById.set(node.id, digitalParentPath(node.id, taxonomy));
  }
  const treeNodes = new Map();
  for (const node of taxonomy.nodes ?? []) {
    const path = pathById.get(node.id);
    if (!path) continue;
    const pathKey = serializeDigitalPath(path);
    const parentPath = node.parent_id === null ? null : pathById.get(node.parent_id);
    treeNodes.set(pathKey, {
      id: node.id,
      nodeId: node.id,
      type: node.type,
      label: node.label_de,
      order: node.order,
      path,
      pathKey,
      parentId: node.parent_id,
      parentPathKey: parentPath ? serializeDigitalPath(parentPath) : null,
      themes: Object.freeze([...(node.themes ?? [])]),
      identityIds: new Set(),
      directIdentityIds: new Set(),
      children: [],
    });
  }
  const diagnostics = [];
  const recordsById = new Map();
  for (const record of sourceRecords) {
    if (!record?.id || recordsById.has(record.id)) continue;
    recordsById.set(record.id, record);
    const derived = deriveDigitalProjectPath(record, { taxonomy });
    if (!derived) continue;
    const parentPathKey = derived.pathKey;
    const parent = treeNodes.get(parentPathKey);
    if (!parent) continue;
    const identityPath = Object.freeze([...derived.path, record.id]);
    const identityPathKey = serializeDigitalPath(identityPath);
    const identityNode = {
      id: record.id,
      nodeId: record.id,
      type: 'identity',
      label: record.title ?? record.id,
      order: 0,
      path: identityPath,
      pathKey: identityPathKey,
      parentId: parent.id,
      parentPathKey,
      projectId: record.id,
      themes: Object.freeze([]),
      identityIds: new Set([record.id]),
      directIdentityIds: new Set([record.id]),
      children: [],
      derivation: derived,
    };
    treeNodes.set(identityPathKey, identityNode);
    parent.children.push(identityNode);
    parent.directIdentityIds.add(record.id);
    for (let index = 1; index <= derived.path.length; index += 1) {
      treeNodes.get(serializeDigitalPath(derived.path.slice(0, index)))?.identityIds.add(record.id);
    }
    if (derived.status !== 'classified') diagnostics.push(Object.freeze({ projectId: record.id, status: derived.status, unknownThemes: derived.unknownThemes, candidateNodeIds: derived.candidateNodeIds }));
  }
  for (const node of treeNodes.values()) {
    if (node.type === 'identity') continue;
    const staticChildren = (digitalChildrenByParent(taxonomy).get(node.id) ?? [])
      .map((child) => treeNodes.get(serializeDigitalPath(pathById.get(child.id))))
      .filter(Boolean);
    const identityChildren = node.children
      .filter((child) => child.type === 'identity')
      .sort((left, right) => left.label.localeCompare(right.label, 'de') || left.id.localeCompare(right.id));
    node.children = [...staticChildren, ...identityChildren];
  }
  const frozenNodes = new Map();
  const orderedNodes = [...treeNodes.values()].sort((left, right) => left.pathKey.localeCompare(right.pathKey));
  for (const node of orderedNodes) frozenNodes.set(node.pathKey, freezeDigitalTreeNode(node));
  const rootPathKey = serializeDigitalPath([taxonomy.root_id]);
  const tree = Object.freeze({
    taxonomyVersion: taxonomy.version,
    rootPath: Object.freeze([taxonomy.root_id]),
    rootPathKey,
    nodesByPath: frozenNodes,
    recordsById,
    identityIds: frozenNodes.get(rootPathKey)?.identityIds ?? Object.freeze([]),
    diagnostics: Object.freeze(diagnostics),
  });
  if (!treesByTaxonomy) {
    treesByTaxonomy = new WeakMap();
    digitalTreeCache.set(sourceRecords, treesByTaxonomy);
  }
  treesByTaxonomy.set(taxonomy, tree);
  return tree;
}

export function visibleDigitalNodes(tree, currentPath = DIGITAL_ROOT_PATH, { includeEmpty = false, identityLimit = Infinity } = {}) {
  const rootPathKey = tree?.rootPathKey ?? serializeDigitalPath(DIGITAL_ROOT_PATH);
  const normalized = normalizeDigitalPath(currentPath);
  const requested = normalized.valid ? normalized.pathKey : rootPathKey;
  const current = tree?.nodesByPath?.get(requested) ?? tree?.nodesByPath?.get(rootPathKey) ?? null;
  if (!current) return Object.freeze({ current: null, parent: null, breadcrumb: Object.freeze([]), children: Object.freeze([]) });
  const breadcrumb = current.path
    .map((_, index) => tree.nodesByPath.get(serializeDigitalPath(current.path.slice(0, index + 1))))
    .filter(Boolean);
  let children = current.children.filter((child) => includeEmpty || child.identityCount > 0 || child.type === 'identity');
  if (
    children.length
    && children.every((child) => child.type === 'identity')
    && Number.isFinite(identityLimit)
    && identityLimit >= 0
  ) {
    children = children.slice(0, identityLimit);
  }
  return Object.freeze({
    current,
    parent: current.parentPathKey ? tree.nodesByPath.get(current.parentPathKey) ?? null : null,
    breadcrumb: Object.freeze(breadcrumb),
    children: Object.freeze(children),
  });
}

export function digitalPathLabel(path, { taxonomy = DIGITAL_TAXONOMY, includeRoot = false } = {}) {
  const normalized = normalizeDigitalPath(path, { taxonomy });
  const nodes = digitalNodeMap(taxonomy);
  const labels = normalized.path
    .map((nodeId) => nodes.get(nodeId))
    .filter((node) => node && (includeRoot || node.id !== taxonomy.root_id))
    .map((node) => node.label_de);
  return labels.join(' › ');
}

export function recordDigitalPathLabel(record, { taxonomy = DIGITAL_TAXONOMY } = {}) {
  const derived = deriveDigitalProjectPath(record, { taxonomy });
  if (!derived) return '';
  return digitalPathLabel(derived.path, { taxonomy });
}


export function binaryName(value) {
  return [...new TextEncoder().encode(String(value ?? ''))]
    .map((byte) => byte.toString(2).padStart(8, '0'))
    .join(' ');
}

export function ribbonRepeatCount(recordCount, minimumSegments = 12) {
  const count = Number.isInteger(recordCount) && recordCount > 0 ? recordCount : 1;
  const minimum = Number.isInteger(minimumSegments) && minimumSegments > 0 ? minimumSegments : 12;
  return clamp(Math.ceil(minimum / count), 2, 6);
}

export const RING_ORBIT_MIN_DURATION_S = 24;
export const RING_ORBIT_MAX_DURATION_S = 96;
const RING_ORBIT_SATURATION_COUNT = 48;

export function ringOrbitDuration(entryCount) {
  const count = Number.isInteger(entryCount) && entryCount > 0 ? entryCount : 1;
  const boundedCount = clamp(count, 1, RING_ORBIT_SATURATION_COUNT);
  const scale = boundedCount === 1 ? 0 : Math.log(boundedCount) / Math.log(RING_ORBIT_SATURATION_COUNT);
  const seconds = RING_ORBIT_MIN_DURATION_S + (RING_ORBIT_MAX_DURATION_S - RING_ORBIT_MIN_DURATION_S) * scale;
  return rounded(clamp(seconds, RING_ORBIT_MIN_DURATION_S, RING_ORBIT_MAX_DURATION_S), 2);
}

export function ringOrbitDirection(ringIndex) {
  const index = Number.isInteger(ringIndex) && ringIndex >= 0 ? ringIndex : 0;
  return index % 2 === 0 ? 1 : -1;
}

export function ringOrbitStartAngle(ringIndex) {
  const index = Number.isInteger(ringIndex) && ringIndex >= 0 ? ringIndex : 0;
  return (index * 61) % 360;
}
export function binaryFragment(identifier, length = 12) {
  let hash = 2166136261;
  for (const character of String(identifier)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  let bits = hash.toString(2).padStart(32, '0');
  while (bits.length < length) bits += bits;
  return bits.slice(0, length);
}


export function sphereDetailLevel({ diameter, sideView = false } = {}) {
  if (sideView) return 'close';
  const size = Math.max(0, finite(diameter, 0));
  if (size < 360) return 'micro';
  if (size < 620) return 'compact';
  return 'names';
}


export function cameraFromSearch(search = '') {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  return {
    lng: clamp(finite(parameters.get('lng'), DEFAULT_CAMERA.lng), -180, 180),
    lat: clamp(finite(parameters.get('lat'), DEFAULT_CAMERA.lat), -85, 85),
    zoom: clamp(finite(parameters.get('z'), DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM),
    bearing: clamp(finite(parameters.get('b'), DEFAULT_CAMERA.bearing), -180, 180),
    pitch: clamp(finite(parameters.get('p'), DEFAULT_CAMERA.pitch), 0, 70),
  };
}

export function normalizeQuery(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ').slice(0, 120);
}

export const INTENT_FILTER_VALUES = Object.freeze({
  presence: Object.freeze(['geographic', 'digital']),
  action: Object.freeze(['visit', 'use', 'borrow', 'learn', 'contribute', 'volunteer', 'donate', 'contact', 'replicate']),
  access: Object.freeze(['public', 'membership', 'restricted', 'unknown']),
  freshness: Object.freeze(['current', 'stale', 'unknown']),
  curation: Object.freeze(['listed', 'verified', 'featured', 'unknown']),
});

const filterParameter = (parameters, name) => {
  const value = parameters.get(name);
  return INTENT_FILTER_VALUES[name]?.includes(value) ? value : null;
};

const languageFilterParameter = (parameters) => {
  const value = parameters.get('language');
  return value === 'unknown' || /^[a-z]{2,3}(?:-[A-Z]{2})?$/.test(value ?? '') ? value : null;
};

function normalizedPresenceFilters(values) {
  const requested = new Set(Array.isArray(values) ? values : []);
  return INTENT_FILTER_VALUES.presence.filter((value) => requested.has(value));
}

export function stateFromSearch(search = '', knownProjectIds = []) {
  const parameters = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const known = new Set(knownProjectIds);
  const project = parameters.get('project');
  const layer = parameters.get('layer');
  const requestedDigitalPath = parameters.get('digital_path');
  const hasExplicitDigitalPath = parameters.has('digital_path');
  const normalizedDigitalPath = hasExplicitDigitalPath ? normalizeDigitalPath(requestedDigitalPath) : null;
  const validLayer = LAYERS.some((entry) => entry.id === layer) ? layer : null;
  const digitalPath = hasExplicitDigitalPath
    ? normalizedDigitalPath.path
    : (digitalPathFromLegacyLayer(layer) ?? DIGITAL_ROOT_PATH);
  const presence = normalizedPresenceFilters(parameters.getAll('presence'));
  return {
    camera: cameraFromSearch(search),
    project: project && known.has(project) ? project : null,
    layer: hasExplicitDigitalPath ? null : validLayer,
    digitalPath,
    view: parameters.get('view') === 'layers' ? 'layers' : 'globe',
    surface: parameters.get('surface') === 'text' ? 'text' : 'globe',
    query: normalizeQuery(parameters.get('q')),
    presence: Object.freeze(presence),
    action: filterParameter(parameters, 'action'),
    language: languageFilterParameter(parameters),
    access: filterParameter(parameters, 'access'),
    freshness: filterParameter(parameters, 'freshness'),
    curation: filterParameter(parameters, 'curation'),
  };
}

const serializedNumber = (value, digits) => rounded(value, digits).toString();

export function searchFromState(state) {
  const parameters = new URLSearchParams();
  const camera = state?.camera ?? DEFAULT_CAMERA;
  parameters.set('lng', serializedNumber(clamp(finite(camera.lng, DEFAULT_CAMERA.lng), -180, 180), 4));
  parameters.set('lat', serializedNumber(clamp(finite(camera.lat, DEFAULT_CAMERA.lat), -85, 85), 4));
  parameters.set('z', serializedNumber(clamp(finite(camera.zoom, DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM), 2));
  if (Math.abs(finite(camera.bearing, 0)) >= 0.05) parameters.set('b', serializedNumber(clamp(finite(camera.bearing, 0), -180, 180), 1));
  if (Math.abs(finite(camera.pitch, 0)) >= 0.05) parameters.set('p', serializedNumber(clamp(finite(camera.pitch, 0), 0, 70), 1));
  if (state?.view === 'layers') parameters.set('view', 'layers');
  if (state?.surface === 'text') parameters.set('surface', 'text');
  const legacyLayer = LAYERS.some(({ id }) => id === state?.layer) ? state.layer : null;
  if (legacyLayer) {
    parameters.set('layer', legacyLayer);
  } else {
    const normalizedDigitalPath = normalizeDigitalPath(state?.digitalPath ?? DIGITAL_ROOT_PATH);
    if (normalizedDigitalPath.valid && normalizedDigitalPath.path.length > 1) parameters.set('digital_path', normalizedDigitalPath.pathKey);
  }
  if (state?.project) parameters.set('project', state.project);
  const query = normalizeQuery(state?.query);
  if (query) parameters.set('q', query);
  for (const name of ['action', 'access', 'freshness', 'curation']) {
    const value = state?.[name];
    if (INTENT_FILTER_VALUES[name].includes(value)) parameters.set(name, value);
  }
  for (const presence of normalizedPresenceFilters(state?.presence)) {
    parameters.append('presence', presence);
  }
  const language = state?.language;
  if (language === 'unknown' || /^[a-z]{2,3}(?:-[A-Z]{2})?$/.test(language ?? '')) {
    parameters.set('language', language);
  }
  return '?' + parameters.toString();
}

export const INTENT_SEARCH_RESULT_LIMIT = 50;
export const INTENT_SEARCH_CACHE_LIMIT = 128;

const ACTION_INTENT_TERMS = Object.freeze({
  use: Object.freeze(['nutzen', 'verwenden', 'ausprobieren']),
  learn: Object.freeze(['lernen', 'wissen', 'bildung', 'informieren']),
  contribute: Object.freeze(['mitmachen', 'beitragen', 'beteiligen']),
  volunteer: Object.freeze(['ehrenamt', 'ehrenamtlich', 'helfen']),
  donate: Object.freeze(['spenden', 'unterstützen']),
  visit: Object.freeze(['besuchen', 'vor ort']),
  contact: Object.freeze(['kontakt', 'kontaktieren']),
  replicate: Object.freeze(['nachmachen', 'übertragen', 'gründen']),
  borrow: Object.freeze(['ausleihen', 'leihen']),
});

const THEME_INTENT_TERMS = Object.freeze({
  knowledge: Object.freeze(['wissen']),
  'open-data': Object.freeze(['offene daten', 'freie daten']),
  research: Object.freeze(['forschung']),
  documentation: Object.freeze(['dokumentation']),
  'free-software': Object.freeze(['freie software']),
  'open-source': Object.freeze(['open source', 'quelloffen']),
  infrastructure: Object.freeze(['infrastruktur']),
  platform: Object.freeze(['plattform']),
  'open-media': Object.freeze(['offene medien', 'freie medien']),
  culture: Object.freeze(['kultur']),
  archives: Object.freeze(['archive', 'archiv']),
  'creative-commons': Object.freeze(['creative commons', 'freie inhalte']),
  education: Object.freeze(['bildung']),
  'open-educational-resources': Object.freeze(['freie bildungsmaterialien', 'offene lernmaterialien']),
  learning: Object.freeze(['lernen']),
  communication: Object.freeze(['kommunikation']),
  'community-network': Object.freeze(['gemeinschaftsnetz', 'community netz']),
  federation: Object.freeze(['föderation', 'föderiert']),
  protocol: Object.freeze(['protokoll']),
  housing: Object.freeze(['wohnen', 'wohnraum']),
  'community-land': Object.freeze(['gemeinschaftsland', 'gemeinschaftlicher boden']),
  'shared-space': Object.freeze(['gemeinschaftsraum', 'gemeinsamer raum']),
  agriculture: Object.freeze(['landwirtschaft']),
  seeds: Object.freeze(['saatgut']),
  food: Object.freeze(['ernährung', 'lebensmittel']),
  water: Object.freeze(['wasser']),
  irrigation: Object.freeze(['bewässerung']),
  energy: Object.freeze(['energie']),
  'renewable-energy': Object.freeze(['erneuerbare energie']),
  health: Object.freeze(['gesundheit']),
  'open-knowledge': Object.freeze(['offenes wissen']),
  'software-infrastructure': Object.freeze(['software infrastruktur']),
  'open-hardware': Object.freeze(['offene hardware']),
  'distributed-manufacturing': Object.freeze(['verteilte produktion']),
  'commons-governance': Object.freeze(['commons governance', 'selbstverwaltung']),
  'cooperative-economy': Object.freeze(['kooperative ökonomie', 'genossenschaftlich']),
  'community-ownership': Object.freeze(['gemeinschaftseigentum']),
  cooperative: Object.freeze(['genossenschaft']),
  'civic-tech': Object.freeze(['civic tech', 'digitale selbstorganisation']),
  network: Object.freeze(['netzwerk']),
  'rural-infrastructure': Object.freeze(['ländliche infrastruktur']),
  'digital-equity': Object.freeze(['digitaler zugang']),
  'digital-literacy': Object.freeze(['digitale bildung']),
});

const PRESENCE_INTENT_TERMS = Object.freeze({
  digital: Object.freeze(['digital', 'online', 'ortsunabhängig']),
  geographic: Object.freeze(['geografisch', 'vor ort', 'lokal']),
});
const COMBINED_PRESENCE_INTENT_TERMS = Object.freeze(['beides', 'vor ort und digital']);

const FIELD_WEIGHTS = Object.freeze({
  title: 120,
  location: 100,
  action: 85,
  presence: 70,
  theme: 65,
  digital: 55,
  summary: 45,
  link: 35,
});

export function normalizeSearchText(value) {
  return String(value ?? '')
    .toLocaleLowerCase('de')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .replace(/&/g, ' und ')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

export function searchTokens(value) {
  const normalized = normalizeSearchText(value);
  return normalized ? normalized.split(' ') : [];
}

function validPosition(value) {
  return Array.isArray(value)
    && value.length === 2
    && value.every((number) => Number.isFinite(number))
    && value[0] >= -180 && value[0] <= 180
    && value[1] >= -90 && value[1] <= 90;
}

function validLinearRing(value) {
  return Array.isArray(value)
    && value.length >= 4
    && value.every(validPosition)
    && value[0][0] === value.at(-1)[0]
    && value[0][1] === value.at(-1)[1];
}

function validGeometryCoordinates(type, coordinates) {
  if (type === 'Point') return validPosition(coordinates);
  if (type === 'Polygon') return Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(validLinearRing);
  if (type === 'MultiPolygon') {
    return Array.isArray(coordinates)
      && coordinates.length > 0
      && coordinates.every((polygon) => Array.isArray(polygon) && polygon.length > 0 && polygon.every(validLinearRing));
  }
  return false;
}

export function publicGeographicRepresentationKind(location) {
  if (!location || typeof location !== 'object' || location.mode === 'hidden') return null;
  const type = location?.geometry?.type;
  const coordinates = location?.geometry?.coordinates;
  if (!validGeometryCoordinates(type, coordinates)) return null;
  if (location.mode === 'approximate') {
    return type === 'Point' && Number.isFinite(location.uncertainty_meters_min) && location.uncertainty_meters_min > 0
      ? 'approximate_zone'
      : null;
  }
  if (location.mode !== 'exact') return null;
  if (type === 'Point') return 'exact_anchor';
  if (type === 'Polygon' || type === 'MultiPolygon') return 'public_extent';
  return null;
}

export function publicGeographicLocations(record) {
  const locations = record?.presence?.geographic;
  return Array.isArray(locations)
    ? locations.filter((location) => publicGeographicRepresentationKind(location) !== null)
    : [];
}

function vocabularyValues(value, vocabulary) {
  return [value, ...(vocabulary[value] ?? [])];
}

function recordSearchFields(record) {
  const fields = [];
  const append = (field, reason, values) => {
    const clean = values.flat().filter((value) => typeof value === 'string' && value.trim());
    if (clean.length) fields.push({ field, reason, values: clean });
  };
  append('title', 'Name', [record?.title]);
  append('summary', 'Beschreibung', [record?.summary]);
  append('theme', 'Thema', (record?.themes ?? []).flatMap((theme) => vocabularyValues(theme, THEME_INTENT_TERMS)));
  append('action', 'Möglichkeit', (record?.actions ?? []).flatMap((action) => vocabularyValues(action, ACTION_INTENT_TERMS)));

  const geographicLocations = publicGeographicLocations(record);
  const isGeographic = geographicLocations.length > 0;
  const isDigital = hasDigitalPresence(record);
  const axes = [];
  if (isGeographic) axes.push('geographic');
  if (isDigital) axes.push('digital');
  const presenceTerms = axes.flatMap((axis) => vocabularyValues(axis, PRESENCE_INTENT_TERMS));
  if (isGeographic && isDigital) presenceTerms.push(...COMBINED_PRESENCE_INTENT_TERMS);
  append('presence', 'Präsenz', presenceTerms);

  append('location', 'Ort', geographicLocations.map(({ label }) => label));
  append('digital', 'Digitale Präsenz', [record?.presence?.digital?.label, record?.presence?.digital?.reach]);
  append('link', 'Offizieller Link', (record?.links ?? []).map(({ label, type }) => [label, type]));
  return fields;
}

function recordLanguageValues(record) {
  if (Array.isArray(record?.languages)) return record.languages.filter((value) => typeof value === 'string');
  return Array.isArray(record?.languages?.codes) ? record.languages.codes.filter((value) => typeof value === 'string') : [];
}

function recordAccessValue(record) {
  if (typeof record?.access === 'string') return record.access;
  return typeof record?.access?.type === 'string' ? record.access.type : null;
}

function recordFreshness(record, today) {
  const nextReview = record?.curation?.next_review_at;
  const activity = record?.activity?.status;
  if (typeof nextReview !== 'string' || typeof activity !== 'string') return 'unknown';
  if (nextReview < today || !['active', 'seasonal'].includes(activity)) return 'stale';
  return 'current';
}

export function recordMatchesIntentFilters(record, filters = {}, today = new Date().toISOString().slice(0, 10)) {
  if (filters.layer) {
    if (deriveLayer(record) !== filters.layer) return false;
  } else if (filters.digitalPath && !digitalPathContainsRecord(filters.digitalPath, record)) return false;

  if (Array.isArray(filters.presence) && filters.presence.length > 0) {
    if (filters.presence.includes('geographic') && publicGeographicLocations(record).length === 0) return false;
    if (filters.presence.includes('digital') && !hasDigitalPresence(record)) return false;
  }

  if (filters.action && !(record?.actions ?? []).includes(filters.action)) return false;
  if (filters.language) {
    const languages = recordLanguageValues(record);
    if (filters.language === 'unknown' ? languages.length !== 0 : !languages.includes(filters.language)) return false;
  }
  if (filters.access) {
    const access = recordAccessValue(record);
    if (filters.access === 'unknown' ? access !== null : access !== filters.access) return false;
  }
  if (filters.freshness && recordFreshness(record, today) !== filters.freshness) return false;
  if (filters.curation && record?.curation?.state !== filters.curation) return false;
  return true;
}

function lowerBound(values, target) {
  let low = 0;
  let high = values.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (values[middle] < target) low = middle + 1;
    else high = middle;
  }
  return low;
}

function freezeSearchResult(result) {
  return Object.freeze({
    ...result,
    reasons: Object.freeze([...result.reasons]),
  });
}

export function prepareIntentSearchIndex(records, { cacheLimit = INTENT_SEARCH_CACHE_LIMIT } = {}) {
  const sourceRecords = Array.isArray(records) ? records : [];
  const recordsById = new Map(sourceRecords.map((record) => [record.id, record]));
  const postings = new Map();
  const normalizedTitles = new Map();
  const boundedCacheLimit = Math.max(1, Number.isInteger(cacheLimit) ? cacheLimit : INTENT_SEARCH_CACHE_LIMIT);
  const cache = new Map();
  let fullCatalogueScanCount = 0;

  for (const record of sourceRecords) {
    normalizedTitles.set(record.id, normalizeSearchText(record.title));
    for (const { field, reason, values } of recordSearchFields(record)) {
      const weight = FIELD_WEIGHTS[field] ?? 1;
      const uniqueTokens = new Set(values.flatMap(searchTokens));
      for (const token of uniqueTokens) {
        let byProject = postings.get(token);
        if (!byProject) {
          byProject = new Map();
          postings.set(token, byProject);
        }
        const previous = byProject.get(record.id);
        if (!previous || previous.score < weight) byProject.set(record.id, Object.freeze({ score: weight, reason }));
      }
    }
  }

  const sortedTerms = Object.freeze([...postings.keys()].sort());

  const postingsForToken = (token) => {
    const exact = postings.get(token);
    if (exact) return exact;
    if (token.length < 2) return null;
    const combined = new Map();
    for (let index = lowerBound(sortedTerms, token); index < sortedTerms.length; index += 1) {
      const term = sortedTerms[index];
      if (!term.startsWith(token)) break;
      for (const [identifier, match] of postings.get(term)) {
        const previous = combined.get(identifier);
        if (!previous || previous.score < match.score) combined.set(identifier, match);
      }
    }
    return combined.size ? combined : null;
  };

  const search = ({ query = '', filters = {}, limit = INTENT_SEARCH_RESULT_LIMIT, all = false, today = new Date().toISOString().slice(0, 10) } = {}) => {
    const normalizedQuery = normalizeSearchText(query);
    const boundedLimit = all ? Infinity : Math.max(1, Math.min(200, Number.isInteger(limit) ? limit : INTENT_SEARCH_RESULT_LIMIT));
    const cacheKey = JSON.stringify([normalizedQuery, filters, all ? 'all' : boundedLimit, today]);
    if (cache.has(cacheKey)) return cache.get(cacheKey);

    const queryGroups = [];
    for (const token of [...new Set(searchTokens(normalizedQuery))]) {
      const group = postingsForToken(token);
      if (group) queryGroups.push(group);
    }

    let candidates = null;
    if (normalizedQuery && queryGroups.length === 0) candidates = new Map();
    else if (queryGroups.length) {
      candidates = new Map([...queryGroups[0]].map(([identifier, match]) => [identifier, { score: match.score, reasons: new Set([match.reason]) }]));
      for (const group of queryGroups.slice(1)) {
        for (const [identifier, candidate] of candidates) {
          const match = group.get(identifier);
          if (!match) candidates.delete(identifier);
          else {
            candidate.score += match.score;
            candidate.reasons.add(match.reason);
          }
        }
      }
    }

    if (candidates === null) fullCatalogueScanCount += 1;
    const selectedRecords = candidates === null
      ? sourceRecords.map((record) => ({ record, score: 0, reasons: new Set() }))
      : [...candidates].map(([identifier, candidate]) => ({ record: recordsById.get(identifier), ...candidate }));

    const results = selectedRecords
      .filter(({ record }) => record && recordMatchesIntentFilters(record, filters, today))
      .map(({ record, score, reasons }) => {
        const title = normalizedTitles.get(record.id) ?? '';
        const phraseBonus = normalizedQuery && title === normalizedQuery ? 300 : (normalizedQuery && title.startsWith(normalizedQuery) ? 160 : 0);
        return freezeSearchResult({ id: record.id, record, score: score + phraseBonus, reasons: [...reasons] });
      })
      .sort((left, right) => right.score - left.score || left.record.title.localeCompare(right.record.title, 'de') || left.id.localeCompare(right.id));

    if (Number.isFinite(boundedLimit)) results.splice(boundedLimit);

    const frozen = Object.freeze(results);
    cache.set(cacheKey, frozen);
    if (cache.size > boundedCacheLimit) cache.delete(cache.keys().next().value);
    return frozen;
  };

  return Object.freeze({
    indexedRecordCount: sourceRecords.length,
    indexedTermCount: postings.size,
    cacheLimit: boundedCacheLimit,
    recordsById,
    search,
    matchingRecords(options = {}) {
      return Object.freeze(search({ ...options, all: options.all !== false }).map(({ record }) => record));
    },
    cacheSize() {
      return cache.size;
    },
    fullCatalogueScanCount() {
      return fullCatalogueScanCount;
    },
  });
}

export function filterRecords(records, state = {}) {
  if (state.searchIndex?.matchingRecords) {
    return state.searchIndex.matchingRecords({
      query: state.query,
      filters: {
        layer: state.layer ?? null,
        digitalPath: state.digitalPath ?? null,
        presence: state.presence ?? null,
        action: state.action ?? null,
        language: state.language ?? null,
        access: state.access ?? null,
        freshness: state.freshness ?? null,
        curation: state.curation ?? null,
      },
      all: true,
      today: state.today,
    });
  }
  const query = normalizeSearchText(normalizeQuery(state.query));
  return (Array.isArray(records) ? records : []).filter((record) => {
    if (!recordMatchesIntentFilters(record, state, state.today)) return false;
    if (!query) return true;
    return recordSearchFields(record).some(({ values }) => normalizeSearchText(values.join(' ')).includes(query));
  });
}

export function recordPresentationLabel(record) {
  const isGeo = publicGeographicLocations(record).length > 0;
  const isDigital = hasDigitalPresence(record);
  const pathLabel = recordDigitalPathLabel(record);
  const digitalLabel = `Digital${pathLabel ? ` · ${pathLabel}` : ''}`;

  if (isGeo && isDigital) return `Vor Ort · ${digitalLabel}`;
  if (isGeo) return 'Vor Ort';
  if (isDigital) return digitalLabel;
  return 'Commons';
}



function cloneCoordinates(value) {
  return Array.isArray(value) ? value.map(cloneCoordinates) : value;
}

const EARTH_RADIUS_METERS = 6371008.8;
const UNCERTAINTY_ZONE_VERTEX_COUNT = 64;
export const PUBLIC_MAP_COLLECTION_CACHE_LIMIT = 64;
const EMPTY_CATALOG_RECORDS = Object.freeze([]);
const catalogProjectionCache = new WeakMap();

function freezeCatalogSnapshot(value) {
  if (!value || typeof value !== 'object') return value;
  const pending = [value];
  const seen = new WeakSet();
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current || typeof current !== 'object' || seen.has(current)) continue;
    seen.add(current);
    for (const child of Object.values(current)) {
      if (child && typeof child === 'object') pending.push(child);
    }
    Object.freeze(current);
  }
  return value;
}

export function geodesicDistanceMeters(origin, destination) {
  if (!Array.isArray(origin) || origin.length !== 2 || !origin.every(Number.isFinite)) return Number.NaN;
  if (!Array.isArray(destination) || destination.length !== 2 || !destination.every(Number.isFinite)) return Number.NaN;
  const radians = Math.PI / 180;
  const originLatitude = origin[1] * radians;
  const destinationLatitude = destination[1] * radians;
  const latitudeDelta = (destination[1] - origin[1]) * radians;
  const longitudeDelta = (destination[0] - origin[0]) * radians;
  const haversine = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(originLatitude) * Math.cos(destinationLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(clamp(haversine, 0, 1)));
}

function approximateUncertaintyZone(location) {
  const center = location?.geometry?.coordinates;
  const radiusMeters = finite(location?.uncertainty_meters_min, 0);
  if (!Array.isArray(center) || center.length !== 2 || !center.every(Number.isFinite) || radiusMeters <= 0) return null;
  const longitude = center[0] * Math.PI / 180;
  const latitude = center[1] * Math.PI / 180;
  const angularDistance = radiusMeters / EARTH_RADIUS_METERS;
  const ring = [];
  for (let index = 0; index < UNCERTAINTY_ZONE_VERTEX_COUNT; index += 1) {
    const bearing = 2 * Math.PI * index / UNCERTAINTY_ZONE_VERTEX_COUNT;
    const targetLatitude = Math.asin(
      Math.sin(latitude) * Math.cos(angularDistance)
      + Math.cos(latitude) * Math.sin(angularDistance) * Math.cos(bearing),
    );
    const targetLongitude = longitude + Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude),
      Math.cos(angularDistance) - Math.sin(latitude) * Math.sin(targetLatitude),
    );
    const longitudeDegrees = ((targetLongitude * 180 / Math.PI + 540) % 360) - 180;
    ring.push([longitudeDegrees, targetLatitude * 180 / Math.PI]);
  }
  ring.push([...ring[0]]);
  return { type: 'Polygon', coordinates: [ring] };
}

function publicGeometry(location, representationKind) {
  if (representationKind === 'approximate_zone') return approximateUncertaintyZone(location);
  return {
    type: location.geometry.type,
    coordinates: cloneCoordinates(location.geometry.coordinates),
  };
}

function publicMapFeature(record, location) {
  const representationKind = publicGeographicRepresentationKind(location);
  if (!representationKind) return null;
  return Object.freeze({
    type: 'Feature',
    id: record.id + ':' + location.id,
    geometry: freezeCatalogSnapshot(publicGeometry(location, representationKind)),
    properties: Object.freeze({
      project_id: record.id,
      location_id: location.id,
      title: record.title ?? record.id,
      location_label: location.label ?? record.title ?? record.id,
      location_mode: location.mode,
      representation_kind: representationKind,
      uncertainty_meters_min: location.mode === 'approximate' ? finite(location.uncertainty_meters_min, 0) : 0,
    }),
  });
}

function featureCollection(features) {
  return Object.freeze({ type: 'FeatureCollection', features: Object.freeze(features) });
}

function buildEvidencedRelations(records, recordsById) {
  const relations = [];
  for (const record of records) {
    for (const relation of Array.isArray(record?.relations) ? record.relations : []) {
      const target = recordsById.get(relation?.target_id);
      if (!target || !Array.isArray(relation?.source_ids) || relation.source_ids.length === 0) continue;
      relations.push(Object.freeze({
        source_project_id: record.id,
        source_title: record.title ?? record.id,
        target_project_id: target.id,
        target_title: target.title ?? target.id,
        relation_type: relation.type,
        source_ids: Object.freeze([...relation.source_ids]),
        note: relation.note ?? '',
      }));
    }
  }
  return Object.freeze(relations);
}

function buildCatalogProjection(records) {
  const recordsById = new Map(records.filter((record) => record?.id).map((record) => [record.id, record]));
  const projectIds = records.filter((record) => record?.id).map((record) => record.id);
  const featuresByProjectId = new Map();
  const allFeatures = [];
  for (const record of records) {
    if (!record?.id) continue;
    const projectFeatures = [];
    const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
    for (const location of locations) {
      if (!location || location.mode === 'hidden' || !location.geometry) continue;
      const feature = publicMapFeature(record, location);
      if (!feature) continue;
      projectFeatures.push(feature);
      allFeatures.push(feature);
    }
    featuresByProjectId.set(record.id, Object.freeze(projectFeatures));
  }

  const collections = new Map([['*', featureCollection(allFeatures)]]);
  const relations = buildEvidencedRelations(records, recordsById);

  function collectionFor(visibleProjectIds = null) {
    if (visibleProjectIds === null || visibleProjectIds === undefined) return collections.get('*');
    const requested = visibleProjectIds instanceof Set
      ? visibleProjectIds
      : new Set(Array.isArray(visibleProjectIds) ? visibleProjectIds : []);
    const visibleIds = projectIds.filter((identifier) => requested.has(identifier));
    const key = 'ids:' + visibleIds.join('\u001f');
    const cached = collections.get(key);
    if (cached) {
      collections.delete(key);
      collections.set(key, cached);
      return cached;
    }
    const features = visibleIds.flatMap((identifier) => featuresByProjectId.get(identifier) ?? []);
    const collection = featureCollection(features);
    while (collections.size >= PUBLIC_MAP_COLLECTION_CACHE_LIMIT) {
      const oldest = [...collections.keys()].find((candidate) => candidate !== '*');
      if (!oldest) break;
      collections.delete(oldest);
    }
    collections.set(key, collection);
    return collection;
  }

  return Object.freeze({
    recordsById,
    relations,
    publicMapFeatureCollection: collectionFor,
  });
}

export function prepareCatalogProjection(records) {
  const values = Array.isArray(records) ? records : EMPTY_CATALOG_RECORDS;
  let projection = catalogProjectionCache.get(values);
  if (!projection) {
    freezeCatalogSnapshot(values);
    projection = buildCatalogProjection(values);
    catalogProjectionCache.set(values, projection);
  }
  return projection;
}

export function publicMapFeatureCollection(records, visibleProjectIds = null) {
  return prepareCatalogProjection(records).publicMapFeatureCollection(visibleProjectIds);
}

export function publicProjectNavigationTarget(publicMapData, projectId) {
  const features = Array.isArray(publicMapData?.features) ? publicMapData.features : [];
  const coordinates = [];
  const collect = (value) => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && Number.isFinite(Number(value[0])) && Number.isFinite(Number(value[1]))) {
      coordinates.push([Number(value[0]), Number(value[1])]);
      return;
    }
    for (const nested of value) collect(nested);
  };
  for (const feature of features) {
    if (feature?.properties?.project_id !== projectId) continue;
    collect(feature?.geometry?.coordinates);
  }
  if (coordinates.length === 0) return null;
  let west = coordinates[0][0];
  let east = coordinates[0][0];
  let south = coordinates[0][1];
  let north = coordinates[0][1];
  for (const [longitude, latitude] of coordinates.slice(1)) {
    west = Math.min(west, longitude);
    east = Math.max(east, longitude);
    south = Math.min(south, latitude);
    north = Math.max(north, latitude);
  }
  if (west === east && south === north) {
    return Object.freeze({ kind: 'point', center: Object.freeze([west, south]), zoom: 15 });
  }
  return Object.freeze({
    kind: 'bounds',
    bounds: Object.freeze([
      Object.freeze([west, south]),
      Object.freeze([east, north]),
    ]),
  });
}

export function evidencedRelations(records) {
  return prepareCatalogProjection(records).relations;
}

function formattedUncertainty(meters) {
  const value = Math.max(0, finite(meters, 0));
  if (value >= 1000 && value % 1000 === 0) return `${value / 1000} km`;
  return `${Math.round(value)} m`;
}

export function recordLocationSummaries(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  return locations.map((location) => {
    const label = location?.label ?? 'Ort';
    if (location?.mode === 'hidden') return `${label} · Ort verborgen`;
    if (location?.mode === 'approximate') return `${label} · ungefähr, mindestens ${formattedUncertainty(location.uncertainty_meters_min)} Unschärfe`;
    const type = location?.geometry?.type;
    if (type === 'Polygon' || type === 'MultiPolygon') return `${label} · öffentliche Fläche`;
    return `${label} · exakter öffentlicher Punkt`;
  });
}

export function semanticZoomLevel(zoom, selectedProjectId = null) {
  if (selectedProjectId) return 'focus';
  const value = clamp(finite(zoom, DEFAULT_CAMERA.zoom), 0, MAX_MAP_ZOOM);
  if (value < 1.8) return 'planet';
  if (value < 3.4) return 'macroregion';
  if (value < 5.5) return 'region';
  return 'local';
}

function spatialIdentityCount(records) {
  return (Array.isArray(records) ? records : []).filter((record) => publicGeographicLocations(record).length > 0).length;
}

function focusSpatialSummary(record) {
  const locations = Array.isArray(record?.presence?.geographic) ? record.presence.geographic : [];
  const publicLocations = publicGeographicLocations(record);
  const isGeo = publicLocations.length > 0;
  const isDigital = hasDigitalPresence(record);
  if (isDigital && locations.length === 0) return 'Digital · Ortsunabhängige digitale Präsenz';

  const visible = publicLocations.length;
  const hidden = locations.filter((location) => location?.mode === 'hidden').length;

  let presenceLabel = 'Commons';
  if (isGeo && isDigital) presenceLabel = 'Vor Ort · Digital';
  else if (isGeo) presenceLabel = 'Vor Ort';
  else if (isDigital) presenceLabel = 'Digital';
  else if (hidden > 0) presenceLabel = 'Verborgene Orte';

  if (visible === 0) return `${presenceLabel} · ${hidden} ${hidden === 1 ? 'verborgener Ort' : 'verborgene Orte'}`;

  const publicLabel = `${visible} ${visible === 1 ? 'öffentlicher Ort' : 'öffentliche Orte'}`;
  const hiddenLabel = `${hidden} ${hidden === 1 ? 'verborgener Ort' : 'verborgene Orte'}`;
  return hidden ? `${presenceLabel} · ${publicLabel} · ${hiddenLabel}` : `${presenceLabel} · ${publicLabel}`;
}

export function semanticLocationLine({
  zoom = DEFAULT_CAMERA.zoom,
  records = [],
  selectedProjectId = null,
  selectedRecord = null,
} = {}) {
  const selected = selectedProjectId
    ? (selectedRecord?.id === selectedProjectId
      ? selectedRecord
      : (Array.isArray(records) ? records : []).find(({ id }) => id === selectedProjectId))
    : null;
  const level = semanticZoomLevel(zoom, selected?.id ?? null);
  if (selected) {
    return {
      level,
      crumbs: ['Erde', 'Commons', selected.title ?? selected.id],
      summary: focusSpatialSummary(selected),
    };
  }
  const count = spatialIdentityCount(records);
  const countLabel = `${count} räumlich belegte Commons`;
  if (level === 'planet') return { level, crumbs: ['Erde', 'Gesamtansicht'], summary: countLabel };
  if (level === 'macroregion') return { level, crumbs: ['Erde', 'Großregion'], summary: `${countLabel} · regionale Zusammenhänge` };
  if (level === 'region') return { level, crumbs: ['Erde', 'Region'], summary: `${countLabel} · öffentliche Flächen und ungefähre Orte` };
  return { level, crumbs: ['Erde', 'Lokaler Zusammenhang'], summary: `${countLabel} · öffentliche Punkte, Flächen und Beziehungen` };
}

const HORIZON_BEARINGS = Object.freeze([0, 45, 90, 135, 180, 225, 270, 315]);

export function globeHorizonCoordinates(center = DEFAULT_CAMERA, angularDistanceDegrees = 89.994) {
  const radians = Math.PI / 180;
  const latitude = clamp(finite(center?.lat, DEFAULT_CAMERA.lat), -85.051129, 85.051129) * radians;
  const longitude = finite(center?.lng, DEFAULT_CAMERA.lng) * radians;
  const distance = clamp(finite(angularDistanceDegrees, 89.994), 1, 89.9999) * radians;
  return HORIZON_BEARINGS.map((bearingDegrees) => {
    const bearing = bearingDegrees * radians;
    const destinationLatitude = Math.asin(
      Math.sin(latitude) * Math.cos(distance)
      + Math.cos(latitude) * Math.sin(distance) * Math.cos(bearing),
    );
    const destinationLongitude = longitude + Math.atan2(
      Math.sin(bearing) * Math.sin(distance) * Math.cos(latitude),
      Math.cos(distance) - Math.sin(latitude) * Math.sin(destinationLatitude),
    );
    return {
      lng: rounded((((destinationLongitude / radians + 540) % 360) + 360) % 360 - 180, 6),
      lat: rounded(destinationLatitude / radians, 6),
    };
  });
}

export function projectedGlobeCircle({ center = null, horizon = [] } = {}) {
  const x = finite(center?.x, Number.NaN);
  const y = finite(center?.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const radii = (Array.isArray(horizon) ? horizon : [])
    .map((point) => {
      const projectedX = finite(point?.x, Number.NaN);
      const projectedY = finite(point?.y, Number.NaN);
      return Number.isFinite(projectedX) && Number.isFinite(projectedY)
        ? Math.hypot(projectedX - x, projectedY - y)
        : Number.NaN;
    })
    .filter((radius) => Number.isFinite(radius) && radius > 0)
    .sort((left, right) => left - right);
  if (radii.length < 4) return null;
  const middle = Math.floor(radii.length / 2);
  const radius = radii.length % 2
    ? radii[middle]
    : (radii[middle - 1] + radii[middle]) / 2;
  return {
    x: rounded(x, 2),
    y: rounded(y, 2),
    diameter: rounded(radius * 2, 2),
  };
}

export function sphereLayout({ width, height, padding = {}, globe = null, sideView = false } = {}) {
  const stageWidth = Math.max(1, finite(width, 1));
  const stageHeight = Math.max(1, finite(height, 1));
  const left = clamp(finite(padding.left, 0), 0, stageWidth - 1);
  const right = clamp(finite(padding.right, 0), 0, stageWidth - left - 1);
  const top = clamp(finite(padding.top, 0), 0, stageHeight - 1);
  const bottom = clamp(finite(padding.bottom, 0), 0, stageHeight - top - 1);
  const availableWidth = Math.max(1, stageWidth - left - right);
  const availableHeight = Math.max(1, stageHeight - top - bottom);
  const fallbackX = left + availableWidth / 2;
  const fallbackY = top + availableHeight / 2;
  const shortestSide = Math.min(stageWidth, stageHeight);
  if (sideView) {
    const diameter = Math.max(stageWidth * 2.05, stageHeight * 2.25);
    return {
      x: rounded(stageWidth * 0.08, 2),
      y: rounded(stageHeight * 0.58, 2),
      diameter: rounded(diameter, 2),
      globeDiameter: rounded(diameter, 2),
    };
  }
  const x = clamp(finite(globe?.x, fallbackX), 0, stageWidth);
  const y = clamp(finite(globe?.y, fallbackY), 0, stageHeight);
  const fallbackGlobeDiameter = Math.min(availableWidth, availableHeight) * 0.88;
  const maximumSafeDiameter = Math.hypot(stageWidth, stageHeight) * 2.5;
  const globeDiameter = clamp(finite(globe?.diameter, fallbackGlobeDiameter), 1, maximumSafeDiameter);
  return {
    x: rounded(x, 2),
    y: rounded(y, 2),
    diameter: rounded(globeDiameter * 1.32, 2),
    globeDiameter: rounded(globeDiameter, 2),
  };
}

export function digitalLayerCamera(camera = DEFAULT_CAMERA) {
  const bearing = finite(camera?.bearing, DEFAULT_CAMERA.bearing);
  const normalizedBearing = ((((bearing + 28) + 180) % 360) + 360) % 360 - 180;
  return {
    center: [
      clamp(finite(camera?.lng, DEFAULT_CAMERA.lng), -180, 180),
      clamp(finite(camera?.lat, DEFAULT_CAMERA.lat), -85, 85),
    ],
    zoom: clamp(Math.max(2.15, finite(camera?.zoom, DEFAULT_CAMERA.zoom) + 1.05), 0, DIGITAL_LAYER_MAX_ZOOM),
    bearing: rounded(normalizedBearing, 1),
    pitch: 58,
    padding: { top: 0, right: 0, bottom: 0, left: 0 },
  };
}

export function mapCamera(map) {
  const center = map.getCenter();
  return {
    lng: center.lng,
    lat: center.lat,
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  };
}

export function mapFailurePolicy({ providerReadbackFailed = false } = {}) {
  return Object.freeze({ degraded: true, replaceStyle: providerReadbackFailed === true });
}

export function sphereOpacityForGlobeRatio(globeViewportRatio) {
  const value = finite(globeViewportRatio, 0);
  if (value <= 1.05) return 1;
  if (value >= 2.1) return 0;
  return Number(((2.1 - value) / 1.05).toFixed(4));
}
