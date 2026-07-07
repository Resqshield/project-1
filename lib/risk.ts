import type { District, RainPoint, RiskScore, Severity } from './types';

/**
 * Composite risk index — transparent weighted overlay (v1).
 *
 *   risk = 0.40 · rain          (live: observed 24 h + forecast 48 h, normalized)
 *        + 0.25 · landslide     (static susceptibility × rain amplification)
 *        + 0.25 · flood         (static proneness × rain amplification)
 *        + 0.10 · exposure      (population density, normalized)
 *
 * Rain amplifies the terrain factors: a highly susceptible slope is only
 * dangerous when it is raining. Weights are published deliberately —
 * researchers must be able to audit the model. Calibrate against historical
 * events before operational use.
 */

const WEIGHTS = { rain: 0.4, landslide: 0.25, flood: 0.25, exposure: 0.1 } as const;

/** mm of rain over (24h observed + 48h forecast) considered "extreme" for normalization. */
const RAIN_NORM_MM = 250;
const MAX_DENSITY = 1600;

export function computeRisk(district: District, rain: RainPoint | undefined): RiskScore {
  const rainMm = rain ? rain.past24h + rain.next48h : 0;
  const rainN = clamp01(rainMm / RAIN_NORM_MM);
  // Amplification: terrain risk scales from 25% (dry) to 100% (extreme rain).
  const amp = 0.25 + 0.75 * rainN;

  const drivers = {
    rain: rainN,
    landslide: district.landslideSusceptibility * amp,
    flood: district.floodProneness * amp,
    exposure: clamp01(district.popDensity / MAX_DENSITY),
  };

  const score01 =
    WEIGHTS.rain * drivers.rain +
    WEIGHTS.landslide * drivers.landslide +
    WEIGHTS.flood * drivers.flood +
    WEIGHTS.exposure * drivers.exposure;

  const score = Math.round(score01 * 100);

  return { districtId: district.id, score, severity: severityFor(score), drivers };
}

export function severityFor(score: number): Severity {
  if (score >= 65) return 'red';
  if (score >= 45) return 'orange';
  if (score >= 25) return 'yellow';
  return 'green';
}

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}
