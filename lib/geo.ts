import { DISTRICT_GEOJSON_URLS, NAME_TO_ID } from './districts';

export interface DistrictFeatureCollection {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    properties: { districtId: string; name: string };
    geometry: GeoJSON.Geometry;
  }>;
}

let cache: DistrictFeatureCollection | null = null;

/**
 * Fetch Kerala district boundary polygons at runtime and normalize their
 * properties to our district ids. Returns null if every source fails —
 * callers must degrade to centroid-based rendering.
 */
export async function fetchDistrictBoundaries(): Promise<DistrictFeatureCollection | null> {
  if (cache) return cache;
  for (const url of DISTRICT_GEOJSON_URLS) {
    try {
      const res = await fetch(url, { cache: 'force-cache' });
      if (!res.ok) continue;
      const gj = (await res.json()) as GeoJSON.FeatureCollection;
      const features = gj.features
        .map((f) => {
          const props = (f.properties ?? {}) as Record<string, unknown>;
          const rawName = String(
            props.DISTRICT ?? props.district ?? props.NAME ?? props.name ?? props.District ?? ''
          ).trim();
          const id = NAME_TO_ID[rawName.toLowerCase()];
          if (!id || !f.geometry) return null;
          return {
            type: 'Feature' as const,
            properties: { districtId: id, name: rawName },
            geometry: f.geometry,
          };
        })
        .filter((f): f is NonNullable<typeof f> => f !== null);
      if (features.length >= 10) {
        cache = { type: 'FeatureCollection', features };
        return cache;
      }
    } catch {
      // try next source
    }
  }
  return null;
}
