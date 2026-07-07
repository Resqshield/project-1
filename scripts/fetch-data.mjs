/**
 * Downloads district boundary GeoJSON into public/data/ so the app serves it
 * from its own origin (faster, offline-safe, no third-party runtime dependency).
 *
 * Run once locally or in the Vercel build step:  npm run fetch:data
 * The app works without it — lib/geo.ts falls back to the remote source,
 * and to centroid rendering if that also fails.
 */
import { mkdir, writeFile } from 'node:fs/promises';

const SOURCES = [
  'https://raw.githubusercontent.com/geohacker/kerala/master/geojsons/district.geojson',
];

const outDir = new URL('../public/data/', import.meta.url);
await mkdir(outDir, { recursive: true });

for (const url of SOURCES) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const gj = await res.json();
    if (!gj?.features?.length) throw new Error('no features');
    await writeFile(new URL('districts.json', outDir), JSON.stringify(gj));
    console.log(`✓ districts.json — ${gj.features.length} features from ${url}`);
    process.exit(0);
  } catch (err) {
    console.warn(`✗ ${url}: ${err.message}`);
  }
}
console.warn('No boundary source reachable — app will use runtime fetch/centroid fallback.');
