import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { countryCompositionFeatureCollection } from '../assets/commonworld-core.mjs';

const ROOT = process.cwd();
const CATALOG_PATH = path.join(ROOT, 'catalog/catalog.json');
const SOURCE_PATH = path.join(ROOT, 'data/vendor/natural-earth/ne_110m_admin_0_countries.geojson');
const OUTPUT_PATH = path.join(ROOT, 'assets/map/commonworld-country-boundaries.geojson');

const catalog = JSON.parse(await readFile(CATALOG_PATH, 'utf8'));
const projectFiles = Array.isArray(catalog.project_files) ? catalog.project_files : [];
if (projectFiles.length === 0) throw new Error('catalog has no project_files');
const records = [];
for (const relative of projectFiles) {
  const target = path.join(ROOT, 'catalog', relative);
  records.push(JSON.parse(await readFile(target, 'utf8')));
}
const boundaries = JSON.parse(await readFile(SOURCE_PATH, 'utf8'));
const compositions = countryCompositionFeatureCollection(records, boundaries);
if (!Array.isArray(compositions.features) || compositions.features.length === 0) {
  throw new Error('country boundary subset would be empty');
}
const features = compositions.features.map(({ geometry, properties }) => ({
  type: 'Feature',
  id: properties.country_id,
  properties: {
    ADM0_A3: properties.country_id,
    NAME: properties.country_name,
    NAME_EN: properties.country_name,
  },
  geometry,
}));
const output = {
  type: 'FeatureCollection',
  features,
};
await mkdir(path.dirname(OUTPUT_PATH), { recursive: true });
await writeFile(OUTPUT_PATH, `${JSON.stringify(output)}\n`, 'utf8');
process.stdout.write(`commonworld country boundary subset built: ${features.length} countries\n`);
